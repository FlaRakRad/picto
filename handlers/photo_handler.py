import asyncio, os, uuid, subprocess, sys
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.fsm_states import ProcessState
from keyboards.photo import get_functions_kb
from locales.i18n import get_t
from database.requests import get_user_data, add_task

router = Router()
# Сховище для ID фотографій (у оперативці)
storage = {}  # {uid: [file_id1, file_id2, ...]}


# --- 1. ПРИЙОМ ФОТОГРАФІЙ ---
@router.message(F.photo, ProcessState.waiting_for_photos)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id
    if uid not in storage: storage[uid] = []

    storage[uid].append(message.photo[-1].file_id)
    captured_count = len(storage[uid])

    # Чекаємо 3 секунди на довантаження пачки
    await asyncio.sleep(3)

    # Якщо за цей час прийшли нові фото - цей "потік" закриваємо
    if uid not in storage or len(storage[uid]) > captured_count:
        return

    # Пачка зібрана - забираємо ID і очищуємо RAM-сховище
    photo_ids = storage.pop(uid)
    user_info = get_user_data(uid)
    lang = user_info[3] if user_info else 'en'

    # Зберігаємо список ID у стані юзера
    await state.update_data(photo_ids=photo_ids, lang=lang)

    m = await message.answer(
        get_t(lang, 'batch_received', count=len(photo_ids)),
        reply_markup=get_functions_kb(lang)
    )
    await state.update_data(msg_to_del=m.message_id)
    await state.set_state(ProcessState.ready_to_start)


# --- 2. ДОПОМІЖНА ФУНКЦІЯ ЗАВАНТАЖЕННЯ (RUN LOGIC) ---
async def run_common_logic(callback: CallbackQuery, state: FSMContext, bot: Bot, func_name: str):
    uid = callback.from_user.id
    data = await state.get_data()
    lang, p_ids = data.get('lang', 'en'), data.get('photo_ids', [])

    # Пріоритет: 1 для VIP, 0 для безкоштовних
    user_data = get_user_data(uid)
    priority = 1 if (user_data and user_data[2] > 1) else 0
    # Генеруємо Batch ID для всієї пачки
    batch_id = f"b_{uuid.uuid4().hex[:6]}"

    # Очищуємо чат (видаляємо кнопку)
    try:
        await bot.delete_message(uid, data.get('msg_to_del'))
    except:
        pass

    await callback.message.answer(get_t(lang, 'processing', count=len(p_ids)))

    # Шляхи до папок
    base_path = os.getcwd()
    target_dir = os.path.join(base_path, "tmp", func_name, "input")
    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(os.path.join(base_path, "tmp", func_name, "output"), exist_ok=True)

    print(f"[SYSTEM] 📂 Юзер {uid} | Функція: {func_name} | Фото: {len(p_ids)}")

    # Качаємо файли напряму
    for p_id in p_ids:
        unique_name = f"{uid}_{uuid.uuid4().hex[:6]}.png"
        path = os.path.join(target_dir, unique_name)

        try:
            file_info = await bot.get_file(p_id)
            await bot.download_file(file_info.file_path, path)
            # Додаємо завдання в базу з batch_id
            add_task(uid, unique_name, func_name, priority, batch_id)
        except Exception as e:
            print(f"[ERROR] Помилка завантаження файлу: {e}")

    # Запускаємо воркер через ОС
    worker_script = os.path.join(base_path, "modules", f"{func_name}.py")
    if os.path.exists(worker_script):
        subprocess.Popen([sys.executable, worker_script])
        print(f"[SYSTEM] ✅ Воркер {func_name}.py запущено.")
    else:
        print(f"[CRITICAL] ❌ Файл воркера {worker_script} не знайдено!")

    await state.clear()


# --- 3. ОБРОБНИК ДЛЯ BGCHANGER (Валідація 2-х фото) ---
@router.callback_query(F.data == "func:bgchanger", ProcessState.ready_to_start)
async def check_bgchanger_logic(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    p_ids = data.get('photo_ids', [])
    lang = data.get('lang', 'en')

    # Якщо юзер кинув не 2 фото - шлемо алерт
    if len(p_ids) != 2:
        await callback.message.answer(get_t(lang, 'bg_err_count'))
        return

    await run_common_logic(callback, state, callback.bot, "bgchanger")


# --- 4. ОБРОБНИК ДЛЯ ІНШИХ ФУНКЦІЙ (Стандарт) ---
@router.callback_query(F.data.startswith("func:"), ProcessState.ready_to_start)
async def other_functions_logic(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    func_name = callback.data.split(":")[1]
    await run_common_logic(callback, state, callback.bot, func_name)