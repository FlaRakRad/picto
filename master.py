import asyncio, subprocess, sys, os
from aiogram import Bot, Dispatcher
import my_token
from handlers.photo_handler import router as photo_router
from handlers.common import router as common_router
from database.requests import db_init


async def main():
    db_init()
    # Автозапуск сендера
    subprocess.Popen([sys.executable, os.path.join("modules", "sender.py")])

    bot = Bot(token=my_token.TOKEN)
    dp = Dispatcher()
    dp.include_router(common_router)
    dp.include_router(photo_router)

    print("🚀 PictoBot запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())