from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from database.requests import upsert_user, set_user_lang, get_user_data, set_sub
from keyboards.main_menu import get_lang_kb, get_main_menu, get_sub_kb
from locales.i18n import get_t, LANGUAGES

router = Router()


@router.message(CommandStart())
@router.message(F.text.in_([LANGUAGES[l]['btn_lang'] for l in LANGUAGES]))
async def cmd_start_or_lang(message: Message):
    upsert_user(message.from_user.id, message.from_user.first_name)
    await message.answer("🌍 Choose your language / Оберіть мову:", reply_markup=get_lang_kb())


@router.callback_query(F.data.startswith("set_lang:"))
async def select_lang(callback: CallbackQuery):
    lang = callback.data.split(":")[1]
    set_user_lang(callback.from_user.id, lang)
    await callback.message.delete()
    await callback.message.answer(get_t(lang, 'main_menu'), reply_markup=get_main_menu(lang))


# Кнопка підписки
@router.message(F.text.in_([LANGUAGES[l]['btn_sub'] for l in LANGUAGES]))
async def sub_menu(message: Message):
    u = get_user_data(message.from_user.id)
    lang = u[3] if u else 'en'
    await message.answer(get_t(lang, 'sub_title'), reply_markup=get_sub_kb(lang))


# Обробка вибору оплати (симуляція успішної оплати)
@router.callback_query(F.data.startswith("buy:"))
async def process_payment(callback: CallbackQuery):
    months = int(callback.data.split(":")[1])
    uid = callback.from_user.id

    # Викликаємо функцію з БД (вона вже в нас є)
    set_sub(uid, months)

    u = get_user_data(uid)
    lang = u[3] if u else 'en'

    await callback.message.edit_text(get_t(lang, 'sub_success'))
    await callback.answer()