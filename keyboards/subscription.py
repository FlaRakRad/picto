from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_sub_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 міс (Base)", callback_data="sub:1"),
         InlineKeyboardButton(text="3 міс (Pro)", callback_data="sub:3")],
        [InlineKeyboardButton(text="6 міс (VIP)", callback_data="sub:6"),
         InlineKeyboardButton(text="12 міс (Infinity)", callback_data="sub:12")]
    ])