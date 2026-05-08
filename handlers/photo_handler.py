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

# Шляхи
QUEUE_DIR = os.path.join(os.getcwd(), "tmp", "queue")
os.makedirs(QUEUE_DIR, exist_ok=True)


# 1. ОБРОБКА ФОТО (тільки якщо юзер у стані waiting_for_photos)
@router.message(F.photo, ProcessState.waiting_for_photos)
async def handle_photo(message: Message, state: FSMContext):
    uid = message.from_user.id
    print(f"\n[PHOTO] 📥 Новий файл від {uid}")

    if uid not in storage: storage[uid] = []

    # ГЕНЕРУЄМО КРУТУ НАЗВУ: ID_UUID.png
    # Так ми відразу бачимо, чиє це фото в папці
    f_uuid = f"{uid}_{uuid.uuid4().hex[:8]}.png"
    target_path = os.path.join(QUEUE_DIR, f_uuid)

    try:
        f_info = await message.bot.get_file(message.photo[-1].file_id)
        await message.bot.download_file(f_info.file_path, target_path)
        storage[uid].append(f_uuid)
        print(f"[FILE] ✅ Збережено як: {f_uuid}")
    except Exception as e:
        print(f"[ERROR] ❌ Помилка завантаження: {e}")

    # Акумуляція (ждемо 2.5 сек)
    curr_len = len(storage[uid])
    await asyncio.sleep(2.5)

    if len(storage[uid]) > curr_len:
        # Хтось ще досилає фото, не зупиняємось
        return

    # --- ПАЧКА ЗІБРАНА ---
    photo_ids = storage[uid].copy()
    print(f"[BATCH] 📦 ПАЧКА ГОТОВА: {len(photo_ids)} шт від {uid}")

    user_data = get_user_data(uid)
    lang = user_data[3] if user_data else 'en'
    # Пріоритет (якщо в юзера max_limit > 1 — він VIP)
    priority = 1 if user_data and user_data[2] > 1 else 0

    await state.update_data(photo_ids=photo_ids, lang=lang, priority=priority)

    # Виводимо кнопку
    m = await message.answer(
        get_t(lang, 'batch_received', count=len(photo_ids)),
        reply_markup=get_start_process_kb(lang)
    )

    # ВАЖЛИВО: зберігаємо ID повідомлення та міняємо стан
    await state.update_data(msg_to_del=m.message_id)
    await state.set_state(ProcessState.ready_to_start)
    print(f"[FSM] Юзер {uid} тепер у стані: ready_to_start (чекаю кнопку)")

# 2. НАТИСКАННЯ НА КНОПКУ "СТАРТ"
@router.callback_query(F.data == "run_upscale", ProcessState.ready_to_start)
async def start_upscale(callback: CallbackQuery, state: FSMContext, bot: Bot):
    uid = callback.from_user.id
    print(f"\n[RUN] 🚀 СТАРТ ОБРОБКИ для юзера {uid}")

    data = await state.get_data()
    lang = data.get('lang', 'en')
    p_ids = data.get('photo_ids', [])
    priority = data.get('priority', 0)

    # Видаляємо повідомлення з кнопкою
    try:
        await bot.delete_message(uid, data.get('msg_to_del'))
    except:
        pass

    # Повідомлення про прогрес
    status_msg = await callback.message.answer(get_t(lang, 'processing', count=len(p_ids)))
    print(f"[RUN] Кількість завдань: {len(p_ids)}. Розкидаю по папках...")

    # РОЗКИДАЄМО В ПАПКИ
    for f_name in p_ids:
        source = os.path.join(QUEUE_DIR, f_name)
        target = f"tmp/upscaler/input/{f_name}"  # Переконайся, що папка існує!

        try:
            if not os.path.exists("tmp/upscaler/input"):
                os.makedirs("tmp/upscaler/input")
                print("[DIR] Створено відсутню папку input")

            shutil.copy(source, target)
            print(f"[TASK] Фото {f_name} копійовано -> upscaler/input")

            # Записуємо в БД завдання
            add_task(uid, f_name, "upscaler", priority)
            print(f"[DB] Завдання для {f_name} додано в чергу (Priority: {priority})")
        except Exception as e:
            print(f"[ERROR] ❌ Помилка на етапі постановки в чергу: {e}")

    storage.pop(uid, None)  # Чистимо за собою оперативку
    await state.clear()  # Скидаємо стан юзера - тепер він може знову тиснути меню
    print(f"[SUCCESS] ✅ Юзер {uid} успішно поставлений в чергу. FSM очищено.")
    print(f"[SYSTEM] Запускаю скрипт через систему...")

    # Варіант 1: Через лібу OS (найпростіший)
    # os.system(f"python modules/upscaler.py") # АЛЕ це заморозить бота до кінця обробки!

    # Варіант 2: Через subprocess (найправильніший для Windows/Linux)
    # Він запустить скрипт у фоні, бот зможе працювати далі, а скрипт почне "молотити" чергу
    try:
        worker_script = os.path.join(os.getcwd(), "modules", "upscaler.py")

        # Запускаємо процес паралельно
        # sys.executable — це шлях до твого пітона в системі (автоматично знайде venv, якщо ти в ньому)
        subprocess.Popen([sys.executable, worker_script])

        print("✅ Скрипт воркера активовано і запущено у фоні.")
    except Exception as e:
        print(f"❌ Не вдалося запустити воркер: {e}")