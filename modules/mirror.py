import sys
import os
import subprocess
import time
import shutil
from pathlib import Path

# --- 1. ФІКС ШЛЯХІВ ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
from database.requests import get_conn

# --- 2. КОНФІГУРАЦІЯ ---
MY_FUNC = "mirror"
INPUT_DIR = os.path.join(BASE_DIR, "tmp", MY_FUNC, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "tmp", MY_FUNC, "output")
FAILED_DIR = os.path.join(BASE_DIR, "tmp", MY_FUNC, "failed")

for d in [INPUT_DIR, OUTPUT_DIR, FAILED_DIR]: os.makedirs(d, exist_ok=True)

def main():
    conn = get_conn(); cur = conn.cursor()
    print(f"[{MY_FUNC.upper()}] Воркер активовано...")

    while True:
        # Шукаємо файли в папці
        files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if not files:
            print(f"[{MY_FUNC.upper()}] Папка порожня. Вимикаюсь.")
            break

        for filename in files:
            # Знаходимо ID в базі
            cur.execute("SELECT id, user_id FROM tasks WHERE file_name=? AND function=? AND status='pending' LIMIT 1", (filename, MY_FUNC))
            task = cur.fetchone()
            if not task: continue

            task_id, uid = task
            input_path = os.path.join(INPUT_DIR, filename)
            output_name = f"mir_{filename}"
            output_path = os.path.join(OUTPUT_DIR, output_name)

            conn.execute("UPDATE tasks SET status='processing' WHERE id=?", (task_id,))
            conn.commit()

            print(f"[{MY_FUNC.upper()}] Дзеркалю {filename}...")

            try:
                # Використовуємо magick для Windows/Linux
                subprocess.run(["magick", input_path, "-flop", output_path], check=True, capture_output=True)

                if os.path.exists(output_path):
                    # Ставимо DONE щоб Сендер побачив
                    conn.execute("UPDATE tasks SET status='done', output_name=? WHERE id=?", (output_name, task_id))
                    os.remove(input_path)
                    print(f"✅ Готово: {output_name}")
                else: raise Exception
            except Exception as e:
                print(f"❌ Помилка {task_id}: {e}")
                conn.execute("UPDATE tasks SET status='error' WHERE id=?", (task_id,))
                shutil.move(input_path, os.path.join(FAILED_DIR, filename))
            conn.commit()
    conn.close()

if __name__ == "__main__":
    main()