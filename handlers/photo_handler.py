import asyncio, os, uuid, subprocess, sys
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.fsm_states import ProcessState
from keyboards.photo import get_functions_kb  # Важливо: онови клаву (код нижче)
from locales.i18n import get_t
from database.requests import get_user_data, add_task

router = Router()
# Тимчасове сховище ID файлів у пам'яті (RAM)
storage = {}


@router.message(F.photo, ProcessState.waiting_for_photos)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id
    if uid not in storage: storage[uid] = []

    # Зберігаємо тільки ID, не качаємо файл!
    storage[uid].append(message.photo[-1].file_id)

    curr_len = len(storage[uid])
    await asyncio.sleep(2.5)  # Акумуляція пачки
    if uid in storage and len(storage[uid]) > curr_len: return

    user_data = get_user_data(uid)
    lang = user_data[3] if user_data else 'en'

    # Зберігаємо список ID в стан FSM
    await state.update_data(photo_ids=storage[uid].copy(), lang=lang)

    # Видаємо меню з 3 функціями (код клавіатури нижче)
    m = await message.answer(
        get_t(lang, 'batch_received', count=len(storage[uid])),
        reply_markup=get_functions_kb(lang)
    )
    await state.update_data(msg_to_del=m.message_id)
    await state.set_state(ProcessState.ready_to_start)


# УНІВЕРСАЛЬНИЙ ОБРОБНИК ДЛЯ БУДЬ-ЯКОЇ ФУНКЦІЇ (upscaler, mirror, bgchanger)
@router.callback_query(F.data.startswith("func:"), ProcessState.ready_to_start)
async def start_function_logic(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()

    uid = callback.from_user.id
    # Отримуємо назву (upscaler, mirror або bgchanger)
    func_name = callback.data.split(":")[1]

    data = await state.get_data()
    lang, p_ids = data.get('lang', 'en'), data.get('photo_ids', [])

    u_data = get_user_data(uid)
    priority = 1 if u_data and u_data[2] > 1 else 0

    try:
        await bot.delete_message(uid, data.get('msg_to_del'))
    except:
        pass

    await callback.message.answer(get_t(lang, 'processing', count=len(p_ids)))

    # Шляхи до папок обраної функції
    target_dir = os.path.join(os.getcwd(), "tmp", func_name, "input")
    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(os.path.join(os.getcwd(), "tmp", func_name, "output"), exist_ok=True)

    # 1. ЗАВАНТАЖУЄМО ФАЙЛИ НАПРЯМУ В ЦІЛЬОВУ ПАПКУ
    for p_id in p_ids:
        f_name = f"{uid}_{uuid.uuid4().hex[:6]}.png"
        path = os.path.join(target_dir, f_name)

        try:
            file_info = await bot.get_file(p_id)
            await bot.download_file(file_info.file_path, path)
            # Додаємо в базу замовлення для цієї конкретної функції
            add_task(uid, f_name, func_name, priority)
            print(f"[DIRECT-LOG] Фото {f_name} завантажено прямо в {func_name}")
        except Exception as e:
            print(f"[ERROR] Помилка завантаження: {e}")

    storage.pop(uid, None)

    # 2. ЗАПУСКАЄМО ВОРКЕР (назва файла має бути такою ж як func_name)
    worker_script = os.path.join(os.getcwd(), "modules", f"{func_name}.py")
    if os.path.exists(worker_script):
        subprocess.Popen([sys.executable, worker_script])
        print(f"[SYSTEM] Воркер активовано: {func_name}")
    else:
        print(f"[CRITICAL] Скрипт {worker_script} не знайдено!")

    await state.clear()