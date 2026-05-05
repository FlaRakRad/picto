import asyncio
from aiogram import Bot, Dispatcher
import my_token
from handlers.photo_handler import router as photo_router
from handlers.common import router as common_router
from database.requests import db_init


async def main():
    print("\n" + "=" * 30)
    print("🚀 ПІКТОБОТ ЗАПУСКАЄТЬСЯ")
    print("=" * 30)

    db_init()
    print("[DB] База даних ініціалізована.")

    bot = Bot(token=my_token.TOKEN)
    dp = Dispatcher()

    dp.include_router(common_router)
    dp.include_router(photo_router)

    print("[SYSTEM] Роутери підключені. Починаю polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[SYSTEM] Бот вимкнений вручну.")