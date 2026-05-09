import asyncio, os, uuid, subprocess, sys
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.fsm_states import ProcessState
from keyboards.photo import get_functions_kb
from locales.i18n import get_t
from database.requests import get_user_data, add_task, check_reset_limit

router = Router()
storage = {}  # Тимчасове сховище ID файлів у RAM (RAM > DISK)


# --- 1. ПРИЙОМ ОСНОВНИХ ФОТО (ОБ'ЄКТІВ) ---
@router.message(F.photo, ProcessState.waiting_for_photos)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id

    # Синхронізація лімітів: перевіряємо, чи настав час оновити годину
    next_cycle_dt = check_reset_limit(uid)
    u_info = get_user_data(uid)  # (limit, date, max_limit, lang)
    lang = u_info[3] or 'en'

    # 1. Швидка перевірка: чи є в юзера взагалі хоча б 1 ліміт?
    if u_info[0] <= 0:
        time_str = next_cycle_dt.strftime("%H:%M")
        return await message.answer(get_t(lang, 'batch_limit_error', limit=0, count="?", time=time_str))

    if uid not in storage: storage[uid] = []
    storage[uid].append(message.photo[-1].file_id)

    captured_count = len(storage[uid])
    await asyncio.sleep(3.5)  # Акумуляція

    if uid not in storage or len(storage[uid]) > captured_count:
        return

    # Пачка готова
    photo_ids = storage.pop(uid)

    # 2. Жорстка перевірка: чи не перевищує пачка залишок лімітів на годину?
    if len(photo_ids) > u_info[0]:
        time_str = next_cycle_dt.strftime("%H:%M")
        return await message.answer(
            get_t(lang, 'batch_limit_error', limit=u_info[0], count=len(photo_ids), time=time_str))

    # Зберігаємо ID та мову у стані
    await state.update_data(photo_ids=photo_ids, lang=lang)

    m = await message.answer(
        get_t(lang, 'batch_received', count=len(photo_ids)),
        reply_markup=get_functions_kb(lang)
    )
    await state.update_data(msg_to_del=m.message_id)
    await state.set_state(ProcessState.ready_to_start)


# --- 2. ДОПОМІЖНА ФУНКЦІЯ ЗАПУСКУ (ДЛЯ UPSCALER / MIRROR) ---
async def run_common_logic(callback: CallbackQuery, state: FSMContext, bot: Bot, func_name: str):
    uid = callback.from_user.id
    data = await state.get_data()
    lang, p_ids = data.get('lang', 'en'), data.get('photo_ids', [])

    user_data = get_user_data(uid)
    priority = 1 if user_data[2] > 1 else 0
    # Один Batch ID для всього альбому!
    batch_id = f"b_{uuid.uuid4().hex[:6]}"

    try:
        await bot.delete_message(uid, data.get('msg_to_del'))
    except:
        pass

    await callback.message.answer(get_t(lang, 'processing', count=len(p_ids)))

    # Папки
    base = os.getcwd()
    target_dir = os.path.join(base, "tmp", func_name, "input")
    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(os.path.join(base, "tmp", func_name, "output"), exist_ok=True)

    # Завантаження (пряме)
    for p_id in p_ids:
        f_unique = f"{uid}_{uuid.uuid4().hex[:6]}.png"
        path = os.path.join(target_dir, f_unique)
        f_info = await bot.get_file(p_id)
        await bot.download_file(f_info.file_path, path)
        add_task(uid, f_unique, func_name, priority, batch_id)

    # Старт воркера
    worker_script = os.path.join(base, "modules", f"{func_name}.py")
    if os.path.exists(worker_script):
        subprocess.Popen([sys.executable, worker_script])

    await state.clear()


# --- 3. ЛОГІКА BGCHANGER (Очікування фону) ---
@router.callback_query(F.data == "func:bgchanger", ProcessState.ready_to_start)
async def ask_for_bg(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    lang = (await state.get_data()).get('lang', 'en')
    await callback.message.edit_text(get_t(lang, 'bg_send_new'))
    await state.set_state(ProcessState.waiting_for_background)


# --- 4. ПРИЙОМ ФОНУ ТА ФІНАЛЬНИЙ СТАРТ ---
@router.message(F.photo, ProcessState.waiting_for_background)
async def handle_background(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    bg_id = message.photo[-1].file_id

    data = await state.get_data()
    obj_ids, lang = data.get('photo_ids', []), data.get('lang', 'en')
    u_info = get_user_data(uid)

    # Один Batch ID об'єднує і об'єкти, і фон!
    batch_id = f"bg_{uuid.uuid4().hex[:6]}"

    await message.answer(get_t(lang, 'processing', count=len(obj_ids)))

    target_dir = os.path.join(os.getcwd(), "tmp", "bgchanger", "input")
    os.makedirs(target_dir, exist_ok=True)

    priority = 1 if u_info[2] > 1 else 0

    # Спочатку завантажуємо об'єкти
    for i, p_id in enumerate(obj_ids):
        f_obj = f"{uid}_part_{i}_{uuid.uuid4().hex[:4]}.png"
        await bot.download_file((await bot.get_file(p_id)).file_path, os.path.join(target_dir, f_obj))
        add_task(uid, f_obj, "bgchanger", priority, batch_id)

    # Останнім качаємо фон (воркер бере [-1])
    f_bg = f"{uid}_FINAL_BG.png"
    await bot.download_file((await bot.get_file(bg_id)).file_path, os.path.join(target_dir, f_bg))
    add_task(uid, f_bg, "bgchanger", priority, batch_id)

    # Пуск воркера bgchanger.py
    subprocess.Popen([sys.executable, os.path.join(os.getcwd(), "modules", "bgchanger.py")])
    await state.clear()


# --- 5. ОБРОБНИК ІНШИХ ФУНКЦІЙ (Upscaler / Mirror) ---
@router.callback_query(F.data.startswith("func:"), ProcessState.ready_to_start)
async def other_functions_logic(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    func = callback.data.split(":")[1]
    await run_common_logic(callback, state, callback.bot, func)