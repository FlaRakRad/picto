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
# Абсолютний шлях до черги оригіналів
QUEUE_DIR = os.path.join(os.getcwd(), "tmp", "queue")
os.makedirs(QUEUE_DIR, exist_ok=True)


@router.message(F.photo, ProcessState.waiting_for_photos)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id
    if uid not in storage: storage[uid] = []

    # Створюємо унікальне ім'я для файлу в черзі
    f_uuid = f"{uid}_{uuid.uuid4().hex[:8]}.png"
    path = os.path.join(QUEUE_DIR, f_uuid)

    try:
        f_info = await message.bot.get_file(message.photo[-1].file_id)
        await message.bot.download_file(f_info.file_path, path)
        storage[uid].append(f_uuid)
        print(f"[PHOTO] 📥 Збережено в queue: {f_uuid}")
    except Exception as e:
        print(f"[ERROR] Не вдалося завантажити фото: {e}")

    # Акумуляція (ждемо 2.5 сек поки долетять всі фото з пачки)
    curr_len = len(storage[uid])
    await asyncio.sleep(2.5)
    if len(storage[uid]) > curr_len:
        return

    # Якщо ми тут - пачка зібрана
    user_data = get_user_data(uid)
    lang = user_data[3] if user_data else 'en'
    priority = 1 if user_data and user_data[2] > 1 else 0

    p_ids = storage[uid].copy()
    await state.update_data(photo_ids=p_ids, lang=lang, priority=priority)

    # Виводимо повідомлення з кнопкою початку обробки
    m = await message.answer(
        get_t(lang, 'batch_received', count=len(p_ids)),
        reply_markup=get_start_process_kb(lang)
    )
    await state.update_data(msg_to_del=m.message_id)
    await state.set_state(ProcessState.ready_to_start)


@router.callback_query(F.data == "run_upscale", ProcessState.ready_to_start)
async def start_upscale(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()