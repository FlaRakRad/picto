import asyncio, os
from aiogram import Bot
from aiogram.types import BufferedInputFile
import my_token  # Переконайся, що цей файл існує
from database.requests import get_conn, get_user_data, consume_one
from locales.i18n import get_t


async def sender():
    bot = Bot(token=my_token.TOKEN)
    while True:
        conn = get_conn();
        cur = conn.cursor()
        # Шукаємо готові завдання
        cur.execute("SELECT id, user_id, function, output_name FROM tasks WHERE status = 'done'")
        tasks = cur.fetchall()

        for t_id, uid, func, out_name in tasks:
            try:
                path = f"tmp/{func}/output/{out_name}"
                u_data = get_user_data(uid)
                lang = u_data[3] if u_data else 'en'

                if os.path.exists(path):
                    with open(path, "rb") as f:
                        file = BufferedInputFile(f.read(), filename=out_name)
                        await bot.send_document(uid, file, caption=get_t(lang, 'done'))

                    consume_one(uid)
                    conn.execute("DELETE FROM tasks WHERE id = ?", (t_id,))
                    conn.commit()
                    os.remove(path)
            except Exception as e:
                print(f"Error sending: {e}")

        conn.close()
        await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(sender())