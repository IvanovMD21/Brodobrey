"""Планировщик: напоминания и автоотмена неоплаченных."""
from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from bot.config import config
from bot.db import crud
from bot.db.session import async_session
from bot.services import notify_service as ns


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    scheduler.add_job(
        send_reminders_24h, "interval", minutes=15, args=[bot],
        id="reminders_24h", replace_existing=True,
    )
    scheduler.add_job(
        send_reminders_2h, "interval", minutes=10, args=[bot],
        id="reminders_2h", replace_existing=True,
    )
    scheduler.add_job(
        cancel_unpaid, "interval", minutes=5, args=[bot],
        id="cancel_unpaid", replace_existing=True,
    )
    scheduler.add_job(
        mark_completed, "interval", hours=1,
        id="mark_completed", replace_existing=True,
    )
    return scheduler


async def send_reminders_24h(bot: Bot) -> None:
    now = datetime.utcnow()
    target = now + timedelta(hours=24)
    window_from = target - timedelta(minutes=15)
    window_to = target + timedelta(minutes=15)

    async with async_session() as session:
        appts = await crud.get_reminder_candidates(
            session, window_from, window_to, "reminder_24_sent"
        )
        for a in appts:
            try:
                await bot.send_message(
                    a.user.tg_id,
                    (
                        "🔔 <b>Напоминание о визите</b>\n\n"
                        f"Завтра в {a.datetime_start.strftime('%H:%M')}\n"
                        f"✂️ {a.service.name}\n"
                        f"💈 {a.barber.name}\n"
                        f"📍 ул. Ленина 7"
                    ),
                )
            except Exception as e:
                logger.warning(f"Напоминание 24ч не отправлено: {e}")
            await crud.set_reminder_flag(session, a.id, "reminder_24_sent")


async def send_reminders_2h(bot: Bot) -> None:
    now = datetime.utcnow()
    target = now + timedelta(hours=2)
    window_from = target - timedelta(minutes=10)
    window_to = target + timedelta(minutes=10)

    async with async_session() as session:
        appts = await crud.get_reminder_candidates(
            session, window_from, window_to, "reminder_2_sent"
        )
        for a in appts:
            try:
                await bot.send_message(
                    a.user.tg_id,
                    (
                        "⏰ <b>Скоро визит!</b>\n\n"
                        f"Сегодня в {a.datetime_start.strftime('%H:%M')}\n"
                        f"💈 {a.barber.name}\n"
                        f"📍 ул. Ленина 7"
                    ),
                )
            except Exception as e:
                logger.warning(f"Напоминание 2ч не отправлено: {e}")
            await crud.set_reminder_flag(session, a.id, "reminder_2_sent")


async def cancel_unpaid(bot: Bot) -> None:
    """Отмена неоплаченных prepaid-записей за N минут до старта."""
    now = datetime.utcnow()
    threshold = now + timedelta(minutes=config.cancel_unpaid_before_min)

    async with async_session() as session:
        # Найти pending prepaid записи, у которых старт < threshold
        from sqlalchemy import select, and_
        from bot.db.models import Appointment
        res = await session.execute(
            select(Appointment).where(
                and_(
                    Appointment.status == "pending",
                    Appointment.payment_method == "prepaid",
                    Appointment.datetime_start <= threshold,
                )
            )
        )
        appts = res.scalars().all()

        for a in appts:
            await crud.cancel_appointment(session, a.id)
            try:
                await bot.send_message(
                    a.user.tg_id,
                    (
                        "❌ <b>Запись отменена</b>\n\n"
                        "Оплата не поступила вовремя. Слот освобождён.\n"
                        "Вы можете записаться снова через /start"
                    ),
                )
            except Exception as e:
                logger.warning(f"Не удалось уведомить об отмене: {e}")
            await ns.notify_cancel(bot, a, by_admin=False)


async def mark_completed() -> None:
    async with async_session() as session:
        count = await crud.mark_completed_old(session)
        if count:
            logger.info(f"Помечено завершённых записей: {count}")