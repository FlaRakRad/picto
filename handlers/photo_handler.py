import asyncio
import os
import uuid
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

# Визначаємо шляхи до папок тут для зручності
BASE_DIR = os.getcwd()  # Отримуємо поточну робочу директорію
INPUT_DIR = os.path.join(BASE_DIR, "tmp", "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "tmp", "output")

# Створюємо папки, якщо їх раптом немає
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

router = Router()


# --- Існуючі команди (start, help, menu, subscribe) залишаються без змін ---
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
    upsert_user(uid, message.from_user.first_name)
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


# --- FSM обробники для вибору налаштувань (без змін) ---
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


@router.message(ProcessState.entering_custom_res)
async def process_custom_resolution(message: Message, state: FSMContext):
    if not re.match(r'^\d+x\d+$', message.text):
        return await message.answer("Неправильний формат. Спробуй ще раз (напр. `1920x1080`)")

    await state.update_data(resolution=message.text)
    await message.answer("Розмір прийнято! Тепер обери, чи прибирати водяні знаки:", reply_markup=get_wm_kb())
    await state.set_state(ProcessState.choosing_wm)


# --- ОНОВЛЕНИЙ ФІНАЛЬНИЙ КРОК: ЗБЕРЕЖЕННЯ, ОЧІКУВАННЯ ТА ВІДПРАВКА ---
@router.callback_query(ProcessState.choosing_wm, F.data.startswith("wm:"))
async def process_wm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.edit_text("⏳ Прийняв! Починаю обробку... Це може зайняти до хвилини.")
    await callback.answer()

    user_data = await state.get_data()
    photo_id = user_data.get("photo_id")

    # 1. Завантажуємо фото з Telegram
    file_info = await bot.get_file(photo_id)
    photo_bytes = await bot.download_file(file_info.file_path)

    # 2. Зберігаємо файл в 'input' з унікальним ім'ям
    # Унікальне ім'я, щоб уникнути конфліктів при одночасній обробці
    file_stem = f"{callback.from_user.id}_{uuid.uuid4().hex[:8]}"
    input_filename = f"{file_stem}.png"  # Зберігаємо в png для якості
    input_path = os.path.join(INPUT_DIR, input_filename)

    with open(input_path, "wb") as f:
        f.write(photo_bytes.getvalue())

    # 3. Визначаємо, де чекати на результат (згідно логіки upscaler.py)
    output_filename = f"up_{file_stem}.png"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    # 4. Очікуємо на результат
    processed_successfully = False
    for _ in range(60):  # Чекаємо максимум 60 секунд
        if os.path.exists(output_path):
            try:
                # Файл з'явився! Читаємо і надсилаємо користувачу.
                with open(output_path, "rb") as photo_file:
                    result_file_to_send = BufferedInputFile(photo_file.read(), filename=output_filename)

                await callback.message.answer_document(
                    result_file_to_send,
                    caption="✅ Ваше покращене зображення."
                )

                # Списуємо ліміт та інформуємо користувача
                consume_one(callback.from_user.id)
                data = get_user_data(callback.from_user.id)
                await callback.message.edit_text(f"✅ Готово! Ваш ліміт оновлено.\n"
                                                 f"Залишилось: {data[0]} з {data[2]}")
                processed_successfully = True

            except Exception as e:
                print(f"Помилка під час відправки файлу: {e}")
                await callback.message.edit_text("❌ Сталася помилка під час відправки обробленого файлу.")

            finally:
                # ВАЖЛИВО: Видаляємо файл з папки 'output', щоб не накопичувати
                os.remove(output_path)
                break  # Виходимо з циклу очікування

        await asyncio.sleep(1)  # Якщо файлу ще немає, чекаємо 1 секунду

    # Якщо цикл завершився, а файл так і не з'явився
    if not processed_successfully:
        await callback.message.edit_text("❌ Помилка: обробка зображення тривала занадто довго. Спробуйте пізніше.")
        # Також варто видалити вхідний файл, щоб він не оброблявся даремно
        if os.path.exists(input_path):
            os.remove(input_path)

    # Скидаємо стан FSM, щоб користувач міг почати нову обробку
    await state.clear()