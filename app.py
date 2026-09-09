import asyncio
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# DISABLE SYSTEM PROXY ENVIRONMENT VARIABLES
# ---------------------------------------------------------

for proxy_var in (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
):
    os.environ.pop(proxy_var, None)


from telegram import Update

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from telegram.request import HTTPXRequest

from config import (
    BOT_TOKEN,
    UPI_ID,
    PLAN_PRICE,
    PLAN_DURATION_DAYS,
)

from database import (
    init_db,
    SessionLocal,
)

from models.subscription import (
    Subscription,
)

from keyboards.menu import (
    main_menu,
    payment_menu,
)

from handlers.payment import (
    payment_conversation,
)

from handlers.admin import (
    approve_payment,
    reject_payment,
)

from handlers.marketing import (
    marketing_command,
    marketing_conversation,
)

from services.subscription_service import (
    subscription_worker,
)


IST = ZoneInfo("Asia/Kolkata")


# ---------------------------------------------------------
# TIME HELPERS
# ---------------------------------------------------------

def format_ist(dt):
    """Convert stored UTC-naive datetime to IST."""

    if not dt:
        return "Unknown"

    utc_aware = dt.replace(
        tzinfo=timezone.utc
    )

    ist_time = utc_aware.astimezone(
        IST
    )

    return ist_time.strftime(
        "%d %b %Y, %I:%M %p"
    )


def days_remaining(expires_at):
    """Return whole days remaining until expiry."""

    if not expires_at:
        return 0

    now_utc = (
        datetime.now(timezone.utc)
        .replace(tzinfo=None)
    )

    remaining = (
        expires_at - now_utc
    )

    if remaining.total_seconds() <= 0:
        return 0

    return remaining.days


# ---------------------------------------------------------
# START COMMAND
# ---------------------------------------------------------

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    # -----------------------------------------------------
    # CAMPAIGN DEEP-LINK TRACKING
    # -----------------------------------------------------

    if context.args:

        payload = context.args[0]

        if payload.startswith(
            "campaign_"
        ):

            campaign = payload[
                len("campaign_"):
            ]

            from handlers.marketing import (
                record_campaign_visit,
            )

            await record_campaign_visit(
                update,
                context,
                campaign,
            )

            print(
                "🔗 Campaign deep link detected: "
                f"{campaign}"
            )

    await update.message.reply_text(
        "🎉 Welcome to Equity Bot!\n\n"
        "Get access to our premium market analysis, "
        "intraday calls and exclusive updates.\n\n"
        "💎 Premium Membership\n"
        f"₹{PLAN_PRICE} / {PLAN_DURATION_DAYS} days",
        reply_markup=main_menu(),
    )


# ---------------------------------------------------------
# SUBSCRIPTION STATUS
# ---------------------------------------------------------

async def show_subscription(
    query,
):
    """Show current and scheduled subscription periods."""

    telegram_id = query.from_user.id

    db = SessionLocal()

    try:

        active_subscription = (
            db.query(Subscription)
            .filter(
                Subscription.telegram_id == telegram_id,
                Subscription.status == "active",
            )
            .order_by(
                Subscription.expires_at.desc(),
                Subscription.id.desc(),
            )
            .first()
        )

        scheduled_subscription = (
            db.query(Subscription)
            .filter(
                Subscription.telegram_id == telegram_id,
                Subscription.status == "scheduled",
            )
            .order_by(
                Subscription.started_at.asc(),
                Subscription.id.asc(),
            )
            .first()
        )

        if active_subscription:

            remaining_days = days_remaining(
                active_subscription.expires_at
            )

            text = (
                "📊 YOUR SUBSCRIPTION\n\n"
                "💎 Premium Membership\n\n"
                "🟢 Status: ACTIVE\n\n"
                f"📅 Current access until:\n"
                f"{format_ist(active_subscription.expires_at)}\n\n"
                f"⏳ Days remaining: "
                f"{remaining_days} day"
                f"{'s' if remaining_days != 1 else ''}\n\n"
                f"💰 Plan: "
                f"₹{PLAN_PRICE} / "
                f"{PLAN_DURATION_DAYS} days"
            )

            if scheduled_subscription:

                text += (
                    "\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🔄 NEXT RENEWAL SCHEDULED\n\n"
                    f"▶️ Starts:\n"
                    f"{format_ist(scheduled_subscription.started_at)}\n\n"
                    f"📆 Extends access until:\n"
                    f"{format_ist(scheduled_subscription.expires_at)}\n\n"
                    "✅ Your renewal is already paid "
                    "and will activate automatically."
                )

            await query.message.reply_text(
                text,
                reply_markup=main_menu(),
            )

            return

        if scheduled_subscription:

            await query.message.reply_text(
                "📊 YOUR SUBSCRIPTION\n\n"
                "🟡 Status: RENEWAL SCHEDULED\n\n"
                f"▶️ Starts:\n"
                f"{format_ist(scheduled_subscription.started_at)}\n\n"
                f"📆 Expires:\n"
                f"{format_ist(scheduled_subscription.expires_at)}\n\n"
                "🔄 Your paid renewal will "
                "activate automatically.",
                reply_markup=main_menu(),
            )

            return

        latest_subscription = (
            db.query(Subscription)
            .filter(
                Subscription.telegram_id == telegram_id,
            )
            .order_by(
                Subscription.created_at.desc(),
                Subscription.id.desc(),
            )
            .first()
        )

        if latest_subscription:

            if latest_subscription.status == "expired":

                await query.message.reply_text(
                    "📊 YOUR SUBSCRIPTION\n\n"
                    "🔴 Status: EXPIRED\n\n"
                    f"📅 Expired:\n"
                    f"{format_ist(latest_subscription.expires_at)}\n\n"
                    "🔄 Renew your membership to "
                    "regain access to the premium channel.",
                    reply_markup=main_menu(),
                )

                return

        await query.message.reply_text(
            "📊 YOUR SUBSCRIPTION\n\n"
            "⚪ Status: NO ACTIVE SUBSCRIPTION\n\n"
            "You currently don't have an active "
            "premium membership.\n\n"
            "💎 Purchase a membership to get access "
            "to the premium channel.",
            reply_markup=main_menu(),
        )

    finally:

        db.close()


# ---------------------------------------------------------
# BUTTON HANDLER
# ---------------------------------------------------------

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    if query.data == "buy_membership":

        await query.message.reply_text(
            "💎 PREMIUM MEMBERSHIP\n\n"
            f"💰 Price: ₹{PLAN_PRICE}\n"
            f"📅 Duration: {PLAN_DURATION_DAYS} days\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💳 Pay using UPI\n\n"
            f"UPI ID:\n{UPI_ID}\n\n"
            "📷 Tap the button below to view "
            "the QR code.\n\n"
            "After completing the payment, tap "
            "✅ I've Paid.",
            reply_markup=payment_menu(),
        )

    elif query.data == "view_qr":

        try:

            with open(
                "images/qr.png",
                "rb",
            ) as qr_file:

                await query.message.reply_photo(
                    photo=qr_file,
                    caption=(
                        "💳 UPI PAYMENT\n\n"
                        f"💰 Amount: ₹{PLAN_PRICE}\n"
                        f"📅 Duration: "
                        f"{PLAN_DURATION_DAYS} days\n\n"
                        f"UPI ID:\n{UPI_ID}\n\n"
                        "After completing the payment, "
                        "tap ✅ I've Paid."
                    ),
                    reply_markup=payment_menu(),
                )

        except FileNotFoundError:

            await query.message.reply_text(
                "⚠️ QR code is currently unavailable.\n\n"
                f"Please pay using this UPI ID:\n{UPI_ID}"
            )

    elif query.data == "my_subscription":

        await show_subscription(query)

    elif query.data == "support":

        await query.message.reply_text(
            "📞 SUPPORT\n\n"
            "Please contact the administrator "
            "for assistance."
        )

    elif query.data == "back_to_menu":

        await query.message.reply_text(
            "🏠 Main Menu",
            reply_markup=main_menu(),
        )


# ---------------------------------------------------------
# ERROR HANDLER
# ---------------------------------------------------------

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    print()
    print("=" * 70)
    print("❌ BOT ERROR")
    print("=" * 70)

    if context.error:

        print(
            f"Error type: "
            f"{type(context.error).__name__}"
        )

        print(
            f"Error details: "
            f"{context.error}"
        )

    if update:

        print(
            f"Update: "
            f"{update}"
        )

    print("=" * 70)
    print()


# ---------------------------------------------------------
# APPLICATION STARTUP
# ---------------------------------------------------------

async def post_init(
    application,
):

    print(
        "⏰ Starting subscription worker..."
    )

    worker = asyncio.create_task(
        subscription_worker(
            application.bot
        )
    )

    application.bot_data[
        "subscription_worker"
    ] = worker

    print(
        "✅ Subscription worker task created."
    )


# ---------------------------------------------------------
# APPLICATION SHUTDOWN
# ---------------------------------------------------------

async def post_shutdown(
    application,
):

    worker = application.bot_data.get(
        "subscription_worker"
    )

    if worker:

        print(
            "⏰ Stopping subscription worker..."
        )

        worker.cancel()

        try:

            await worker

        except asyncio.CancelledError:

            pass

        print(
            "✅ Subscription worker stopped."
        )


# ---------------------------------------------------------
# TELEGRAM HTTP REQUEST
# ---------------------------------------------------------

def create_telegram_request():

    return HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30,
        read_timeout=60,
        write_timeout=60,
        pool_timeout=30,
        http_version="1.1",
        proxy=None,
        httpx_kwargs={
            "trust_env": False,
            "http2": False,
            "follow_redirects": True,
        },
    )


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():

    init_db()

    request = create_telegram_request()

    get_updates_request = (
        create_telegram_request()
    )

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .request(request)
        .get_updates_request(
            get_updates_request
        )
        .post_init(
            post_init
        )
        .post_shutdown(
            post_shutdown
        )
        .build()
    )

    app.bot_data[
        "plan_price"
    ] = PLAN_PRICE

    # -----------------------------------------------------
    # PAYMENT CONVERSATION
    # -----------------------------------------------------

    app.add_handler(
        payment_conversation()
    )

    # -----------------------------------------------------
    # MARKETING CONVERSATION
    # -----------------------------------------------------

    app.add_handler(
        marketing_conversation()
    )

    # -----------------------------------------------------
    # ADMIN PAYMENT ACTIONS
    # -----------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            approve_payment,
            pattern=r"^approve_payment:\d+$",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            reject_payment,
            pattern=r"^reject_payment:\d+$",
        )
    )

    # -----------------------------------------------------
    # ADMIN MARKETING COMMAND
    # -----------------------------------------------------

    app.add_handler(
        CommandHandler(
            "marketing",
            marketing_command,
        )
    )

    # -----------------------------------------------------
    # START COMMAND
    # -----------------------------------------------------

    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    # -----------------------------------------------------
    # GENERAL BUTTON HANDLER
    # -----------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    # -----------------------------------------------------
    # ERROR HANDLER
    # -----------------------------------------------------

    app.add_error_handler(
        error_handler
    )

    print()
    print("=" * 60)
    print("🤖 Equity Bot is starting...")
    print("=" * 60)
    print()
    print("🌐 Telegram connection: HTTP/1.1")
    print("🔒 HTTPX trust_env: False")
    print("🔌 System proxy: Disabled")
    print("↪️ HTTP redirects: Enabled")
    print("📡 getUpdates request: Explicitly configured")
    print("🔄 Bootstrap retries: Unlimited")
    print("🗄️ Database: Initialized")
    print("⏰ Subscription worker: Enabled")
    print("🔄 Scheduled renewals: Enabled")
    print("📊 Dynamic subscription status: Enabled")
    print("📣 Marketing system: Enabled")
    print("🔗 Campaign deep links: Enabled")
    print("📈 Campaign attribution: Enabled")
    print("🛡️ Single subscription worker: Enabled")
    print("=" * 60)
    print()

    app.run_polling(
        drop_pending_updates=False,
        bootstrap_retries=-1,
    )


if __name__ == "__main__":
    main()