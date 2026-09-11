import re
from datetime import datetime

from sqlalchemy import func

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

from config import (
    ADMIN_ID,
    FREE_CHANNEL_ID,
    PLAN_PRICE,
)

from database import SessionLocal

from models.marketing import MarketingVisit
from models.payment import Payment

from keyboards.menu import (
    marketing_menu,
    campaign_menu,
)


WAITING_FOR_CAMPAIGN = 10
WAITING_FOR_PROMO = 11
WAITING_FOR_LINK_CAMPAIGN = 12


CAMPAIGN_PATTERN = re.compile(
    r"^[A-Za-z0-9_-]{1,40}$"
)


# ---------------------------------------------------------
# PROMOTIONAL DISCLAIMER
# ---------------------------------------------------------

PROMO_DISCLAIMER = (
    "⚠️ Disclaimer: Our content is shared for educational "
    "and informational purposes. I am not a SEBI-registered "
    "investment adviser. Investments in the market are subject "
    "to risks, and returns are not guaranteed. Please do your "
    "own research before investing."
)


# ---------------------------------------------------------
# CAMPAIGN HELPERS
# ---------------------------------------------------------

def normalize_campaign(
    value: str,
) -> str | None:

    value = value.strip().lower()

    if not CAMPAIGN_PATTERN.fullmatch(value):
        return None

    return value


def build_campaign_link(
    bot_username: str,
    campaign: str,
) -> str:

    bot_username = bot_username.lstrip("@")

    return (
        f"https://t.me/{bot_username}"
        f"?start=campaign_{campaign}"
    )


def campaign_link_keyboard(
    bot_username: str,
    campaign: str,
):

    link = build_campaign_link(
        bot_username,
        campaign,
    )

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔗 Open Campaign Link",
                    url=link,
                )
            ]
        ]
    )


# ---------------------------------------------------------
# CAMPAIGN VISIT TRACKING
# ---------------------------------------------------------

async def record_campaign_visit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    campaign: str,
):

    campaign = normalize_campaign(
        campaign
    )

    if not campaign:
        return

    if not update.effective_user:
        return

    telegram_id = update.effective_user.id

    now = datetime.utcnow()

    db = SessionLocal()

    try:

        visit = (
            db.query(MarketingVisit)
            .filter(
                MarketingVisit.telegram_id == telegram_id,
                MarketingVisit.campaign == campaign,
            )
            .first()
        )

        if visit:

            visit.last_seen_at = now
            visit.visit_count += 1

        else:

            db.add(
                MarketingVisit(
                    telegram_id=telegram_id,
                    campaign=campaign,
                    first_seen_at=now,
                    last_seen_at=now,
                    visit_count=1,
                )
            )

        db.commit()

        context.user_data[
            "campaign"
        ] = campaign

        print(
            "📊 Campaign visit recorded: "
            f"user={telegram_id}, "
            f"campaign={campaign}"
        )

    finally:

        db.close()


# ---------------------------------------------------------
# ADMIN MARKETING COMMAND
# ---------------------------------------------------------

async def marketing_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_user:
        return

    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "📣 MARKETING PANEL\n\n"
        "Use this panel to publish promotions, "
        "generate campaign links, and view "
        "conversion statistics.",
        reply_markup=marketing_menu(),
    )


# ---------------------------------------------------------
# MARKETING BUTTON HANDLER
# ---------------------------------------------------------

async def marketing_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if query.from_user.id != ADMIN_ID:

        try:
            await query.answer(
                "Not authorized.",
                show_alert=True,
            )
        except Exception:
            pass

        return ConversationHandler.END

    try:
        await query.answer()
    except Exception:
        pass

    # -----------------------------------------------------
    # PUBLISH PROMO
    # -----------------------------------------------------

    if query.data == "marketing_publish":

        await query.message.reply_text(
            "📢 PUBLISH PROMO\n\n"
            "Enter a campaign code.\n\n"
            "Examples:\n"
            "`whatsapp`\n"
            "`telegram`\n"
            "`september`\n"
            "`diwali`\n\n"
            "Only letters, numbers, `_` and `-` "
            "are allowed.\n\n"
            "Type /cancel to cancel.",
            parse_mode="Markdown",
        )

        return WAITING_FOR_CAMPAIGN

    # -----------------------------------------------------
    # CAMPAIGN LINKS
    # -----------------------------------------------------

    if query.data == "marketing_links":

        await query.message.reply_text(
            "🔗 CAMPAIGN LINK\n\n"
            "Enter the campaign code to generate "
            "a tracking link.\n\n"
            "Example:\n"
            "`whatsapp`\n\n"
            "Type /cancel to cancel.",
            parse_mode="Markdown",
        )

        return WAITING_FOR_LINK_CAMPAIGN

    # -----------------------------------------------------
    # CAMPAIGN STATS
    # -----------------------------------------------------

    if query.data == "marketing_stats":

        await send_marketing_stats(
            query.message
        )

        return ConversationHandler.END

    return ConversationHandler.END


# ---------------------------------------------------------
# RECEIVE PROMO CAMPAIGN
# ---------------------------------------------------------

async def receive_campaign(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    campaign = normalize_campaign(
        update.message.text
    )

    if not campaign:

        await update.message.reply_text(
            "⚠️ Invalid campaign code.\n\n"
            "Use only letters, numbers, `_` or `-`, "
            "up to 40 characters."
        )

        return WAITING_FOR_CAMPAIGN

    context.user_data[
        "marketing_campaign"
    ] = campaign

    await update.message.reply_text(
        "✅ Campaign code saved:\n"
        f"`{campaign}`\n\n"
        "Now send the promotional message "
        "exactly as you want it published "
        "in the free channel.\n\n"
        "You can use emojis and multiple "
        "paragraphs.\n\n"
        "Type /cancel to cancel.",
        parse_mode="Markdown",
    )

    return WAITING_FOR_PROMO


# ---------------------------------------------------------
# RECEIVE PROMOTIONAL MESSAGE
# ---------------------------------------------------------

async def receive_promo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    campaign = context.user_data.get(
        "marketing_campaign"
    )

    if not campaign:

        await update.message.reply_text(
            "⚠️ Marketing session expired.\n\n"
            "Run /marketing again."
        )

        return ConversationHandler.END

    promo_text = (
        update.message.text or ""
    ).strip()

    if not promo_text:

        await update.message.reply_text(
            "⚠️ Promotional message cannot be empty."
        )

        return WAITING_FOR_PROMO

    bot_username = (
        context.bot.username
    )

    if not bot_username:

        bot_info = await context.bot.get_me()

        bot_username = bot_info.username

    tracking_link = build_campaign_link(
        bot_username,
        campaign,
    )

    # -----------------------------------------------------
    # FINAL PROMOTIONAL MESSAGE
    # -----------------------------------------------------

    promo = (
        f"{promo_text}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💎 Premium Membership — ₹{PLAN_PRICE}\n\n"
        "👇 Tap below to check membership\n\n"
        f"{PROMO_DISCLAIMER}"
    )

    try:

        sent = await context.bot.send_message(
            chat_id=FREE_CHANNEL_ID,
            text=promo,
            reply_markup=campaign_menu(
                campaign,
                bot_username,
            ),
        )

    except Exception as exc:

        await update.message.reply_text(
            "❌ I couldn't publish the promotion.\n\n"
            f"Error: {type(exc).__name__}: {exc}\n\n"
            "Make sure the bot is an administrator "
            "of the free channel with permission "
            "to post messages."
        )

        context.user_data.pop(
            "marketing_campaign",
            None,
        )

        return ConversationHandler.END

    await update.message.reply_text(
        "✅ PROMO PUBLISHED\n\n"
        f"📢 Channel message ID: {sent.message_id}\n"
        f"🏷️ Campaign: {campaign}\n\n"
        "🔗 Tracking link:\n"
        f"{tracking_link}\n\n"
        "The button below opens the tracking link "
        "directly in Telegram.",
        reply_markup=campaign_link_keyboard(
            bot_username,
            campaign,
        ),
    )

    context.user_data.pop(
        "marketing_campaign",
        None,
    )

    return ConversationHandler.END


# ---------------------------------------------------------
# GENERATE CAMPAIGN LINK
# ---------------------------------------------------------

async def receive_link_campaign(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    campaign = normalize_campaign(
        update.message.text
    )

    if not campaign:

        await update.message.reply_text(
            "⚠️ Invalid campaign code.\n\n"
            "Use only letters, numbers, `_` or `-`."
        )

        return WAITING_FOR_LINK_CAMPAIGN

    bot_username = (
        context.bot.username
    )

    if not bot_username:

        bot_info = await context.bot.get_me()

        bot_username = bot_info.username

    link = build_campaign_link(
        bot_username,
        campaign,
    )

    await update.message.reply_text(
        "🔗 CAMPAIGN LINK\n\n"
        f"🏷️ Campaign: {campaign}\n\n"
        f"{link}\n\n"
        "Use the button below to test it.",
        reply_markup=campaign_link_keyboard(
            bot_username,
            campaign,
        ),
    )

    return ConversationHandler.END


# ---------------------------------------------------------
# CAMPAIGN STATISTICS
# ---------------------------------------------------------

async def send_marketing_stats(
    message,
):

    db = SessionLocal()

    try:

        visits = (
            db.query(
                MarketingVisit.campaign,
                func.count(
                    MarketingVisit.id
                ).label("users"),
                func.sum(
                    MarketingVisit.visit_count
                ).label("visits"),
            )
            .group_by(
                MarketingVisit.campaign
            )
            .order_by(
                func.sum(
                    MarketingVisit.visit_count
                ).desc()
            )
            .all()
        )

        approved = (
            db.query(
                Payment.campaign,
                func.count(
                    Payment.id
                ).label("sales"),
            )
            .filter(
                Payment.status == "approved",
                Payment.campaign.isnot(None),
            )
            .group_by(
                Payment.campaign
            )
            .all()
        )

        approved_map = {
            campaign: sales
            for campaign, sales in approved
        }

        if not visits:

            await message.reply_text(
                "📊 CAMPAIGN STATS\n\n"
                "No campaign traffic recorded yet."
            )

            return

        lines = [
            "📊 CAMPAIGN STATS",
            "",
        ]

        total_users = 0
        total_sales = 0

        for (
            campaign,
            users,
            visit_count,
        ) in visits:

            sales = approved_map.get(
                campaign,
                0,
            )

            conversion = (
                sales / users * 100
                if users
                else 0
            )

            total_users += users
            total_sales += sales

            lines.append(
                f"🏷️ {campaign}\n"
                f"👥 Users: {users}\n"
                f"👀 Visits: {visit_count or 0}\n"
                f"💰 Approved sales: {sales}\n"
                f"📈 Conversion: {conversion:.1f}%\n"
            )

        overall_conversion = (
            total_sales / total_users * 100
            if total_users
            else 0
        )

        lines.extend(
            [
                "━━━━━━━━━━━━━━━━━━━━",
                f"👥 Total campaign users: {total_users}",
                f"💰 Total approved sales: {total_sales}",
                f"📈 Overall conversion: "
                f"{overall_conversion:.1f}%",
            ]
        )

        await message.reply_text(
            "\n".join(lines)
        )

    finally:

        db.close()


# ---------------------------------------------------------
# CANCEL
# ---------------------------------------------------------

async def cancel_marketing(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data.pop(
        "marketing_campaign",
        None,
    )

    context.user_data.pop(
        "marketing_link_campaign",
        None,
    )

    await update.message.reply_text(
        "❌ Marketing action cancelled.\n\n"
        "Use /marketing to open the panel again."
    )

    return ConversationHandler.END


# ---------------------------------------------------------
# MARKETING CONVERSATION
# ---------------------------------------------------------

def marketing_conversation():

    return ConversationHandler(

        entry_points=[
            CallbackQueryHandler(
                marketing_button,
                pattern=r"^marketing_(publish|links|stats)$",
            )
        ],

        states={

            WAITING_FOR_CAMPAIGN: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_campaign,
                )
            ],

            WAITING_FOR_PROMO: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_promo,
                )
            ],

            WAITING_FOR_LINK_CAMPAIGN: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_link_campaign,
                )
            ],
        },

        fallbacks=[
            CommandHandler(
                "cancel",
                cancel_marketing,
            )
        ],

        allow_reentry=True,
    )