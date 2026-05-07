from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from locales.i18n import LANGUAGES, get_t


def get_lang_kb():
    # Робимо великі кнопки по 2 у ряд, щоб текст не обрізався
    buttons = []
    for code, data in LANGUAGES.items():
        buttons.append(InlineKeyboardButton(text=data['lang_name'], callback_data=f"set_lang:{code}"))

    # Розбиваємо список кнопок на підсписки по 2 штуки
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)



def get_start_process_kb(lang):
    t = LANGUAGES.get(lang, LANGUAGES['en'])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['btn_start_run'], callback_data="run_upscale")]
    ])


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from locales.i18n import LANGUAGES, get_t

# ... (get_lang_kb залишається як був) ...

def get_main_menu(lang):
    t = LANGUAGES.get(lang, LANGUAGES['en'])
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t['btn_process'])],
        [KeyboardButton(text=t['btn_profile']), KeyboardButton(text=t['btn_sub'])],
        [KeyboardButton(text=t['btn_lang'])] # Нова кнопка мови
    ], resize_keyboard=True)

def get_sub_kb(lang):
    t = LANGUAGES.get(lang, LANGUAGES['en'])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['sub_1'], callback_data="buy:1")],
        [InlineKeyboardButton(text=t['sub_3'], callback_data="buy:3")],
        [InlineKeyboardButton(text=t['sub_6'], callback_data="buy:6")],
        [InlineKeyboardButton(text=t['sub_12'], callback_data="buy:12")]
    ])