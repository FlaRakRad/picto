import asyncio, os, uuid, shutil, subprocess, sys
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.fsm_states import ProcessState
from keyboards.main_menu import get_start_process_kb
from locales.i18n import get_t
from database.requests import get_user_data, add_task

router = Router()
storage = {}
QUEUE_DIR = os.path.join(os.getcwd(), "tmp", "queue")


@router.message(F.photo, ProcessState.waiting_for_photos)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id
    if uid not in storage: storage[uid] = []

    f_uuid = f"{uid}_{uuid.uuid4().hex[:8]}.png"
    path = os.path.join(QUEUE_DIR, f_uuid)

    f_info = await message.bot.get_file(message.photo[-1].file_id)
    await message.bot.download_file(f_info.file_path, path)
    storage[uid].append(f_uuid)

    curr_len = len(storage[uid])
    await asyncio.sleep(2.5)  # Акумуляція
    if len(storage[uid]) > curr_len: return

    user_data = get_user_data(uid)
    lang = user_data[3] if user_data else 'en'
    priority = 1 if user_data and user_data[2] > 1 else 0

    p_ids = storage[uid].copy()
    await state.update_data(photo_ids=p_ids, lang=lang, priority=priority)

    # Видаємо повідомлення з кнопкою
    m = await message.answer(get_t(lang, 'batch_received', count=len(p_ids)),
                             reply_markup=get_start_process_kb(lang))

    # Зберігаємо дані для видалення кнопки та переходимо у стан старту
    await state.update_data(msg_to_del=m.message_id)
    await state.set_state(ProcessState.ready_to_start)


# ТОЙ САМИЙ ОБРОБНИК, ЯКИЙ МАЄ ВІДПОВІДАТИ НА КНОПКУ
@router.callback_query(F.data == "run_upscale", ProcessState.ready_to_start)
async def start_upscale_fixed(callback: CallbackQuery, state: FSMContext, bot: Bot):
    # ПЕРШЕ: кажемо Телеграму, що ми прийняли сигнал (прибирає сіре підвисання)
    await callback.answer()

    uid = callback.from_user.id
    data = await state.get_data()
    lang = data.get('lang', 'en')
    p_ids = data.get('photo_ids', [])
    priority = data.get('priority', 0)
    msg_id = data.get('msg_to_del')

    # Видаляємо кнопку
    try:
        await bot.delete_message(uid, msg_id)
    except:
        pass

    await callback.message.answer(get_t(lang, 'processing', count=len(p_ids)))

    for f_name in p_ids:
        # ПЕРЕМІЩУЄМО в input нашого воркера upscaler
        target_dir = os.path.join(os.getcwd(), "tmp", "upscaler", "input")
        os.makedirs(target_dir, exist_ok=True)

        source = os.path.join(QUEUE_DIR, f_name)
        target = os.path.join(target_dir, f_name)

        if os.path.exists(source):
            shutil.move(source, target)
            add_task(uid, f_name, "upscaler", priority)  # Пишемо 'upscaler'

    # Очищуємо storage і запускаємо скрипт
    storage.pop(uid, None)
    worker_script = os.path.join(os.getcwd(), "modules", "upscaler.py")
    subprocess.Popen([sys.executable, worker_script])

    await state.clear()