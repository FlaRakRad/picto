import asyncio, os, uuid, subprocess, sys
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.fsm_states import ProcessState
from keyboards.photo import get_functions_kb
from locales.i18n import get_t
from database.requests import get_user_data, add_task

router = Router()
storage = {}  # Тимчасове сховище ID файлів у RAM


# --- 1. ПРИЙОМ ОСНОВНИХ ФОТО (ОБ'ЄКТІВ) ---
@router.message(F.photo, ProcessState.waiting_for_photos)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id
    if uid not in storage: storage[uid] = []

    storage[uid].append(message.photo[-1].file_id)
    captured_count = len(storage[uid])

    await asyncio.sleep(3)

    if uid not in storage or len(storage[uid]) > captured_count:
        return

    photo_ids = storage.pop(uid)
    user_info = get_user_data(uid)
    lang = user_info[3] if user_info else 'en'

    # Зберігаємо список ID у стані
    await state.update_data(photo_ids=photo_ids, lang=lang)

    m = await message.answer(
        get_t(lang, 'batch_received', count=len(photo_ids)),
        reply_markup=get_functions_kb(lang)
    )
    await state.update_data(msg_to_del=m.message_id)
    await state.set_state(ProcessState.ready_to_start)


# --- 2. ДОПОМІЖНА ФУНКЦІЯ (ДЛЯ UPSCALER / MIRROR) ---
async def run_common_logic(callback: CallbackQuery, state: FSMContext, bot: Bot, func_name: str):
    uid = callback.from_user.id
    data = await state.get_data()
    lang, p_ids = data.get('lang', 'en'), data.get('photo_ids', [])

    user_data = get_user_data(uid)
    priority = 1 if (user_data and user_data[2] > 1) else 0
    batch_id = f"b_{uuid.uuid4().hex[:6]}"

    try:
        await bot.delete_message(uid, data.get('msg_to_del'))
    except:
        pass

    await callback.message.answer(get_t(lang, 'processing', count=len(p_ids)))

    target_dir = os.path.join(os.getcwd(), "tmp", func_name, "input")
    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(os.path.join(os.getcwd(), "tmp", func_name, "output"), exist_ok=True)

    # Пряме завантаження
    for p_id in p_ids:
        unique_name = f"{uid}_{uuid.uuid4().hex[:6]}.png"
        path = os.path.join(target_dir, unique_name)
        f_info = await bot.get_file(p_id)
        await bot.download_file(f_info.file_path, path)
        add_task(uid, unique_name, func_name, priority, batch_id)

    # Пуск воркера
    worker_script = os.path.join(os.getcwd(), "modules", f"{func_name}.py")
    if os.path.exists(worker_script):
        subprocess.Popen([sys.executable, worker_script])

    await state.clear()


# --- 3. ЛОГІКА BGCHANGER (ПЕРЕХІД ДО ОЧІКУВАННЯ ФОНУ) ---
@router.callback_query(F.data == "func:bgchanger", ProcessState.ready_to_start)
async def ask_for_bg(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = data.get('lang', 'en')

    # Просимо юзера скинути фон (Додай цей ключ у locales/uk.py: 'bg_send_new')
    await callback.message.edit_text(get_t(lang, 'bg_send_new'))

    # Змінюємо стан на очікування фону
    await state.set_state(ProcessState.waiting_for_background)


# --- 4. ПРИЙОМ ФОНУ ТА ФІНАЛЬНИЙ СТАРТ ---
@router.message(F.photo, ProcessState.waiting_for_background)
async def handle_background(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    bg_file_id = message.photo[-1].file_id

    data = await state.get_data()
    obj_ids = data.get('photo_ids', [])  # Ті самі об'єкти, що юзер кинув раніше
    lang = data.get('lang', 'en')

    user_data = get_user_data(uid)
    priority = 1 if (user_data and user_data[2] > 1) else 0
    batch_id = f"bg_{uuid.uuid4().hex[:6]}"

    await message.answer(get_t(lang, 'processing', count=len(obj_ids)))

    # Папки для bgchanger
    target_dir = os.path.join(os.getcwd(), "tmp", "bgchanger", "input")
    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(os.path.join(os.getcwd(), "tmp", "bgchanger", "output"), exist_ok=True)

    # А) Качаємо ОБ'ЄКТИ спочатку (щоб ID в БД були менші)
    for idx, p_id in enumerate(obj_ids):
        name = f"{uid}_{idx}_obj_{uuid.uuid4().hex[:4]}.png"
        path = os.path.join(target_dir, name)
        await bot.download_file((await bot.get_file(p_id)).file_path, path)
        add_task(uid, name, "bgchanger", priority, batch_id)

    # Б) Качаємо ФОН останнім (він буде rows[-1] у воркері)
    bg_name = f"{uid}_final_BG_{uuid.uuid4().hex[:4]}.png"
    await bot.download_file((await bot.get_file(bg_file_id)).file_path, os.path.join(target_dir, bg_name))
    add_task(uid, bg_name, "bgchanger", priority, batch_id)

    # В) Запуск воркера
    subprocess.Popen([sys.executable, os.path.join(os.getcwd(), "modules", "bgchanger.py")])

    await state.clear()
    print(f"[SYSTEM] Пачка {batch_id} (фон+об'єкти) готова до ШІ.")


# --- 5. ОБРОБНИК ІНШИХ ФУНКЦІЙ (Upscaler / Mirror) ---
@router.callback_query(F.data.startswith("func:"), ProcessState.ready_to_start)
async def other_functions_logic(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    func_name = callback.data.split(":")[1]
    await run_common_logic(callback, state, callback.bot, func_name)