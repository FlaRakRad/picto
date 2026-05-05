import asyncio
import os
import sys
import subprocess
import uuid
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from keyboards.photo import get_resolution_kb, get_wm_kb
from handlers.fsm_states import ProcessState
from database.requests import check_reset_limit, get_user_data, consume_one

router = Router()

BASE_DIR = os.getcwd()
INPUT_DIR = os.path.join(BASE_DIR, "tmp", "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "tmp", "output")
UPSCALER_SCRIPT = os.path.join(BASE_DIR, "modules", "upscaller.py")

# Словник для накопичення фото {user_id: [photo_ids]}
storage = {}


@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id
    photo_id = message.photo[-1].file_id

    # Ініціалізуємо список для юзера, якщо його немає
    if uid not in storage:
        storage[uid] = []
        print(f"\n[BATCH] 📸 Користувач {uid} почав завантаження пачки...")

    storage[uid].append(photo_id)

    # Чекаємо 2 секунди після кожного фото.
    # Якщо за 2 сек нових фото не буде — йдемо далі.
    initial_count = len(storage[uid])
    await asyncio.sleep(2)

    if len(storage[uid]) > initial_count:
        # Якщо кількість фото збільшилась, значить ми ще в процесі отримання пачки
        return

    # Якщо ми тут, значить пачка зібрана
    final_list = storage[uid].copy()
    print(f"[BATCH] ✅ Зібрано {len(final_list)} фото від {uid}")

    check_reset_limit(uid)
    limit_data = get_user_data(uid)

    if limit_data[0] < len(final_list):
        storage.pop(uid, None)
        return await message.answer(f"❌ Недостатньо лімітів для {len(final_list)} фото. Залишилось: {limit_data[0]}")

    await state.update_data(photo_ids=final_list)  # Зберігаємо весь список
    await message.answer(f"📸 Отримано {len(final_list)} фото. Оберіть якість для всієї пачки:",
                         reply_markup=get_resolution_kb())
    await state.set_state(ProcessState.choosing_resolution)


@router.callback_query(ProcessState.choosing_resolution, F.data.startswith("res:"))
async def process_resolution(callback: CallbackQuery, state: FSMContext):
    res = callback.data.split(":")[1]
    await state.update_data(resolution=res)
    await callback.message.edit_text("Прибрати водяні знаки на всіх фото?", reply_markup=get_wm_kb())
    await state.set_state(ProcessState.choosing_wm)


@router.callback_query(ProcessState.choosing_wm, F.data.startswith("wm:"))
async def process_wm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    uid = callback.from_user.id
    data = await state.get_data()
    photo_ids = data.get("photo_ids", [])

    await callback.message.edit_text(f"⏳ Починаю обробку пачки з {len(photo_ids)} фото...")

    # Очищуємо сховище юзера перед роботою
    storage.pop(uid, None)

    session_files = []  # Список для відслідковування імен файлів у цій сесії

    try:
        # 1. Завантажуємо ВСІ фото
        print(f"[BATCH] 📥 Завантаження {len(photo_ids)} файлів...")
        for i, p_id in enumerate(photo_ids):
            file_info = await bot.get_file(p_id)
            photo_bytes = await bot.download_file(file_info.file_path)

            # Унікальне ім'я: UID_UUID_INDEX
            filename = f"{uid}_{uuid.uuid4().hex[:4]}_{i}.png"
            input_path = os.path.join(INPUT_DIR, filename)

            with open(input_path, "wb") as f:
                f.write(photo_bytes.getvalue())

            session_files.append(filename.replace(".png", ""))  # Запам'ятовуємо основу імені
            print(f"[BATCH] 💾 Збережено ({i + 1}/{len(photo_ids)}): {filename}")

        # 2. Запуск апскейлера (він обробить ВСЕ, що ми щойно поклали)
        print(f"[BATCH] 🚀 Запуск апскейлера для всієї пачки...")
        proc = subprocess.run([sys.executable, UPSCALER_SCRIPT], capture_output=True, text=True)
        print(f"[BATCH] --- Лог апскейлера ---\n{proc.stdout}\n------------------------")

        # 3. Відправляємо результати
        print(f"[BATCH] 📤 Пошук результатів для сесії...")
        files_sent = 0

        for file_stem in session_files:
            expected_output = f"up_{file_stem}.png"
            output_path = os.path.join(OUTPUT_DIR, expected_output)

            if os.path.exists(output_path):
                with open(output_path, "rb") as f:
                    final_file = BufferedInputFile(f.read(), filename=expected_output)
                    await bot.send_document(uid, final_file)

                os.remove(output_path)
                consume_one(uid)
                files_sent += 1
                print(f"[BATCH] ✅ Надіслано: {expected_output}")
            else:
                print(f"[BATCH] ❌ Не знайдено результат для: {file_stem}")

        await callback.message.answer(f"✨ Обробка завершена! Надіслано {files_sent} з {len(photo_ids)} фото.")

    except Exception as e:
        print(f"[BATCH] ‼️ Помилка: {e}")
        await callback.message.answer(f"❌ Сталася помилка: {e}")

    await state.clear()