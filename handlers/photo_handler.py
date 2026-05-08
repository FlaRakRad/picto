import asyncio, os, uuid, subprocess, sys
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.fsm_states import ProcessState
from keyboards.photo import get_functions_kb
from locales.i18n import get_t
from database.requests import get_user_data, add_task

router = Router()
storage = {}  # {uid: [file_id1, file_id2, ...]}


@router.message(F.photo, ProcessState.waiting_for_photos)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id
    if uid not in storage: storage[uid] = []

    storage[uid].append(message.photo[-1].file_id)

    # Скільки фото ми вже отримали в цей момент
    captured_count = len(storage[uid])

    # Чекаємо 3 секунди (трішки більше для надійності при великих пачках)
    await asyncio.sleep(3)

    # ПЕРЕВІРКА НА ДУБЛІКАТИ (Ключовий момент)
    # Якщо за 3 секунди кількість фото в сховищі збільшилась -
    # значить це не остання функція, вона має вийти
    if uid not in storage or len(storage[uid]) > captured_count:
        return

    # Якщо ми тут, значить ми - остання запущена функція для цього юзера.
    # Миттєво забираємо дані і ОЧИЩАЄМО глобальне сховище
    final_ids = storage.pop(uid)

    print(f"[COLLECTOR] ✅ Пачка зібрана для {uid}. Всього: {len(final_ids)} фото.")

    user_data = get_user_data(uid)
    lang = user_data[3] if user_data else 'en'

    # Зберігаємо ID у стані
    await state.update_data(photo_ids=final_ids, lang=lang)

    m = await message.answer(
        get_t(lang, 'batch_received', count=len(final_ids)),
        reply_markup=get_functions_kb(lang)
    )
    await state.update_data(msg_to_del=m.message_id)
    await state.set_state(ProcessState.ready_to_start)


@router.callback_query(F.data.startswith("func:"), ProcessState.ready_to_start)
async def start_function_logic(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()

    uid = callback.from_user.id
    func_name = callback.data.split(":")[1]

    data = await state.get_data()
    lang = data.get('lang', 'en')
    # ТУТ ми дістаємо фінальний список (він точно 10 штук, а не 20)
    p_ids = data.get('photo_ids', [])

    user_data = get_user_data(uid)
    priority = 1 if user_data and user_data[2] > 1 else 0

    try:
        await bot.delete_message(uid, data.get('msg_to_del'))
    except:
        pass

    # Повідомляємо юзеру реальну кількість
    await callback.message.answer(get_t(lang, 'processing', count=len(p_ids)))
    print(f"[SYSTEM] Завантажую {len(p_ids)} фото для {func_name}...")

    target_dir = os.path.join(os.getcwd(), "tmp", func_name, "input")
    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(os.path.join(os.getcwd(), "tmp", func_name, "output"), exist_ok=True)

    # КАЧАЄМО
    for p_id in p_ids:
        # Унікальний UUID на кожне фото, щоб вони не злипалися
        f_unique = f"{uid}_{uuid.uuid4().hex[:6]}.png"
        path = os.path.join(target_dir, f_unique)

        try:
            f_info = await bot.get_file(p_id)
            await bot.download_file(f_info.file_path, path)
            add_task(uid, f_unique, func_name, priority)
        except Exception as e:
            print(f"[ERROR] Помилка на фото: {e}")

    # Запускаємо скрипт-воркер
    worker_script = os.path.join(os.getcwd(), "modules", f"{func_name}.py")
    if os.path.exists(worker_script):
        subprocess.Popen([sys.executable, worker_script])

    # Обов'язково чистимо все в кінці
    await state.clear()