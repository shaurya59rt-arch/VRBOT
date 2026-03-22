from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, ChatJoinRequest, Message

from app.context import app_context
from app.keyboards import main_menu_keyboard, required_channels_keyboard, verification_keyboard
from app.utils import display_name

common_router = Router()


async def get_ctx(event):
    return app_context


async def ensure_access(event, user_id: int) -> tuple[bool, str | list[dict] | None]:
    ctx = await get_ctx(event)
    db = ctx["db"]
    bot = event.bot
    user = await db.get_user(user_id)
    if not user:
        return False, "User not found."
    if user["is_banned"]:
        return False, "Your account has been restricted."
    if not user["is_verified"]:
        return False, "verification"

    channels = await db.get_channels()
    missing = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(channel["chat_id"], user_id)
            if member.status in {"left", "kicked"}:
                missing.append(channel)
        except Exception:
            missing.append(channel)

    if missing:
        return False, missing
    return True, None


async def send_access_gate(message: Message, user_id: int) -> None:
    ctx = await get_ctx(message)
    settings = ctx["settings"]
    ok, reason = await ensure_access(message, user_id)
    if ok:
        await message.answer(
            "Welcome back. Choose an option below.",
            reply_markup=main_menu_keyboard(),
        )
        return

    if reason == "verification":
        await message.answer(
            "🔒 <b>Verification Required</b>\n\nPlease complete verification to continue.",
            reply_markup=verification_keyboard(f"{settings.webapp_base_url}/verify"),
        )
        return

    if isinstance(reason, list):
        await message.answer(
            "Please join required channels to continue.",
            reply_markup=required_channels_keyboard(reason),
        )
        return

    await message.answer(str(reason))


@common_router.message(Command("start"))
async def start_handler(message: Message) -> None:
    ctx = await get_ctx(message)
    db = ctx["db"]
    referred_by = None
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("ref_"):
        payload = args[1].replace("ref_", "", 1)
        if payload.isdigit():
            referred_by = int(payload)

    await db.register_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=display_name(message.from_user),
        referred_by=referred_by,
    )
    await send_access_gate(message, message.from_user.id)


@common_router.callback_query(F.data == "check_access")
async def check_access_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    await send_access_gate(callback.message, callback.from_user.id)


@common_router.message(F.web_app_data)
async def webapp_data_handler(message: Message) -> None:
    ctx = await get_ctx(message)
    db = ctx["db"]
    user = await db.get_user(message.from_user.id)
    if user and user["is_verified"]:
        await send_access_gate(message, message.from_user.id)
    else:
        await message.answer(
            "Verification is still pending. Please complete it in the Mini App first."
        )


@common_router.message(Command("admin"))
async def admin_shortcut(message: Message) -> None:
    ctx = await get_ctx(message)
    if message.from_user.id not in ctx["settings"].admin_ids:
        await message.answer("This command is only available to admins.")
        return
    from app.handlers.admin import render_admin_panel

    await render_admin_panel(message)


@common_router.chat_join_request()
async def join_request_handler(update: ChatJoinRequest) -> None:
    ctx = await get_ctx(update)
    db = ctx["db"]
    channels = await db.get_channels()
    channel_ids = {item["chat_id"] for item in channels}
    if update.chat.id not in channel_ids:
        return
    try:
        await update.bot.approve_chat_join_request(update.chat.id, update.from_user.id)
    except Exception:
        return
