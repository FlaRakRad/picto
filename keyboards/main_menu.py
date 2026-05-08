from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from locales.i18n import LANGUAGES, get_t

def get_start_process_kb(lang):
    t = LANGUAGES.get(lang, LANGUAGES['en'])
    # ВАЖЛИВО: callback_data має бути точно "run_upscale"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['btn_start_run'], callback_data="run_upscale")]
    ])

def get_lang_kb():
    buttons = []
    for code, data in LANGUAGES.items():
        buttons.append(InlineKeyboardButton(text=data['lang_name'], callback_data=f"set_lang:{code}"))
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_main_menu(lang):
    t = LANGUAGES.get(lang, LANGUAGES['en'])
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t['btn_process'])],
        [KeyboardButton(text=t['btn_profile']), KeyboardButton(text=t['btn_sub'])],
        [KeyboardButton(text=t['btn_lang'])]
    ], resize_keyboard=True)