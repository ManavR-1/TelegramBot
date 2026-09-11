from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from config import (
    ADMIN_ID,
    CHANNEL_ID,
    PLAN_DURATION_DAYS,
    PLAN_PRICE,
)

from database import SessionLocal

from models.payment import Payment
from models.subscription import Subscription


IST = ZoneInfo("Asia/Kolkata")


def now_utc_naive():
    """Return current UTC time as a naive datetime."""

    return datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )


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


async def approve_payment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    try:
        await query.answer()
    except Exception:
        pass

    # ---------------------------------------------------------
    # ADMIN SECURITY CHECK
    # ---------------------------------------------------------

    if query.from_user.id != ADMIN_ID:

        await query.message.reply_text(
            "❌ You are not authorized to perform "
            "this action."
        )

        return

    # ---------------------------------------------------------
    # GET PAYMENT ID
    # ---------------------------------------------------------

    try:

        payment_id = int(
            query.data.split(":")[1]
        )

    except (
        ValueError,
        IndexError,
    ):

        await query.message.reply_text(
            "❌ Invalid payment request."
        )

        return

    db = SessionLocal()

    try:

        # -----------------------------------------------------
        # LOAD PAYMENT
        # -----------------------------------------------------

        payment = (
            db.query(Payment)
            .filter(
                Payment.id == payment_id
            )
            .first()
        )

        if not payment:

            await query.message.reply_text(
                "❌ Payment record not found."
            )

            return

        # -----------------------------------------------------
        # PREVENT DOUBLE APPROVAL / REJECTION
        # -----------------------------------------------------

        if payment.status == "approved":

            await query.answer(
                "⚠️ This payment is already approved.",
                show_alert=True,
            )

            return

        if payment.status == "rejected":

            await query.answer(
                "⚠️ This payment has already been rejected.",
                show_alert=True,
            )

            return

        telegram_id = payment.telegram_id

        now = now_utc_naive()

        # -----------------------------------------------------
        # FIND CURRENT ACTIVE SUBSCRIPTION
        #
        # Only a subscription whose expiry is still in the
        # future counts as the current active period.
        # -----------------------------------------------------

        active_subscription = (
            db.query(Subscription)
            .filter(
                Subscription.telegram_id == telegram_id,
                Subscription.status == "active",
                Subscription.expires_at > now,
            )
            .order_by(
                Subscription.expires_at.desc(),
                Subscription.id.desc(),
            )
            .first()
        )

        # -----------------------------------------------------
        # MARK STALE ACTIVE SUBSCRIPTIONS AS EXPIRED
        #
        # This handles:
        #
        # old subscription expires
        #        ↓
        # worker hasn't processed it yet
        #        ↓
        # user buys again
        #        ↓
        # admin approves
        #
        # The stale record must not remain active.
        # -----------------------------------------------------

        stale_active_subscriptions = (
            db.query(Subscription)
            .filter(
                Subscription.telegram_id == telegram_id,
                Subscription.status == "active",
                Subscription.expires_at <= now,
            )
            .all()
        )

        for stale_subscription in (
            stale_active_subscriptions
        ):

            stale_subscription.status = "expired"

            print(
                "🧹 Marked stale subscription "
                f"#{stale_subscription.id} as expired "
                f"for Telegram ID {telegram_id}."
            )

        # -----------------------------------------------------
        # FIND LATEST SCHEDULED RENEWAL
        #
        # IMPORTANT:
        #
        # We look for the scheduled renewal BEFORE deciding
        # the start date.
        #
        # This ensures multiple early renewals chain:
        #
        # Active:
        # Sep 08 → Oct 08
        #
        # Renewal 1:
        # Oct 08 → Nov 07
        #
        # Renewal 2:
        # Nov 07 → Dec 07
        #
        # Renewal 3:
        # Dec 07 → Jan 06
        # -----------------------------------------------------

        latest_scheduled_subscription = (
            db.query(Subscription)
            .filter(
                Subscription.telegram_id == telegram_id,
                Subscription.status == "scheduled",
            )
            .order_by(
                Subscription.expires_at.desc(),
                Subscription.id.desc(),
            )
            .first()
        )

        # -----------------------------------------------------
        # DETERMINE NEW SUBSCRIPTION PERIOD
        # -----------------------------------------------------

        if latest_scheduled_subscription:

            # -------------------------------------------------
            # MULTIPLE PREPAID RENEWALS
            #
            # Always append after the latest scheduled period.
            # -------------------------------------------------

            start_at = (
                latest_scheduled_subscription.expires_at
            )

            new_status = "scheduled"

        elif active_subscription:

            # -------------------------------------------------
            # FIRST EARLY RENEWAL
            #
            # Current subscription remains active.
            # Renewal starts exactly when current access ends.
            # -------------------------------------------------

            start_at = (
                active_subscription.expires_at
            )

            new_status = "scheduled"

        else:

            # -------------------------------------------------
            # BRAND NEW / EXPIRED SUBSCRIPTION
            # -------------------------------------------------

            start_at = now

            new_status = "active"

        expires_at = (
            start_at
            + timedelta(
                days=PLAN_DURATION_DAYS
            )
        )

        # -----------------------------------------------------
        # CREATE SUBSCRIPTION
        # -----------------------------------------------------

        subscription = Subscription(
            payment_id=payment.id,
            telegram_id=telegram_id,
            status=new_status,
            started_at=start_at,
            expires_at=expires_at,
            invite_link=None,
            invite_expires_at=None,
            reminder_3d_sent=False,
            reminder_1d_sent=False,
        )

        db.add(subscription)

        # -----------------------------------------------------
        # MARK PAYMENT APPROVED
        # -----------------------------------------------------

        payment.status = "approved"
        payment.reviewed_at = datetime.utcnow()

        db.commit()

        db.refresh(subscription)

        subscription_id = subscription.id

        print()
        print("=" * 70)
        print(
            f"✅ PAYMENT #{payment_id} APPROVED"
        )
        print(
            f"👤 Telegram ID: {telegram_id}"
        )
        print(
            f"💰 Amount: ₹{PLAN_PRICE}"
        )
        print(
            f"📊 Subscription #{subscription_id}"
        )
        print(
            f"📊 Status: {new_status}"
        )
        print(
            f"📅 Starts: {format_ist(start_at)}"
        )
        print(
            f"📅 Expires: {format_ist(expires_at)}"
        )
        print("=" * 70)
        print()

    except Exception as e:

        db.rollback()

        print(
            "❌ Approval database error: "
            f"{type(e).__name__}: {e}"
        )

        await query.message.reply_text(
            "❌ An error occurred while approving "
            "this payment.\n\n"
            "No changes were saved. Please try again."
        )

        return

    finally:

        db.close()

    # ---------------------------------------------------------
    # CHECK CHANNEL MEMBERSHIP
    # ---------------------------------------------------------

    already_member = False

    try:

        member = await context.bot.get_chat_member(
            chat_id=CHANNEL_ID,
            user_id=telegram_id,
        )

        if member.status in (
            "creator",
            "administrator",
            "member",
        ):

            already_member = True

    except TelegramError as e:

        print(
            "⚠️ Could not check channel membership: "
            f"{type(e).__name__}: {e}"
        )

    # ---------------------------------------------------------
    # GENERATE SINGLE-USE INVITE
    # ---------------------------------------------------------

    invite_link = None

    if not already_member:

        try:

            invite = (
                await context.bot.create_chat_invite_link(
                    chat_id=CHANNEL_ID,
                    member_limit=1,
                    expire_date=datetime.now(
                        timezone.utc
                    ) + timedelta(
                        hours=24
                    ),
                )
            )

            invite_link = invite.invite_link

            # -------------------------------------------------
            # SAVE INVITE LINK
            # -------------------------------------------------

            db = SessionLocal()

            try:

                subscription = (
                    db.query(Subscription)
                    .filter(
                        Subscription.id
                        == subscription_id
                    )
                    .first()
                )

                if subscription:

                    subscription.invite_link = (
                        invite_link
                    )

                    subscription.invite_expires_at = (
                        datetime.now(
                            timezone.utc
                        )
                        .replace(
                            tzinfo=None
                        )
                        + timedelta(
                            hours=24
                        )
                    )

                    db.commit()

            finally:

                db.close()

        except TelegramError as e:

            print(
                "❌ Failed to create invite link: "
                f"{type(e).__name__}: {e}"
            )

    # ---------------------------------------------------------
    # CUSTOMER MESSAGE
    # ---------------------------------------------------------

    if new_status == "active":

        customer_text = (
            "🎉 PAYMENT APPROVED!\n\n"
            "💎 Your Premium Membership is now ACTIVE.\n\n"
            f"💰 Amount paid: ₹{PLAN_PRICE}\n"
            f"📅 Valid for: {PLAN_DURATION_DAYS} days\n\n"
            f"▶️ Starts:\n"
            f"{format_ist(start_at)}\n\n"
            f"📆 Expires:\n"
            f"{format_ist(expires_at)}\n\n"
        )

        if invite_link:

            customer_text += (
                "🔐 PREMIUM CHANNEL ACCESS\n\n"
                "Use the button below to join the "
                "premium channel.\n\n"
                "⚠️ This invite link is for your account "
                "and can only be used once."
            )

        elif already_member:

            customer_text += (
                "✅ You already have access to the "
                "premium channel."
            )

        else:

            customer_text += (
                "⚠️ Your payment is approved, but the "
                "channel invite could not be generated.\n\n"
                "Please contact support."
            )

    else:

        customer_text = (
            "🎉 RENEWAL PAYMENT APPROVED!\n\n"
            "💎 Your renewal has been successfully "
            "recorded.\n\n"
            "🟢 Your current membership remains active.\n\n"
            f"🔄 NEXT RENEWAL\n\n"
            f"▶️ Starts:\n"
            f"{format_ist(start_at)}\n\n"
            f"📆 Extends access until:\n"
            f"{format_ist(expires_at)}\n\n"
            "✅ Your paid renewal will activate "
            "automatically when the previous membership "
            "period ends."
        )

        if already_member:

            customer_text += (
                "\n\n"
                "🔐 You already have access to the "
                "premium channel, so no new invite is "
                "required."
            )

        elif invite_link:

            customer_text += (
                "\n\n"
                "🔐 PREMIUM CHANNEL ACCESS\n\n"
                "Use the button below to join the "
                "premium channel.\n\n"
                "⚠️ This invite link can only be used once."
            )

        else:

            customer_text += (
                "\n\n"
                "⚠️ Your payment is approved, but a "
                "channel invite could not be generated.\n\n"
                "Please contact support."
            )

    # ---------------------------------------------------------
    # CUSTOMER INVITE BUTTON
    # ---------------------------------------------------------

    customer_keyboard = None

    if invite_link:

        customer_keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔐 Join Premium Channel",
                        url=invite_link,
                    )
                ]
            ]
        )

    # ---------------------------------------------------------
    # SEND CUSTOMER MESSAGE
    # ---------------------------------------------------------

    try:

        await context.bot.send_message(
            chat_id=telegram_id,
            text=customer_text,
            reply_markup=customer_keyboard,
        )

        print(
            f"✅ Approval message sent to "
            f"Telegram ID {telegram_id}."
        )

    except TelegramError as e:

        print(
            "❌ Failed to send approval message "
            f"to customer: {type(e).__name__}: {e}"
        )

    # ---------------------------------------------------------
    # UPDATE ADMIN MESSAGE
    # ---------------------------------------------------------

    try:

        admin_username = (
            f"@{payment.username}"
            if payment.username
            else "No username"
        )

        if new_status == "active":

            status_text = (
                "🟢 APPROVED — ACTIVE"
            )

        else:

            status_text = (
                "🟢 APPROVED — RENEWAL SCHEDULED"
            )

        updated_caption = (
            "💰 PAYMENT SUBMISSION\n\n"
            f"🆔 Payment ID: #{payment_id}\n"
            f"👤 Name: {payment.first_name}\n"
            f"📱 Username: {admin_username}\n"
            f"🔢 Telegram ID: {telegram_id}\n\n"
            f"💵 Amount: ₹{PLAN_PRICE}\n"
            f"🔢 UTR: {payment.utr}\n"
            f"📊 Status: {status_text}\n\n"
            f"📅 Starts: {format_ist(start_at)}\n"
            f"📆 Expires: {format_ist(expires_at)}"
        )

        await query.message.edit_caption(
            caption=updated_caption,
            reply_markup=None,
        )

    except TelegramError as e:

        print(
            "⚠️ Failed to update admin payment message: "
            f"{type(e).__name__}: {e}"
        )

    # ---------------------------------------------------------
    # ADMIN CONFIRMATION
    # ---------------------------------------------------------

    if new_status == "active":

        await query.message.reply_text(
            "✅ PAYMENT APPROVED\n\n"
            f"Payment #{payment_id}\n"
            f"Subscription #{subscription_id}\n\n"
            "🟢 Status: ACTIVE\n"
            f"📅 Starts: {format_ist(start_at)}\n"
            f"📆 Expires: {format_ist(expires_at)}\n\n"
            + (
                "🔐 Single-use invite generated "
                "and sent to the customer."
                if invite_link
                else (
                    "👤 Customer already has channel "
                    "access."
                    if already_member
                    else
                    "⚠️ Invite generation failed."
                )
            )
        )

    else:

        await query.message.reply_text(
            "✅ PAYMENT APPROVED\n\n"
            f"Payment #{payment_id}\n"
            f"Subscription #{subscription_id}\n\n"
            "🔄 Status: RENEWAL SCHEDULED\n\n"
            f"▶️ Starts: {format_ist(start_at)}\n"
            f"📆 Expires: {format_ist(expires_at)}\n\n"
            "✅ Current subscription remains active "
            "until the scheduled start date.\n\n"
            + (
                "🔐 Customer already has channel access."
                if already_member
                else (
                    "🔐 Single-use invite generated "
                    "and sent to the customer."
                    if invite_link
                    else
                    "⚠️ Invite generation failed."
                )
            )
        )


async def reject_payment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    try:
        await query.answer()
    except Exception:
        pass

    # ---------------------------------------------------------
    # ADMIN SECURITY CHECK
    # ---------------------------------------------------------

    if query.from_user.id != ADMIN_ID:

        await query.message.reply_text(
            "❌ You are not authorized to perform "
            "this action."
        )

        return

    # ---------------------------------------------------------
    # GET PAYMENT ID
    # ---------------------------------------------------------

    try:

        payment_id = int(
            query.data.split(":")[1]
        )

    except (
        ValueError,
        IndexError,
    ):

        await query.message.reply_text(
            "❌ Invalid payment request."
        )

        return

    db = SessionLocal()

    try:

        payment = (
            db.query(Payment)
            .filter(
                Payment.id == payment_id
            )
            .first()
        )

        if not payment:

            await query.message.reply_text(
                "❌ Payment record not found."
            )

            return

        if payment.status == "approved":

            await query.answer(
                "⚠️ This payment is already approved.",
                show_alert=True,
            )

            return

        if payment.status == "rejected":

            await query.answer(
                "⚠️ This payment is already rejected.",
                show_alert=True,
            )

            return

        # -----------------------------------------------------
        # MARK PAYMENT REJECTED
        # -----------------------------------------------------

        payment.status = "rejected"
        payment.reviewed_at = datetime.utcnow()

        db.commit()

        telegram_id = payment.telegram_id

        print()
        print("=" * 70)
        print(
            f"❌ PAYMENT #{payment_id} REJECTED"
        )
        print(
            f"👤 Telegram ID: {telegram_id}"
        )
        print(
            f"🔢 UTR: {payment.utr}"
        )
        print("=" * 70)
        print()

    except Exception as e:

        db.rollback()

        print(
            "❌ Rejection database error: "
            f"{type(e).__name__}: {e}"
        )

        await query.message.reply_text(
            "❌ An error occurred while rejecting "
            "this payment.\n\n"
            "No changes were saved."
        )

        return

    finally:

        db.close()

    # ---------------------------------------------------------
    # NOTIFY CUSTOMER
    # ---------------------------------------------------------

    try:

        await context.bot.send_message(
            chat_id=telegram_id,
            text=(
                "❌ PAYMENT NOT APPROVED\n\n"
                "Unfortunately, your payment could "
                "not be verified.\n\n"
                f"🔢 UTR: {payment.utr}\n\n"
                "If you believe this was a mistake, "
                "please contact support."
            ),
        )

    except TelegramError as e:

        print(
            "❌ Failed to notify customer about "
            f"rejected payment: {type(e).__name__}: {e}"
        )

    # ---------------------------------------------------------
    # UPDATE ADMIN MESSAGE
    # ---------------------------------------------------------

    try:

        admin_username = (
            f"@{payment.username}"
            if payment.username
            else "No username"
        )

        updated_caption = (
            "💰 PAYMENT SUBMISSION\n\n"
            f"🆔 Payment ID: #{payment_id}\n"
            f"👤 Name: {payment.first_name}\n"
            f"📱 Username: {admin_username}\n"
            f"🔢 Telegram ID: {telegram_id}\n\n"
            f"💵 Amount: ₹{PLAN_PRICE}\n"
            f"🔢 UTR: {payment.utr}\n"
            "📊 Status: ❌ REJECTED"
        )

        await query.message.edit_caption(
            caption=updated_caption,
            reply_markup=None,
        )

    except TelegramError as e:

        print(
            "⚠️ Failed to update rejected payment "
            "message: "
            f"{type(e).__name__}: {e}"
        )

    # ---------------------------------------------------------
    # ADMIN CONFIRMATION
    # ---------------------------------------------------------

    await query.message.reply_text(
        "❌ PAYMENT REJECTED\n\n"
        f"Payment #{payment_id}\n"
        f"UTR: {payment.utr}\n\n"
        "The customer has been notified."
    )