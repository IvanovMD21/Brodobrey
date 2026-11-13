"""Календарь на 14 дней вперёд."""
from __future__ import annotations

from datetime import date, timedelta

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


MONTHS_RU = [
    "янв", "фев", "мар", "апр", "май", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек",
]
WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def calendar_kb(days_ahead: int = 14) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    today = date.today()
    for i in range(days_ahead):
        d = today + timedelta(days=i)
        label = f"{WEEKDAYS_RU[d.weekday()]}, {d.day} {MONTHS_RU[d.month - 1]}"
        kb.button(text=label, callback_data=f"book:date:{d.isoformat()}")
    kb.button(text="⬅️ Назад", callback_data="book:back_to_barbers")
    kb.adjust(2)
    return kb.as_markup()


def times_kb(slots: list[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t in slots:
        kb.button(text=f"🕐 {t}", callback_data=f"book:time:{t}")
    kb.button(text="⏳ В лист ожидания", callback_data="book:waitlist")
    kb.button(text="⬅️ Назад", callback_data="book:back_to_dates")
    kb.adjust(3, 3, 3, 3, 3, 1, 1)
    return kb.as_markup()