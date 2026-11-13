"""FastAPI-сервер: админка Mini App + вебхуки ЮKassa."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from aiogram import Bot
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from telegram_init_data import parse, validate

from bot.config import config
from bot.db import crud
from bot.db.models import (
    Appointment,
    Barber,
    Payment,
    Service,
    User as UModel,
)
from bot.db.session import async_session
from bot.handlers.payment import process_yookassa_event

app = FastAPI(title="Brodobrey Admin MiniApp")


# ═══════════════════════════════════════════════════════════
#  АВТОРИЗАЦИЯ
# ═══════════════════════════════════════════════════════════
def verify_admin(x_init_data: Optional[str] = Header(None)) -> dict:
    """Проверяет подпись initData и что это ADMIN_ID."""
    if not x_init_data:
        raise HTTPException(401, "initData отсутствует")
    try:
        validate(x_init_data, config.bot_token)
        data = parse(x_init_data)
    except Exception as e:
        raise HTTPException(401, f"Неверная подпись: {e}")
    user = data.get("user")
    if not user or user.get("id") != config.admin_id:
        raise HTTPException(403, "Доступ только для админа")
    return data


# ═══════════════════════════════════════════════════════════
#  HTML-СТРАНИЦА АДМИНКИ
# ═══════════════════════════════════════════════════════════
@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    with open("webapp/static/admin.html", "r", encoding="utf-8") as f:
        return f.read()


# ═══════════════════════════════════════════════════════════
#  ВЕБХУК ЮKASSA
# ═══════════════════════════════════════════════════════════
@app.post("/yookassa/webhook")
async def yookassa_webhook(request: Request):
    """Приём уведомлений от ЮKassa."""
    try:
        data = await request.json()
    except Exception as e:
        return {"ok": False, "error": f"bad json: {e}"}

    bot = Bot(token=config.bot_token)
    try:
        result = await process_yookassa_event(data, bot)
        return result
    finally:
        await bot.session.close()


# ═══════════════════════════════════════════════════════════
#  ЗАПИСИ
# ═══════════════════════════════════════════════════════════
@app.get("/api/admin/appointments")
async def api_appointments(
    status: str = "all", _: dict = Depends(verify_admin)
):
    """status: all | today | pending | confirmed | completed | canceled"""
    now = datetime.utcnow()
    async with async_session() as session:
        stmt = (
            select(Appointment)
            .options(
                selectinload(Appointment.user),
                selectinload(Appointment.barber),
                selectinload(Appointment.service),
            )
            .order_by(Appointment.datetime_start.desc())
        )
        if status == "today":
            start = datetime.combine(date.today(), datetime.min.time())
            end = start + timedelta(days=1)
            stmt = stmt.where(
                and_(
                    Appointment.datetime_start >= start,
                    Appointment.datetime_start < end,
                )
            )
        elif status != "all":
            stmt = stmt.where(Appointment.status == status)
        else:
            stmt = stmt.where(
                and_(
                    Appointment.datetime_start >= now - timedelta(days=60),
                    Appointment.datetime_start <= now + timedelta(days=60),
                )
            )

        res = await session.execute(stmt.limit(200))
        appts = res.scalars().all()

    return {
        "count": len(appts),
        "appointments": [
            {
                "id": a.id,
                "datetime": a.datetime_start.strftime("%d.%m.%Y %H:%M"),
                "user": a.user.name if a.user else "—",
                "phone": a.user.phone if a.user else "—",
                "barber": a.barber.name if a.barber else "—",
                "service": a.service.name if a.service else "—",
                "price": a.service.price if a.service else 0,
                "status": a.status,
                "payment": a.payment_method,
            }
            for a in appts
        ],
    }


class CancelRequest(BaseModel):
    appointment_id: int


@app.post("/api/admin/appointment/cancel")
async def api_cancel_appointment(
    req: CancelRequest, _: dict = Depends(verify_admin)
):
    from bot.services import notify_service as ns
    from bot.services import payment_service as ps

    bot = Bot(token=config.bot_token)
    try:
        async with async_session() as session:
            appt = await crud.get_appointment(session, req.appointment_id)
            if not appt:
                raise HTTPException(404, "Запись не найдена")
            if appt.status not in ("pending", "confirmed"):
                raise HTTPException(400, "Эту запись нельзя отменить")

            # Возврат, если была оплата
            refund_ok = False
            refund_data = None
            refund_amount = 0

            if appt.payment_id:
                payment = await session.get(Payment, appt.payment_id)
                if (
                    payment
                    and payment.status == "succeeded"
                    and payment.yookassa_id
                ):
                    refund_data = await ps.create_refund(
                        payment.yookassa_id, payment.amount
                    )
                    if refund_data:
                        await crud.update_payment_status(
                            session, payment.id, "refunded"
                        )
                        refund_ok = True
                        refund_amount = payment.amount
                        await ns.notify_refund(bot, appt, payment.amount)

            await crud.cancel_appointment(session, req.appointment_id)
            await ns.notify_cancel(bot, appt, by_admin=True)

            # Уведомление клиенту об отмене
            try:
                await bot.send_message(
                    appt.user.tg_id,
                    f"❌ <b>Ваша запись отменена администратором</b>\n\n"
                    f"📌 Запись #{appt.id}\n"
                    f"✂️ {appt.service.name}\n"
                    f"🕐 {appt.datetime_start.strftime('%d.%m.%Y в %H:%M')}",
                )
            except Exception:
                pass

            # Уведомление клиенту о возврате
            if refund_ok:
                try:
                    await ns.notify_refund_to_client(
                        bot, appt, refund_amount, refund_data
                    )
                except Exception:
                    pass
    finally:
        await bot.session.close()

    return {"ok": True, "refunded": refund_ok}


# ═══════════════════════════════════════════════════════════
#  КЛИЕНТЫ
# ═══════════════════════════════════════════════════════════
@app.get("/api/admin/clients")
async def api_clients(_: dict = Depends(verify_admin)):
    async with async_session() as session:
        res = await session.execute(
            select(UModel).order_by(UModel.created_at.desc())
        )
        users = res.scalars().all()
    return {
        "count": len(users),
        "clients": [
            {
                "id": u.id,
                "name": u.name,
                "phone": u.phone,
                "is_blocked": u.is_blocked,
                "created_at": u.created_at.strftime("%d.%m.%Y"),
            }
            for u in users
        ],
    }


class BlockRequest(BaseModel):
    user_id: int


@app.post("/api/admin/client/toggle_block")
async def api_toggle_block(req: BlockRequest, _: dict = Depends(verify_admin)):
    async with async_session() as session:
        user = await session.get(UModel, req.user_id)
        if not user:
            raise HTTPException(404, "Клиент не найден")
        new_state = not user.is_blocked
        await crud.set_user_blocked(session, req.user_id, new_state)
    return {"ok": True, "is_blocked": new_state}


# ═══════════════════════════════════════════════════════════
#  БАРБЕРЫ
# ═══════════════════════════════════════════════════════════
@app.get("/api/admin/barbers")
async def api_barbers(_: dict = Depends(verify_admin)):
    async with async_session() as session:
        res = await session.execute(select(Barber).order_by(Barber.id))
        barbers = res.scalars().all()
    return {
        "barbers": [
            {
                "id": b.id,
                "name": b.name,
                "nickname": b.nickname,
                "is_active": b.is_active,
            }
            for b in barbers
        ],
    }


class AddBarberRequest(BaseModel):
    name: str
    nickname: str


@app.post("/api/admin/barber/add")
async def api_add_barber(req: AddBarberRequest, _: dict = Depends(verify_admin)):
    if len(req.name) < 2 or len(req.nickname) < 1:
        raise HTTPException(400, "Имя или ник слишком короткие")
    async with async_session() as session:
        b = await crud.add_barber(session, req.name, req.nickname)
    return {"ok": True, "id": b.id}


class ToggleBarberRequest(BaseModel):
    barber_id: int


@app.post("/api/admin/barber/toggle")
async def api_toggle_barber(
    req: ToggleBarberRequest, _: dict = Depends(verify_admin)
):
    async with async_session() as session:
        barber = await session.get(Barber, req.barber_id)
        if not barber:
            raise HTTPException(404, "Барбер не найден")
        barber.is_active = not barber.is_active
        await session.commit()
        return {"ok": True, "is_active": barber.is_active}


# ═══════════════════════════════════════════════════════════
#  ВЫРУЧКА
# ═══════════════════════════════════════════════════════════
@app.get("/api/admin/revenue")
async def api_revenue(_: dict = Depends(verify_admin)):
    now = datetime.utcnow()
    today_start = datetime.combine(date.today(), datetime.min.time())
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    async with async_session() as session:
        day = await crud.get_revenue(session, today_start, now)
        week = await crud.get_revenue(session, week_start, now)
        month = await crud.get_revenue(session, month_start, now)
        cnt_day = await crud.count_appointments(
            session, today_start, today_start + timedelta(days=1)
        )
    return {"today": day, "week": week, "month": month, "count_today": cnt_day}


# ═══════════════════════════════════════════════════════════
#  ПРАЙС
# ═══════════════════════════════════════════════════════════
@app.get("/api/admin/services")
async def api_services(_: dict = Depends(verify_admin)):
    async with async_session() as session:
        res = await session.execute(select(Service).order_by(Service.id))
        services = res.scalars().all()
    return {
        "services": [
            {
                "id": s.id,
                "name": s.name,
                "price": s.price,
                "duration_min": s.duration_min,
                "is_active": s.is_active,
            }
            for s in services
        ],
    }


class UpdatePriceRequest(BaseModel):
    service_id: int
    price: int


@app.post("/api/admin/service/price")
async def api_update_price(
    req: UpdatePriceRequest, _: dict = Depends(verify_admin)
):
    if req.price <= 0:
        raise HTTPException(400, "Цена должна быть больше 0")
    async with async_session() as session:
        await crud.update_service_price(session, req.service_id, req.price)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
#  ЛИСТ ОЖИДАНИЯ
# ═══════════════════════════════════════════════════════════
@app.get("/api/admin/waitlist")
async def api_waitlist(_: dict = Depends(verify_admin)):
    async with async_session() as session:
        entries = await crud.get_waitlist(session)
        user_ids = [w.user_id for w in entries]
        users_map = {}
        if user_ids:
            res = await session.execute(
                select(UModel).where(UModel.id.in_(user_ids))
            )
            users_map = {u.id: u for u in res.scalars().all()}
    return {
        "entries": [
            {
                "id": w.id,
                "user_name": users_map[w.user_id].name
                if w.user_id in users_map
                else "—",
                "user_phone": users_map[w.user_id].phone
                if w.user_id in users_map
                else "—",
                "preferred_date": w.preferred_date.strftime("%d.%m.%Y"),
            }
            for w in entries
        ],
    }


# ═══════════════════════════════════════════════════════════
#  HEALTHCHECK
# ═══════════════════════════════════════════════════════════
@app.get("/health")
async def health():
    return {"status": "ok"}