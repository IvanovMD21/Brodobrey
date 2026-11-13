"""Админ-хендлер: Mini App только для администратора."""
from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonDefault,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)
from loguru import logger

from bot.config import config
from bot.filters.is_admin import IsAdmin

router = Router(name="admin")
router.message.filter(IsAdmin())


def _webapp_url() -> str:
    """URL Mini App для текущего ngrok-домена."""
    base = config.webhook_base_url
    if ":8080" in base:
        base = base.replace(":8080", ":8000")
    return f"{base}/admin"


def _admin_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛠 Открыть админку",
                    web_app=WebAppInfo(url=_webapp_url()),
                )
            ]
        ]
    )


async def setup_admin_menu_button(bot: Bot, chat_id: int) -> None:
    """Устанавливает кнопку меню Mini App. Вызывать только для админа."""
    try:
        await bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonWebApp(
                text="🛠 Админка",
                web_app=WebAppInfo(url=_webapp_url()),
            ),
        )
        logger.info(f"Кнопка меню Mini App установлена для chat_id={chat_id}")
    except Exception as e:
        logger.warning(f"Не удалось установить кнопку меню: {e}")


async def clear_menu_button(bot: Bot, chat_id: int) -> None:
    """Сбрасывает кнопку меню на стандартную (для не-админов)."""
    try:
        await bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonDefault(),
        )
    except Exception:
        pass


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext, bot: Bot):
    await state.clear()

    # Переустанавливаем на случай, если слетела
    await setup_admin_menu_button(bot, message.chat.id)

    await message.answer(
        "🛠 <b>Админ-панель Brodobrey</b>\n\n"
        "Нажмите кнопку ниже или используйте кнопку меню "
        "(слева от поля ввода) для открытия админки.",
        reply_markup=_admin_inline_kb(),
    )