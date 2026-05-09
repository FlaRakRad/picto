from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from locales.i18n import LANGUAGES, get_t


# --- КНОПКА ЗАПУСКУ ШІ ---
def get_start_process_kb(lang):
    t = LANGUAGES.get(lang, LANGUAGES['en'])
    # Ми використовуємо callback run_upscale, як і домовлялися для загального старту
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['btn_start_run'], callback_data="run_upscale")]
    ])


# --- ПЕРШОПОЧАТКОВИЙ ВИБІР МОВИ (Inline) ---
def get_lang_kb():
    buttons = []
    # Створюємо сітку мов 2 в ряд
    for code, data in LANGUAGES.items():
        buttons.append(InlineKeyboardButton(text=data['lang_name'], callback_data=f"set_lang:{code}"))

    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --- ГОЛОВНЕ МЕНЮ (Reply) ---
def get_main_menu(lang):
    t = LANGUAGES.get(lang, LANGUAGES['en'])
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t['btn_process'])],  # Велика кнопка обробки на всю ширину
            [KeyboardButton(text=t['btn_profile']), KeyboardButton(text=t['btn_sub'])],  # Профіль та гроші поруч
            [KeyboardButton(text=t['btn_support']), KeyboardButton(text=t['btn_feedback'])]  # Службові кнопки
        ],
        resize_keyboard=True,
        input_field_placeholder="Оберіть функцію PictoBot..."
    )


# --- МЕНЮ ПІДПИСКИ (Оплата) ---
def get_sub_kb(lang):
    t = LANGUAGES.get(lang, LANGUAGES['en'])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['sub_1'], callback_data="buy:1")],
        [InlineKeyboardButton(text=t['sub_3'], callback_data="buy:3")],
        [InlineKeyboardButton(text=t['sub_6'], callback_data="buy:6")],
        [InlineKeyboardButton(text=t['sub_12'], callback_data="buy:12")]
    ])