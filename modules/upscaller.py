import subprocess
import os
import shutil
from pathlib import Path
from PIL import Image

BASE_DIR = "/home/tabarejka/picto/"
INPUT_DIR = os.path.join(BASE_DIR, "tmp/input")
OUTPUT_DIR = os.path.join(BASE_DIR, "tmp/output")
FAILED_DIR = os.path.join(BASE_DIR, "tmp/failed")
MODEL_NAME = "realesr-animevideov3-x4"
SCALE = 4

# Створюємо потрібні папки
for d in [INPUT_DIR, OUTPUT_DIR, FAILED_DIR]:
    os.makedirs(d, exist_ok=True)

print("Скрипт запущено. Очікування файлів...")

while True:
    files = [f for f in os.listdir(INPUT_DIR)
             if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]

    if not files:
        print("Папка input порожня. Завершення роботи.")
        break

    for filename in files:
        input_path = os.path.join(INPUT_DIR, filename)
        file_stem = Path(filename).stem
        output_filename = f"up_{file_stem}.png"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        # Зберігаємо оригінальний розмір ДО апскейлу
        try:
            with Image.open(input_path) as img:
                original_size = img.size  # (width, height)
            print(f"Оригінальний розмір: {original_size[0]}x{original_size[1]}")
        except Exception as e:
            print(f"!!! Не вдалося прочитати розмір {filename}: {e}")
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
            print(f"Обробка: {filename} -> {output_filename}")
            subprocess.run(command, check=True, text=True, capture_output=True)

            if os.path.exists(output_path):
                # Повертаємо до оригінального розміру після апскейлу
                with Image.open(output_path) as upscaled_img:
                    print(f"Розмір після апскейлу: {upscaled_img.size[0]}x{upscaled_img.size[1]}")
                    resized_img = upscaled_img.resize(original_size, Image.LANCZOS)

                resized_img.save(output_path, format="PNG")
                print(f"Готово (повернуто до {original_size[0]}x{original_size[1]}): {output_filename}")

                os.remove(input_path)
                print(f"Видалено вхідний файл: {filename}")
            else:
                print(f"Попередження: Команда ніби ОК, але {output_filename} не знайдено.")

        except subprocess.CalledProcessError as e:
            print(f"!!! Помилка при обробці {filename}: {e.stderr}")
            print(f"Переміщую {filename} в папку 'failed'...")
            shutil.move(input_path, os.path.join(FAILED_DIR, filename))
            continue