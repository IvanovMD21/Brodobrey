"""Уведомления клиенту и админу."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from aiogram import Bot
from loguru import logger

from bot.config import config
from bot.db.models import Appointment


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y в %H:%M")


async def notify_admin(bot: Bot, text: str) -> None:
    try:
        await bot.send_message(config.admin_id, text)
    except Exception as e:
        logger.warning(f"Не удалось уведомить админа: {e}")


async def notify_new_booking(bot: Bot, appt: Appointment) -> None:
    text = (
        "🆕 <b>Новая запись</b>\n\n"
        f"👤 {appt.user.name} ({appt.user.phone})\n"
        f"✂️ {appt.service.name} — {appt.service.price}₽\n"
        f"💈 {appt.barber.name} («{appt.barber.nickname}»)\n"
        f"🕐 {_fmt_dt(appt.datetime_start)}\n"
        f"💳 {'Предоплата' if appt.payment_method == 'prepaid' else 'Наличные'}"
    )
    await notify_admin(bot, text)


async def notify_cancel(bot: Bot, appt: Appointment, by_admin: bool = False) -> None:
    who = "админом" if by_admin else "клиентом"
    text = (
        f"❌ <b>Запись отменена {who}</b>\n\n"
        f"👤 {appt.user.name} ({appt.user.phone})\n"
        f"✂️ {appt.service.name}\n"
        f"💈 {appt.barber.name}\n"
        f"🕐 {_fmt_dt(appt.datetime_start)}"
    )
    await notify_admin(bot, text)


async def notify_payment_success(bot: Bot, appt: Appointment, amount: int) -> None:
    text = (
        "💰 <b>Оплата получена</b>\n\n"
        f"👤 {appt.user.name}\n"
        f"✂️ {appt.service.name}\n"
        f"🕐 {_fmt_dt(appt.datetime_start)}\n"
        f"💵 {amount}₽"
    )
    await notify_admin(bot, text)


async def notify_refund(bot: Bot, appt: Appointment, amount: int) -> None:
    """Уведомление админу о возврате."""
    text = (
        "↩️ <b>Возврат средств</b>\n\n"
        f"👤 {appt.user.name}\n"
        f"💵 {amount}₽\n"
        f"🕐 {_fmt_dt(appt.datetime_start)}"
    )
    await notify_admin(bot, text)


async def notify_refund_to_client(
    bot: Bot,
    appt: Appointment,
    amount: int,
    refund_data: Optional[dict] = None,
) -> None:
    """Уведомление клиенту об успешном возврате средств."""
    refund_id = (refund_data or {}).get("id", "—")
    refund_status = (refund_data or {}).get("status", "succeeded")

    # Определяем, куда вернутся средства
    method_info = ""
    if refund_data:
        rm = refund_data.get("refund_method") or {}
        if rm.get("type") == "card" and rm.get("card", {}).get("last4"):
            method_info = f" на карту •••• {rm['card']['last4']}"
        elif refund_data.get("payment_method"):
            pm_type = refund_data["payment_method"].get("type")
            if pm_type == "bank_card":
                card = refund_data["payment_method"].get("card", {})
                last4 = card.get("last4")
                if last4:
                    method_info = f" на карту •••• {last4}"
            elif pm_type == "yoo_money":
                method_info = " на кошелёк ЮMoney"
            elif pm_type == "sbp":
                method_info = " по СБП"

    if refund_status == "succeeded":
        title = "💳 <b>Возврат средств выполнен</b>"
        status_line = "✅ Возврат обработан успешно."
        eta_line = (
            "\n\n⏳ <b>Срок зачисления:</b>\n"
            "• Обычно 1–3 рабочих дня (зависит от банка)\n"
            "• До 30 дней в редких случаях"
        )
    elif refund_status == "pending":
        title = "💳 <b>Возврат средств запущен</b>"
        status_line = "⏳ Возврат в обработке."
        eta_line = "\n\n⏳ Обычно занимает 1–3 рабочих дня."
    else:
        title = "💳 <b>Возврат средств</b>"
        status_line = f"Статус: {refund_status}"
        eta_line = ""

    text = (
        f"{title}\n\n"
        f"📌 Запись #{appt.id}\n"
        f"✂️ {appt.service.name}\n"
        f"💈 {appt.barber.name}\n"
        f"🕐 {_fmt_dt(appt.datetime_start)}\n\n"
        f"💵 <b>Сумма возврата: {amount}₽</b>{method_info}\n"
        f"🆔 Возврат: <code>{refund_id}</code>\n\n"
        f"{status_line}"
        f"{eta_line}"
    )

    try:
        await bot.send_message(appt.user.tg_id, text)
        logger.info(f"Клиент {appt.user.tg_id} уведомлён о возврате {amount}₽")
    except Exception as e:
        logger.warning(f"Не удалось уведомить клиента о возврате: {e}")


async def notify_waitlist(bot: Bot, user_tg: int, slot: str, barber_name: str) -> None:
    try:
        await bot.send_message(
            user_tg,
            (
                "🎉 <b>Освободился слот!</b>\n\n"
                f"💈 {barber_name}\n"
                f"🕐 {slot}\n\n"
                "Запишитесь через /start → 📅 Записаться"
            ),
        )
    except Exception as e:
        logger.warning(f"Не удалось уведомить о слоте: {e}")