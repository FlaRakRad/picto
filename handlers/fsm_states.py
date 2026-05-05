from aiogram.fsm.state import StatesGroup, State

class ProcessState(StatesGroup):
    ready_to_start = State()