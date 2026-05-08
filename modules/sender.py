import asyncio, os, sys
from aiogram import Bot
from aiogram.types import BufferedInputFile, InputMediaDocument

# 1. ФІКС ШЛЯХІВ
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import my_token
from database.requests import get_conn, get_user_data, consume_one
from locales.i18n import get_t


async def sender():
    bot = Bot(token=my_token.TOKEN)
    print("📨 [SENDER] Модуль групової відправки запущено...")

    while True:
        try:
            conn = get_conn();
            cur = conn.cursor()

            # 1. Отримуємо список унікальних user_id, у яких є хоча б одне готове фото
            cur.execute("SELECT DISTINCT user_id FROM tasks WHERE status='done'")
            users_with_done_tasks = cur.fetchall()

            for (uid,) in users_with_done_tasks:
                # 2. Для кожного юзера беремо ВСІ його готові завдання
                cur.execute("SELECT id, function, output_name FROM tasks WHERE user_id=? AND status='done'", (uid,))
                tasks = cur.fetchall()

                if not tasks: continue

                # Дізнаємося мову юзера
                user_info = get_user_data(uid)
                lang = user_info[3] if user_info else 'en'

                media_group = []
                task_ids_to_delete = []
                paths_to_delete = []

                # 3. Збираємо файли в медіагрупу
                for t_id, func, out_name in tasks:
                    path = os.path.join(BASE_DIR, "tmp", func, "output", out_name)

                    if os.path.exists(path):
                        with open(path, "rb") as f:
                            # Додаємо файл до альбому як документ
                            media_group.append(InputMediaDocument(
                                media=BufferedInputFile(f.read(), filename=out_name)
                            ))

                        task_ids_to_delete.append(t_id)
                        paths_to_delete.append(path)

                # 4. ВІДПРАВКА
                if media_group:
                    # Telegram дозволяє макс 10 файлів в одному альбомі
                    # Розбиваємо, якщо фото більше 10
                    for i in range(0, len(media_group), 10):
                        chunk = media_group[i:i + 10]

                        # Додаємо підпис тільки до першого файлу в альбомі
                        if i == 0:
                            chunk[0].caption = get_t(lang, 'done')

                        await bot.send_media_group(chat_id=uid, media=chunk)

                    print(f"✅ [SENDER] Надіслано альбом ({len(media_group)} шт) юзеру {uid}")

                    # 5. ОЧИЩЕННЯ (тільки після успішної відправки всього альбому)
                    for t_id in task_ids_to_delete:
                        consume_one(uid)
                        conn.execute("DELETE FROM tasks WHERE id=?", (t_id,))
                    conn.commit()

                    for p in paths_to_delete:
                        if os.path.exists(p): os.remove(p)

            conn.close()
        except Exception as e:
            print(f"❌ [SENDER] Помилка: {e}")

        await asyncio.sleep(4)  # Перевіряємо раз на 4 сек, щоб воркер встиг доробити пачку


if __name__ == "__main__":
    asyncio.run(sender())