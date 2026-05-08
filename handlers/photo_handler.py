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


@router.message(F.photo, ProcessState.waiting_for_photos)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id
    if uid not in storage: storage[uid] = []
    storage[uid].append(message.photo[-1].file_id)

    captured_count = len(storage[uid])
    await asyncio.sleep(3)  # Час на довантаження великої пачки

    if uid not in storage or len(storage[uid]) > captured_count:
        return

    final_ids = storage.pop(uid)
    user_info = get_user_data(uid)
    lang = user_info[3] if user_info else 'en'

    await state.update_data(photo_ids=final_ids, lang=lang)
    m = await message.answer(get_t(lang, 'batch_received', count=len(final_ids)), reply_markup=get_functions_kb(lang))
    await state.update_data(msg_to_del=m.message_id)
    await state.set_state(ProcessState.ready_to_start)


@router.callback_query(F.data.startswith("func:"), ProcessState.ready_to_start)
async def start_logic(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    uid = callback.from_user.id
    func = callback.data.split(":")[1]

    data = await state.get_data()
    p_ids, lang = data.get('photo_ids', []), data.get('lang', 'en')

    # Генеруємо унікальний ID для цієї пачки
    batch_id = f"b_{uuid.uuid4().hex[:6]}"

    try:
        await bot.delete_message(uid, data.get('msg_to_del'))
    except:
        pass

    await callback.message.answer(get_t(lang, 'processing', count=len(p_ids)))

    target_dir = os.path.join(os.getcwd(), "tmp", func, "input")
    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(os.path.join(os.getcwd(), "tmp", func, "output"), exist_ok=True)

    priority = 1 if (get_user_data(uid) or [0, 0, 0])[2] > 1 else 0

    print(f"[SYSTEM] Початок завантаження пачки {batch_id} ({len(p_ids)} фото)")

    for p_id in p_ids:
        unique_name = f"{uid}_{uuid.uuid4().hex[:6]}.png"
        path = os.path.join(target_dir, unique_name)
        file_info = await bot.get_file(p_id)
        await bot.download_file(file_info.file_path, path)
        # Додаємо batch_id в БД
        add_task(uid, unique_name, func, priority, batch_id)

    # Запускаємо воркер
    worker_script = os.path.join(os.getcwd(), "modules", f"{func}.py")
    if os.path.exists(worker_script):
        subprocess.Popen([sys.executable, worker_script])

    await state.clear()