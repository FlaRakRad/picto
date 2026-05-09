import os, sys
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

# Фікс шляхів
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from database.requests import upsert_user, set_user_lang, get_user_data, check_reset_limit
from keyboards.main_menu import get_lang_kb, get_main_menu, get_sub_kb
from locales.i18n import get_t, LANGUAGES
from handlers.fsm_states import ProcessState

router = Router()


# 1. КОМАНДА СТАРТ - ТІЛЬКИ АНГЛІЙСЬКА (як ти просив на 2 скріні)
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    upsert_user(message.from_user.id, message.from_user.first_name)

    # Тимчасово прибираємо стару клаву
    await message.answer("🛸", reply_markup=ReplyKeyboardRemove())

    # ВІТАННЯ ТІЛЬКИ АНГЛІЙСЬКОЮ
    await message.answer(
        "🌍 <b>Welcome! Please choose your language to continue:</b>\n"
        "<i>Select your interface language below 👇</i>",
        reply_markup=get_lang_kb()
    )


# 2. ОБРОБНИК ВИБОРУ МОВИ
@router.callback_query(F.data.startswith("set_lang:"))
async def select_lang(callback: CallbackQuery):
    lang = callback.data.split(":")[1]
    set_user_lang(callback.from_user.id, lang)

    await callback.message.delete()

    # ТУТ ПРИЛІТАЄ ГАРНЕ УКРАЇНСЬКЕ МЕНЮ (якщо обрали UA)
    await callback.message.answer(
        get_t(lang, 'main_menu'),
        reply_markup=get_main_menu(lang)
    )


# 3. ПРОФІЛЬ (УКРАЇНСЬКОЮ, ЗІ СТАТИСТИКОЮ)
@router.message(F.text.in_([LANGUAGES[l].get('btn_profile') for l in LANGUAGES]))
async def view_profile(message: Message):
    uid = message.from_user.id
    check_reset_limit(uid)
    u = get_user_data(uid)  # (limit, date, max, lang, sub, total)

    if not u: return
    lang = u[3]

    text = get_t(lang, 'profile',
                 user_name=message.from_user.first_name,
                 limit=u[0], max=u[2],
                 total_all=u[5],
                 sub_date=u[4].split(" ")[0] if u[4] else "---")
    await message.answer(text)


# 4. ПІДТРИМКА ТА ВІДГУКИ (Тепер теж мультиязичні!)
@router.message(F.text.in_([LANGUAGES[l].get('btn_support') for l in LANGUAGES]))
async def support_handler(message: Message):
    u = get_user_data(message.from_user.id)
    lang = u[3] if u else 'en'
    # Текст візьметься з uk.py ('support_info')
    await message.answer(get_t(lang, 'support_info'))


@router.message(F.text.in_([LANGUAGES[l].get('btn_feedback') for l in LANGUAGES]))
async def feedback_handler(message: Message):
    u = get_user_data(message.from_user.id)
    lang = u[3] if u else 'en'
    await message.answer(get_t(lang, 'feedback_info'))


# 5. ПІДПИСКА
@router.message(F.text.in_([LANGUAGES[l].get('btn_sub') for l in LANGUAGES]))
async def sub_menu(message: Message):
    u = get_user_data(message.from_user.id)
    await message.answer(get_t(u[3], 'sub_title'), reply_markup=get_sub_kb(u[3]))


# 6. РЕЖИМ ОБРОБКИ
@router.message(F.text.in_([LANGUAGES[l].get('btn_process') for l in LANGUAGES]))
async def start_process_command(message: Message, state: FSMContext):
    u = get_user_data(message.from_user.id)
    await state.set_state(ProcessState.waiting_for_photos)
    await message.answer(get_t(u[3], 'btn_process_instruction'))