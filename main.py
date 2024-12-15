import logging
from io import BytesIO
import time
import asyncio
from bakong_khqr import KHQR
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters, ConversationHandler
import qrcode
from qrcode.constants import ERROR_CORRECT_L
import http.client
import json
from keep_alive import keep_alive

keep_alive()
# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Bakong and Telegram configurations
BAKONG_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImlkIjoiOTFhNzgzZmQwOWE5NGQxIn0sImlhdCI6MTczMDM4Nzc1MSwiZXhwIjoxNzM4MTYzNzUxfQ.jSBGdjXNmznbcc5wXO5J-PEevLfraJIIESMODAJvjyo'
khqr = KHQR(BAKONG_TOKEN)

# Conversation states
MLBB_ORDER = 0
# ========================================================
PASSWORD = "hjstarwar1688"

# Store authenticated users
authenticated_users = set()

# ID of the group where alerts will be sent
ALERT_GROUP_ID = -1002389771587  # Replace with your group ID
# ========================================================
# Product prices
PRODUCTS = {
    "test": 0.1,
    "86": 1.05, 
    "172": 2.10, 
    "112": 1.85, 
    "257": 3.11, 
    "343": 4.09,
    "429": 5.21,
    "514": 6.35,
    "600": 7.30,
    "706": 8.70,
    "792": 9.60,
    "878": 10.80,
    "963": 12.85,
    "1050": 12.00,
    "1135": 14.35,
    "1412": 16.20,
    "1584": 18.40,
    "1755": 22.00,
    "1926": 27.00,
    "2195": 31.00,
    "2538": 34.00,
    "2901": 36.70,
    "3688": 48.00,
    "4394": 54.70,
    "5532": 73.50,
    "6238": 92.00,
    "6944": 95.00,
    "7727": 112.00,
    "8433": 122.00,
    "9288": 117.00,
    "10700": 141.00,
    "wkp": 1.34,
    "2wkp": 2.68,
    "3wkp": 4.02,
    "Twilight": 7.49
}


async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    # Check if the user is already authenticated
    if user_id in authenticated_users:
        keyboard = [[KeyboardButton("MLBB"), KeyboardButton("FF")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Welcome back to Top-Up Bot!\n\n"
            "Choose a game to top up:",
            reply_markup=reply_markup
        )
        return
    
    # If user is not authenticated, ask for the password
    await update.message.reply_text(
        "🔐 Please enter the password to access the bot:"
    )
# ======================================================================================
async def handle_password(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_input = update.message.text.strip()

    if user_input == PASSWORD:
        if user_id not in authenticated_users:  # Avoid duplicate users
            authenticated_users.add(user_id)

            # Get user details for alert
            username = update.effective_user.username if update.effective_user.username else "No Username"
            full_name = f"{update.effective_user.first_name} {update.effective_user.last_name}" if update.effective_user.last_name else update.effective_user.first_name
            
            # Alert the group with the username and Telegram ID
            alert_message = (
                f"🚀 **New User Accessed the Bot!**\n"
                f"👤 **Name:** {full_name}\n"
                f"📛 **Username:** @{username}\n"
                f"🆔 **Telegram ID:** `{user_id}`"
            )
            try:
                await context.bot.send_message(chat_id=ALERT_GROUP_ID, text=alert_message, parse_mode="Markdown")
            except Exception as e:
                print(f"⚠️ Failed to send alert to group: {e}")
        
        # Send the user a success message
        keyboard = [[KeyboardButton("MLBB"), KeyboardButton("FF")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "✅ Password accepted!\nWelcome to Top-Up Bot.\n\n"
            "Choose a game to top up:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("❌ Incorrect password. Please try again.")

# ======================================================================================
async def remove_user(update: Update, context: CallbackContext):
    try:
        # Get the user ID from the command argument
        telegram_id = int(context.args[0])  # Extract ID from command argument

        if telegram_id in authenticated_users:
            authenticated_users.remove(telegram_id)
            await update.message.reply_text(f"✅ Successfully removed user with Telegram ID: `{telegram_id}`", parse_mode="Markdown")
            
            # Alert the group
            alert_message = f"🚫 **User Removed from Access List!**\n🆔 **Telegram ID:** `{telegram_id}`"
            try:
                await context.bot.send_message(chat_id=ALERT_GROUP_ID, text=alert_message, parse_mode="Markdown")
            except Exception as e:
                print(f"⚠️ Failed to send alert to group: {e}")
        else:
            await update.message.reply_text(f"⚠️ User with Telegram ID `{telegram_id}` is not in the authenticated list.", parse_mode="Markdown")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Please provide a valid Telegram ID to remove. Example: `/remove_user 123456789`")
    except Exception as e:
        print(f"⚠️ Unknown error occurred: {e}")


# ======================================================================================
async def handle_mlbb(update: Update, context: CallbackContext):
    price_list = (
        "Products List Mobile Legends\n\n" +
        "\n".join([f"*{product}* - ${price:.2f}" for product, price in PRODUCTS.items()]) +
        "\n\nPlease provide your order details\nin this format:\n"
        "`<ID> <Server> <Product>`\n\n"
        "Example:\n`12345678 2205 86`"
    )
    await update.message.reply_text(price_list, parse_mode="Markdown")
    return MLBB_ORDER

async def handle_mlbb_order(update: Update, context: CallbackContext):
    user_input = update.message.text.strip()

    try:
        # Split input using ':'
        order_details = user_input.split(" ")
        if len(order_details) != 3:
            raise ValueError("Invalid input format. Use `<ID> <Server> <Product>`")

        user_id, server, product = order_details

        # Validate product
        if product not in PRODUCTS:
            raise ValueError("Invalid product number. Please select from the provided list.")

        product_price = PRODUCTS[product]

        # Validate user ID and server
        if not user_id or not server:
            raise ValueError("User ID and Server are required fields.")

        # Check the username using the API
        username = await get_username_from_api(user_id, server)
        if username == "Invalid User":
            raise ValueError("The provided user ID or server is invalid. Please check your details and try again.")

        # Generate QR Code for payment
        qr_data, qr_img, md5_hash = generate_qr_code(product_price, username, user_id, server, product)

        # Send order confirmation and QR code
        message = await update.message.reply_photo(
            photo=qr_img, 
            caption=f"Order Details:\n"
                    f"*User ID*: `{user_id}`\n"
                    f"*Server ID*: `{server}`\n"
                    f"*Username*: {username}\n"
                    f"*Product*: `{product}`\n"
                    f"*Price*: ${product_price:.2f}\n"
                    f"*Status*: Waiting for Payment ⏳\n\n"
                    "Please scan the QR code to complete payment.",
            parse_mode="Markdown"
        )

        # Start payment status checking
        asyncio.create_task(check_payment_status(
            update, 
            context, 
            md5_hash, 
            product_price, 
            user_id, 
            server, 
            product, 
            username, 
            message.message_id
        ))

    except ValueError as e:
        await update.message.reply_text(f"❌ {e}")
    
    return ConversationHandler.END

async def check_payment_status(update: Update, context: CallbackContext, 
                                md5_hash: str, amount: float, 
                                user_id: str, server: str, 
                                product: str, username: str, 
                                original_message_id: int):
    try:
        max_attempts = 12  # Check for 1 minute (12 attempts, 5 seconds apart)
        for attempt in range(max_attempts):
            # Check payment status using KHQR
            payment_status = khqr.check_payment(md5_hash)

            if payment_status == "PAID":
                # **Delete the QR code message after payment success**
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id, 
                    message_id=original_message_id
                )

                # **Send a new message with order details**
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=(
                        "\u2705 *Order Details*\n"  # ✅ emoji
                        f"*User ID*: `{user_id}`\n"
                        f"*Server ID*: `{server}`\n"
                        f"*Username*: {username}\n"
                        f"*Product*: `{product}`\n"
                        f"*Price*: ${amount:.2f}\n"
                        "*Status*: Payment Successful \u2705"  # ✅ emoji
                    ),
                    parse_mode="Markdown"
                )

                # Send order details to a specific channel
                await send_order_to_channel(
                    context, 
                    user_id, 
                    server, 
                    product, 
                    amount, 
                    username
                )

                return  # Exit the function if payment is confirmed

            # Wait 5 seconds before the next attempt
            await asyncio.sleep(5)

        # If payment is not confirmed within the timeout
        await context.bot.delete_message(
            chat_id=update.effective_chat.id, 
            message_id=original_message_id
        )

        # **Send a new message with order details (status: Payment Timeout)**
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                "\u274C *Order Details*\n"  # ❌ emoji
                f"*User ID*: `{user_id}`\n"
                f"*Server ID*: `{server}`\n"
                f"*Username*: {username}\n"
                f"*Product*: `{product}`\n"
                f"*Price*: ${amount:.2f}\n"
                "*Status*: Payment Timeout \u274C"  # ❌ emoji
            ),
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error checking payment: {e}")
        
        # Notify user about the error
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="An error occurred while checking payment status. Please try again."
        )

        # **Delete the QR code message in case of an error**
        await context.bot.delete_message(
            chat_id=update.effective_chat.id, 
            message_id=original_message_id
        )

async def send_order_to_channel(context: CallbackContext, 
                                 user_id: str, 
                                 server: str, 
                                 product: str, 
                                 amount: float, 
                                 username: str):
    channel_message = (
        f"✅ Order Details\n"
        f"*User ID*: `{user_id}`\n"
        f"*Server ID*: `{server}`\n"
        f"*Username*: {username}\n"
        f"*Product*: `{product}`\n"
        f"*Price*: ${amount:.2f}\n"
        f"*Status*: Payment Successful ✅"
    )

    # Replace with your actual channel ID
    await context.bot.send_message(
        chat_id='-1002389771587', 
        text=channel_message, 
        parse_mode="Markdown"
    )

def generate_qr_code(amount, username, user_id, server, product):
    # Define QR code generation parameters
    bank_account = "hj_xbor@wing"
    merchant_name = "Game Top-Up"
    merchant_city = "Phnom Penh"
    currency = "USD"
    store_label = f"Top-Up {username}"
    phone_number = "90854415"
    bill_number = f"TRX{user_id}{server}{product}"

    # Generate QR data
    qr_data = khqr.create_qr(
        bank_account=bank_account,
        merchant_name=merchant_name,
        merchant_city=merchant_city,
        amount=amount,
        currency=currency,
        store_label=store_label,
        phone_number=phone_number,
        bill_number=bill_number,
        terminal_label="Cashier-01",
        static=False
    )

    # Generate MD5 hash for payment tracking
    md5_hash = khqr.generate_md5(qr_data)

    # Create QR code image
    qr = qrcode.QRCode(
        version=1,
        error_correction=ERROR_CORRECT_L,
        box_size=10,
        border=1
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white")
    byte_io = BytesIO()
    qr_img.save(byte_io, 'PNG')
    byte_io.seek(0)

    return qr_data, byte_io, md5_hash

async def get_username_from_api(user_id: str, server: str):
    conn = http.client.HTTPSConnection("api-mobile-game-nickname-checker.p.rapidapi.com")

    headers = {
        'x-rapidapi-key': "3b718b8c69mshd9b51ee9f85a67fp195d79jsn25eb3f81b401",
        'x-rapidapi-host': "api-mobile-game-nickname-checker.p.rapidapi.com",
        'Content-Type': "application/json"
    }

    url = f"/mobile-legend?userId={user_id}&zoneId={server}"

    conn.request("GET", url, headers=headers)
    res = conn.getresponse()
    data = res.read()

    response_data = json.loads(data.decode("utf-8"))
    
    return response_data.get("nickname", "Invalid User")

async def handle_ff(update: Update, context: CallbackContext):
    await update.message.reply_text("Coming soon...")

async def edit_price(update: Update, context: CallbackContext):
    # Check if the user is an admin (optional check, you can customize this)
    user_id = update.message.from_user.id
    admin_id = 6979490626  # Replace with your admin user ID
    if user_id != admin_id:
        await update.message.reply_text("❌ You don't have permission to edit prices.")
        return

    # Ensure the message contains the correct format for editing
    if len(context.args) != 2:
        await update.message.reply_text("❌ Please provide the correct format: /edit_price <product> <new_price>")
        return

    product = context.args[0]
    try:
        new_price = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid price format. Please provide a valid number.")
        return

    if product not in PRODUCTS:
        await update.message.reply_text(f"❌ Product `{product}` not found.")
        return

    # Update the product price
    PRODUCTS[product] = new_price
    await update.message.reply_text(f"✅ Price for product `{product}` updated to ${new_price:.2f}.")

def main():
    application = Application.builder().token("7552963790:AAFDuDy1UQh8ymn2ZG7AWiR8xPUIwDP5qrM").build()

    conversation_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^MLBB$"), handle_mlbb)],
        states={
            MLBB_ORDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mlbb_order)],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    application.add_handler(conversation_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^FF$"), handle_ff))
    application.add_handler(CommandHandler("edit_price", edit_price))  # Add this line
# Handles user input after /start for password entry
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password))

        # Handles the /remove_user command
    application.add_handler(CommandHandler("remove_user", remove_user))

    application.run_polling()

if __name__ == '__main__':
    main()
