"""Точка входа: запуск бота и планировщика (без webhook-сервера)."""
from __future__ import annotations

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

from bot.config import config
from bot.db.session import init_db
from bot.handlers import admin as admin_h
from bot.handlers import user as user_h
from bot.middlewares.admin_middleware import UserMiddleware
from bot.scheduler import setup_scheduler


async def seed_initial_data() -> None:
    from sqlalchemy import select
    from bot.db.session import async_session
    from bot.db.models import Barber, Service

    async with async_session() as session:
        res = await session.execute(select(Barber))
        if not res.scalars().first():
            session.add_all([
                Barber(name="Алексей", nickname="Лёха"),
                Barber(name="Дмитрий", nickname="Дима"),
                Barber(name="Сергей", nickname="Серж"),
                Barber(name="Максим", nickname="Макс"),
            ])
            await session.commit()
            logger.info("Добавлены стартовые барберы")

        res = await session.execute(select(Service))
        if not res.scalars().first():
            session.add_all([
                Service(name="Мужская стрижка", price=1500, duration_min=45),
                Service(name="Стрижка машинкой", price=1000, duration_min=30),
                Service(name="Оформление бороды", price=800, duration_min=30),
                Service(name="Комплекс: стрижка + борода", price=2000, duration_min=75),
                Service(name="Детская стрижка (до 12 лет)", price=1000, duration_min=30),
                Service(name="Королевское бритьё", price=1200, duration_min=45),
                Service(name="Камуфляж седины", price=1000, duration_min=30),
                Service(name="Укладка/стайлинг", price=500, duration_min=15),
            ])
            await session.commit()
            logger.info("Добавлены стартовые услуги")


async def main() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level=config.log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>",
    )
    logger.add(
        "logs/bot.log", rotation="10 MB", retention="10 days",
        level="DEBUG", encoding="utf-8",
    )

    if not config.bot_token:
        logger.error("BOT_TOKEN не задан в .env")
        return

    await init_db()
    await seed_initial_data()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())

    dp.include_router(admin_h.router)
    dp.include_router(user_h.router)

    @dp.errors()
    async def on_error(event):
        logger.exception(f"Необработанная ошибка: {event.exception}")
        return True

    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("⏰ Планировщик запущен")

    logger.info("🚀 Бот запущен")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")