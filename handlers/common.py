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


# 1. КОМАНДА СТАРТ - Повна чистка та вибір мови
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()  # Скидаємо ШІ-чергу та інше
    upsert_user(message.from_user.id, message.from_user.first_name)

    # Видаляємо будь-які старі кнопки, щоб юзер бачив ТІЛЬКИ вибір мови
    await message.answer(
        "👋", reply_markup=ReplyKeyboardRemove()
    )

    await message.answer(
        "🌍 <b>Welcome! Please choose your language:</b>\n"
        "Оберіть мову інтерфейсу, щоб продовжити 👇",
        reply_markup=get_lang_kb()
    )


# 2. ОБРОБНИК ОБРАНОЇ МОВИ
@router.callback_query(F.data.startswith("set_lang:"))
async def select_lang(callback: CallbackQuery):
    lang = callback.data.split(":")[1]
    set_user_lang(callback.from_user.id, lang)

    await callback.message.delete()

    # Видаємо вітання мовою користувача та ОФІЦІЙНЕ ГОЛОВНЕ МЕНЮ
    await callback.message.answer(
        get_t(lang, 'main_menu'),
        reply_markup=get_main_menu(lang)
    )


# 3. ПРОФІЛЬ
@router.message(F.text.in_([LANGUAGES[l]['btn_profile'] for l in LANGUAGES]))
async def view_profile(message: Message):
    uid = message.from_user.id
    check_reset_limit(uid)  # Скидаємо годинний ліміт якщо час настав

    u = get_user_data(uid)
    if not u:  # На випадок якщо база порожня
        upsert_user(uid, message.from_user.first_name)
        u = get_user_data(uid)

    lang = u[3]
    # Форматуємо дату закінчення VIP
    sub_date = u[4].split(" ")[0] if u[4] else "---"

    text = get_t(lang, 'profile',
                 user_name=message.from_user.first_name,
                 limit=u[0], max=u[2],
                 total_all=u[5], sub_date=sub_date)
    await message.answer(text)


# 4. МЕНЮ ПІДПИСКИ
@router.message(F.text.in_([LANGUAGES[l]['btn_sub'] for l in LANGUAGES]))
async def sub_menu(message: Message):
    u = get_user_data(message.from_user.id)
    lang = u[3] if u else 'en'
    await message.answer(get_t(lang, 'sub_title'), reply_markup=get_sub_kb(lang))


# 5. КНОПКА ОБРОБКИ
@router.message(F.text.in_([LANGUAGES[l]['btn_process'] for l in LANGUAGES]))
async def start_process_command(message: Message, state: FSMContext):
    u = get_user_data(message.from_user.id)
    lang = u[3] if u else 'en'
    check_reset_limit(message.from_user.id)

    await state.set_state(ProcessState.waiting_for_photos)
    await message.answer(get_t(lang, 'btn_process_instruction'))


# 6. ПІДТРИМКА (🆘)
@router.message(F.text.in_([LANGUAGES[l]['btn_support'] for l in LANGUAGES]))
async def support_handler(message: Message):
    u = get_user_data(message.from_user.id)
    lang = u[3] if u else 'en'
    # Напиши свій контакт або чат підтримки
    await message.answer("🛠 <b>Support Center</b>\n\nContact us: @ВашЮзернейм_Підтримки")


# 7. ВІДГУКИ (⭐️)
@router.message(F.text.in_([LANGUAGES[l]['btn_feedback'] for l in LANGUAGES]))
async def feedback_handler(message: Message):
    # Тут може бути посилання на твій канал з відгуками
    await message.answer("⭐️ <b>Community Feedback</b>\n\nChannel: @PictoReviews")