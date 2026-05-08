import asyncio, os, sys
from aiogram import Bot
from aiogram.types import BufferedInputFile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import my_token
from database.requests import get_conn, get_user_data, consume_one
from locales.i18n import get_t

async def sender():
    bot = Bot(token=my_token.TOKEN)
    while True:
        try:
            conn = get_conn(); cur = conn.cursor()
            cur.execute("SELECT id, user_id, function, output_name FROM tasks WHERE status='done'")
            for task_id, uid, func, out_name in cur.fetchall():
                path = os.path.join(BASE_DIR, "tmp", func, "output", out_name)
                if os.path.exists(path):
                    # Отримуємо дані юзера
                    user_data = get_user_data(uid)
                    lang = user_data[3] if user_data else 'en'

                    with open(path, "rb") as f:
                        # ВИПРАВЛЕНО ТУТ: get_t без пробілу
                        await bot.send_document(
                            uid,
                            BufferedInputFile(f.read(), filename=out_name),
                            caption=get_t(lang, 'done')
                        )

                    consume_one(uid)
                    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
                    conn.commit()
                    os.remove(path)
                    print(f"[SENDER] Надіслано файл для {uid}")
        except:
            pass
        await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(sender())