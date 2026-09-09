import asyncio
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from telegram.error import TelegramError

from config import CHANNEL_ID

from database import SessionLocal
from models.subscription import Subscription


IST = ZoneInfo("Asia/Kolkata")


def utc_now():
    """Return current UTC time as a naive datetime."""

    return datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )


def format_ist(dt):
    """Format a stored UTC-naive datetime in IST."""

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


def test_mode_enabled():
    """
    Return True when safe subscription testing is enabled.

    Test mode:
    - detects expired subscriptions
    - marks them expired
    - sends expiry notification
    - DOES NOT remove the user from the channel
    """

    value = os.getenv(
        "SUBSCRIPTION_TEST_MODE",
        "false",
    ).strip().lower()

    return value in {
        "1",
        "true",
        "yes",
        "on",
    }


def get_latest_active_subscription(
    telegram_id,
):
    """
    Return the newest active subscription for a user.

    The newest record is determined primarily by
    started_at and secondarily by subscription ID.
    """

    db = SessionLocal()

    try:
        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.telegram_id == telegram_id,
                Subscription.status == "active",
            )
            .order_by(
                Subscription.started_at.desc(),
                Subscription.id.desc(),
            )
            .first()
        )

        if not subscription:
            return None

        return {
            "id": subscription.id,
            "telegram_id": subscription.telegram_id,
            "expires_at": subscription.expires_at,
        }

    finally:
        db.close()


async def expire_subscription(
    bot,
    subscription_id,
):
    """
    Expire a subscription safely.

    Before expiring anything, this function checks whether
    a newer active subscription exists for the same user.

    If a newer active subscription exists:
        - the old subscription is marked renewed
        - the user is NOT removed
        - no expiry notification is sent

    If this is the user's current subscription:
        - the user is removed in production mode
        - the subscription is marked expired
        - expiry notification is sent

    In test mode:
        - channel removal is skipped
        - everything else is tested normally
    """

    db = SessionLocal()

    try:
        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.id == subscription_id
            )
            .first()
        )

        if not subscription:
            print(
                f"⚠️ Subscription #{subscription_id} "
                "was not found."
            )
            return

        if subscription.status != "active":
            print(
                f"ℹ️ Subscription #{subscription_id} "
                f"is already '{subscription.status}'. "
                "Skipping."
            )
            return

        telegram_id = subscription.telegram_id
        expiry_time = subscription.expires_at
        current_id = subscription.id

        latest_active = (
            db.query(Subscription)
            .filter(
                Subscription.telegram_id == telegram_id,
                Subscription.status == "active",
            )
            .order_by(
                Subscription.started_at.desc(),
                Subscription.id.desc(),
            )
            .first()
        )

        # -------------------------------------------------
        # PROTECT AGAINST OLD SUBSCRIPTION EXPIRATION
        # -------------------------------------------------

        if (
            latest_active
            and latest_active.id != current_id
        ):
            print()
            print(
                f"🛡️ Subscription #{current_id} "
                "is an old subscription."
            )
            print(
                f"🆕 Newer active subscription found: "
                f"#{latest_active.id}"
            )
            print(
                f"👤 Telegram ID: {telegram_id}"
            )
            print(
                "🚫 User will NOT be removed "
                "from the premium channel."
            )

            subscription.status = "renewed"

            db.commit()

            print(
                f"✅ Old subscription #{current_id} "
                "marked as renewed/superseded."
            )
            print()

            return

    except Exception as e:

        db.rollback()

        print(
            f"❌ Error checking subscription "
            f"#{subscription_id}: "
            f"{type(e).__name__}: {e}"
        )

        return

    finally:
        db.close()

    # -----------------------------------------------------
    # CURRENT SUBSCRIPTION EXPIRATION
    # -----------------------------------------------------

    safe_test_mode = test_mode_enabled()

    print()
    print("=" * 70)
    print(
        f"⏰ EXPIRING CURRENT SUBSCRIPTION "
        f"#{subscription_id}"
    )
    print("=" * 70)
    print(
        f"👤 Telegram ID: {telegram_id}"
    )
    print(
        f"📅 Expiry: {format_ist(expiry_time)}"
    )
    print(
        f"🧪 Test mode: {safe_test_mode}"
    )
    print("=" * 70)

    # -----------------------------------------------------
    # REMOVE USER FROM PREMIUM CHANNEL
    # -----------------------------------------------------

    if safe_test_mode:

        print(
            "🧪 TEST MODE ENABLED"
        )

        print(
            f"🛡️ User {telegram_id} "
            "will NOT be removed from the channel."
        )

        print(
            "🛡️ Channel membership remains untouched."
        )

    else:

        try:

            print(
                f"🚪 Removing expired user "
                f"{telegram_id} "
                "from premium channel..."
            )

            await bot.ban_chat_member(
                chat_id=CHANNEL_ID,
                user_id=telegram_id,
            )

            await bot.unban_chat_member(
                chat_id=CHANNEL_ID,
                user_id=telegram_id,
                only_if_banned=True,
            )

            print(
                f"✅ User {telegram_id} "
                "removed from premium channel."
            )

        except TelegramError as e:

            print(
                f"❌ Failed to remove user "
                f"{telegram_id} from channel."
            )

            print(
                f"Error: {type(e).__name__}: {e}"
            )

    # -----------------------------------------------------
    # MARK SUBSCRIPTION AS EXPIRED
    # -----------------------------------------------------

    db = SessionLocal()

    try:

        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.id == subscription_id
            )
            .first()
        )

        if not subscription:
            print(
                f"⚠️ Subscription #{subscription_id} "
                "was not found during final update."
            )
            return

        if subscription.status != "active":
            print(
                f"ℹ️ Subscription #{subscription_id} "
                f"is now '{subscription.status}'. "
                "Skipping expiration update."
            )
            return

        subscription.status = "expired"

        db.commit()

        print(
            f"✅ Subscription #{subscription_id} "
            "marked as EXPIRED."
        )

    except Exception as e:

        db.rollback()

        print(
            f"❌ Failed to mark subscription "
            f"#{subscription_id} as expired."
        )

        print(
            f"Error: {type(e).__name__}: {e}"
        )

        return

    finally:
        db.close()

    # -----------------------------------------------------
    # SEND EXPIRY NOTIFICATION
    # -----------------------------------------------------

    try:

        await bot.send_message(
            chat_id=telegram_id,
            text=(
                "❌ PREMIUM MEMBERSHIP EXPIRED\n\n"
                "Your premium membership has expired.\n\n"
                f"📅 Expired on: "
                f"{format_ist(expiry_time)}\n\n"
                "🔄 Renew your membership to regain "
                "access to the premium channel."
            ),
        )

        print(
            f"📨 Expiry notification sent "
            f"to {telegram_id}."
        )

    except TelegramError as e:

        print(
            f"❌ Failed to send expiry notification "
            f"to {telegram_id}."
        )

        print(
            f"Error: {type(e).__name__}: {e}"
        )

    print("=" * 70)
    print(
        f"✅ Expiration process completed "
        f"for subscription #{subscription_id}."
    )
    print("=" * 70)
    print()


async def activate_scheduled_subscriptions(
    bot,
):
    """
    Activate scheduled subscriptions whose start time
    has arrived.

    A scheduled subscription is activated only when:
        - its status is 'scheduled'
        - its started_at <= now
        - the user has no current active subscription

    This function is intentionally idempotent.

    It is safe to run every worker cycle.
    """

    now = utc_now()

    db = SessionLocal()

    try:

        ready_subscriptions = (
            db.query(Subscription)
            .filter(
                Subscription.status == "scheduled",
                Subscription.started_at <= now,
            )
            .order_by(
                Subscription.started_at.asc(),
                Subscription.id.asc(),
            )
            .all()
        )

        if not ready_subscriptions:
            return

        print()
        print(
            "=" * 70
        )
        print(
            f"🔄 Found {len(ready_subscriptions)} "
            "scheduled subscription(s) ready for activation."
        )
        print(
            "=" * 70
        )

        for scheduled in ready_subscriptions:

            telegram_id = scheduled.telegram_id

            # -------------------------------------------------
            # CHECK FOR CURRENT ACTIVE SUBSCRIPTION
            # -------------------------------------------------

            active = (
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

            if active:

                print(
                    f"⏳ Subscription #{scheduled.id} "
                    f"cannot activate yet."
                )

                print(
                    f"👤 Telegram ID: {telegram_id}"
                )

                print(
                    f"🟢 Current active subscription: "
                    f"#{active.id}"
                )

                print(
                    f"📅 Active until: "
                    f"{format_ist(active.expires_at)}"
                )

                continue

            # -------------------------------------------------
            # ACTIVATE SUBSCRIPTION
            # -------------------------------------------------

            print()
            print(
                f"🚀 ACTIVATING SCHEDULED "
                f"SUBSCRIPTION #{scheduled.id}"
            )
            print(
                "-" * 70
            )
            print(
                f"👤 Telegram ID: {telegram_id}"
            )
            print(
                f"📅 Started: "
                f"{format_ist(scheduled.started_at)}"
            )
            print(
                f"📅 Expires: "
                f"{format_ist(scheduled.expires_at)}"
            )

            scheduled.status = "active"

            # Reset reminder flags in case this subscription
            # was ever prepared/reused during testing.
            scheduled.reminder_3d_sent = False
            scheduled.reminder_1d_sent = False

            db.commit()

            print(
                f"✅ Subscription #{scheduled.id} "
                "is now ACTIVE."
            )

            # -------------------------------------------------
            # CHECK CHANNEL ACCESS
            # -------------------------------------------------

            member_exists = False

            try:

                member = await bot.get_chat_member(
                    chat_id=CHANNEL_ID,
                    user_id=telegram_id,
                )

                member_status = member.status

                member_exists = member_status in {
                    "creator",
                    "administrator",
                    "member",
                    "restricted",
                }

                print(
                    f"🔍 Channel membership status: "
                    f"{member_status}"
                )

            except TelegramError as e:

                print(
                    f"⚠️ Could not check channel membership "
                    f"for {telegram_id}."
                )

                print(
                    f"Error: {type(e).__name__}: {e}"
                )

            # -------------------------------------------------
            # CREATE NEW INVITE IF NECESSARY
            # -------------------------------------------------

            if member_exists:

                print(
                    f"🔐 User {telegram_id} already has "
                    "channel access."
                )

                print(
                    "🔐 No new invite is required."
                )

            else:

                try:

                    print(
                        f"🔗 Creating activation invite "
                        f"for {telegram_id}..."
                    )

                    invite = (
                        await bot.create_chat_invite_link(
                            chat_id=CHANNEL_ID,
                            member_limit=1,
                        )
                    )

                    scheduled.invite_link = (
                        invite.invite_link
                    )

                    scheduled.invite_expires_at = None

                    db.commit()

                    await bot.send_message(
                        chat_id=telegram_id,
                        text=(
                            "🎉 YOUR PREMIUM MEMBERSHIP "
                            "IS NOW ACTIVE!\n\n"
                            "💎 Your paid renewal has "
                            "automatically activated.\n\n"
                            f"📅 Access until: "
                            f"{format_ist(scheduled.expires_at)}\n\n"
                            "🔗 Join the premium channel "
                            "using your personal invite link:\n\n"
                            f"{invite.invite_link}\n\n"
                            "⚠️ This invite is for your "
                            "account only."
                        ),
                    )

                    print(
                        f"📨 Activation invite sent "
                        f"to {telegram_id}."
                    )

                except TelegramError as e:

                    print(
                        f"❌ Failed to create/send activation "
                        f"invite for {telegram_id}."
                    )

                    print(
                        f"Error: {type(e).__name__}: {e}"
                    )

                    try:

                        await bot.send_message(
                            chat_id=telegram_id,
                            text=(
                                "🎉 YOUR PREMIUM MEMBERSHIP "
                                "IS NOW ACTIVE!\n\n"
                                f"📅 Your access is active "
                                f"until: "
                                f"{format_ist(scheduled.expires_at)}\n\n"
                                "⚠️ We could not generate your "
                                "channel invite automatically.\n\n"
                                "Please contact support."
                            ),
                        )

                    except TelegramError:
                        pass

            # -------------------------------------------------
            # ACTIVE CONFIRMATION FOR EXISTING MEMBERS
            # -------------------------------------------------

            if member_exists:

                try:

                    await bot.send_message(
                        chat_id=telegram_id,
                        text=(
                            "🎉 RENEWAL ACTIVATED!\n\n"
                            "💎 Your paid renewal has "
                            "automatically become active.\n\n"
                            f"📅 Your premium access now "
                            f"continues until:\n"
                            f"{format_ist(scheduled.expires_at)}\n\n"
                            "🔐 You already have access to "
                            "the premium channel, so no "
                            "new invite is required."
                        ),
                    )

                    print(
                        f"📨 Activation confirmation sent "
                        f"to {telegram_id}."
                    )

                except TelegramError as e:

                    print(
                        f"⚠️ Failed to send activation "
                        f"confirmation to {telegram_id}: "
                        f"{type(e).__name__}: {e}"
                    )

        print()
        print(
            "=" * 70
        )
        print(
            "✅ Scheduled activation check completed."
        )
        print(
            "=" * 70
        )
        print()

    except Exception as e:

        db.rollback()

        print()
        print(
            "❌ SCHEDULED ACTIVATION ERROR"
        )
        print(
            f"Error type: {type(e).__name__}"
        )
        print(
            f"Error details: {e}"
        )
        print()

    finally:
        db.close()


async def subscription_worker(bot):
    """
    Continuously check subscriptions.

    Runs once every 60 seconds.

    Checks:
        1. 3-day reminder
        2. 1-day reminder
        3. Expired subscriptions
        4. Scheduled subscription activation

    The expiration step happens BEFORE activation.

    This guarantees that when a current subscription ends,
    its next scheduled renewal can immediately become active.
    """

    print(
        "⏰ Subscription worker started."
    )

    while True:

        db = None

        try:

            now = utc_now()

            db = SessionLocal()

            # -------------------------------------------------
            # 3-DAY REMINDER
            # -------------------------------------------------

            three_days_from_now = (
                now + timedelta(days=3)
            )

            subscriptions_3d = (
                db.query(Subscription)
                .filter(
                    Subscription.status == "active",
                    Subscription.reminder_3d_sent == False,
                    Subscription.expires_at
                    <= three_days_from_now,
                    Subscription.expires_at > now,
                )
                .all()
            )

            for subscription in subscriptions_3d:

                try:

                    await bot.send_message(
                        chat_id=subscription.telegram_id,
                        text=(
                            "🔔 MEMBERSHIP EXPIRING SOON\n\n"
                            "Your premium membership expires "
                            "in approximately 3 days.\n\n"
                            f"📅 Expiry: "
                            f"{format_ist(subscription.expires_at)}\n\n"
                            "🔄 Renew your membership before "
                            "it expires to keep your access."
                        ),
                    )

                    subscription.reminder_3d_sent = True

                    db.commit()

                    print(
                        f"🔔 3-day reminder sent "
                        f"for subscription #{subscription.id}."
                    )

                except TelegramError as e:

                    db.rollback()

                    print(
                        f"❌ 3-day reminder failed "
                        f"for subscription #{subscription.id}: "
                        f"{type(e).__name__}: {e}"
                    )

            # -------------------------------------------------
            # 1-DAY REMINDER
            # -------------------------------------------------

            one_day_from_now = (
                now + timedelta(days=1)
            )

            subscriptions_1d = (
                db.query(Subscription)
                .filter(
                    Subscription.status == "active",
                    Subscription.reminder_1d_sent == False,
                    Subscription.expires_at
                    <= one_day_from_now,
                    Subscription.expires_at > now,
                )
                .all()
            )

            for subscription in subscriptions_1d:

                try:

                    await bot.send_message(
                        chat_id=subscription.telegram_id,
                        text=(
                            "⚠️ MEMBERSHIP EXPIRES TOMORROW\n\n"
                            "Your premium membership will "
                            "expire within 24 hours.\n\n"
                            f"📅 Expiry: "
                            f"{format_ist(subscription.expires_at)}\n\n"
                            "🔄 Renew now to avoid losing "
                            "access to the premium channel."
                        ),
                    )

                    subscription.reminder_1d_sent = True

                    db.commit()

                    print(
                        f"⚠️ 1-day reminder sent "
                        f"for subscription #{subscription.id}."
                    )

                except TelegramError as e:

                    db.rollback()

                    print(
                        f"❌ 1-day reminder failed "
                        f"for subscription #{subscription.id}: "
                        f"{type(e).__name__}: {e}"
                    )

            # -------------------------------------------------
            # FIND EXPIRED ACTIVE SUBSCRIPTIONS
            # -------------------------------------------------

            expired_subscriptions = (
                db.query(Subscription)
                .filter(
                    Subscription.status == "active",
                    Subscription.expires_at <= now,
                )
                .all()
            )

            expired_ids = [
                subscription.id
                for subscription in expired_subscriptions
            ]

            if expired_ids:

                print(
                    f"⏰ Found {len(expired_ids)} "
                    "expired active subscription(s): "
                    f"{expired_ids}"
                )

            db.close()
            db = None

            # -------------------------------------------------
            # PROCESS EXPIRATIONS FIRST
            # -------------------------------------------------

            for subscription_id in expired_ids:

                await expire_subscription(
                    bot,
                    subscription_id,
                )

            # -------------------------------------------------
            # ACTIVATE SCHEDULED RENEWALS
            # -------------------------------------------------

            await activate_scheduled_subscriptions(
                bot,
            )

        except asyncio.CancelledError:

            if db:
                db.close()

            print(
                "⏰ Subscription worker cancelled."
            )

            raise

        except Exception as e:

            if db:
                db.close()

            print()
            print(
                "❌ SUBSCRIPTION WORKER ERROR"
            )
            print(
                f"Error type: {type(e).__name__}"
            )
            print(
                f"Error details: {e}"
            )
            print()

        # -----------------------------------------------------
        # WAIT BEFORE NEXT CHECK
        # -----------------------------------------------------

        await asyncio.sleep(60)