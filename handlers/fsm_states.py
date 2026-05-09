from aiogram.fsm.state import StatesGroup, State

class ProcessState(StatesGroup):
    waiting_for_photos = State()
    ready_to_start = State()
    waiting_for_background = State()