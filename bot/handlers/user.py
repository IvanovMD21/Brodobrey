"""Клиентские хендлеры: /start, меню, запись, мои записи."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import config
from bot.db import crud
from bot.db.models import Payment, Service
from bot.keyboards import user_kb as ukb
from bot.keyboards.calendar_kb import calendar_kb, times_kb
from bot.services import booking_service as bs
from bot.services import notify_service as ns
from bot.states.booking import BookingStates
from bot.utils.telegram_safe import safe_answer, safe_edit_text, safe_replace_message

router = Router(name="user")


# ─── /start ───────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, db_user, session: AsyncSession, bot: Bot
):
    await state.clear()

    is_admin = message.from_user.id == config.admin_id

    # Кнопка меню: админу — Mini App, клиентам — стандартная
    from bot.handlers.admin import setup_admin_menu_button, clear_menu_button
    if is_admin:
        await setup_admin_menu_button(bot, message.chat.id)
    else:
        await clear_menu_button(bot, message.chat.id)

    if db_user is None:
        await message.answer(
            "👋 Добро пожаловать в барбершоп <b>Brodobrey</b>!\n\n"
            "Для начала работы с ботом поделитесь, пожалуйста, вашим именем и телефоном.\n\n"
            "Введите ваше <b>имя</b>:",
        )
        await state.set_state(BookingStates.entering_name)
        return

    if db_user.is_blocked:
        await message.answer("🚫 Ваш доступ к боту заблокирован.")
        return

    await message.answer(
        f"👋 Здравствуйте, <b>{db_user.name}</b>!\n\n"
        "Выберите действие:",
        reply_markup=ukb.main_menu_kb(),
    )

# ─── Регистрация: имя ─────────────────────────────────────
@router.message(BookingStates.entering_name, F.text)
async def reg_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Пожалуйста, введите корректное имя (от 2 символов).")
        return
    await state.update_data(reg_name=name)
    await message.answer(
        "Отлично! Теперь введите ваш <b>номер телефона</b> "
        "(например: +7 999 123-45-67):"
    )
    await state.set_state(BookingStates.entering_phone)


@router.message(BookingStates.entering_phone, F.text)
async def reg_phone(
    message: Message, state: FSMContext, session: AsyncSession, db_user
):
    phone_raw = message.text.strip()
    phone = "".join(ch for ch in phone_raw if ch.isdigit() or ch == "+")

    if len(phone) < 10:
        await message.answer("Номер слишком короткий. Попробуйте снова.")
        return

    existing = await crud.get_user_by_phone(session, phone)
    if existing and existing.tg_id != message.from_user.id:
        await message.answer(
            "⚠️ Этот номер телефона уже привязан к другому аккаунту.\n\n"
            "Если это ваш номер — обратитесь к администратору."
        )
        return

    data = await state.get_data()
    name = data.get("reg_name", "Клиент")

    if db_user is not None:
        db_user.name = name
        db_user.phone = phone
        await session.commit()
        user = db_user
    else:
        user = await crud.create_user(session, message.from_user.id, name, phone)

    await state.clear()
    await message.answer(
        f"✅ Спасибо, <b>{user.name}</b>! Регистрация завершена.\n\n"
        "Выберите действие:",
        reply_markup=ukb.main_menu_kb(),
    )


# ─── Меню ─────────────────────────────────────────────────
@router.callback_query(F.data == "menu:back")
async def menu_back(call: CallbackQuery, state: FSMContext, db_user):
    await state.clear()
    if db_user is None:
        await safe_replace_message(call, "Пожалуйста, начните с /start")
        await safe_answer(call)
        return
    await safe_replace_message(call,
        f"👋 Здравствуйте, <b>{db_user.name}</b>!\n\nВыберите действие:",
        reply_markup=ukb.main_menu_kb(),
    )
    await safe_answer(call)


@router.callback_query(F.data == "menu:price")
async def menu_price(call: CallbackQuery, session: AsyncSession):
    services = await crud.get_active_services(session)
    text = "💰 <b>Прайс-лист</b>\n\n"
    for s in services:
        text += f"• {s.name} — <b>{s.price}₽</b> ({s.duration_min} мин)\n"
    await safe_replace_message(call, text, reply_markup=ukb.main_menu_kb())
    await safe_answer(call)


@router.callback_query(F.data == "menu:contacts")
async def menu_contacts(call: CallbackQuery):
    await safe_replace_message(call,
        "📍 <b>Brodobrey</b>\n\n"
        "Санкт-Петербург, ул. Ленина 7\n"
        "🕐 Ежедневно с 10:00 до 22:00\n"
        "🥗 Обед: 14:00–15:00",
        reply_markup=ukb.main_menu_kb(),
    )
    await safe_answer(call)


@router.callback_query(F.data == "menu:faq")
async def menu_faq(call: CallbackQuery):
    text = (
        "❓ <b>Часто задаваемые вопросы</b>\n\n"
        "<b>Как записаться?</b>\n"
        "Нажмите «📅 Записаться», выберите услугу, барбера, дату и время.\n\n"
        "<b>Как отменить запись?</b>\n"
        "«📖 Мои записи» → выберите запись → «❌ Отменить».\n\n"
        "<b>Способы оплаты:</b>\n"
        "• Предоплата через ЮKassa\n"
        "• Наличными на месте\n\n"
        "<b>Адрес:</b>\n"
        "Санкт-Петербург, ул. Ленина 7"
    )
    await safe_replace_message(call, text, reply_markup=ukb.main_menu_kb())
    await safe_answer(call)


# ─── Запись: услуга ───────────────────────────────────────
@router.callback_query(F.data == "menu:book")
async def book_start(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    services = await crud.get_active_services(session)
    await state.clear()
    await safe_replace_message(call,
        "✂️ <b>Выберите услугу:</b>",
        reply_markup=ukb.services_kb(list(services)),
    )
    await state.set_state(BookingStates.choosing_service)
    await safe_answer(call)


@router.callback_query(BookingStates.choosing_service, F.data.startswith("book:service:"))
async def book_service(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
):
    service_id = int(call.data.split(":", 2)[2])
    service = await crud.get_service(session, service_id)
    if not service:
        await safe_answer(call, "Услуга не найдена", show_alert=True)
        return

    await state.update_data(service_id=service.id)
    barbers = await crud.get_active_barbers(session)
    await safe_replace_message(call,
        f"✂️ Услуга: <b>{service.name}</b> ({service.price}₽)\n\n"
        "💈 <b>Выберите барбера:</b>",
        reply_markup=ukb.barbers_kb(list(barbers)),
    )
    await state.set_state(BookingStates.choosing_barber)
    await safe_answer(call)


@router.callback_query(F.data == "book:back_to_services")
async def back_to_services(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    services = await crud.get_active_services(session)
    await safe_replace_message(call,
        "✂️ <b>Выберите услугу:</b>",
        reply_markup=ukb.services_kb(list(services)),
    )
    await state.set_state(BookingStates.choosing_service)
    await safe_answer(call)


# ─── Запись: барбер ───────────────────────────────────────
@router.callback_query(BookingStates.choosing_barber, F.data.startswith("book:barber:"))
async def book_barber(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    value = call.data.split(":", 2)[2]
    if value == "any":
        await state.update_data(barber_id=None, barber_any=True)
        barber_label = "🎲 Любой свободный"
    else:
        barber_id = int(value)
        barber = await crud.get_barber(session, barber_id)
        if not barber:
            await safe_answer(call, "Барбер не найден", show_alert=True)
            return
        await state.update_data(barber_id=barber_id, barber_any=False)
        barber_label = f"{barber.name} («{barber.nickname}»)"

    await safe_replace_message(call,
        f"💈 Барбер: <b>{barber_label}</b>\n\n"
        "📅 <b>Выберите дату:</b>",
        reply_markup=calendar_kb(14),
    )
    await state.set_state(BookingStates.choosing_date)
    await safe_answer(call)


@router.callback_query(F.data == "book:back_to_barbers")
async def back_to_barbers(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    barbers = await crud.get_active_barbers(session)
    await safe_replace_message(call,
        "💈 <b>Выберите барбера:</b>",
        reply_markup=ukb.barbers_kb(list(barbers)),
    )
    await state.set_state(BookingStates.choosing_barber)
    await safe_answer(call)


# ─── Запись: дата ─────────────────────────────────────────
@router.callback_query(BookingStates.choosing_date, F.data.startswith("book:date:"))
async def book_date(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    day_str = call.data.split(":", 2)[2]
    day = date.fromisoformat(day_str)
    data = await state.get_data()
    service = await crud.get_service(session, data.get("service_id"))
    if not service:
        await safe_answer(call, "Услуга не найдена. Начните заново.", show_alert=True)
        await state.clear()
        return

    slots_map = None
    if data.get("barber_any"):
        slots_map = await bs.get_free_slots_any_barber(session, service, day)
        slots = list(slots_map.keys())
    else:
        barber_id = data.get("barber_id")
        if not barber_id:
            await safe_answer(call, "Барбер не выбран. Начните заново.", show_alert=True)
            await state.clear()
            return
        slots = await bs.get_free_slots(session, barber_id, service, day)

    await state.update_data(date=day_str, slots_map=slots_map)

    if not slots:
        await safe_replace_message(call,
            f"😔 На {day.strftime('%d.%m.%Y')} свободных слотов нет.\n\n"
            "Хотите встать в лист ожидания?",
            reply_markup=times_kb([]),
        )
        await state.set_state(BookingStates.choosing_time)
        await safe_answer(call)
        return

    await safe_replace_message(call,
        f"📅 Дата: <b>{day.strftime('%d.%m.%Y')}</b>\n\n"
        "🕐 <b>Выберите время:</b>",
        reply_markup=times_kb(slots),
    )
    await state.set_state(BookingStates.choosing_time)
    await safe_answer(call)


@router.callback_query(F.data == "book:back_to_dates")
async def back_to_dates(call: CallbackQuery, state: FSMContext):
    await safe_replace_message(call,
        "📅 <b>Выберите дату:</b>",
        reply_markup=calendar_kb(14),
    )
    await state.set_state(BookingStates.choosing_date)
    await safe_answer(call)


# ─── Запись: время ────────────────────────────────────────
@router.callback_query(BookingStates.choosing_time, F.data.startswith("book:time:"))
async def book_time(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    slot = call.data.split(":", 2)[2]
    data = await state.get_data()

    day_str = data.get("date")
    service_id = data.get("service_id")
    if not day_str or not service_id:
        await safe_answer(call, "Сессия истекла. Начните заново.", show_alert=True)
        await state.clear()
        return

    day = date.fromisoformat(day_str)
    service = await crud.get_service(session, service_id)
    if not service:
        await safe_answer(call, "Услуга не найдена. Начните заново.", show_alert=True)
        await state.clear()
        return

    if data.get("barber_any"):
        slots_map = data.get("slots_map") or {}
        barber_id = slots_map.get(slot)
        if not barber_id:
            slots_map = await bs.get_free_slots_any_barber(session, service, day)
            barber_id = slots_map.get(slot)
        if not barber_id:
            await safe_answer(call, "😔 Этот слот уже занят. Выберите другой.", show_alert=True)
            return
        await state.update_data(barber_id=barber_id)
    else:
        barber_id = data.get("barber_id")
        if not barber_id:
            await safe_answer(call, "Барбер не выбран. Начните заново.", show_alert=True)
            await state.clear()
            return

    start_dt = bs.slot_to_datetime(day, slot)

    if not await bs.is_slot_still_free(session, barber_id, service, start_dt):
        await safe_answer(call, "😔 Этот слот только что заняли. Выберите другой.", show_alert=True)
        return

    await state.update_data(slot=slot)
    await safe_replace_message(call,
        "💳 <b>Выберите способ оплаты:</b>",
        reply_markup=ukb.payment_method_kb(),
    )
    await state.set_state(BookingStates.choosing_payment)
    await safe_answer(call)


@router.callback_query(BookingStates.choosing_time, F.data == "book:waitlist")
async def book_waitlist(call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user):
    if db_user is None:
        await safe_answer(call, "Сначала зарегистрируйтесь через /start", show_alert=True)
        return
    data = await state.get_data()
    day_str = data.get("date")
    service_id = data.get("service_id")
    if not day_str or not service_id:
        await safe_answer(call, "Сессия истекла. Начните заново.", show_alert=True)
        await state.clear()
        return
    day = date.fromisoformat(day_str)
    await crud.add_to_waitlist(session, db_user.id, service_id, day)

    await safe_replace_message(call,
        "⏳ Вы добавлены в <b>лист ожидания</b>.\n\n"
        "Если освободится слот на эту дату — мы вам сообщим.",
        reply_markup=ukb.main_menu_kb(),
    )
    await ns.notify_admin(
        call.bot,
        f"⏳ Новая заявка в лист ожидания:\n"
        f"👤 {db_user.name} ({db_user.phone})\n"
        f"📅 {day.strftime('%d.%m.%Y')}"
    )
    await state.clear()
    await safe_answer(call)


# ─── Запись: способ оплаты ────────────────────────────────
@router.callback_query(BookingStates.choosing_payment, F.data.startswith("pay:"))
async def book_payment(
    call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user
):
    if db_user is None:
        await safe_answer(call, "Сначала зарегистрируйтесь через /start", show_alert=True)
        return

    method = call.data.split(":", 1)[1]
    data = await state.get_data()
    day_str = data.get("date")
    slot = data.get("slot")
    service_id = data.get("service_id")
    barber_id = data.get("barber_id")

    if not all([day_str, slot, service_id, barber_id]):
        await safe_answer(call, "Сессия истекла. Начните заново.", show_alert=True)
        await state.clear()
        return

    day = date.fromisoformat(day_str)
    start_dt = bs.slot_to_datetime(day, slot)
    service = await crud.get_service(session, service_id)
    end_dt = start_dt + timedelta(minutes=service.duration_min)
    barber = await crud.get_barber(session, barber_id)

    if not await bs.is_slot_still_free(session, barber_id, service, start_dt):
        await safe_answer(call, "😔 Слот заняли. Начните заново.", show_alert=True)
        await state.clear()
        await safe_replace_message(call,
            "Слот заняли, попробуйте снова.",
            reply_markup=ukb.main_menu_kb(),
        )
        return

    appt = await crud.create_appointment(
        session,
        user_id=db_user.id,
        barber_id=barber_id,
        service_id=service.id,
        start=start_dt,
        end=end_dt,
        payment_method=method,
    )

    if method == "cash":
        await safe_replace_message(call,
            f"✅ <b>Вы записаны!</b>\n\n"
            f"💈 {barber.name}\n"
            f"✂️ {service.name} — {service.price}₽\n"
            f"🕐 {start_dt.strftime('%d.%m.%Y в %H:%M')}\n"
            f"💵 Оплата: наличными на месте\n\n"
            "За 24 часа и за 2 часа до визита придёт напоминание.",
            reply_markup=ukb.main_menu_kb(),
        )
        await ns.notify_new_booking(call.bot, appt)
        await state.clear()
        await safe_answer(call)
        return

    # ─── Предоплата через ЮKassa ──────────────────────────
    from bot.services import payment_service as ps

    payment = await crud.create_payment(session, appt.id, service.price)
    yk = await ps.create_payment(
        amount=service.price,
        description=f"Оплата услуги «{service.name}» в Brodobrey",
        metadata={"appointment_id": appt.id, "payment_id": payment.id},
    )

    if not yk or "confirmation" not in yk:
        await safe_replace_message(call,
            "⚠️ Не удалось создать платёж. Попробуйте позже или выберите оплату наличными.",
            reply_markup=ukb.main_menu_kb(),
        )
        await safe_answer(call)
        return

    payment.yookassa_id = yk.get("id")
    await session.commit()
    await crud.attach_payment_to_appointment(session, appt.id, payment.id)

    pay_url = yk["confirmation"]["confirmation_url"]
    await safe_replace_message(call,
        f"💳 <b>Предоплата</b>\n\n"
        f"✂️ {service.name} — {service.price}₽\n"
        f"💈 {barber.name}\n"
        f"🕐 {start_dt.strftime('%d.%m.%Y в %H:%M')}\n\n"
        f"Ссылка на оплату (действует 30 минут):\n{pay_url}\n\n"
        "После оплаты запись подтвердится автоматически.",
        reply_markup=ukb.main_menu_kb(),
    )
    await ns.notify_new_booking(call.bot, appt)
    await state.clear()
    await safe_answer(call)


# ─── Мои записи ───────────────────────────────────────────
def _build_appt_items(appts) -> list[dict]:
    items = []
    for a in appts:
        dt = a.datetime_start.strftime("%d.%m %H:%M")
        service_name = a.service.name if a.service else "услуга"
        items.append({"id": a.id, "label": f"📌 {dt} — {service_name}"})
    return items


@router.callback_query(F.data == "menu:my")
async def my_appointments(call: CallbackQuery, session: AsyncSession, db_user):
    if db_user is None:
        await safe_answer(call, "Сначала /start", show_alert=True)
        return

    appts = await crud.get_user_appointments(session, db_user.id)
    if not appts:
        await safe_replace_message(call,
            "📖 У вас пока нет активных записей.",
            reply_markup=ukb.main_menu_kb(),
        )
        await safe_answer(call)
        return

    await safe_replace_message(call,
        "📖 <b>Ваши активные записи:</b>",
        reply_markup=ukb.my_appointments_kb(_build_appt_items(appts)),
    )
    await safe_answer(call)


@router.callback_query(F.data == "appt:back_to_list")
async def back_to_my_list(call: CallbackQuery, session: AsyncSession, db_user):
    if db_user is None:
        await safe_answer(call, "Сначала /start", show_alert=True)
        return
    appts = await crud.get_user_appointments(session, db_user.id)
    await safe_replace_message(call,
        "📖 <b>Ваши активные записи:</b>",
        reply_markup=ukb.my_appointments_kb(_build_appt_items(appts)),
    )
    await safe_answer(call)


@router.callback_query(F.data.startswith("appt:"))
async def appt_detail(call: CallbackQuery, session: AsyncSession, db_user):
    if db_user is None:
        await safe_answer(call, "Сначала /start", show_alert=True)
        return

    parts = call.data.split(":", 2)
    if len(parts) < 2:
        await safe_answer(call)
        return

    if parts[1] == "pay" and len(parts) >= 3:
        await _appt_pay(call, session, int(parts[2]))
        return
    if parts[1] == "cancel" and len(parts) >= 3:
        await _appt_cancel(call, session, int(parts[2]))
        return
    if parts[1] == "reschedule" and len(parts) >= 3:
        await _appt_reschedule(call)
        return

    try:
        appt_id = int(parts[1])
    except ValueError:
        await safe_answer(call)
        return

    appt = await crud.get_appointment(session, appt_id)
    if not appt or appt.user_id != db_user.id:
        await safe_answer(call, "Запись не найдена", show_alert=True)
        return

    can_pay = appt.payment_method == "prepaid" and appt.status == "pending"
    pay_info = (
        "💵 Наличными на месте"
        if appt.payment_method == "cash"
        else ("💳 Оплачено" if appt.status == "confirmed" else "💳 Ожидает оплаты")
    )

    await safe_replace_message(call,
        f"📌 <b>Запись #{appt.id}</b>\n\n"
        f"✂️ {appt.service.name} — {appt.service.price}₽\n"
        f"💈 {appt.barber.name} («{appt.barber.nickname}»)\n"
        f"🕐 {appt.datetime_start.strftime('%d.%m.%Y в %H:%M')}\n"
        f"{pay_info}",
        reply_markup=ukb.appointment_actions_kb(appt.id, can_pay),
    )
    await safe_answer(call)


async def _appt_pay(call: CallbackQuery, session: AsyncSession, appt_id: int):
    from bot.services import payment_service as ps

    appt = await crud.get_appointment(session, appt_id)
    if not appt or appt.status != "pending":
        await safe_answer(call, "Запись уже не требует оплаты", show_alert=True)
        return

    payment = await crud.create_payment(session, appt.id, appt.service.price)
    yk = await ps.create_payment(
        amount=appt.service.price,
        description=f"Оплата «{appt.service.name}»",
        metadata={"appointment_id": appt.id, "payment_id": payment.id},
    )
    if not yk or "confirmation" not in yk:
        await safe_answer(call, "Ошибка создания платежа", show_alert=True)
        return

    payment.yookassa_id = yk["id"]
    await session.commit()
    await crud.attach_payment_to_appointment(session, appt.id, payment.id)

    await safe_replace_message(call,
        f"💳 Ссылка на оплату:\n{yk['confirmation']['confirmation_url']}",
        reply_markup=ukb.main_menu_kb(),
    )
    await safe_answer(call)


async def _appt_cancel(call: CallbackQuery, session: AsyncSession, appt_id: int):
    from bot.services import payment_service as ps

    appt = await crud.get_appointment(session, appt_id)
    if not appt:
        await safe_answer(call, "Не найдено", show_alert=True)
        return

    refund_ok = False
    refund_data = None
    refund_amount = 0

    if appt.payment_id:
        payment = await session.get(Payment, appt.payment_id)
        if payment and payment.status == "succeeded" and payment.yookassa_id:
            refund_data = await ps.create_refund(payment.yookassa_id, payment.amount)
            if refund_data:
                await crud.update_payment_status(session, payment.id, "refunded")
                refund_ok = True
                refund_amount = payment.amount
                await ns.notify_refund(call.bot, appt, payment.amount)

    await crud.cancel_appointment(session, appt_id)
    await ns.notify_cancel(call.bot, appt, by_admin=False)

    await safe_replace_message(call,
        "❌ <b>Запись отменена.</b>",
        reply_markup=ukb.main_menu_kb(),
    )

    if refund_ok:
        await ns.notify_refund_to_client(
            call.bot, appt, refund_amount, refund_data
        )

    await safe_answer(call)


async def _appt_reschedule(call: CallbackQuery):
    await safe_replace_message(call,
        "🔄 Для переноса: отмените текущую запись и создайте новую.\n\n"
        "Нажмите «📅 Записаться» в меню.",
        reply_markup=ukb.main_menu_kb(),
    )
    await safe_answer(call)

