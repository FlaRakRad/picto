from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from handlers.fsm_states import ProcessState
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import CommandStart
from database.requests import upsert_user, set_user_lang, get_user_data, set_sub, check_reset_limit
from keyboards.main_menu import get_lang_kb, get_main_menu, get_sub_kb
from locales.i18n import get_t, LANGUAGES

router = Router()

# Словник: ID плану -> Кількість фото за годинний цикл
LIMITS_CONFIG = {1: 10, 3: 15, 6: 25, 12: 50}


@router.message(CommandStart())
@router.message(F.text.in_([LANGUAGES[l]['btn_lang'] for l in LANGUAGES]))
async def cmd_start_or_lang(message: Message, state: FSMContext):
    await state.clear()
    upsert_user(message.from_user.id, message.from_user.first_name)
    await message.answer("🌍 Choose your language / Оберіть мову:", reply_markup=get_lang_kb())


@router.callback_query(F.data.startswith("set_lang:"))
async def select_lang(callback: CallbackQuery):
    lang = callback.data.split(":")[1]
    set_user_lang(callback.from_user.id, lang)
    await callback.message.delete()
    await callback.message.answer(get_t(lang, 'main_menu'), reply_markup=get_main_menu(lang))


# КНОПКА МІЙ ПРОФІЛЬ (Перевірка циклу)
@router.message(F.text.in_([LANGUAGES[l]['btn_profile'] for l in LANGUAGES]))
async def view_profile(message: Message):
    uid = message.from_user.id

    # 1. Спробуємо оновити ліміти
    check_reset_limit(uid)

    # 2. Беремо дані
    u = get_user_data(uid)

    # 🚨 ОСЬ ЦЕЙ ЖОРСТКИЙ ЗАХИСТ: Якщо тебе нема в базі (u == None)
    if u is None:
        from database.requests import upsert_user
        print(f"[FIX] Юзер {uid} не знайдений в БД. Реєструю на ходу...")
        upsert_user(uid, message.from_user.first_name)
        u = get_user_data(uid)  # Тепер він точно там є

    # Тепер дістаємо дані, бо 'u' вже точно не None
    limit = u[0]
    max_limit = u[2]
    lang = u[3]

    await message.answer(get_t(lang, 'profile', limit=limit, max=max_limit))


# МЕНЮ ПІДПИСКИ
@router.message(F.text.in_([LANGUAGES[l]['btn_sub'] for l in LANGUAGES]))
async def sub_menu(message: Message):
    u = get_user_data(message.from_user.id)
    lang = u[3] or 'en'
    # Тут використовуй inline-кнопки вибору оплати (Stars/Crypto)
    # Поки для простоти відправляємо стандартне вікно підписки
    await message.answer(get_t(lang, 'sub_title'), reply_markup=get_sub_kb(lang))


# ОБРОБКА ТЕСТОВОЇ ОПЛАТИ (buy:1, buy:3 ...)
@router.callback_query(F.data.startswith("buy:"))
async def process_payment(callback: CallbackQuery):
    plan_id = int(callback.data.split(":")[1])
    uid = callback.from_user.id

    # Визначаємо новий макс_ліміт за обраним планом
    new_max = LIMITS_CONFIG.get(plan_id, 10)

    # У цій версії - СИМУЛЯЦІЯ УСПІХУ ТА ОНОВЛЕННЯ ЛІМІТІВ
    # В майбутньому тут буде виклик get_payment_methods_kb
    set_sub(uid, plan_id, new_max)

    u = get_user_data(uid);
    lang = u[3] or 'en'
    await callback.message.edit_text(get_t(lang, 'sub_success'))
    await callback.answer()


# КНОПКА ОБРОБКИ
@router.message(F.text.in_([LANGUAGES[l]['btn_process'] for l in LANGUAGES]))
async def start_process_mode(message: Message, state: FSMContext):
    u = get_user_data(message.from_user.id)
    check_reset_limit(message.from_user.id)  # Важливо оновити перед роботою

    await state.set_state(ProcessState.waiting_for_photos)
    await message.answer("📸 " + get_t(u[3], 'btn_process') + ": Send photos now!")


