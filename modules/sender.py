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
    print("📨 [SENDER] Надсилаю результати альбомами (Текст зверху)...")

    while True:
        try:
            conn = get_conn();
            cur = conn.cursor()

            # Шукаємо пачки, де ВСІ файли готові
            cur.execute("""
                SELECT batch_id, user_id, function FROM tasks 
                GROUP BY batch_id 
                HAVING COUNT(id) = COUNT(CASE WHEN status IN ('done', 'processed') THEN 1 END)
                AND COUNT(CASE WHEN status = 'done' THEN 1 END) > 0
            """)
            ready_batches = cur.fetchall()

            for b_id, uid, func in ready_batches:
                # Беремо тільки файли 'done'
                cur.execute("SELECT id, output_name FROM tasks WHERE batch_id=? AND status='done'", (b_id,))
                ready_photos = cur.fetchall()

                u_info = get_user_data(uid)
                lang = u_info[3] if u_info else 'en'

                media = []
                for t_id, out_name in ready_photos:
                    path = os.path.join(BASE_DIR, "tmp", func, "output", out_name)
                    if os.path.exists(path):
                        with open(path, "rb") as f:
                            # Додаємо файли чистими, БЕЗ підпису в caption
                            media.append(InputMediaDocument(media=BufferedInputFile(f.read(), filename=out_name)))
                        os.remove(path)

                if media:
                    # 🚀 КРОК 1: НАДСИЛАЄМО ТЕКСТ (Заголовок)
                    # Оскільки він іде першим — він завжди буде зверху над пачкою
                    await bot.send_message(uid, get_t(lang, 'done'))

                    # 🚀 КРОК 2: НАДСИЛАЄМО МЕДІАГРУПУ (Фото)
                    for i in range(0, len(media), 10):
                        chunk = media[i:i + 10]
                        await bot.send_media_group(chat_id=uid, media=chunk)

                    print(f"✨ [SENDER] Відправлено пачку для {uid}")

                    # Списання та чистка бази
                    consume_one(uid, len(media))
                    conn.execute("DELETE FROM tasks WHERE batch_id = ?", (b_id,))
                    conn.commit()

            conn.close()
        except Exception as e:
            print(f"❌ [SENDER ERROR]: {e}")

        await asyncio.sleep(4)


if __name__ == "__main__":
    asyncio.run(sender())