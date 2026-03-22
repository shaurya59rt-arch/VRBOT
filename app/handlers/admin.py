from aiogram import F, Router
from aiogram.filters import Filter
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.context import app_context
from app.keyboards import admin_panel_keyboard, channel_management_keyboard, gift_code_admin_keyboard
from app.states import (
    AdminBalanceState,
    AdminBanState,
    AdminChannelState,
    AdminGiftCreateState,
    AdminNumericState,
    AdminPayoutState,
    AdminResetBalanceState,
    AdminTalkState,
)
from app.utils import format_money, human_datetime, is_admin, parse_float

admin_router = Router()


class AdminFilter(Filter):
    async def __call__(self, event) -> bool:
        return is_admin(event.from_user.id, app_context["settings"].admin_ids)


admin_router.message.filter(AdminFilter())
admin_router.callback_query.filter(AdminFilter())


async def get_ctx(event):
    return app_context


async def render_admin_panel(message: Message) -> None:
    ctx = await get_ctx(message)
    db = ctx["db"]
    withdraw_enabled = await db.get_setting("withdraw_enabled", "1") == "1"
    await message.answer(
        "⚙️ <b>Admin Panel</b>\nChoose a management action below.",
        reply_markup=admin_panel_keyboard(withdraw_enabled),
    )


@admin_router.callback_query(F.data == "admin_home")
async def admin_home(callback: CallbackQuery) -> None:
    ctx = await get_ctx(callback)
    db = ctx["db"]
    withdraw_enabled = await db.get_setting("withdraw_enabled", "1") == "1"
    await callback.message.edit_text(
        "⚙️ <b>Admin Panel</b>\nChoose a management action below.",
        reply_markup=admin_panel_keyboard(withdraw_enabled),
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_channels")
async def admin_channels(callback: CallbackQuery) -> None:
    ctx = await get_ctx(callback)
    db = ctx["db"]
    channels = await db.get_channels()
    lines = ["📢 <b>Required Channels</b>"]
    if channels:
        lines.extend([f"• {item['title']} (<code>{item['chat_id']}</code>)" for item in channels])
    else:
        lines.append("No required channels configured.")
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=channel_management_keyboard(channels),
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_add_channel")
async def admin_add_channel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminChannelState.waiting_chat)
    await callback.message.answer("Send the channel ID or @username to add.")
    await callback.answer()


@admin_router.message(AdminChannelState.waiting_chat)
async def admin_add_channel_save(message: Message, state: FSMContext) -> None:
    ctx = await get_ctx(message)
    db = ctx["db"]
    ref = (message.text or "").strip()
    try:
        chat = await message.bot.get_chat(ref)
        invite = await message.bot.create_chat_invite_link(
            chat_id=chat.id,
            creates_join_request=True,
            name="Required Access Link",
        )
    except TelegramForbiddenError:
        await message.answer(
            "The bot must be an admin in this channel to generate an invite link."
        )
        return
    except TelegramBadRequest as exc:
        await message.answer(f"Unable to add channel: {exc.message}")
        return
    except Exception:
        await message.answer("Unable to add this channel. Make sure the bot is an admin there.")
        return

    await db.add_channel(chat.id, chat.title or str(chat.id), invite.invite_link)
    await state.clear()
    await message.answer("✅ Channel added successfully.")
    await render_admin_panel(message)


@admin_router.callback_query(F.data.startswith("remove_channel:"))
async def admin_remove_channel(callback: CallbackQuery) -> None:
    ctx = await get_ctx(callback)
    db = ctx["db"]
    chat_id = int(callback.data.split(":")[1])
    await db.remove_channel(chat_id)
    channels = await db.get_channels()
    await callback.message.edit_text(
        "📢 <b>Required Channels</b>\nChannel removed successfully.",
        reply_markup=channel_management_keyboard(channels),
    )
    await callback.answer("Removed")


@admin_router.callback_query(F.data == "admin_referral_reward")
async def admin_referral_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminNumericState.waiting_value)
    await state.update_data(setting_key="referral_reward", label="referral reward")
    await callback.message.answer("Send the new referral reward amount.")
    await callback.answer()


@admin_router.callback_query(F.data == "admin_bonus_amount")
async def admin_bonus_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminNumericState.waiting_value)
    await state.update_data(setting_key="bonus_amount", label="bonus amount")
    await callback.message.answer("Send the new maximum daily bonus amount.")
    await callback.answer()


@admin_router.callback_query(F.data == "admin_tax")
async def admin_tax_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminNumericState.waiting_value)
    await state.update_data(setting_key="withdraw_tax_percent", label="withdraw tax percent")
    await callback.message.answer("Send the withdraw tax percentage.")
    await callback.answer()


@admin_router.message(AdminNumericState.waiting_value)
async def admin_numeric_save(message: Message, state: FSMContext) -> None:
    ctx = await get_ctx(message)
    db = ctx["db"]
    data = await state.get_data()
    try:
        value = parse_float(message.text)
    except Exception:
        await message.answer("Please send a valid number.")
        return
    await db.set_setting(data["setting_key"], str(value))
    await state.clear()
    await message.answer(f"✅ {data['label'].capitalize()} updated to {format_money(value)}.")


@admin_router.callback_query(F.data == "admin_toggle_withdraw")
async def admin_toggle_withdraw(callback: CallbackQuery) -> None:
    ctx = await get_ctx(callback)
    db = ctx["db"]
    current = await db.get_setting("withdraw_enabled", "1")
    await db.set_setting("withdraw_enabled", "0" if current == "1" else "1")
    withdraw_enabled = await db.get_setting("withdraw_enabled", "1") == "1"
    await callback.message.edit_text(
        "⚙️ <b>Admin Panel</b>\nChoose a management action below.",
        reply_markup=admin_panel_keyboard(withdraw_enabled),
    )
    await callback.answer("Updated")


@admin_router.callback_query(F.data == "admin_payout_channel")
async def admin_payout_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminPayoutState.waiting_value)
    await callback.message.answer("Send the payout channel ID or @username.")
    await callback.answer()


@admin_router.message(AdminPayoutState.waiting_value)
async def admin_payout_save(message: Message, state: FSMContext) -> None:
    ctx = await get_ctx(message)
    db = ctx["db"]
    await db.set_setting("payout_channel", (message.text or "").strip())
    await state.clear()
    await message.answer("✅ Payout channel updated.")


@admin_router.callback_query(F.data == "admin_reset_balance")
async def admin_reset_balance_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminResetBalanceState.waiting_user)
    await callback.message.answer("Send the user ID to reset the balance.")
    await callback.answer()


@admin_router.message(AdminResetBalanceState.waiting_user)
async def admin_reset_balance_save(message: Message, state: FSMContext) -> None:
    ctx = await get_ctx(message)
    db = ctx["db"]
    user_id = (message.text or "").strip()
    if not user_id.isdigit():
        await message.answer("Please send a valid numeric user ID.")
        return
    await db.set_balance(int(user_id), 0)
    await state.clear()
    await message.answer("✅ User balance reset to 0.")


@admin_router.callback_query(F.data == "admin_withdrawals")
async def admin_withdrawals(callback: CallbackQuery) -> None:
    ctx = await get_ctx(callback)
    db = ctx["db"]
    items = await db.list_withdrawals()
    if not items:
        text = "No withdrawal requests found."
    else:
        text = "\n\n".join(
            [
                "\n".join(
                    [
                        f"#{item['id']} | User: <code>{item['user_id']}</code>",
                        f"Amount: <b>{format_money(item['amount'])}</b>",
                        f"Net: <b>{format_money(item['net_amount'])}</b>",
                        f"Wallet: <code>{item['wallet']}</code>",
                        f"Status: <b>{item['status']}</b>",
                        f"Date: {human_datetime(item['created_at'])}",
                    ]
                )
                for item in items
            ]
        )
    await callback.message.answer(f"💸 <b>Recent Withdrawals</b>\n\n{text}")
    await callback.answer()


@admin_router.callback_query(F.data == "admin_gift_codes")
async def admin_gift_codes(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🎟 <b>Gift Code Management</b>",
        reply_markup=gift_code_admin_keyboard(),
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_create_gift")
async def admin_create_gift_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminGiftCreateState.waiting_data)
    await callback.message.answer(
        "Send gift code details in this format:\n<code>CODE AMOUNT MAX_USES</code>"
    )
    await callback.answer()


@admin_router.message(AdminGiftCreateState.waiting_data)
async def admin_create_gift_save(message: Message, state: FSMContext) -> None:
    ctx = await get_ctx(message)
    db = ctx["db"]
    parts = (message.text or "").strip().split()
    if len(parts) != 3:
        await message.answer("Format must be: CODE AMOUNT MAX_USES")
        return
    try:
        await db.create_gift_code(parts[0].upper(), parse_float(parts[1]), int(parts[2]), message.from_user.id)
    except Exception:
        await message.answer("Unable to create gift code. It may already exist.")
        return
    await state.clear()
    await message.answer("✅ Gift code created successfully.")


@admin_router.callback_query(F.data == "admin_view_gifts")
async def admin_view_gifts(callback: CallbackQuery) -> None:
    ctx = await get_ctx(callback)
    db = ctx["db"]
    items = await db.list_gift_codes()
    if not items:
        text = "No gift codes created yet."
    else:
        text = "\n\n".join(
            [
                "\n".join(
                    [
                        f"Code: <code>{item['code']}</code>",
                        f"Amount: <b>{format_money(item['amount'])}</b>",
                        f"Uses: <b>{item['uses_count']}/{item['max_uses']}</b>",
                        f"Status: <b>{'Active' if item['is_active'] else 'Inactive'}</b>",
                    ]
                )
                for item in items
            ]
        )
    await callback.message.answer(f"🎟 <b>Gift Codes</b>\n\n{text}")
    await callback.answer()


@admin_router.callback_query(F.data == "admin_talk_user")
async def admin_talk_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminTalkState.waiting_user)
    await callback.message.answer("Send the target user ID.")
    await callback.answer()


@admin_router.message(AdminTalkState.waiting_user)
async def admin_talk_user(message: Message, state: FSMContext) -> None:
    user_id = (message.text or "").strip()
    if not user_id.isdigit():
        await message.answer("Please send a valid numeric user ID.")
        return
    await state.update_data(target_user_id=int(user_id))
    await state.set_state(AdminTalkState.waiting_message)
    await message.answer("Now send the message you want to deliver.")


@admin_router.message(AdminTalkState.waiting_message)
async def admin_talk_send(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        await message.bot.send_message(
            data["target_user_id"],
            f"📩 <b>Message from Admin</b>\n\n{message.text}",
        )
        await message.answer("✅ Message sent successfully.")
    except Exception:
        await message.answer("Unable to deliver the message to this user.")
    await state.clear()


@admin_router.callback_query(F.data == "admin_balance")
async def admin_balance_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBalanceState.waiting_data)
    await callback.message.answer(
        "Send balance update in this format:\n<code>USER_ID +/-AMOUNT</code>\nExample: <code>123456789 +50</code>"
    )
    await callback.answer()


@admin_router.message(AdminBalanceState.waiting_data)
async def admin_balance_save(message: Message, state: FSMContext) -> None:
    ctx = await get_ctx(message)
    db = ctx["db"]
    parts = (message.text or "").strip().split()
    if len(parts) != 2 or not parts[0].isdigit():
        await message.answer("Format must be: USER_ID +/-AMOUNT")
        return
    raw_amount = parts[1]
    try:
        amount = parse_float(raw_amount.replace("+", ""))
        if raw_amount.startswith("-"):
            amount *= -1
    except Exception:
        await message.answer("Please send a valid amount.")
        return
    await db.adjust_balance(int(parts[0]), amount)
    await state.clear()
    await message.answer("✅ Balance updated successfully.")


@admin_router.callback_query(F.data == "admin_ban_menu")
async def admin_ban_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBanState.waiting_data)
    await callback.message.answer(
        "Send ban command in this format:\n<code>USER_ID ban</code> or <code>USER_ID unban</code>"
    )
    await callback.answer()


@admin_router.message(AdminBanState.waiting_data)
async def admin_ban_save(message: Message, state: FSMContext) -> None:
    ctx = await get_ctx(message)
    db = ctx["db"]
    parts = (message.text or "").strip().split()
    if len(parts) != 2 or not parts[0].isdigit():
        await message.answer("Format must be: USER_ID ban|unban")
        return
    if parts[1].lower() not in {"ban", "unban"}:
        await message.answer("Use either ban or unban.")
        return
    action = parts[1].lower()
    await db.set_ban_status(int(parts[0]), action == "ban")
    await state.clear()
    await message.answer(f"✅ User {action}ned successfully.")


@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery) -> None:
    ctx = await get_ctx(callback)
    db = ctx["db"]
    stats = await db.stats()
    await callback.message.answer(
        "\n".join(
            [
                "📊 <b>Bot Stats</b>",
                f"Users: <b>{stats['users']}</b>",
                f"Verified users: <b>{stats['verified']}</b>",
                f"Withdrawals: <b>{stats['withdrawals']}</b>",
            ]
        )
    )
    await callback.answer()
