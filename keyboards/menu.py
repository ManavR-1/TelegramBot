from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


def main_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "💎 Buy Membership",
                callback_data="buy_membership",
            )
        ],
        [
            InlineKeyboardButton(
                "📊 My Subscription",
                callback_data="my_subscription",
            )
        ],
        [
            InlineKeyboardButton(
                "📞 Support",
                callback_data="support",
            )
        ],
    ]

    return InlineKeyboardMarkup(
        keyboard
    )


def payment_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "📷 View QR Code",
                callback_data="view_qr",
            )
        ],
        [
            InlineKeyboardButton(
                "✅ I've Paid",
                callback_data="payment_submitted",
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="back_to_menu",
            )
        ],
    ]

    return InlineKeyboardMarkup(
        keyboard
    )


def marketing_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "📢 Publish Promo",
                callback_data="marketing_publish",
            )
        ],
        [
            InlineKeyboardButton(
                "🔗 Campaign Links",
                callback_data="marketing_links",
            )
        ],
        [
            InlineKeyboardButton(
                "📊 Campaign Stats",
                callback_data="marketing_stats",
            )
        ],
    ]

    return InlineKeyboardMarkup(
        keyboard
    )


def campaign_menu(
    campaign: str,
    bot_username: str,
):

    bot_username = bot_username.lstrip("@")

    tracking_link = (
        f"https://t.me/{bot_username}"
        f"?start=campaign_{campaign}"
    )

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💎 Join Premium",
                    url=tracking_link,
                )
            ]
        ]
    )