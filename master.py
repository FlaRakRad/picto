import asyncio
import subprocess
import sys
import os
from aiogram import Bot, Dispatcher
import my_token
from handlers.photo_handler import router as photo_router
from handlers.common import router as common_router
from database.requests import db_init

async def main():
    # 1. Ініціалізуємо базу даних
    db_init()
    print("[SYSTEM] База даних готова.")

    # 2. ЗАПУСК МОДУЛЯ ВІДПРАВКИ (SENDER)
    # Ми запускаємо його один раз, він має свій цикл і буде працювати весь час
    print("[SYSTEM] Запуск модуля відправки (sender.py)...")
    sender_path = os.path.join(os.getcwd(), "modules", "sender.py")
    subprocess.Popen([sys.executable, sender_path])

    # 3. ЗАПУСК БОТА
    bot = Bot(token=my_token.TOKEN)
    dp = Dispatcher()

    # Підключаємо роутери
    dp.include_router(common_router)
    dp.include_router(photo_router)

    print("\n" + "="*30)
    print("🚀 ПІКТОБОТ ЗАПУЩЕНИЙ")
    print("="*30)

    # Починаємо прослуховування Telegram
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[SYSTEM] Роботу зупинено вручну.")