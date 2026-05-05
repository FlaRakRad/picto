from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🖼 Обробка фото")],
            [KeyboardButton(text="📊 Мій профіль"), KeyboardButton(text="💎 Підписка")],
            [KeyboardButton(text="ℹ️ Допомога")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Оберіть дію..."
    )