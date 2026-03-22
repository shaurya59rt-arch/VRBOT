from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Balance"), KeyboardButton(text="🎁 Bonus")],
            [KeyboardButton(text="👥 Refer & Earn"), KeyboardButton(text="🏦 Link Wallet")],
            [KeyboardButton(text="💸 Withdraw"), KeyboardButton(text="🎟 Gift Code")],
        ],
        resize_keyboard=True,
    )


def verification_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Verify Now",
                    web_app=WebAppInfo(url=webapp_url),
                )
            ],
            [InlineKeyboardButton(text="🔄 Check Verification", callback_data="check_access")],
        ]
    )


def required_channels_keyboard(channels: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for channel in channels:
        builder.row(
            InlineKeyboardButton(
                text=f"📢 {channel['title']}",
                url=channel["invite_link"],
            )
        )
    builder.row(InlineKeyboardButton(text="✅ I've Joined", callback_data="check_access"))
    return builder.as_markup()


def admin_panel_keyboard(withdraw_enabled: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📢 Channels", "admin_channels"),
        ("🎁 Gift Codes", "admin_gift_codes"),
        ("💸 Withdrawals", "admin_withdrawals"),
        ("👤 Talk to User", "admin_talk_user"),
        ("💳 Adjust Balance", "admin_balance"),
        ("🚫 Ban / Unban", "admin_ban_menu"),
        ("🎯 Referral Reward", "admin_referral_reward"),
        ("🎲 Bonus Amount", "admin_bonus_amount"),
        ("♻ Reset Balance", "admin_reset_balance"),
        (
            "🔓 Disable Withdraw" if withdraw_enabled else "🔒 Enable Withdraw",
            "admin_toggle_withdraw",
        ),
        ("📡 Payout Channel", "admin_payout_channel"),
        ("🧾 Withdraw Tax", "admin_tax"),
        ("📊 Stats", "admin_stats"),
    ]
    for text, data in buttons:
        builder.button(text=text, callback_data=data)
    builder.adjust(2, 2, 2, 2, 2, 2, 1)
    return builder.as_markup()


def channel_management_keyboard(channels: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Add Channel", callback_data="admin_add_channel"))
    for channel in channels:
        builder.row(
            InlineKeyboardButton(
                text=f"❌ Remove {channel['title']}",
                callback_data=f"remove_channel:{channel['chat_id']}",
            )
        )
    builder.row(InlineKeyboardButton(text="⬅ Back", callback_data="admin_home"))
    return builder.as_markup()


def gift_code_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Create Gift Code", callback_data="admin_create_gift")],
            [InlineKeyboardButton(text="📄 View Gift Codes", callback_data="admin_view_gifts")],
            [InlineKeyboardButton(text="⬅ Back", callback_data="admin_home")],
        ]
    )
