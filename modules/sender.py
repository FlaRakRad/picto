import asyncio

import sys
import os

# Додаємо кореневу папку проекту до шляху пошуку модулів
# os.path.abspath(__file__) - це шлях до цього скрипта
# подвійний dirname підіймає нас на рівень вище (в корінь проекту)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aiogram import Bot
from aiogram.types import BufferedInputFile
import my_token
from database.requests import get_conn, get_user_data, consume_one
from locales.i18n import get_t


async def sender():
    bot = Bot(token=my_token.TOKEN)
    print("📨 [SENDER] Універсальний модуль відправки запущено...")

    while True:
        try:
            conn = get_conn()
            cur = conn.cursor()

            # Шукаємо завдання, які готові (done), але ще не видалені з черги
            cur.execute("SELECT id, user_id, function, output_name FROM tasks WHERE status = 'done'")
            ready_tasks = cur.fetchall()

            for task_id, uid, func, out_name in ready_tasks:
                # Динамічний шлях на основі назви функції!
                path = os.path.join(os.getcwd(), "tmp", func, "output", out_name)

                print(f"[SENDER] Шукаю результат {func} за шляхом: {path}")

                if os.path.exists(path):
                    # Дізнаємося мову юзера
                    u_data = get_user_data(uid)
                    lang = u_data[3] if u_data else 'en'

                    # Читаємо та надсилаємо
                    with open(path, "rb") as f:
                        file_to_send = BufferedInputFile(f.read(), filename=out_name)
                        await bot.send_document(uid, file_to_send, caption=get_t(lang, 'done'))

                    # Списуємо 1 ліміт
                    consume_one(uid)

                    # Очищення
                    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                    conn.commit()
                    os.remove(path)
                    print(f"✅ [SENDER] Результат '{func}' відправлено юзеру {uid}")
                else:
                    print(f"⚠️ [SENDER] Упс! В БД статус 'done', але файл за шляхом {path} не знайдено.")

            conn.close()
        except Exception as e:
            print(f"❌ [SENDER] ПОМИЛКА: {e}")

        await asyncio.sleep(3)  # Відпочиваємо 3 сек і знову заглядаємо в БД


if __name__ == "__main__":
    asyncio.run(sender())