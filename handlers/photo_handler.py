import asyncio, os, uuid, subprocess, sys
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.fsm_states import ProcessState
from keyboards.photo import get_functions_kb
from locales.i18n import get_t
from database.requests import get_user_data, add_task, check_reset_limit, upsert_user
from datetime import datetime
router = Router()
storage = {}


@router.message(F.photo, ProcessState.waiting_for_photos)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id
    nxt = check_reset_limit(uid)
    u = get_user_data(uid)
    if not u: upsert_user(uid, message.from_user.first_name); u = get_user_data(uid)

    # 1. ПЕРША ПЕРЕВІРКА (на самому початку)
    if u[0] <= 0:
        diff = nxt - datetime.now()
        mins_left = int(diff.total_seconds() // 60)
        return await message.answer(get_t(u[3], 'batch_limit_error',
                                          limit=u[0],
                                          count="?",
                                          time=nxt.strftime("%H:%M"),
                                          minutes=mins_left))

    if uid not in storage: storage[uid] = []
    storage[uid].append(message.photo[-1].file_id)
    c = len(storage[uid])
    await asyncio.sleep(3.5)

    if uid not in storage or len(storage[uid]) > c: return
    p_ids = storage.pop(uid)

    # 2. ДРУГА ПЕРЕВІРКА (після збору пачки) - ОСЬ ТУТ БУЛА ПОМИЛКА
    if len(p_ids) > u[0]:
        diff = nxt - datetime.now()
        mins_left = int(diff.total_seconds() // 60)
        return await message.answer(get_t(u[3], 'batch_limit_error',
                                          limit=u[0],
                                          count=len(p_ids),
                                          time=nxt.strftime("%H:%M"),
                                          minutes=mins_left))  # ДОДАВ МИНУТЫ СЮДИ!

    # Якщо все ок, далі йде виклик меню...
    await state.update_data(photo_ids=p_ids, lang=u[3])
    m = await message.answer(get_t(u[3], 'batch_received', count=len(p_ids)), reply_markup=get_functions_kb(u[3]))
    await state.update_data(msg_to_del=m.message_id)
    await state.set_state(ProcessState.ready_to_start)
    await message.answer(get_t(u[3], 'next_cycle', time=nxt.strftime("%H:%M")))


# Допоміжна функція розкидання файлів
async def run_common_logic(callback: CallbackQuery, state: FSMContext, bot: Bot, func_name: str):
    d = await state.get_data();
    uid = callback.from_user.id
    p_ids, lang = d.get('photo_ids', []), d.get('lang', 'en')
    u = get_user_data(uid)
    batch_id = f"b_{uuid.uuid4().hex[:6]}"

    try:
        await bot.delete_message(uid, d.get('msg_to_del'))
    except:
        pass
    await callback.message.answer(get_t(lang, 'processing', count=len(p_ids)))

    target_dir = os.path.join(os.getcwd(), "tmp", func_name, "input")
    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(os.path.join(os.getcwd(), "tmp", func_name, "output"), exist_ok=True)

    for p_id in p_ids:
        f_name = f"{uid}_{uuid.uuid4().hex[:6]}.png"
        path = os.path.join(target_dir, f_name)
        f_info = await bot.get_file(p_id)
        await bot.download_file(f_info.file_path, path)
        add_task(uid, f_name, func_name, (1 if u[2] > 1 else 0), batch_id)

    worker_script = os.path.join(os.getcwd(), "modules", f"{func_name}.py")
    if os.path.exists(worker_script):
        subprocess.Popen([sys.executable, worker_script])

    await state.clear()


@router.callback_query(F.data == "func:bgchanger", ProcessState.ready_to_start)
async def ask_bg(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    lang = (await state.get_data()).get('lang', 'en')
    await callback.message.edit_text(get_t(lang, 'bg_send_new'))
    await state.set_state(ProcessState.waiting_for_background)


@router.message(F.photo, ProcessState.waiting_for_background)
async def handle_bg_final(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    d = await state.get_data()
    obj_ids, lang = d.get('photo_ids', []), d.get('lang', 'en')
    u = get_user_data(uid);
    bid = f"bg_{uuid.uuid4().hex[:6]}"

    await message.answer(get_t(lang, 'processing', count=len(obj_ids)))
    tdir = os.path.join(os.getcwd(), "tmp", "bgchanger", "input");
    os.makedirs(tdir, exist_ok=True)

    # Качаємо Об'єкти
    for i, pid in enumerate(obj_ids):
        name = f"{uid}_{i}_obj.png";
        await bot.download_file((await bot.get_file(pid)).file_path, os.path.join(tdir, name))
        add_task(uid, name, "bgchanger", (1 if u[2] > 1 else 0), bid)

    # Качаємо Фон (останній)
    bgname = f"{uid}_FINAL_BG.png";
    await bot.download_file((await bot.get_file(message.photo[-1].file_id)).file_path, os.path.join(tdir, bgname))
    add_task(uid, bgname, "bgchanger", (1 if u[2] > 1 else 0), bid)

    subprocess.Popen([sys.executable, os.path.join(os.getcwd(), "modules", "bgchanger.py")])
    await state.clear()


@router.callback_query(F.data.startswith("func:"), ProcessState.ready_to_start)
async def start_any_func(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    func = callback.data.split(":")[1]
    await run_common_logic(callback, state, callback.bot, func)