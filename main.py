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
import os
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
# List to store user IDs
USER_IDS = set()
# List to store authorized user IDs
AUTHORIZED_USERS = set()

# Load authorized users from a file (if it exists)
if os.path.exists("authorized_users.txt"):
    with open("authorized_users.txt", "r") as file:
        AUTHORIZED_USERS = set(map(int, file.read().splitlines()))
# Product prices
PRODUCTS = {
    "86": 1.06, 
    "172": 2.12, 
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
    user_id = update.message.from_user.id

    # Check if the user is authorized
    if not is_user_authorized(user_id):
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return

    USER_IDS.add(user_id)  # Track all active users

    keyboard = [
        [KeyboardButton("MLBB"), KeyboardButton("FF")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Welcome to Top-Up Bot!\n\n"
        "Choose a game to top up:",
        reply_markup=reply_markup
    )

def save_authorized_users():
    with open("authorized_users.txt", "w") as file:
        for user_id in AUTHORIZED_USERS:
            file.write(f"{user_id}\n")
def is_user_authorized(user_id):
    """Check if a user is authorized to use the bot."""
    return user_id in AUTHORIZED_USERS

async def add_user(update: Update, context: CallbackContext):
    """Add a user to the authorized users list."""
    admin_id = 6979490626  # Replace this with your admin user ID
    user_id = update.message.from_user.id

    if user_id != admin_id:
        await update.message.reply_text("❌ You don't have permission to add users.")
        return

    if not context.args:
        await update.message.reply_text("❌ Please provide a user ID to add. Example: /adduser 123456789")
        return

    try:
        new_user_id = int(context.args[0])
        if new_user_id in AUTHORIZED_USERS:
            await update.message.reply_text(f"ℹ️ User {new_user_id} is already authorized.")
        else:
            AUTHORIZED_USERS.add(new_user_id)
            save_authorized_users()  # Save the list to the file
            await update.message.reply_text(f"✅ User {new_user_id} has been authorized.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Please enter a numeric user ID.")


async def remove_user(update: Update, context: CallbackContext):
    """Remove a user from the authorized users list."""
    admin_id = 6979490626  # Replace this with your admin user ID
    user_id = update.message.from_user.id

    if user_id != admin_id:
        await update.message.reply_text("❌ You don't have permission to remove users.")
        return

    if not context.args:
        await update.message.reply_text("❌ Please provide a user ID to remove. Example: /removeuser 123456789")
        return

    try:
        remove_user_id = int(context.args[0])
        if remove_user_id not in AUTHORIZED_USERS:
            await update.message.reply_text(f"ℹ️ User {remove_user_id} is not in the authorized user list.")
        else:
            AUTHORIZED_USERS.remove(remove_user_id)
            save_authorized_users()  # Save the list to the file
            await update.message.reply_text(f"✅ User {remove_user_id} has been removed from the authorized user list.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Please enter a numeric user ID.")


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
# ======================================================================================================
async def broadcast(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    admin_id = 6979490626  # Replace this with your admin user ID
    
    if user_id != admin_id:
        await update.message.reply_text("❌ You don't have permission to broadcast messages.")
        return

    if not context.args:
        await update.message.reply_text("❌ Please provide a message to broadcast. Example:\n/broadcast Hello everyone!")
        return

    message = " ".join(context.args)

    sent_count = 0
    failed_count = 0

    for user_id in USER_IDS:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send message to {user_id}: {e}")
            failed_count += 1

    await update.message.reply_text(f"✅ Broadcast complete.\nSent: {sent_count}\nFailed: {failed_count}")

# ======================================================================================================
async def handle_mlbb_order(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Check if the user is authorized
    if not is_user_authorized(user_id):
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return

    USER_IDS.add(user_id)  # Track active users
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
    bank_account = "hj_xbot@wing"
    merchant_name = "Top-up Reseller"
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
    application = Application.builder().token("7639850946:AAGhrEvtGEWdPDJ7b8qeOdiOLlr8lNXw6ME").build()

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
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("adduser", add_user))
    application.add_handler(CommandHandler("removeuser", remove_user))

    application.run_polling()

if __name__ == '__main__':
    main()
