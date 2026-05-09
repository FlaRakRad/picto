import asyncio, os, uuid, subprocess, sys
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.fsm_states import ProcessState
from keyboards.photo import get_functions_kb
from locales.i18n import get_t
from database.requests import get_user_data, add_task

router = Router()
storage = {}
# Абсолютний корінь проекту
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@router.message(F.photo, ProcessState.waiting_for_photos)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id
    if uid not in storage: storage[uid] = []
    storage[uid].append(message.photo[-1].file_id)

    curr_len = len(storage[uid])
    await asyncio.sleep(3)  # Чекаємо збору всієї пачки
    if uid not in storage or len(storage[uid]) > curr_len: return

    photo_ids = storage.pop(uid)
    user = get_user_data(uid)
    lang = user[3] if user else 'en'

    await state.update_data(photo_ids=photo_ids, lang=lang)
    m = await message.answer(get_t(lang, 'batch_received', count=len(photo_ids)), reply_markup=get_functions_kb(lang))
    await state.update_data(msg_to_del=m.message_id)
    await state.set_state(ProcessState.ready_to_start)


@router.callback_query(F.data.startswith("func:"), ProcessState.ready_to_start)
async def start_logic(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    uid, func = callback.from_user.id, callback.data.split(":")[1]
    data = await state.get_data()
    p_ids, lang = data.get('photo_ids', []), data.get('lang', 'en')
    batch_id = f"b_{uuid.uuid4().hex[:6]}"

    try:
        await bot.delete_message(uid, data.get('msg_to_del'))
    except:
        pass
    await callback.message.answer(get_t(lang, 'processing', count=len(p_ids)))

    target_dir = os.path.join(BASE_DIR, "tmp", func, "input")
    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "tmp", func, "output"), exist_ok=True)

    priority = 1 if (get_user_data(uid) or [0, 0, 0])[2] > 1 else 0

    for p_id in p_ids:
        f_unique = f"{uid}_{uuid.uuid4().hex[:6]}.png"
        path = os.path.join(target_dir, f_unique)
        file_info = await bot.get_file(p_id)
        await bot.download_file(file_info.file_path, path)
        add_task(uid, f_unique, func, priority, batch_id)

    # Автозапуск воркера (назва воркера = назва функциї)
    script = os.path.join(BASE_DIR, "modules", f"{func}.py")
    if os.path.exists(script):
        subprocess.Popen([sys.executable, script])

    await state.clear()