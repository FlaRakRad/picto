from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
import re
import io

from keyboards.photo import get_resolution_kb, get_wm_kb
from keyboards.subscription import get_sub_kb
from handlers.fsm_states import ProcessState
from database.requests import upsert_user, check_reset_limit, get_user_data, consume_one, set_sub
from serviсes.image_api import process_image_by_api

router = Router()


# --- Існуючі команди (з попередніх кроків) ---
@router.message(Command("start"))
async def cmd_start(message: Message):
    upsert_user(message.from_user.id, message.from_user.first_name)
    await message.answer("Привіт! Я PictoBot.\nТвій цикл обробки оновлюється кожні 3 години.")


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer("Я PictoBot для обробки фото.\n"
                         "Просто надішли мені фото, щоб почати.\n"
                         "Ліміти оновлюються кожні 3 години.\n"
                         "Команда /menu — показати стан лімітів.")


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    uid = message.from_user.id
    upsert_user(uid, message.from_user.first_name)  # На випадок якщо юзер новий
    check_reset_limit(uid)
    data = get_user_data(uid)

    limit, _, max_limit = data
    await message.answer(f"📊 Твій стан:\n"
                         f"Залишилось: {limit} з {max_limit}\n"
                         "Команда /subscribe для розширення лімітів.")


@router.message(Command("subscribe"))
async def cmd_sub(message: Message):
    await message.answer("Обери термін підписки:", reply_markup=get_sub_kb())


# --- Обробка фото ---
@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id
    upsert_user(uid, message.from_user.first_name)
    check_reset_limit(uid)

    limit_data = get_user_data(uid)
    if limit_data[0] <= 0:
        return await message.answer(f"❌ Ліміт вичерпано. У тебе {limit_data[0]}/{limit_data[2]} доступних фото.\n"
                                    "Зачекай оновлення або придбай підписку: /subscribe",
                                    reply_markup=get_sub_kb())

    await state.update_data(photo_id=message.photo[-1].file_id)
    await message.answer(f"Який розмір обираємо? (Залишилось: {limit_data[0]})", reply_markup=get_resolution_kb())
    await state.set_state(ProcessState.choosing_resolution)


# --- Обробка колбеку підписки ---
@router.callback_query(F.data.startswith("sub:"))
async def process_sub(callback: CallbackQuery):
    months = int(callback.data.split(":")[1])
    set_sub(callback.from_user.id, months)
    await callback.message.edit_text(f"✅ Підписка активована на {months} міс! Твій ліміт тепер 15 фото/цикл.")
    await callback.answer()


# --- НОВІ ОБРОБНИКИ ДЛЯ FSM (Finite State Machine) ---

# Крок 1: Обробка вибору роздільної здатності
@router.callback_query(ProcessState.choosing_resolution, F.data.startswith("res:"))
async def process_resolution(callback: CallbackQuery, state: FSMContext):
    resolution = callback.data.split(":")[1]

    if resolution == "custom":
        await callback.message.edit_text("Введи бажаний розмір у форматі **Ширина**x**Висота** (напр. `1920x1080`)")
        await state.set_state(ProcessState.entering_custom_res)
    else:
        await state.update_data(resolution=resolution)
        await callback.message.edit_text("Тепер обери, чи прибирати водяні знаки:", reply_markup=get_wm_kb())
        await state.set_state(ProcessState.choosing_wm)
    await callback.answer()


# Крок 1.2: Обробка власної роздільної здатності
@router.message(ProcessState.entering_custom_res)
async def process_custom_resolution(message: Message, state: FSMContext):
    # Перевірка формату "123x456"
    if not re.match(r'^\d+x\d+$', message.text):
        return await message.answer("Неправильний формат. Спробуй ще раз (напр. `1920x1080`)")

    await state.update_data(resolution=message.text)
    await message.answer("Розмір прийнято! Тепер обери, чи прибирати водяні знаки:", reply_markup=get_wm_kb())
    await state.set_state(ProcessState.choosing_wm)


# Крок 2: Обробка вибору водяного знаку та фінальний процес
@router.callback_query(ProcessState.choosing_wm, F.data.startswith("wm:"))
async def process_wm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    remove_wm = True if callback.data.split(":")[1] == "yes" else False

    user_data = await state.get_data()
    photo_id = user_data.get("photo_id")
    resolution = user_data.get("resolution")

    await callback.message.edit_text("⏳ Прийняв! Починаю обробку...")

    # Завантажуємо фото з серверів Telegram
    file_info = await bot.get_file(photo_id)
    photo_bytes = await bot.download_file(file_info.file_path)

    # Викликаємо "API" для обробки (зараз це просто емуляція)
    result = await process_image_by_api(photo_bytes, resolution, remove_wm)

    # Якщо обробка успішна - списуємо ліміт
    if result:
        consume_one(callback.from_user.id)
        # Уявно, надсилаємо оброблене фото (зараз просто текст)
        # file_to_send = BufferedInputFile(result, filename="processed.jpg")
        # await callback.message.answer_document(file_to_send)
        await callback.message.edit_text(f"✅ Готово! Параметри: {resolution}, видалення знаків: {remove_wm}. "
                                         "Твій ліміт оновлено.")
    else:
        await callback.message.edit_text("❌ Сталася помилка під час обробки.")

    await state.clear()  # Скидаємо стан FSM
    await callback.answer()