import asyncio
import os
import sys
import subprocess
import uuid
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InputMediaDocument, BufferedInputFile
from aiogram.fsm.context import FSMContext

from keyboards.photo import get_start_kb
from handlers.fsm_states import ProcessState
from database.requests import check_reset_limit, get_user_data, consume_one

router = Router()

BASE_DIR = os.getcwd()
INPUT_DIR = os.path.join(BASE_DIR, "tmp", "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "tmp", "output")
UPSCALER_SCRIPT = os.path.join(BASE_DIR, "modules", "upscaller.py")

storage = {}


@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id
    photo_id = message.photo[-1].file_id

    if uid not in storage:
        storage[uid] = []
        print(f"\n[BATCH] 📸 Користувач {uid} скидає фото...")

    storage[uid].append(photo_id)

    # Акумуляція фото (чекаємо 2 секунди)
    current_count = len(storage[uid])
    await asyncio.sleep(2)
    if len(storage[uid]) > current_count:
        return

    # Фото зібрані
    photo_ids = storage[uid].copy()
    await state.update_data(photo_ids=photo_ids)

    print(f"[BATCH] ✅ Зібрано {len(photo_ids)} фото. Чекаю на команду 'Старт'.")
    await message.answer(f"📦 Отримано {len(photo_ids)} фото. Натисніть кнопку, щоб почати.",
                         reply_markup=get_start_kb())
    await state.set_state(ProcessState.ready_to_start)


@router.callback_query(F.data == "start_process", ProcessState.ready_to_start)
async def process_batch(callback: CallbackQuery, state: FSMContext, bot: Bot):
    uid = callback.from_user.id
    data = await state.get_data()
    photo_ids = data.get("photo_ids", [])

    if not photo_ids:
        return await callback.answer("Помилка: фото не знайдено.")

    await callback.message.edit_text(f"⏳ Обробка {len(photo_ids)} фото... Це займе деякий час.")
    storage.pop(uid, None)  # Чистимо тимчасове сховище

    session_stems = []

    try:
        # 1. Завантаження всіх фото
        for i, p_id in enumerate(photo_ids):
            file_info = await bot.get_file(p_id)
            photo_bytes = await bot.download_file(file_info.file_path)

            stem = f"{uid}_{uuid.uuid4().hex[:4]}_{i}"
            input_path = os.path.join(INPUT_DIR, f"{stem}.png")

            with open(input_path, "wb") as f:
                f.write(photo_bytes.getvalue())

            session_stems.append(stem)
            print(f"[DEBUG] Завантажено {i + 1}/{len(photo_ids)}")

        # 2. Запуск апскейлера (чекаємо завершення всієї пачки)
        print(f"[DEBUG] Запуск апскейлера...")
        subprocess.run([sys.executable, UPSCALER_SCRIPT], capture_output=True, text=True)

        # 3. Збираємо результати в медіагрупу
        media_group = []
        print(f"[DEBUG] Збір результатів...")

        for stem in session_stems:
            output_path = os.path.join(OUTPUT_DIR, f"up_{stem}.png")
            if os.path.exists(output_path):
                with open(output_path, "rb") as f:
                    # Читаємо файл і додаємо до групи
                    file_content = f.read()
                    media_group.append(InputMediaDocument(
                        media=BufferedInputFile(file_content, filename=f"up_{stem}.png")
                    ))
                os.remove(output_path)  # Видаляємо відразу після читання
                consume_one(uid)

        # 4. Відправка всієї пачки одним повідомленням
        if media_group:
            # Telegram дозволяє максимум 10 файлів у одній медіагрупі
            # Розбиваємо список на частини по 10, якщо фото більше
            for i in range(0, len(media_group), 10):
                chunk = media_group[i:i + 10]
                await bot.send_media_group(chat_id=uid, media=chunk)

            print(f"[DEBUG] ✅ Всі фото надіслані користувачу {uid}")
            await callback.message.answer("✨ Всі фото успішно оброблені!")
        else:
            await callback.message.answer("❌ Не вдалося обробити жодного фото.")

    except Exception as e:
        print(f"[ERROR] {e}")
        await callback.message.answer(f"❌ Сталася помилка: {e}")

    await state.clear()