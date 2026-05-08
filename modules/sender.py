import asyncio, os, sys
from aiogram import Bot
from aiogram.types import BufferedInputFile, InputMediaDocument

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import my_token
from database.requests import get_conn, get_user_data, consume_one
from locales.i18n import get_t


async def sender():
    bot = Bot(token=my_token.TOKEN)
    print("📨 [SENDER] Скрипт розумної відправки запущено...")

    while True:
        try:
            conn = get_conn();
            cur = conn.cursor()

            # Шукаємо пачки, де КІЛЬКІСТЬ 'done' дорівнює ЗАГАЛЬНІЙ КІЛЬКОСТІ завдань у пачці
            # Це означає, що ВСІ фото в пачці оброблені
            cur.execute("""
                SELECT batch_id, user_id, function FROM tasks 
                GROUP BY batch_id 
                HAVING COUNT(id) = COUNT(CASE WHEN status = 'done' THEN 1 END)
            """)
            ready_batches = cur.fetchall()

            for b_id, uid, func in ready_batches:
                # Беремо всі записи цієї пачки
                cur.execute("SELECT id, output_name FROM tasks WHERE batch_id=?", (b_id,))
                ready_tasks = cur.fetchall()

                lang = (get_user_data(uid) or [None, None, None, 'en'])[3]
                media_group = []
                paths_to_remove = []
                ids_to_del = []

                for t_id, out_name in ready_tasks:
                    path = os.path.join(BASE_DIR, "tmp", func, "output", out_name)
                    if os.path.exists(path):
                        with open(path, "rb") as f:
                            media_group.append(InputMediaDocument(
                                media=BufferedInputFile(f.read(), filename=out_name)
                            ))
                        paths_to_remove.append(path)
                        ids_to_del.append(t_id)

                if media_group:
                    # Telegram обмеження: максимум 10 файлів в альбомі
                    for i in range(0, len(media_group), 10):
                        chunk = media_group[i:i + 10]
                        if i == 0: chunk[0].caption = get_t(lang, 'done')
                        await bot.send_media_group(chat_id=uid, media=chunk)

                    print(f"✅ [SENDER] Пачка {b_id} надіслана ({len(media_group)} фото)")

                    # ВИДАЛЕННЯ: Списуємо ліміти за кількість реально надісланих фото
                    consume_one(uid, len(media_group))

                    # Видаляємо завдання пачки з БД одним запитом
                    conn.execute("DELETE FROM tasks WHERE batch_id = ?", (b_id,))
                    conn.commit()

                    for p in paths_to_remove:
                        if os.path.exists(p): os.remove(p)

            conn.close()
        except Exception as e:
            print(f"❌ [SENDER] Помилка: {e}")

        await asyncio.sleep(4)  # Даємо воркеру час на "дожувати" останнє фото


if __name__ == "__main__":
    asyncio.run(sender())