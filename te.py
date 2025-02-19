from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import os
import json
import logging
import hashlib

# Configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "335725631")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@mr_amiir")
BOT_TOKEN = os.getenv("BOT_TOKEN", "6674800630:AAFGczcrUrPk8eSy9-t8pH6sx6i3aqAjgZA")

# Conversation states
PLATFORM, ACCOUNT_USERNAME, FOLLOWERS, PRICE, CONFIRMATION = range(5)

# Temporary storage
ads_db = {}

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start/reset the conversation"""
    context.user_data.clear()
    
    if update.message:
        if context.args and 'restart' in context.args:
            await update.message.reply_text("🔄 Session reset successfully!")
        
        await update.message.reply_text(
            "🔖 Welcome to Account Marketplace!\nPlease choose a platform:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Instagram", callback_data="instagram")],
                [InlineKeyboardButton("Twitter", callback_data="twitter")],
                [InlineKeyboardButton("Telegram", callback_data="telegram")]
            ])
        )
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "🔖 Welcome to Account Marketplace!\nPlease choose a platform:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Instagram", callback_data="instagram")],
                [InlineKeyboardButton("Twitter", callback_data="twitter")],
                [InlineKeyboardButton("Telegram", callback_data="telegram")]
            ])
        )
    return PLATFORM

async def handle_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle platform selection"""
    query = update.callback_query
    await query.answer()
    context.user_data['platform'] = query.data.capitalize()
    await query.edit_message_text(
        f"📌 Selected platform: {context.user_data['platform']}\n"
        "Please enter the account @username:"
    )
    return ACCOUNT_USERNAME

async def get_account_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store account username"""
    context.user_data['account_username'] = update.message.text
    await update.message.reply_text("🔢 Enter number of followers:")
    return FOLLOWERS

async def validate_followers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validate followers input"""
    try:
        followers = int(update.message.text)
        if followers < 0:
            raise ValueError
        context.user_data['followers'] = followers
        await update.message.reply_text("💰 Enter price in USD:")
        return PRICE
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number!")
        return FOLLOWERS

async def validate_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validate price input"""
    try:
        price = float(update.message.text)
        if price < 1:
            raise ValueError
        context.user_data['price'] = f"${price:.2f}"
        return await show_summary(update, context)
    except ValueError:
        await update.message.reply_text("❌ Invalid price! Please enter a number greater than 1.")
        return PRICE

async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show ad summary"""
    summary = (
        "📋 Ad Summary:\n"
        f"• Platform: {context.user_data['platform']}\n"
        f"• Username: @{context.user_data['account_username']}\n"
        f"• Followers: {context.user_data['followers']}\n"
        f"• Price: {context.user_data['price']}"
    )
    
    await update.message.reply_text(
        summary,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm & Send", callback_data="confirm")],
            [InlineKeyboardButton("✏️ Edit Again", callback_data="restart")]
        ])
    )
    return CONFIRMATION

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle final confirmation"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm":
        # Generate unique ad ID
        ad_id = hashlib.sha256(os.urandom(64)).hexdigest()[:16]
        ads_db[ad_id] = {
            'platform': context.user_data['platform'],
            'account_username': context.user_data['account_username'],
            'followers': context.user_data['followers'],
            'price': context.user_data['price'],
            'user_id': query.from_user.id,
            'seller_username': query.from_user.username
        }
        
        # Create admin buttons
        admin_markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{ad_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{ad_id}")
            ]
        ])
        
        # Send to admin
        await context.bot.send_message(
            ADMIN_CHAT_ID,
            f"📮 New Ad Submission:\n{json.dumps(ads_db[ad_id], indent=2)}",
            reply_markup=admin_markup
        )
        
        # Create restart URL
        restart_url = f"https://t.me/{context.bot.username}?start=restart"
        user_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Back to Menu", url=restart_url)]
        ])
        
        await query.edit_message_text(
            "📬 Your ad has been submitted for review!",
            reply_markup=user_keyboard
        )
        return ConversationHandler.END
        
    elif query.data == "restart":
        context.user_data.clear()
        return await start(update, context)

async def handle_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin actions"""
    query = update.callback_query
    await query.answer()
    
    action, ad_id = query.data.split('_', 1)
    ad_data = ads_db.get(ad_id)
    
    if not ad_data:
        await query.edit_message_text("❌ Ad not found!")
        return
    
    if action == "approve":
        # Post to channel
        channel_msg = (
            "🛒 New Account Listing:\n\n"
            f"📌 Platform: {ad_data['platform']}\n"
            f"🆔 Username: @{ad_data['account_username']}\n"
            f"👥 Followers: {ad_data['followers']}\n"
            f"💰 Price: {ad_data['price']}\n"
            f"🤝 Seller: @{ad_data['seller_username']}"
        )
        await context.bot.send_message(CHANNEL_ID, channel_msg)
        await query.edit_message_text(f"✅ Ad {ad_id} published!")
        
        # Notify user
        await context.bot.send_message(
            ad_data['user_id'],
            "🎉 Your ad has been published!\n"
            f"🔗 View ad: https://t.me/{CHANNEL_ID.split('@')[1]}"
        )
        
    elif action == "reject":
        await query.edit_message_text(f"📝 Please enter rejection reason for ad {ad_id}:")
        context.user_data['reject_data'] = ad_data
        return "REJECT_REASON"
    
    # Cleanup
    del ads_db[ad_id]

async def handle_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process rejection reason"""
    reason = update.message.text
    ad_data = context.user_data.get('reject_data')
    
    if ad_data:
        await context.bot.send_message(
            ad_data['user_id'],
            f"❌ Your ad was rejected!\n📝 Reason: {reason}"
        )
        await update.message.reply_text("✅ Rejection reason sent.")
    else:
        await update.message.reply_text("❌ Error processing request!")
    
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # User conversation handler
    user_conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            PLATFORM: [CallbackQueryHandler(handle_platform)],
            ACCOUNT_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_account_username)],
            FOLLOWERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, validate_followers)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, validate_price)],
            CONFIRMATION: [CallbackQueryHandler(handle_confirmation)]
        },
        fallbacks=[]
    )
    
    # Admin conversation handler
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_admin_action, pattern=r"^(approve|reject)_")],
        states={
            "REJECT_REASON": [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reject_reason)]
        },
        fallbacks=[]
    )
    
    app.add_handler(user_conv)
    app.add_handler(admin_conv)
    
    app.run_polling()

if __name__ == "__main__":
    main()