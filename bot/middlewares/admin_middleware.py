"""Middleware: автоматически передаёт пользователя и его статус."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser
from loguru import logger

from bot.db import crud
from bot.db.session import async_session


class UserMiddleware(BaseMiddleware):
    """Кладёт в data['db_user'] запись User из БД (если есть)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        async with async_session() as session:
            user = await crud.get_user_by_tg(session, tg_user.id)
            data["db_user"] = user
            data["session"] = session

            # Блокировка: клиент с is_blocked=True не может пользоваться ботом
            if user and user.is_blocked and tg_user.id != data.get("admin_id"):
                from bot.config import config
                if tg_user.id != config.admin_id:
                    if hasattr(event, "answer"):
                        try:
                            await event.answer(
                                "🚫 Ваш доступ к боту заблокирован администратором."
                            )
                        except Exception as e:
                            logger.debug(f"Не удалось отправить блокировку: {e}")
                    return None

            return await handler(event, data)