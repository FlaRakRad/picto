import asyncio, os, sys
from aiogram import Bot
from aiogram.types import BufferedInputFile, InputMediaDocument
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

# Фікс шляхів
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import my_token
from database.requests import get_conn, get_user_data, consume_one
from locales.i18n import get_t


async def sender():
    bot = Bot(token=my_token.TOKEN)
    print("📨 [SENDER] Універсальна система видачі альбомів запущена...")

    while True:
        try:
            conn = get_conn()
            cur = conn.cursor()

            # 1. Шукаємо ПОВНІСТЮ готові пачки (бандли)
            # Вважаємо пачку готовою, якщо статус 'pending' та 'processing' зникли
            cur.execute("""
                SELECT batch_id, user_id, function FROM tasks 
                GROUP BY batch_id 
                HAVING COUNT(CASE WHEN status IN ('pending', 'processing') THEN 1 END) = 0
                AND COUNT(CASE WHEN status = 'done' THEN 1 END) > 0
            """)
            ready_batches = cur.fetchall()

            for b_id, uid, func in ready_batches:
                # 2. Витягуємо лише результати (status = 'done')
                cur.execute("SELECT id, output_name FROM tasks WHERE batch_id=? AND status='done'", (b_id,))
                photos_data = cur.fetchall()

                # Отримуємо мову для тексту
                user_info = get_user_data(uid)
                lang = user_info[3] if user_info else 'en'

                media = []
                paths_to_remove = []

                # 3. Готуємо файли
                for t_id, out_name in photos_data:
                    path = os.path.join(BASE_DIR, "tmp", func, "output", out_name)
                    if os.path.exists(path):
                        with open(path, "rb") as f:
                            media.append(InputMediaDocument(
                                media=BufferedInputFile(f.read(), filename=out_name)
                            ))
                        paths_to_remove.append(path)

                if media:
                    try:
                        print(f"📦 [SENDER] Відправка {len(media)} фото юзеру {uid}...")

                        # ШАГ 1: ТЕКСТ ЗВЕРХУ (Заголовок альбому)
                        await bot.send_message(uid, get_t(lang, 'done'))

                        # ШАГ 2: АЛЬБОМИ (По 10 штук за раз)
                        for i in range(0, len(media), 10):
                            chunk = media[i:i + 10]
                            await bot.send_media_group(uid, media=chunk)

                        # 4. УСПІХ - Списуємо ліміт та видаляємо записи
                        consume_one(uid, len(media))
                        conn.execute("DELETE FROM tasks WHERE batch_id = ?", (b_id,))
                        conn.commit()

                        # Фізично видаляємо файли з диска
                        for p in paths_to_remove:
                            if os.path.exists(p): os.remove(p)

                        print(f"✅ [SENDER] Бандл {b_id} доставлено успішно.")

                    except TelegramForbiddenError:
                        print(f"🚫 [SENDER] Юзер {uid} заблокував бота. Видаляю пачку.")
                        conn.execute("DELETE FROM tasks WHERE batch_id = ?", (b_id,))
                        conn.commit()
                    except TelegramRetryAfter as e:
                        print(f"⏳ [SENDER] Флуд-контроль. Чекаю {e.retry_after} сек.")
                        await asyncio.sleep(e.retry_after)
                    except Exception as send_err:
                        print(f"⚠ [SENDER] Помилка відправки: {send_err}")
                else:
                    # Якщо запис у базі є, а файлів на диску нема — чистимо сміття
                    conn.execute("DELETE FROM tasks WHERE batch_id = ?", (b_id,))
                    conn.commit()

            conn.close()
        except Exception as global_err:
            print(f"❌ [SENDER CRITICAL]: {global_err}")

        # Пауза між циклами перевірки бази
        await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(sender())