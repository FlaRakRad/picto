import asyncio
from aiogram import Bot, Dispatcher
import my_token
from handlers.photo_handler import router as photo_router
from handlers.common import router as common_router # файл з кнопками меню
from database.requests import db_init

async def main():
    db_init()
    bot = Bot(token=my_token.TOKEN)
    dp = Dispatcher()

    # Підключаємо роутери
    dp.include_router(photo_router)
    dp.include_router(common_router)

    print("🚀 Бот запущений!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())