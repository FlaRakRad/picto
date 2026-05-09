import sys
import os
import shutil
import time
from pathlib import Path
from PIL import Image
from rembg import remove, new_session

# --- 1. АВТО-ФІКС ШЛЯХІВ (щоб бачити папку database) ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from database.requests import get_conn

# --- 2. НАЛАШТУВАННЯ ---
MY_FUNC = "bgchanger"
INPUT_DIR = os.path.join(PROJECT_ROOT, "tmp", MY_FUNC, "input")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "tmp", MY_FUNC, "output")
FAILED_DIR = os.path.join(PROJECT_ROOT, "tmp", MY_FUNC, "failed")

for d in [INPUT_DIR, OUTPUT_DIR, FAILED_DIR]:
    os.makedirs(d, exist_ok=True)

# Ініціалізація ШІ-сесії моделі (робимо 1 раз для швидкості)
print(f"[{MY_FUNC.upper()}] Завантаження ШІ-моделі rembg...")
ai_session = new_session("u2net")


def main():
    print(f"[{MY_FUNC.upper()}] Воркер запущений. Чекаю на замовлення в БД...")

    while True:
        conn = get_conn()
        cur = conn.cursor()

        # 1. Знаходимо пачки (Batch), де статус 'pending'
        cur.execute(f"SELECT DISTINCT batch_id, user_id FROM tasks WHERE function='{MY_FUNC}' AND status='pending'")
        ready_batches = cur.fetchall()

        if not ready_batches:
            conn.close()
            # Робимо break, якщо воркер запускається через Popen, або sleep(3) для циклу
            print(f"[{MY_FUNC.upper()}] Роботу завершено. Пачка пуста.")
            break

        for b_id, uid in ready_batches:
            # 2. Беремо ВСІ файли цього батчу (ID ASC гарантує: ФОН БУДЕ ОСТАННІМ)
            cur.execute("SELECT id, file_name FROM tasks WHERE batch_id=? ORDER BY id ASC", (b_id,))
            tasks = cur.fetchall()

            if len(tasks) < 2:
                print(f"!!! Пачка {b_id} містить мало файлів ({len(tasks)}). Треба мінімум 1 об'єкт + 1 фон.")
                conn.execute("UPDATE tasks SET status='error' WHERE batch_id=?", (b_id,))
                conn.commit()
                continue

            # Розподіляємо ролі: остання фотографія — фон, решта — об'єкти
            bg_row = tasks[-1]
            obj_rows = tasks[:-1]

            bg_task_id, bg_file_name = bg_row
            bg_path = os.path.join(INPUT_DIR, bg_file_name)

            print(f"\n[{MY_FUNC.upper()}] Початок батчу: {b_id} (Об'єктів: {len(obj_rows)})")

            # Міняємо статус на processing для всього батчу
            conn.execute("UPDATE tasks SET status='processing' WHERE batch_id=?", (b_id,))
            conn.commit()

            try:
                # 3. Відкриваємо файл фону один раз на весь батч
                with Image.open(bg_path).convert("RGBA") as bg_raw:

                    for task_id, obj_file_name in obj_rows:
                        obj_path = os.path.join(INPUT_DIR, obj_file_name)
                        output_name = f"final_{obj_file_name}"
                        output_path = os.path.join(OUTPUT_DIR, output_name)

                        print(f"   >>> Обробка об'єкта: {obj_file_name}")

                        # А) Видаляємо фон з об'єкта
                        with Image.open(obj_path).convert("RGBA") as obj_img:
                            # AI робота
                            no_bg_obj = remove(obj_img, session=ai_session)

                            # Б) Масштабуємо фон під розмір об'єкта
                            bg_canvas = bg_raw.resize(obj_img.size, Image.LANCZOS)

                            # В) Накладаємо вирізаний об'єкт на фон
                            # Використовуємо no_bg_obj як маску для прозорості
                            bg_canvas.paste(no_bg_obj, (0, 0), no_bg_obj)

                            # Г) Зберігаємо як високоякісний JPEG або PNG
                            bg_canvas.convert("RGB").save(output_path, "JPEG", quality=95)

                        # Д) Статус успіху для ОБ'ЄКТА
                        conn.execute("UPDATE tasks SET status='done', output_name=? WHERE id=?", (output_name, task_id))
                        os.remove(obj_path)

                # 4. ФОН оброблено — ставимо 'processed' (не шлемо його юзеру)
                conn.execute("UPDATE tasks SET status='processed' WHERE id=?", (bg_task_id,))
                os.remove(bg_path)
                print(f"✨ Бандл {b_id} готовий для Сендера.")

            except Exception as e:
                print(f"❌ ПОМИЛКА БАТЧУ {b_id}: {e}")
                conn.execute("UPDATE tasks SET status='error' WHERE batch_id=?", (b_id,))

            conn.commit()

        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as top_e:
        print(f"КРИТИЧНИЙ ЗБІЙ СКРИПТА: {top_e}")