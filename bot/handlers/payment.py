"""Обработка вебхуков от ЮKassa."""
from __future__ import annotations

from aiogram import Bot
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.db import crud
from bot.db.models import Appointment
from bot.db.session import async_session
from bot.services import notify_service as ns


async def process_yookassa_event(data: dict, bot: Bot) -> dict:
    """
    Универсальная обработка вебхука ЮKassa.
    Принимает JSON как dict, возвращает dict для ответа.
    """
    event = data.get("event")
    obj = data.get("object", {})
    yk_id = obj.get("id")

    logger.info(f"ЮKassa webhook: event={event} id={yk_id}")

    try:
        async with async_session() as session:
            if event == "payment.succeeded":
                await _on_payment_succeeded(session, yk_id, obj, bot)
            elif event == "payment.canceled":
                await _on_payment_canceled(session, yk_id, bot)
            elif event == "refund.succeeded":
                logger.info(f"Возврат успешен: {yk_id}")
    except Exception as e:
        logger.exception(f"Ошибка обработки вебхука ЮKassa: {e}")

    return {"ok": True}


async def _load_appointment_with_relations(
    session, appointment_id: int
) -> Appointment | None:
    """Загружает запись с eager-загрузкой user/barber/service."""
    stmt = (
        select(Appointment)
        .options(
            selectinload(Appointment.user),
            selectinload(Appointment.barber),
            selectinload(Appointment.service),
        )
        .where(Appointment.id == appointment_id)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def _on_payment_succeeded(
    session, yk_id: str, obj: dict, bot: Bot
) -> None:
    payment = await crud.get_payment_by_yookassa(session, yk_id)
    if not payment:
        logger.warning(f"Платёж {yk_id} не найден в БД")
        return
    if payment.status == "succeeded":
        logger.info(f"Платёж {yk_id} уже обработан, пропускаем")
        return

    await crud.update_payment_status(session, payment.id, "succeeded")

    appt = await _load_appointment_with_relations(session, payment.appointment_id)
    if not appt:
        logger.warning(f"Запись {payment.appointment_id} не найдена")
        return

    appt.status = "confirmed"
    await session.commit()

    amount = payment.amount

    # Уведомление админу
    try:
        await ns.notify_payment_success(bot, appt, amount)
    except Exception as e:
        logger.warning(f"Не удалось уведомить админа об оплате: {e}")

    # Чек клиенту
    try:
        await bot.send_message(
            appt.user.tg_id,
            (
                "✅ <b>Оплата получена</b>\n\n"
                f"📌 Запись #{appt.id}\n"
                f"✂️ {appt.service.name}\n"
                f"💈 {appt.barber.name}\n"
                f"🕐 {appt.datetime_start.strftime('%d.%m.%Y в %H:%M')}\n"
                f"💵 Сумма: {amount}₽\n\n"
                "Ждём вас!"
            ),
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить чек клиенту: {e}")

    # Сохраняем текстовый «чек»
    try:
        await crud.create_receipt(
            session,
            payment_id=payment.id,
            user_id=appt.user_id,
            amount=amount,
            text=(
                f"Оплата {amount}₽ за {appt.service.name}, "
                f"{appt.datetime_start.strftime('%d.%m.%Y %H:%M')}"
            ),
        )
    except Exception as e:
        logger.warning(f"Не удалось сохранить чек в БД: {e}")

    logger.info(f"Платёж {yk_id} обработан: запись #{appt.id} подтверждена")


async def _on_payment_canceled(session, yk_id: str, bot: Bot) -> None:
    payment = await crud.get_payment_by_yookassa(session, yk_id)
    if not payment:
        return
    await crud.update_payment_status(session, payment.id, "canceled")
    logger.info(f"Платёж {yk_id} отменён")