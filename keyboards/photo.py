from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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