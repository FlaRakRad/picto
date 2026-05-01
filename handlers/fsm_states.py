from aiogram.fsm.state import StatesGroup, State

class ProcessState(StatesGroup):
    choosing_resolution = State()
    entering_custom_res = State()
    choosing_wm = State()