import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class ThrottleMiddleware(BaseMiddleware):
    def __init__(self, cooldown: float = 0.8) -> None:
        self.cooldown = cooldown
        self.activity: dict[int, float] = defaultdict(float)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if not user_id:
            return await handler(event, data)

        now = time.monotonic()
        if now - self.activity[user_id] < self.cooldown:
            if isinstance(event, CallbackQuery):
                await event.answer("Please slow down a little.", show_alert=False)
            return None

        self.activity[user_id] = now
        return await handler(event, data)
