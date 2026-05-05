import asyncio
import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from keyboards.photo import get_resolution_kb, get_wm_kb
from handlers.fsm_states import ProcessState
from database.requests import check_reset_limit, get_user_data, consume_one

router = Router()

# Шляхи до папок (відносно кореня проекту)
BASE_DIR = os.getcwd()
INPUT_DIR = os.path.join(BASE_DIR, "tmp", "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "tmp", "output")


@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id
    check_reset_limit(uid)
    limit_data = get_user_data(uid)

    if limit_data[0] <= 0:
        return await message.answer("❌ Ліміт вичерпано. Придбайте підписку.")

    await state.update_data(photo_id=message.photo[-1].file_id)
    await message.answer("Оберіть якість:", reply_markup=get_resolution_kb())
    await state.set_state(ProcessState.choosing_resolution)


@router.callback_query(ProcessState.choosing_resolution, F.data.startswith("res:"))
async def process_resolution(callback: CallbackQuery, state: FSMContext):
    await state.update_data(resolution=callback.data.split(":")[1])
    await callback.message.edit_text("Прибрати водяні знаки?", reply_markup=get_wm_kb())
    await state.set_state(ProcessState.choosing_wm)


@router.callback_query(ProcessState.choosing_wm, F.data.startswith("wm:"))
async def process_wm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback.from_user.id
    await callback.message.edit_text("⏳ Обробка розпочата. Будь ласка, зачекайте...")

    data = await state.get_data()
    photo_id = data.get("photo_id")

    try:
        # 1. Завантажуємо фото
        file_info = await bot.get_file(photo_id)
        photo_bytes = await bot.download_file(file_info.file_path)

        # 2. Зберігаємо в input. Назва — просто ID користувача.
        # Апскейлер візьме його і зробить "up_ID.png"
        input_filename = f"{user_id}.png"
        input_path = os.path.join(INPUT_DIR, input_filename)

        with open(input_path, "wb") as f:
            f.write(photo_bytes.getvalue())

        # 3. Чекаємо результат
        expected_output = f"up_{user_id}.png"
        output_path = os.path.join(OUTPUT_DIR, expected_output)

        found = False
        for _ in range(120):  # Чекаємо 2 хвилини (120 ітерацій по 1 сек)
            if os.path.exists(output_path):
                # ФІКС ДЛЯ ВЕЛИКИХ ФАЙЛІВ:
                # Чекаємо, поки розмір файлу перестане змінюватися (значить апскейлер його допиcaв)
                prev_size = -1
                while True:
                    current_size = os.path.getsize(output_path)
                    if current_size == prev_size and current_size > 0:
                        break
                    prev_size = current_size
                    await asyncio.sleep(1)

                # Відправляємо файл БЕЗ стиснення
                with open(output_path, "rb") as f:
                    final_file = BufferedInputFile(f.read(), filename=expected_output)
                    await bot.send_document(user_id, final_file, caption="✅ Ваше покращене фото (без стиснення)")

                # Чистимо за собою
                os.remove(output_path)
                consume_one(user_id)
                found = True
                break

            await asyncio.sleep(1)

        if not found:
            await callback.message.answer(
                "❌ Час очікування вичерпано. Можливо, фото занадто велике або сталась помилка.")

    except Exception as e:
        print(f"Error: {e}")
        await callback.message.answer("❌ Виникла помилка при обробці.")

    await state.clear()