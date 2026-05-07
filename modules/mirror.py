import subprocess
import os
import shutil
from pathlib import Path

# Конфігурація шляхів
BASE_DIR = "/home/tabarejka/picto/"
INPUT_DIR = os.path.join(BASE_DIR, "tmp/mirror/input")
OUTPUT_DIR = os.path.join(BASE_DIR, "tmp/mirror/output")
FAILED_DIR = os.path.join(BASE_DIR, "tmp/mirror/failed")

# Створюємо потрібні папки
for d in [INPUT_DIR, OUTPUT_DIR, FAILED_DIR]:
    os.makedirs(d, exist_ok=True)

print("Скрипт ImageMagick (Mirror) запущено. Очікування файлів...")

while True:
    # Отримуємо список зображень
    files = [f for f in os.listdir(INPUT_DIR)
             if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.tiff'))]

    if not files:
        print("Папка input порожня. Завершення роботи.")
        break

    for filename in files:
        input_path = os.path.join(INPUT_DIR, filename)
        file_stem = Path(filename).stem
        # Зберігаємо розширення оригіналу, або міняємо на png
        output_filename = f"mirrored_{file_stem}{Path(filename).suffix}"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        # Команда ImageMagick
        # magick input.jpg -flop output.jpg
        # Примітка: якщо у вас стара версія ImageMagick (v6), замініть "magick" на "convert"
        command = [
            "magick",
            input_path,
            "-flop",
            output_path
        ]

        try:
            print(f"Обробка: {filename} -> {output_filename}")

            # Виконуємо команду
            result = subprocess.run(command, check=True, text=True, capture_output=True)

            if os.path.exists(output_path):
                print(f"Готово: {output_filename}")
                # Видаляємо вхідний файл після успішної обробки
                os.remove(input_path)
            else:
                print(f"Помилка: Файл {output_filename} не був створений.")
                shutil.move(input_path, os.path.join(FAILED_DIR, filename))

        except subprocess.CalledProcessError as e:
            print(f"!!! Помилка ImageMagick на файлі {filename}: {e.stderr}")
            shutil.move(input_path, os.path.join(FAILED_DIR, filename))
        except Exception as e:
            print(f"!!! Непередбачена помилка: {e}")
            shutil.move(input_path, os.path.join(FAILED_DIR, filename))