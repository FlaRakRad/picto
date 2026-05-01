import asyncio
import importlib.util
import sys
from aiogram import Bot, Dispatcher
from handlers.photo_handler import router

# 1. Завантажуємо ваш my_token.py "магічним" способом, щоб уникнути конфліктів
try:
    spec = importlib.util.spec_from_file_location("my_token", "my_token.py")
    my_token_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(my_token_module)
    TOKEN = my_token_module.TOKEN
except Exception as e:
    print(f"❌ Помилка завантаження файлу token.py: {e}")
    sys.exit(1)


async def main():
    bot = Bot(token=TOKEN)

    # 2. Провірка старту (Чи бачить Телеграм бота з цим токеном)
    print("⏳ Перевірка підключення до Telegram...")
    try:
        bot_info = await bot.get_me()
        print(f"✅ Успішно! Бот: @{bot_info.username} готовий до роботи.")
    except Exception as e:
        print(f"❌ Не вдалося підключитися. Перевірте токен у файлі token.py")
        print(f"Технічна помилка: {e}")
        return

    dp = Dispatcher()
    dp.include_router(router)

    print("🚀 Master Node чекає на фото...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())