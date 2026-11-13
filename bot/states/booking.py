"""FSM-состояния записи."""
from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    choosing_service = State()
    choosing_barber = State()
    choosing_date = State()
    choosing_time = State()
    entering_name = State()
    entering_phone = State()
    choosing_payment = State()
    confirming = State()