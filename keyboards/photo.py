from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from locales.i18n import get_t

def get_functions_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_t(lang, 'btn_upscaler'), callback_data="func:upscaler")],
        [InlineKeyboardButton(text=get_t(lang, 'btn_bgchanger'), callback_data="func:bgchanger")],
        [InlineKeyboardButton(text=get_t(lang, 'btn_mirror'), callback_data="func:mirror")]
    ])

def get_resolution_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="480p", callback_data="res:480"), InlineKeyboardButton(text="720p", callback_data="res:720")],
        [InlineKeyboardButton(text="1080p", callback_data="res:1080"), InlineKeyboardButton(text="2K", callback_data="res:2k")],
        [InlineKeyboardButton(text="4K", callback_data="res:4k"), InlineKeyboardButton(text="Власний", callback_data="res:custom")]
    ])

def get_wm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Прибрати вотермарку", callback_data="wm:yes")],
        [InlineKeyboardButton(text="❌ Залишити як є", callback_data="wm:no")]
    ])


def get_start_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 ПОЧАТИ ОБРОБКУ", callback_data="start_process")]
    ])

