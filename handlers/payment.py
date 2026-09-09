from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.error import TelegramError
from telegram.ext import (
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    filters,
)
from sqlalchemy.exc import IntegrityError

from config import (
    ADMIN_ID,
    PLAN_PRICE,
)

from database import SessionLocal
from models.payment import Payment


WAITING_FOR_UTR = 1
WAITING_FOR_SCREENSHOT = 2


async def start_payment_submission(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    context.user_data.pop("payment_utr", None)
    context.user_data.pop("payment_screenshot_file_id", None)

    await query.message.reply_text(
        "💳 PAYMENT VERIFICATION\n\n"
        "Please enter your UTR / Transaction ID.\n\n"
        "🔢 The UTR is usually a 12-digit number "
        "shown in your UPI payment receipt.\n\n"
        "Example:\n"
        "123456789012\n\n"
        "⚠️ Please enter the UTR exactly as shown "
        "in your payment receipt.\n\n"
        "Type /cancel to cancel."
    )

    return WAITING_FOR_UTR


async def receive_utr(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    utr = update.message.text.strip()

    if not utr:
        await update.message.reply_text(
            "⚠️ Please enter a valid UTR / Transaction ID."
        )
        return WAITING_FOR_UTR

    if len(utr) < 6:
        await update.message.reply_text(
            "⚠️ That UTR looks too short.\n\n"
            "Please check your payment receipt and "
            "enter the complete UTR / Transaction ID."
        )
        return WAITING_FOR_UTR

    db = SessionLocal()

    try:
        existing_payment = (
            db.query(Payment)
            .filter(Payment.utr == utr)
            .first()
        )

        if existing_payment:
            if existing_payment.status == "pending":
                await update.message.reply_text(
                    "⚠️ This UTR has already been submitted "
                    "and is currently waiting for verification."
                )
            elif existing_payment.status == "approved":
                await update.message.reply_text(
                    "⚠️ This UTR has already been verified."
                )
            else:
                await update.message.reply_text(
                    "⚠️ This UTR has already been submitted "
                    "before.\n\n"
                    "Please contact support if you believe "
                    "this is an error."
                )

            return ConversationHandler.END

    finally:
        db.close()

    context.user_data["payment_utr"] = utr

    await update.message.reply_text(
        "✅ UTR received.\n\n"
        "📷 Now send the payment screenshot.\n\n"
        "Please send the screenshot as an image "
        "showing the successful payment.\n\n"
        "Type /cancel to cancel."
    )

    return WAITING_FOR_SCREENSHOT


async def receive_screenshot(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message.photo:
        await update.message.reply_text(
            "⚠️ Please send the payment screenshot "
            "as an image."
        )
        return WAITING_FOR_SCREENSHOT

    photo = update.message.photo[-1]
    screenshot_file_id = photo.file_id

    utr = context.user_data.get("payment_utr")

    if not utr:
        await update.message.reply_text(
            "⚠️ Your payment session has expired.\n\n"
            "Please start the payment submission again."
        )
        return ConversationHandler.END

    user = update.effective_user

    telegram_id = user.id
    username = user.username
    first_name = user.first_name
    campaign = context.user_data.get("campaign")

    db = SessionLocal()

    try:
        existing_payment = (
            db.query(Payment)
            .filter(Payment.utr == utr)
            .first()
        )

        if existing_payment:
            await update.message.reply_text(
                "⚠️ This UTR has already been submitted.\n\n"
                "Please contact support if you believe "
                "this is an error."
            )
            return ConversationHandler.END

        payment = Payment(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            utr=utr,
            amount=PLAN_PRICE,
            screenshot_file_id=screenshot_file_id,
            campaign=campaign,
            status="pending",
        )

        db.add(payment)

        try:
            db.commit()
        except IntegrityError:
            db.rollback()

            await update.message.reply_text(
                "⚠️ This UTR has already been submitted.\n\n"
                "Please contact support if you believe "
                "this is an error."
            )
            return ConversationHandler.END

        db.refresh(payment)
        payment_id = payment.id

    finally:
        db.close()

    username_display = (
        f"@{username}"
        if username
        else "No username"
    )

    admin_caption = (
        "💰 NEW PAYMENT SUBMISSION\n\n"
        f"🆔 Payment ID: #{payment_id}\n"
        f"👤 Name: {first_name}\n"
        f"📱 Username: {username_display}\n"
        f"🔢 Telegram ID: {telegram_id}\n\n"
        f"💵 Amount: ₹{PLAN_PRICE}\n"
        f"🔢 UTR: {utr}\n"
        f"🏷️ Campaign: {campaign or 'Direct / Unknown'}\n"
        f"📊 Status: PENDING\n\n"
        "⚠️ Please verify the payment in your "
        "bank/UPI app before approving."
    )

    admin_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Approve",
                    callback_data=f"approve_payment:{payment_id}",
                ),
                InlineKeyboardButton(
                    "❌ Reject",
                    callback_data=f"reject_payment:{payment_id}",
                ),
            ]
        ]
    )

    try:
        print(
            f"📤 Sending payment notification to admin "
            f"{ADMIN_ID}..."
        )

        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=screenshot_file_id,
            caption=admin_caption,
            reply_markup=admin_keyboard,
        )

        print(
            f"✅ Admin notification sent successfully "
            f"for Payment #{payment_id}"
        )

    except TelegramError as e:
        print(
            f"❌ Admin notification failed: "
            f"{type(e).__name__}: {e}"
        )

        await update.message.reply_text(
            "✅ PAYMENT SUBMITTED\n\n"
            "Your payment details have been securely "
            "recorded.\n\n"
            "⏳ Your payment is pending manual verification.\n\n"
            "You will receive a message once your payment "
            "has been reviewed."
        )

        context.user_data.pop("payment_utr", None)
        context.user_data.pop("payment_screenshot_file_id", None)

        return ConversationHandler.END

    await update.message.reply_text(
        "✅ PAYMENT SUBMITTED\n\n"
        "Your payment details and screenshot have "
        "been received successfully.\n\n"
        f"🔢 UTR: {utr}\n"
        f"💰 Amount: ₹{PLAN_PRICE}\n\n"
        "⏳ Your payment is now pending manual "
        "verification.\n\n"
        "You will receive a message once the "
        "administrator has reviewed it."
    )

    context.user_data.pop("payment_utr", None)
    context.user_data.pop("payment_screenshot_file_id", None)

    return ConversationHandler.END


async def cancel_payment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.pop("payment_utr", None)
    context.user_data.pop("payment_screenshot_file_id", None)

    await update.message.reply_text(
        "❌ PAYMENT SUBMISSION CANCELLED\n\n"
        "You can start again whenever you're ready."
    )

    return ConversationHandler.END


def payment_conversation():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                start_payment_submission,
                pattern="^payment_submitted$",
            )
        ],
        states={
            WAITING_FOR_UTR: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_utr,
                )
            ],
            WAITING_FOR_SCREENSHOT: [
                MessageHandler(
                    filters.PHOTO,
                    receive_screenshot,
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_payment),
        ],
        allow_reentry=True,
    )
