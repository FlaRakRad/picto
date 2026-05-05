import asyncio
import os
import sys
import subprocess
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


@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id
    print(f"\n[BOT] 📸 Отримано фото від користувача {uid}")

    check_reset_limit(uid)
    limit_data = get_user_data(uid)
    print(f"[BOT] Поточні ліміти: {limit_data[0]}/{limit_data[2]}")

    if limit_data[0] <= 0:
        print(f"[BOT] 🛑 Відмова: ліміт вичерпано.")
        return await message.answer("❌ Ліміт вичерпано.")

    await state.update_data(photo_id=message.photo[-1].file_id)
    await message.answer("Яку якість обираємо?", reply_markup=get_resolution_kb())
    await state.set_state(ProcessState.choosing_resolution)


@router.callback_query(ProcessState.choosing_resolution, F.data.startswith("res:"))
async def process_resolution(callback: CallbackQuery, state: FSMContext):
    res = callback.data.split(":")[1]
    print(f"[BOT] ⚙️ Користувач вибрав роздільну здатність: {res}")
    await state.update_data(resolution=res)
    await callback.message.edit_text("Прибрати водяні знаки?", reply_markup=get_wm_kb())
    await state.set_state(ProcessState.choosing_wm)


@router.callback_query(ProcessState.choosing_wm, F.data.startswith("wm:"))
async def process_wm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    uid = callback.from_user.id
    print(f"[BOT] ⚙️ Користувач вибрав вотермарку: {callback.data}")
    await callback.message.edit_text("⏳ Завантажую та запускаю обробку...")

    data = await state.get_data()
    photo_id = data.get("photo_id")

    try:
        # 1. Завантаження
        print(f"[BOT] 📥 Завантаження файлу {photo_id} з Telegram...")
        file_info = await bot.get_file(photo_id)
        photo_bytes = await bot.download_file(file_info.file_path)

        # 2. Збереження
        input_filename = f"{uid}.png"
        input_path = os.path.join(INPUT_DIR, input_filename)
        with open(input_path, "wb") as f:
            f.write(photo_bytes.getvalue())
        print(f"[BOT] 💾 Файл збережено в {input_path}")

        # 3. ЗАПУСК АПСКЕЙЛЕРА
        print(f"[BOT] 🚀 Запуск зовнішнього процесу upscaller.py...")
        # Ми запускаємо його і чекаємо завершення (так як ти просив break)
        proc = subprocess.run([sys.executable, UPSCALER_SCRIPT], capture_output=True, text=True)
        print(f"[BOT] --- Лог апскейлера ---\n{proc.stdout}\n------------------------")

        # 4. Перевірка результату
        expected_output = f"up_{uid}.png"
        output_path = os.path.join(OUTPUT_DIR, expected_output)

        if os.path.exists(output_path):
            print(f"[BOT] 📤 Надсилаю результат користувачу {uid}...")
            with open(output_path, "rb") as f:
                final_file = BufferedInputFile(f.read(), filename=expected_output)
                await bot.send_document(uid, final_file, caption="✅ Готово! Файл без стиснення.")

            os.remove(output_path)
            consume_one(uid)
            print(f"[BOT] ✨ Сесія успішно завершена для {uid}")
        else:
            print(f"[BOT] ❌ Файл {expected_output} не знайдено в output!")
            await callback.message.answer("❌ Помилка обробки. Спробуйте інше фото.")

    except Exception as e:
        print(f"[BOT] ‼️ КРИТИЧНА ПОМИЛКА: {e}")
        await callback.message.answer(f"❌ Помилка: {e}")

    await state.clear()