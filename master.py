import asyncio, subprocess, sys, os
from aiogram import Bot, Dispatcher
import my_token
from handlers.photo_handler import router as photo_router
from handlers.common import router as common_router
from database.requests import db_init, db_check
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from handlers.billing_handler import router as billing_handler_router

async def main():
    db_init()
    db_check()
    # Автозапуск сендера
    subprocess.Popen([sys.executable, os.path.join("modules", "sender.py")])

    bot = Bot(
        token=my_token.TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    dp.include_router(billing_handler_router)
    dp.include_router(common_router)
    dp.include_router(photo_router)

    print("🚀 PictoBot запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())