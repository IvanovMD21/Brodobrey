"""Безопасные обёртки над Telegram API — глотают неважные ошибки."""
from __future__ import annotations

from typing import Any, Optional

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from loguru import logger


async def safe_edit_text(
    message: Message,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    **kwargs: Any,
) -> None:
    """edit_text, который не падает на 'message is not modified' и 'query is too old'."""
    try:
        await message.edit_text(text, reply_markup=reply_markup, **kwargs)
    except TelegramBadRequest as e:
        msg = str(e).lower()
        if "message is not modified" in msg:
            logger.debug("edit_text: message not modified (skipped)")
            return
        if "query is too old" in msg or "query id is invalid" in msg:
            logger.debug("edit_text: query too old (skipped)")
            return
        raise


async def safe_answer(
    call: CallbackQuery,
    text: Optional[str] = None,
    show_alert: bool = False,
) -> None:
    """call.answer, который не падает на устаревших callback'ах."""
    try:
        if text is not None:
            await call.answer(text, show_alert=show_alert)
        else:
            await call.answer()
    except TelegramBadRequest as e:
        msg = str(e).lower()
        if "query is too old" in msg or "query id is invalid" in msg:
            logger.debug("answer: query too old (skipped)")
            return
        raise


async def safe_replace_message(
    call: CallbackQuery,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    **kwargs: Any,
) -> None:
    """
    Удаляет сообщение, из которого пришёл callback, и отправляет новое вниз чата.

    Преимущества:
      - Новое сообщение всегда внизу чата.
      - Чат не засоряется — старое сообщение удаляется.
      - Не падает, если сообщение уже удалено или слишком старое.
    """
    chat_id = call.message.chat.id
    old_message_id = call.message.message_id
    bot = call.bot

    # 1. Пробуем удалить старое сообщение
    try:
        await bot.delete_message(chat_id=chat_id, message_id=old_message_id)
    except TelegramBadRequest as e:
        msg = str(e).lower()
        if "message can't be deleted" in msg or "message to delete not found" in msg:
            logger.debug(f"Не удалось удалить сообщение {old_message_id}: {msg}")
        else:
            logger.debug(f"delete_message: {msg}")

    # 2. Отправляем новое
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        **kwargs,
    )