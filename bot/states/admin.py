"""FSM-состояния админки."""
from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    entering_barber_name = State()
    entering_barber_nickname = State()
    entering_new_price = State()
    entering_waitlist_assign = State()