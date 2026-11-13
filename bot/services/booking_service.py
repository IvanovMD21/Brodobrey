"""Логика расчёта слотов и работы с записями."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import config
from bot.db import crud
from bot.db.models import Appointment, Barber, Service


def _time_ranges_for_day() -> list[tuple[time, time]]:
    """Рабочие интервалы с учётом обеда."""
    return [
        (config.work_start, config.lunch_start),
        (config.lunch_end, config.work_end),
    ]


def _overlaps(
    start1: datetime, end1: datetime, start2: datetime, end2: datetime
) -> bool:
    return start1 < end2 and start2 < end1


async def get_free_slots(
    session: AsyncSession,
    barber_id: int,
    service: Service,
    day: date,
) -> list[str]:
    """Список свободных стартовых времён 'HH:MM' для барбера и услуги."""
    busy = await crud.get_busy_slots(session, barber_id, day)
    busy_intervals = [(a.datetime_start, a.datetime_end) for a in busy]

    slots: list[str] = []
    step = timedelta(minutes=config.slot_step_min)
    duration = timedelta(minutes=service.duration_min)

    for r_start, r_end in _time_ranges_for_day():
        cur = datetime.combine(day, r_start)
        end_limit = datetime.combine(day, r_end)
        while cur + duration <= end_limit:
            cand_end = cur + duration
            if not any(
                _overlaps(cur, cand_end, bs, be) for bs, be in busy_intervals
            ):
                slots.append(cur.strftime("%H:%M"))
            cur += step

    return sorted(set(slots))


async def get_free_slots_any_barber(
    session: AsyncSession, service: Service, day: date
) -> dict[str, int]:
    """
    Возвращает {'HH:MM': barber_id} — первый свободный барбер для каждого слота.
    """
    barbers = await crud.get_active_barbers(session)
    result: dict[str, int] = {}
    for b in barbers:
        for slot in await get_free_slots(session, b.id, service, day):
            result.setdefault(slot, b.id)
    return dict(sorted(result.items()))


def slot_to_datetime(day: date, slot: str) -> datetime:
    """
    Преобразует 'HH:MM' в datetime для указанной даты.
    Устойчив к мусорным значениям — бросает ValueError с понятным текстом.
    """
    if not isinstance(slot, str) or ":" not in slot:
        raise ValueError(f"Некорректный формат слота: {slot!r}")
    parts = slot.split(":")
    if len(parts) != 2:
        raise ValueError(f"Некорректный формат слота: {slot!r}")
    hh, mm = map(int, parts)
    return datetime.combine(day, time(hh, mm))


async def is_slot_still_free(
    session: AsyncSession,
    barber_id: int,
    service: Service,
    start: datetime,
) -> bool:
    """Проверка, что слот не заняли за время FSM."""
    day = start.date()
    slots = await get_free_slots(session, barber_id, service, day)
    return start.strftime("%H:%M") in slots