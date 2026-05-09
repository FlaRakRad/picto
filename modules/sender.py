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
    print("📦 [SENDER] Режим альбомів активовано...")

    while True:
        try:
            conn = get_conn();
            cur = conn.cursor()
            # Шукаємо готові Batch ID
            cur.execute("""
                SELECT batch_id, user_id, function FROM tasks 
                GROUP BY batch_id 
                HAVING COUNT(id) = COUNT(CASE WHEN status IN ('done', 'processed') THEN 1 END)
                AND COUNT(CASE WHEN status = 'done' THEN 1 END) > 0
            """)
            ready_batches = cur.fetchall()

            for b_id, uid, func in ready_batches:
                cur.execute("SELECT id, output_name FROM tasks WHERE batch_id=? AND status='done'", (b_id,))
                ready_photos = cur.fetchall()
                lang = (get_user_data(uid) or [None, None, None, 'en'])[3]
                media = []

                for tid, out_name in ready_photos:
                    path = os.path.join(BASE_DIR, "tmp", func, "output", out_name)
                    if os.path.exists(path):
                        with open(path, "rb") as f:
                            media.append(InputMediaDocument(media=BufferedInputFile(f.read(), filename=out_name)))

                if media:
                    for i in range(0, len(media), 10):
                        chunk = media[i:i + 10]
                        if i == 0: chunk[0].caption = get_t(lang, 'done')
                        await bot.send_media_group(uid, media=chunk)

                    consume_one(uid, len(media))
                    conn.execute("DELETE FROM tasks WHERE batch_id = ?", (b_id,))
                    conn.commit()
                    # Фізична чистка папок
                    for doc in media:
                        p_to_rm = os.path.join(BASE_DIR, "tmp", func, "output", doc.media.filename)
                        if os.path.exists(p_to_rm): os.remove(p_to_rm)
            conn.close()
        except:
            pass
        await asyncio.sleep(4)


if __name__ == "__main__": asyncio.run(sender())