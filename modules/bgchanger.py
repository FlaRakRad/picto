import sys, os, subprocess, time, shutil
from pathlib import Path
from PIL import Image
from rembg import remove, new_session

# --- 1. ФІКС ШЛЯХІВ ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
from database.requests import get_conn

# --- 2. НАЛАШТУВАННЯ ---
MY_FUNC = "bgchanger"
INPUT_DIR = os.path.join(BASE_DIR, "tmp", MY_FUNC, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "tmp", MY_FUNC, "output")
for d in [INPUT_DIR, OUTPUT_DIR]: os.makedirs(d, exist_ok=True)

# Ініціалізація ШІ моделі
session = new_session("u2net")


def main():
    print(f"[{MY_FUNC.upper()}] Воркер запущено. Чекаю на пари фото...")

    while True:
        conn = get_conn();
        cur = conn.cursor()

        # Шукаємо унікальні Batch ID, які ще не оброблені
        cur.execute(f"SELECT DISTINCT batch_id, user_id FROM tasks WHERE function='{MY_FUNC}' AND status='pending'")
        ready_batches = cur.fetchall()

        if not ready_batches:
            conn.close();
            break  # Вихід, якщо нема роботи

        for b_id, uid in ready_batches:
            # Беремо ВСІ фото цієї пачки, сортуємо за ID (перше надіслане — першим)
            cur.execute("SELECT id, file_name FROM tasks WHERE batch_id=? ORDER BY id ASC", (b_id,))
            tasks = cur.fetchall()

            if len(tasks) != 2:
                print(f"!!! Пачка {b_id} має {len(tasks)} фото. Потрібно рівно 2.")
                conn.execute("UPDATE tasks SET status='error' WHERE batch_id=?", (b_id,))
                conn.commit();
                continue

            # Ставимо статус PROCESSING для всієї пачки
            conn.execute("UPDATE tasks SET status='processing' WHERE batch_id=?", (b_id,))
            conn.commit()

            # Розподіляємо: перше - ФОН, друге - ОБ'ЄКТ
            bg_task_id, bg_file = tasks[0]
            obj_task_id, obj_file = tasks[1]

            bg_path = os.path.join(INPUT_DIR, bg_file)
            obj_path = os.path.join(INPUT_DIR, obj_file)

            output_name = f"final_{obj_file}"
            output_path = os.path.join(OUTPUT_DIR, output_name)

            try:
                print(f"🚀 Обробка пари: фон {bg_file} + об'єкт {obj_file}")

                # 1. Відкриваємо об'єкт і видаляємо фон
                input_img = Image.open(obj_path).convert("RGBA")
                no_bg_img = remove(input_img, session=session)

                # 2. Відкриваємо новий фон
                with Image.open(bg_path).convert("RGBA") as bg_img:
                    # Масштабуємо фон під розмір об'єкта
                    bg_resized = bg_img.resize(input_img.size, Image.LANCZOS)
                    # Накладаємо об'єкт без фону
                    bg_resized.paste(no_bg_img, (0, 0), no_bg_img)
                    # Зберігаємо
                    bg_resized.convert("RGB").save(output_path, "JPEG", quality=95)

                # 3. ФІНАЛ: Тільки ОБ'ЄКТУ ставимо 'done' та шлях.
                # ФОНУ просто ставимо статус 'processed', щоб сендер його проігнорував
                conn.execute("UPDATE tasks SET status='done', output_name=? WHERE id=?", (output_name, obj_task_id))
                conn.execute("UPDATE tasks SET status='processed' WHERE id=?",
                             (bg_task_id,))  # processed не тригерить сендер

                print(f"✅ Успішно створено: {output_name}")
                os.remove(bg_path);
                os.remove(obj_path)

            except Exception as e:
                print(f"❌ Помилка в обробці: {e}")
                conn.execute("UPDATE tasks SET status='error' WHERE batch_id=?", (b_id,))

            conn.commit()

        conn.close()


if __name__ == "__main__":
    main()