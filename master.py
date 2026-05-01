import asyncio
from aiogram import Bot, Dispatcher
import my_token
from handlers.photo_handler import router
from database.requests import db_init


async def main():
    db_init()
    bot = Bot(token=my_token.TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    print("🚀 Бот запущений!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())