from aiogram.fsm.state import State, StatesGroup


class WalletState(StatesGroup):
    waiting_wallet = State()


class WithdrawState(StatesGroup):
    waiting_amount = State()


class GiftState(StatesGroup):
    waiting_code = State()


class AdminChannelState(StatesGroup):
    waiting_chat = State()


class AdminNumericState(StatesGroup):
    waiting_value = State()


class AdminResetBalanceState(StatesGroup):
    waiting_user = State()


class AdminGiftCreateState(StatesGroup):
    waiting_data = State()


class AdminTalkState(StatesGroup):
    waiting_user = State()
    waiting_message = State()


class AdminBalanceState(StatesGroup):
    waiting_data = State()


class AdminBanState(StatesGroup):
    waiting_data = State()


class AdminPayoutState(StatesGroup):
    waiting_value = State()
