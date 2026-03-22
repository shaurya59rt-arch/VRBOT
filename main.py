import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from uvicorn import Config, Server

from app.config import settings
from app.context import app_context
from app.database import Database
from app.handlers.admin import admin_router
from app.handlers.common import common_router
from app.handlers.user import user_router
from app.middlewares.throttle import ThrottleMiddleware
from app.web import create_app


async def run_webserver(app) -> None:
    config = Config(
        app=app,
        host=settings.host,
        port=settings.port,
        log_level="info",
        loop="asyncio",
    )
    server = Server(config)
    await server.serve()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    db = Database(settings.db_path)
    await db.connect()
    await db.init()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    me = await bot.get_me()

    dp = Dispatcher()
    dp.message.middleware(ThrottleMiddleware())
    dp.callback_query.middleware(ThrottleMiddleware())

    shared = {
        "db": db,
        "settings": settings,
        "bot_username": me.username or "",
    }
    app_context.clear()
    app_context.update(shared)
    dp.include_router(common_router)
    dp.include_router(admin_router)
    dp.include_router(user_router)

    web_app = create_app(bot=bot, db=db, settings=settings)

    try:
        await asyncio.gather(
            run_webserver(web_app),
            dp.start_polling(bot),
        )
    finally:
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
