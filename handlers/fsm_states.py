from aiogram.fsm.state import StatesGroup, State

class ProcessState(StatesGroup):
    waiting_for_photos = State() # Стан, коли бот чекає саме фото
    ready_to_start = State()     # Стан, коли пачка зібрана і чекає кнопки "Пуск"