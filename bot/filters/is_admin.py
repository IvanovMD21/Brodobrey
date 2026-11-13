"""Фильтр: только для админа."""
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.config import config


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id if event.from_user else 0
        return user_id == config.admin_id