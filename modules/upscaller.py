import subprocess
import os, time
import shutil
from pathlib import Path

BASE_DIR = "/home/tabarejka/picto/"
INPUT_DIR = os.path.join(BASE_DIR, "tmp/input")
OUTPUT_DIR = os.path.join(BASE_DIR, "tmp/output")
FAILED_DIR = os.path.join(BASE_DIR, "tmp/failed")  # Папка для помилок
MODEL_NAME = "realesr-animevideov3-x4"
SCALE = 4

# Створюємо потрібні папки
for d in [INPUT_DIR, OUTPUT_DIR, FAILED_DIR]:
    os.makedirs(d, exist_ok=True)

print("Скрипт запущено. Очікування файлів...")

while True:
    # Отримуємо список файлів
    files = [f for f in os.listdir(INPUT_DIR)
             if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]

    if not files:
        print("Папка input порожня. Завершення роботи.")
        break

    for filename in files:
        input_path = os.path.join(INPUT_DIR, filename)

        # ФІКС 1: Отримуємо ім'я без розширення (напр. "photo" замість "photo.jpg")
        file_stem = Path(filename).stem

        # ФІКС 2: Чітко вказуємо вихідний формат (завжди .png для якості)
        output_filename = f"up_{file_stem}.png"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        command = [
            "realesrgan-ncnn-vulkan",
            "-i", input_path,
            "-o", output_path,
            "-n", MODEL_NAME,
            "-s", str(SCALE)
        ]

        try:
            print(f"Обробка: {filename} -> {output_filename}")

            # ФІКС 3: Якщо обробка пройшла успішно, скрипт іде далі
            # Якщо вилетіла помилка — перестрибує в блок except
            subprocess.run(command, check=True, text=True, capture_output=True)

            # Перевіряємо чи файл реально створився (з урахуванням можливих змін інструменту)
            if os.path.exists(output_path):
                print(f"Готово: {output_filename}")
                os.remove(input_path)
                print(f"Видалено вхідний файл: {filename}")
            else:
                print(f"Попередження: Команда ніби ОК, але {output_filename} не знайдено.")

        except subprocess.CalledProcessError as e:
            print(f"!!! Помилка при обробці {filename}: {e.stderr}")
            # ФІКС 4: Переміщуємо файл, щоб він не зупиняв чергу
            print(f"Переміщую {filename} в папку 'failed'...")
            shutil.move(input_path, os.path.join(FAILED_DIR, filename))
            continue