"""CRUD-функции для работы с БД."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional, Sequence

from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.db.models import (
    Appointment, Barber, Payment, Receipt, Service, User, Waitlist
)


# ─── USERS ────────────────────────────────────────────────
async def get_user_by_tg(session: AsyncSession, tg_id: int) -> Optional[User]:
    res = await session.execute(select(User).where(User.tg_id == tg_id))
    return res.scalar_one_or_none()


async def get_user_by_phone(session: AsyncSession, phone: str) -> Optional[User]:
    res = await session.execute(select(User).where(User.phone == phone))
    return res.scalar_one_or_none()


async def create_user(
    session: AsyncSession, tg_id: int, name: str, phone: str
) -> User:
    user = User(tg_id=tg_id, name=name, phone=phone)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def set_user_blocked(
    session: AsyncSession, user_id: int, blocked: bool
) -> None:
    await session.execute(
        update(User).where(User.id == user_id).values(is_blocked=blocked)
    )
    await session.commit()


async def get_all_users(session: AsyncSession) -> Sequence[User]:
    res = await session.execute(select(User).order_by(User.created_at.desc()))
    return res.scalars().all()


# ─── BARBERS ──────────────────────────────────────────────
async def get_active_barbers(session: AsyncSession) -> Sequence[Barber]:
    res = await session.execute(
        select(Barber).where(Barber.is_active.is_(True)).order_by(Barber.id)
    )
    return res.scalars().all()


async def get_all_barbers(session: AsyncSession) -> Sequence[Barber]:
    res = await session.execute(select(Barber).order_by(Barber.id))
    return res.scalars().all()


async def get_barber(session: AsyncSession, barber_id: int) -> Optional[Barber]:
    return await session.get(Barber, barber_id)


async def add_barber(
    session: AsyncSession, name: str, nickname: str
) -> Barber:
    b = Barber(name=name, nickname=nickname, is_active=True)
    session.add(b)
    await session.commit()
    await session.refresh(b)
    return b


async def deactivate_barber(session: AsyncSession, barber_id: int) -> None:
    await session.execute(
        update(Barber).where(Barber.id == barber_id).values(is_active=False)
    )
    await session.commit()


# ─── SERVICES ─────────────────────────────────────────────
async def get_active_services(session: AsyncSession) -> Sequence[Service]:
    res = await session.execute(
        select(Service).where(Service.is_active.is_(True)).order_by(Service.id)
    )
    return res.scalars().all()


async def get_service(session: AsyncSession, service_id: int) -> Optional[Service]:
    return await session.get(Service, service_id)


async def update_service_price(
    session: AsyncSession, service_id: int, price: int
) -> None:
    await session.execute(
        update(Service).where(Service.id == service_id).values(price=price)
    )
    await session.commit()


# ─── APPOINTMENTS ─────────────────────────────────────────
def _with_relations(stmt):
    """Eager-load user/barber/service, чтобы не ловить MissingGreenlet."""
    return stmt.options(
        selectinload(Appointment.user),
        selectinload(Appointment.barber),
        selectinload(Appointment.service),
    )


async def get_busy_slots(
    session: AsyncSession, barber_id: int, day: date
) -> Sequence[Appointment]:
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    res = await session.execute(
        select(Appointment).where(
            and_(
                Appointment.barber_id == barber_id,
                Appointment.datetime_start >= start,
                Appointment.datetime_start < end,
                Appointment.status.in_(["pending", "confirmed"]),
            )
        )
    )
    return res.scalars().all()


async def create_appointment(
    session: AsyncSession,
    user_id: int,
    barber_id: int,
    service_id: int,
    start: datetime,
    end: datetime,
    payment_method: str,
) -> Appointment:
    appt = Appointment(
        user_id=user_id,
        barber_id=barber_id,
        service_id=service_id,
        datetime_start=start,
        datetime_end=end,
        status="confirmed" if payment_method == "cash" else "pending",
        payment_method=payment_method,
    )
    session.add(appt)
    await session.commit()

    # Перечитываем с eager-загрузкой
    res = await session.execute(
        _with_relations(select(Appointment).where(Appointment.id == appt.id))
    )
    return res.scalar_one()


async def get_user_appointments(
    session: AsyncSession, user_id: int
) -> Sequence[Appointment]:
    stmt = (
        select(Appointment)
        .where(
            and_(
                Appointment.user_id == user_id,
                Appointment.status.in_(["pending", "confirmed"]),
            )
        )
        .order_by(Appointment.datetime_start)
    )
    res = await session.execute(_with_relations(stmt))
    return res.scalars().all()


async def get_appointment(
    session: AsyncSession, appt_id: int
) -> Optional[Appointment]:
    stmt = _with_relations(select(Appointment).where(Appointment.id == appt_id))
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def cancel_appointment(session: AsyncSession, appt_id: int) -> None:
    await session.execute(
        update(Appointment)
        .where(Appointment.id == appt_id)
        .values(status="canceled")
    )
    await session.commit()


async def mark_completed_old(session: AsyncSession) -> int:
    now = datetime.utcnow()
    res = await session.execute(
        update(Appointment)
        .where(
            and_(
                Appointment.datetime_end < now,
                Appointment.status.in_(["pending", "confirmed"]),
            )
        )
        .values(status="completed")
    )
    await session.commit()
    return res.rowcount or 0


async def get_appointments_for_period(
    session: AsyncSession, start: datetime, end: datetime
) -> Sequence[Appointment]:
    stmt = (
        select(Appointment)
        .where(
            and_(
                Appointment.datetime_start >= start,
                Appointment.datetime_start < end,
                Appointment.status.in_(["pending", "confirmed", "completed"]),
            )
        )
        .order_by(Appointment.datetime_start)
    )
    res = await session.execute(_with_relations(stmt))
    return res.scalars().all()


async def get_reminder_candidates(
    session: AsyncSession, from_dt: datetime, to_dt: datetime, flag_field: str
) -> Sequence[Appointment]:
    flag = getattr(Appointment, flag_field)
    stmt = select(Appointment).where(
        and_(
            Appointment.datetime_start >= from_dt,
            Appointment.datetime_start <= to_dt,
            Appointment.status.in_(["pending", "confirmed"]),
            flag.is_(False),
        )
    )
    res = await session.execute(_with_relations(stmt))
    return res.scalars().all()


async def set_reminder_flag(
    session: AsyncSession, appt_id: int, field: str
) -> None:
    await session.execute(
        update(Appointment).where(Appointment.id == appt_id).values(**{field: True})
    )
    await session.commit()


# ─── PAYMENTS ─────────────────────────────────────────────
async def create_payment(
    session: AsyncSession, appointment_id: int, amount: int
) -> Payment:
    p = Payment(appointment_id=appointment_id, amount=amount, status="pending")
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


async def attach_payment_to_appointment(
    session: AsyncSession, appt_id: int, payment_id: int
) -> None:
    await session.execute(
        update(Appointment)
        .where(Appointment.id == appt_id)
        .values(payment_id=payment_id)
    )
    await session.commit()


async def get_payment_by_yookassa(
    session: AsyncSession, yookassa_id: str
) -> Optional[Payment]:
    res = await session.execute(
        select(Payment).where(Payment.yookassa_id == yookassa_id)
    )
    return res.scalar_one_or_none()


async def update_payment_status(
    session: AsyncSession, payment_id: int, status: str
) -> None:
    await session.execute(
        update(Payment).where(Payment.id == payment_id).values(status=status)
    )
    await session.commit()


# ─── RECEIPTS ─────────────────────────────────────────────
async def create_receipt(
    session: AsyncSession,
    payment_id: int,
    user_id: int,
    amount: int,
    text: str,
) -> Receipt:
    r = Receipt(payment_id=payment_id, user_id=user_id, amount=amount, text=text)
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return r


async def get_all_receipts(session: AsyncSession) -> Sequence[Receipt]:
    res = await session.execute(
        select(Receipt).order_by(Receipt.created_at.desc())
    )
    return res.scalars().all()


# ─── WAITLIST ─────────────────────────────────────────────
async def add_to_waitlist(
    session: AsyncSession, user_id: int, service_id: int, preferred_date: date
) -> Waitlist:
    w = Waitlist(
        user_id=user_id, service_id=service_id, preferred_date=preferred_date
    )
    session.add(w)
    await session.commit()
    await session.refresh(w)
    return w


async def get_waitlist(session: AsyncSession) -> Sequence[Waitlist]:
    res = await session.execute(
        select(Waitlist)
        .where(Waitlist.status == "waiting")
        .order_by(Waitlist.created_at)
    )
    return res.scalars().all()


async def get_waitlist_for_date(
    session: AsyncSession, day: date
) -> Sequence[Waitlist]:
    res = await session.execute(
        select(Waitlist).where(
            and_(Waitlist.preferred_date == day, Waitlist.status == "waiting")
        )
    )
    return res.scalars().all()


async def update_waitlist_status(
    session: AsyncSession, wl_id: int, status: str
) -> None:
    await session.execute(
        update(Waitlist).where(Waitlist.id == wl_id).values(status=status)
    )
    await session.commit()


# ─── СТАТИСТИКА ───────────────────────────────────────────
async def get_revenue(session: AsyncSession, start: datetime, end: datetime) -> int:
    """Сумма успешных платежей за период. Плюс учитываем 'confirmed' prepaid-записи."""
    res = await session.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            and_(
                Payment.status == "succeeded",
                Payment.created_at >= start,
                Payment.created_at < end,
            )
        )
    )
    return int(res.scalar_one() or 0)


async def count_appointments(
    session: AsyncSession, start: datetime, end: datetime
) -> int:
    res = await session.execute(
        select(func.count(Appointment.id)).where(
            and_(
                Appointment.datetime_start >= start,
                Appointment.datetime_start < end,
                Appointment.status.in_(["pending", "confirmed", "completed"]),
            )
        )
    )
    return int(res.scalar_one() or 0)