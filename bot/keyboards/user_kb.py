"""Клавиатуры для клиента."""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db.models import Barber, Service


def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Записаться", callback_data="menu:book")
    kb.button(text="📖 Мои записи", callback_data="menu:my")
    kb.button(text="💰 Прайс", callback_data="menu:price")
    kb.button(text="📍 Контакты", callback_data="menu:contacts")
    kb.button(text="❓ FAQ", callback_data="menu:faq")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def services_kb(services: list[Service]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in services:
        kb.button(
            text=f"{s.name} — {s.price}₽ ({s.duration_min} мин)",
            callback_data=f"book:service:{s.id}",
        )
    kb.button(text="⬅️ Назад", callback_data="menu:back")
    kb.adjust(1)
    return kb.as_markup()


def barbers_kb(barbers: list[Barber]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for b in barbers:
        kb.button(
            text=f"{b.name} («{b.nickname}»)",
            callback_data=f"book:barber:{b.id}",
        )
    kb.button(text="🎲 Любой свободный", callback_data="book:barber:any")
    kb.button(text="⬅️ Назад", callback_data="book:back_to_services")
    kb.adjust(1)
    return kb.as_markup()


def payment_method_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Предоплата (ЮKassa)", callback_data="pay:prepaid")
    kb.button(text="💵 Наличными на месте", callback_data="pay:cash")
    kb.button(text="⬅️ Назад", callback_data="menu:back")
    kb.adjust(1)
    return kb.as_markup()


def my_appointments_kb(items: list[dict]) -> InlineKeyboardMarkup:
    """items: [{"id": int, "label": str}, ...]"""
    kb = InlineKeyboardBuilder()
    for item in items:
        kb.button(text=item["label"], callback_data=f"appt:{item['id']}")
    kb.button(text="⬅️ В меню", callback_data="menu:back")
    kb.adjust(1)
    return kb.as_markup()


def appointment_actions_kb(appt_id: int, can_pay: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if can_pay:
        kb.button(text="💳 Оплатить", callback_data=f"appt:pay:{appt_id}")
    kb.button(text="🔄 Перенести", callback_data=f"appt:reschedule:{appt_id}")
    kb.button(text="❌ Отменить", callback_data=f"appt:cancel:{appt_id}")
    kb.button(text="⬅️ Назад", callback_data="menu:my")
    kb.adjust(1)
    return kb.as_markup()