import sys
import os

# --- 1. ФІКС ШЛЯХІВ (МАЄ БУТИ ПЕРШИМ) ---
# Знаходимо корінь проекту, щоб бачити папку 'database'
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

import subprocess
import time
import shutil
from pathlib import Path
from PIL import Image
from database.requests import get_conn

# --- 2. НАЛАШТУВАННЯ ШЛЯХІВ ---
# Використовуємо абсолютний шлях до твого проекту
BASE_DIR = PROJECT_ROOT
# Функція модуля - має співпадати з назвою в БД та папкою в tmp/
MY_FUNC = "upscaler"

INPUT_DIR = os.path.join(BASE_DIR, "tmp", MY_FUNC, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "tmp", MY_FUNC, "output")
FAILED_DIR = os.path.join(BASE_DIR, "tmp", MY_FUNC, "failed")
MODEL_NAME = "realesr-animevideov3-x4"
SCALE = 4

# Створюємо потрібні папки, якщо їх нема
for d in [INPUT_DIR, OUTPUT_DIR, FAILED_DIR]:
    os.makedirs(d, exist_ok=True)


def main():
    conn = get_conn()
    cur = conn.cursor()

    print(f"[{MY_FUNC.upper()}] Скрипт запущено. Очікування файлів...")

    while True:
        # Шукаємо файли в папці input
        files = [f for f in os.listdir(INPUT_DIR)
                 if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]

        if not files:
            print(f"[{MY_FUNC.upper()}] Черга порожня. Вимикаюсь...")
            break  # Скрипт завершується, якщо нема роботи

        for filename in files:
            # --- КРОК 1: ШУКАЄМО TASK_ID У БАЗІ ---
            # Шукаємо запис у БД, де назва файлу співпадає і статус 'pending'
            cur.execute("""SELECT id FROM tasks 
                           WHERE file_name = ? AND function = ? AND status = 'pending' 
                           LIMIT 1""", (filename, MY_FUNC))
            task_res = cur.fetchone()

            if task_res:
                task_id = task_res[0]
                # Оновлюємо статус на "в роботі"
                conn.execute("UPDATE tasks SET status = 'processing' WHERE id = ?", (task_id,))
                conn.commit()
                print(f"\n[{MY_FUNC.upper()}] ПРИЙНЯТО В РОБОТУ: Завдання №{task_id}")
            else:
                # Якщо файл у папці є, а в базі нема - ігноруємо його
                continue

            # --- КРОК 2: ТВОЯ ЛОГІКА ОБРОБКИ ---
            input_path = os.path.join(INPUT_DIR, filename)
            file_stem = Path(filename).stem
            output_filename = f"up_{filename}"
            output_path = os.path.join(OUTPUT_DIR, output_filename)

            # Зберігаємо оригінальний розмір ДО апскейлу
            try:
                with Image.open(input_path) as img:
                    original_size = img.size  # (width, height)
                print(f"[{task_id}] Розмір до обробки: {original_size[0]}x{original_size[1]}")
            except Exception as e:
                print(f"!!! [Завдання {task_id}] Не вдалося прочитати розмір: {e}")
                conn.execute("UPDATE tasks SET status = 'error' WHERE id = ?", (task_id,))
                conn.commit()
                shutil.move(input_path, os.path.join(FAILED_DIR, filename))
                continue

            command = [
                "realesrgan-ncnn-vulkan",
                "-i", input_path,
                "-o", output_path,
                "-n", MODEL_NAME,
                "-s", str(SCALE)
            ]

            try:
                print(f"[{task_id}] AI працює над {filename}...")
                subprocess.run(command, check=True, text=True, capture_output=True)

                if os.path.exists(output_path):
                    # Повертаємо до оригінального розміру після апскейлу
                    with Image.open(output_path) as upscaled_img:
                        print(f"[{task_id}] Розмір ПІСЛЯ ШІ: {upscaled_img.size[0]}x{upscaled_img.size[1]}")
                        resized_img = upscaled_img.resize(original_size, Image.LANCZOS)

                    resized_img.save(output_path, format="PNG")

                    # --- КРОК 3: УСПІХ - СТАВИМО DONE ТА НАЗВУ ---
                    conn.execute(
                        "UPDATE tasks SET status = 'done', output_name = ? WHERE id = ?",
                        (output_filename, task_id)
                    )
                    conn.commit()
                    print(f"[{task_id}] ✅ ГОТОВО: {output_filename}")

                    os.remove(input_path)
                else:
                    raise FileNotFoundError("Output file not found after process")

            except Exception as e:
                # --- КРОК 4: ПОМИЛКА - СТАВИМО ERROR ---
                print(f"!!! [Завдання {task_id}] Помилка обробки: {e}")
                conn.execute("UPDATE tasks SET status = 'error' WHERE id = ?", (task_id,))
                conn.commit()
                if os.path.exists(input_path):
                    shutil.move(input_path, os.path.join(FAILED_DIR, filename))
                continue

    conn.close()


if __name__ == "__main__":
    main()