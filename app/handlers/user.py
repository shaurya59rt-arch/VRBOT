from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.context import app_context
from app.handlers.common import ensure_access
from app.keyboards import main_menu_keyboard
from app.states import GiftState, WalletState, WithdrawState
from app.utils import format_money, human_datetime, make_referral_link, parse_float, random_bonus

user_router = Router()


async def get_ctx(message: Message):
    return app_context


async def access_or_prompt(message: Message) -> bool:
    from app.handlers.common import send_access_gate

    ok, _ = await ensure_access(message, message.from_user.id)
    if not ok:
        await send_access_gate(message, message.from_user.id)
        return False
    return True


@user_router.message(F.text == "💰 Balance")
async def balance_handler(message: Message) -> None:
    if not await access_or_prompt(message):
        return
    ctx = await get_ctx(message)
    db = ctx["db"]
    user = await db.get_user(message.from_user.id)
    await message.answer(
        "\n".join(
            [
                "💰 <b>Your Account</b>",
                f"Balance: <b>{format_money(user['balance'])}</b>",
                f"Referrals: <b>{user['referrals_count']}</b>",
                f"Wallet: <b>{user['wallet'] or 'Not linked'}</b>",
                f"Verified: <b>{'Yes' if user['is_verified'] else 'No'}</b>",
            ]
        ),
        reply_markup=main_menu_keyboard(),
    )


@user_router.message(F.text == "🎁 Bonus")
async def bonus_handler(message: Message) -> None:
    if not await access_or_prompt(message):
        return
    ctx = await get_ctx(message)
    db = ctx["db"]
    can_claim, next_time = await db.can_claim_bonus(message.from_user.id)
    if not can_claim:
        await message.answer(
            f"Your daily bonus is on cooldown.\nNext claim: <b>{human_datetime(next_time)}</b>"
        )
        return

    max_bonus = float(await db.get_setting("bonus_amount", "10"))
    amount = random_bonus(max_bonus)
    await db.claim_bonus(message.from_user.id, amount)
    await message.answer(
        f"🎉 Daily bonus claimed.\nYou received <b>{format_money(amount)}</b>."
    )


@user_router.message(F.text == "👥 Refer & Earn")
async def refer_handler(message: Message) -> None:
    if not await access_or_prompt(message):
        return
    ctx = await get_ctx(message)
    db = ctx["db"]
    reward = await db.get_setting("referral_reward", "0")
    user = await db.get_user(message.from_user.id)
    await message.answer(
        "\n".join(
            [
                "👥 <b>Refer & Earn</b>",
                f"Your link: {make_referral_link(ctx['bot_username'], message.from_user.id)}",
                f"Referral reward: <b>{reward}</b>",
                f"Successful referrals: <b>{user['referrals_count']}</b>",
                "",
                "Referral rewards are credited after the invited user completes verification.",
            ]
        )
    )


@user_router.message(F.text == "🏦 Link Wallet")
async def wallet_prompt(message: Message, state: FSMContext) -> None:
    if not await access_or_prompt(message):
        return
    await state.set_state(WalletState.waiting_wallet)
    await message.answer("Send your UPI ID or Paytm number.")


@user_router.message(WalletState.waiting_wallet)
async def wallet_save(message: Message, state: FSMContext) -> None:
    ctx = await get_ctx(message)
    db = ctx["db"]
    wallet = (message.text or "").strip()
    if len(wallet) < 5:
        await message.answer("Please send a valid UPI ID or Paytm number.")
        return
    await db.set_wallet(message.from_user.id, wallet)
    await state.clear()
    await message.answer("✅ Wallet saved successfully.", reply_markup=main_menu_keyboard())


@user_router.message(F.text == "💸 Withdraw")
async def withdraw_prompt(message: Message, state: FSMContext) -> None:
    if not await access_or_prompt(message):
        return
    ctx = await get_ctx(message)
    db = ctx["db"]
    user = await db.get_user(message.from_user.id)
    if not user["wallet"]:
        await message.answer("Please link your wallet before requesting a withdrawal.")
        return
    if await db.get_setting("withdraw_enabled", "1") != "1":
        await message.answer("Withdrawals are currently disabled by the admin.")
        return
    await state.set_state(WithdrawState.waiting_amount)
    await message.answer(
        f"Your available balance is <b>{format_money(user['balance'])}</b>.\nSend the withdrawal amount."
    )


@user_router.message(WithdrawState.waiting_amount)
async def withdraw_submit(message: Message, state: FSMContext) -> None:
    ctx = await get_ctx(message)
    db = ctx["db"]
    try:
        amount = parse_float(message.text)
    except Exception:
        await message.answer("Please send a valid amount.")
        return

    user = await db.get_user(message.from_user.id)
    if amount <= 0:
        await message.answer("Amount must be greater than zero.")
        return
    if user["balance"] < amount:
        await message.answer("Insufficient balance.")
        return

    tax_percent = float(await db.get_setting("withdraw_tax_percent", "0"))
    tax_amount = round(amount * tax_percent / 100, 2)
    net_amount = round(amount - tax_amount, 2)
    withdraw_id = await db.create_withdrawal(
        user_id=message.from_user.id,
        amount=amount,
        tax_amount=tax_amount,
        net_amount=net_amount,
        wallet=user["wallet"],
    )

    payout_channel = await db.get_setting("payout_channel", "")
    if payout_channel:
        try:
            await message.bot.send_message(
                payout_channel,
                "\n".join(
                    [
                        "💸 <b>New Withdrawal Request</b>",
                        f"ID: <b>#{withdraw_id}</b>",
                        f"User: <code>{message.from_user.id}</code>",
                        f"Amount: <b>{format_money(amount)}</b>",
                        f"Tax: <b>{format_money(tax_amount)}</b>",
                        f"Net: <b>{format_money(net_amount)}</b>",
                        f"Wallet: <code>{user['wallet']}</code>",
                    ]
                ),
            )
        except Exception:
            pass

    for admin_id in ctx["settings"].admin_ids:
        try:
            await message.bot.send_message(
                admin_id,
                "\n".join(
                    [
                        "💸 <b>Withdrawal Request</b>",
                        f"ID: <b>#{withdraw_id}</b>",
                        f"User: <code>{message.from_user.id}</code>",
                        f"Amount: <b>{format_money(amount)}</b>",
                        f"Tax: <b>{format_money(tax_amount)}</b>",
                        f"Net Amount: <b>{format_money(net_amount)}</b>",
                        f"Wallet: <code>{user['wallet']}</code>",
                    ]
                ),
            )
        except Exception:
            pass

    await state.clear()
    await message.answer(
        f"✅ Withdrawal request submitted.\nNet payout after tax: <b>{format_money(net_amount)}</b>."
    )


@user_router.message(F.text == "🎟 Gift Code")
async def gift_prompt(message: Message, state: FSMContext) -> None:
    if not await access_or_prompt(message):
        return
    await state.set_state(GiftState.waiting_code)
    await message.answer("Send your gift code.")


@user_router.message(GiftState.waiting_code)
async def gift_redeem(message: Message, state: FSMContext) -> None:
    ctx = await get_ctx(message)
    db = ctx["db"]
    success, result_message, amount = await db.redeem_gift_code(
        message.from_user.id,
        (message.text or "").strip(),
    )
    await state.clear()
    if success:
        await message.answer(
            f"✅ {result_message}\nAmount added: <b>{format_money(amount)}</b>."
        )
    else:
        await message.answer(result_message)


@user_router.message(F.text.regexp(r"^(?!/).+"))
async def fallback_user_message(message: Message) -> None:
    if not await access_or_prompt(message):
        return
    await message.answer(
        "Please use the menu buttons to continue.",
        reply_markup=main_menu_keyboard(),
    )
