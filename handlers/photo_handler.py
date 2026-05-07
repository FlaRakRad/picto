import asyncio, os, sys, subprocess, uuid
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InputMediaDocument, BufferedInputFile
from aiogram.fsm.context import FSMContext
from keyboards.main_menu import get_start_process_kb
from locales.i18n import get_t
from database.requests import get_user_data, consume_one

router = Router()
storage = {}


@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id
    user = get_user_data(uid)
    lang = user[3] if user else 'en'

    if uid not in storage: storage[uid] = []
    storage[uid].append(message.photo[-1].file_id)

    # Акумуляція (ждемо 2.5 сек)
    count = len(storage[uid])
    await asyncio.sleep(2.5)
    if len(storage[uid]) > count: return

    # Зібрали всі фото
    p_ids = storage[uid].copy()
    await state.update_data(p_ids=p_ids, lang=lang)

    # Виводимо кнопку старту
    m = await message.answer(get_t(lang, 'batch_received', count=len(p_ids)),
                             reply_markup=get_start_process_kb(lang))
    await state.update_data(msg_to_del=m.message_id)


@router.callback_query(F.data == "run_upscale")
async def run_upscale(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    uid, lang, p_ids = callback.from_user.id, data.get('lang', 'en'), data.get('p_ids', [])

    # Видаляємо повідомлення з кнопкою
    try:
        await bot.delete_message(uid, data.get('msg_to_del'))
    except:
        pass

    status_msg = await callback.message.answer(get_t(lang, 'processing', count=len(p_ids)))

    storage.pop(uid, None)
    stems = []

    try:
        # 1. Завантаження
        for i, f_id in enumerate(p_ids):
            f = await bot.get_file(f_id);
            b = await bot.download_file(f.file_path)
            stem = f"{uid}_{uuid.uuid4().hex[:4]}";
            stems.append(stem)
            with open(f"tmp/input/{stem}.png", "wb") as file: file.write(b.getvalue())

        # 2. Виклик апскейлера ( subprocess чекає завершення)
        subprocess.run([sys.executable, "modules/upscaller.py"])

        # 3. Відправка альбомом
        media = []
        for s in stems:
            path = f"tmp/output/up_{s}.png"
            if os.path.exists(path):
                with open(path, "rb") as f:
                    media.append(InputMediaDocument(media=BufferedInputFile(f.read(), filename=f"up_{s}.png")))
                os.remove(path);
                consume_one(uid)

        if media:
            for i in range(0, len(media), 10):
                await bot.send_media_group(chat_id=uid, media=media[i:i + 10])
            await callback.message.answer(get_t(lang, 'done'))

        await status_msg.delete()  # Видаляємо "Обробка..."

    except Exception as e:
        await callback.message.answer(get_t(lang, 'error'))

    await state.clear()