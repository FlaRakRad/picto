import asyncio, os, sys
from aiogram import Bot
from aiogram.types import BufferedInputFile, InputMediaDocument

# Фікс шляхів
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import my_token
from database.requests import get_conn, get_user_data, consume_one
from locales.i18n import get_t


async def sender():
    bot = Bot(token=my_token.TOKEN)
    print("📨 [SENDER] Система видачі альбомів запущена...")

    while True:
        try:
            conn = get_conn();
            cur = conn.cursor()

            # Шукаємо пачки (batch_id), де ВЗАГАЛІ немає статусів 'pending' або 'processing'
            # Але є хоча б одне готове фото ('done')
            cur.execute("""
                SELECT batch_id, user_id, function FROM tasks 
                GROUP BY batch_id 
                HAVING COUNT(CASE WHEN status IN ('pending', 'processing') THEN 1 END) = 0
                AND COUNT(CASE WHEN status = 'done' THEN 1 END) > 0
            """)
            ready_batches = cur.fetchall()

            for b_id, uid, func in ready_batches:
                # Беремо тільки ті файли, які реально треба відправити (status = 'done')
                cur.execute("SELECT id, output_name FROM tasks WHERE batch_id=? AND status='done'", (b_id,))
                ready_photos = cur.fetchall()

                lang = (get_user_data(uid) or [None, None, None, 'en'])[3]
                media = []

                for t_id, out_name in ready_photos:
                    path = os.path.join(BASE_DIR, "tmp", func, "output", out_name)
                    if os.path.exists(path):
                        with open(path, "rb") as f:
                            media.append(InputMediaDocument(media=BufferedInputFile(f.read(), filename=out_name)))

                if media:
                    print(f"📦 [SENDER] Відправляю альбом для {uid} (Пачка: {b_id}, Фото: {len(media)})")
                    # Telegram обмеження - макс 10 у групі
                    for i in range(0, len(media), 10):
                        chunk = media[i:i + 10]
                        if i == 0: chunk[0].caption = get_t(lang, 'done')
                        await bot.send_media_group(chat_id=uid, media=chunk)

                    # ЧИЩЕННЯ БАЗИ ТА ФАЙЛІВ
                    consume_one(uid, len(media))
                    # Видаляємо всі записи цього батчу (включаючи фони та помилкові)
                    conn.execute("DELETE FROM tasks WHERE batch_id = ?", (b_id,))
                    conn.commit()

                    # Видаляємо фізичні файли
                    for m_doc in media:
                        # Дістаємо ім'я файлу з об'єкта медіа
                        p_to_del = os.path.join(BASE_DIR, "tmp", func, "output", m_doc.media.filename)
                        if os.path.exists(p_to_del): os.remove(p_to_del)
                else:
                    # Якщо запис 'done' є, а файлу на диску нема - чистимо базу, щоб не зациклитись
                    conn.execute("DELETE FROM tasks WHERE batch_id = ?", (b_id,))
                    conn.commit()

            conn.close()
        except Exception as e:
            print(f"❌ [SENDER ERROR]: {e}")

        await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(sender())