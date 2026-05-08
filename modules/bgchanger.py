import os
import shutil
from pathlib import Path
from PIL import Image
from rembg import remove, new_session

# --- НАЛАШТУВАННЯ ---
BASE_DIR = "/home/tabarejka/picto/"
INPUT_DIR = os.path.join(BASE_DIR, "tmp/bgchanger/input")
OUTPUT_DIR = os.path.join(BASE_DIR, "tmp/bgchanger/output")
FAILED_DIR = os.path.join(BASE_DIR, "tmp/bgchanger/failed")
# Шлях до картинки, яка стане новим фоном
NEW_BG_PATH = os.path.join(BASE_DIR, "assets/bgchanger/new_background.jpg")

# Створюємо потрібні папки
for d in [INPUT_DIR, OUTPUT_DIR, FAILED_DIR]:
    os.makedirs(d, exist_ok=True)

# Ініціалізація сесії моделі (краще зробити один раз поза циклом)
session = new_session("u2net")

print("Скрипт заміни фону запущено. Очікування файлів...")

while True:
    files = [f for f in os.listdir(INPUT_DIR)
             if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]

    if not files:
        print("Папка input порожня. Завершення роботи.")
        break

    # Перевіряємо, чи існує файл фону
    if not os.path.exists(NEW_BG_PATH):
        print(f"!!! Файл фону не знайдено за шляхом: {NEW_BG_PATH}")
        break

    for filename in files:
        input_path = os.path.join(INPUT_DIR, filename)
        output_filename = f"bg_{Path(filename).stem}.png"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        try:
            print(f"Обробка: {filename}...")

            # 1. Відкриваємо основне зображення
            input_img = Image.open(input_path).convert("RGB")

            # 2. Видаляємо фон за допомогою rembg
            # session допомагає працювати швидше, якщо файлів багато
            no_bg_img = remove(input_img, session=session)

            # 3. Готуємо новий фон
            with Image.open(NEW_BG_PATH).convert("RGB") as bg_img:
                # Масштабуємо фон під розмір вхідного фото
                bg_resized = bg_img.resize(input_img.size, Image.LANCZOS)

                # 4. Накладаємо об'єкт без фону на нову картинку
                # no_bg_img використовується як маска (третій аргумент)
                bg_resized.paste(no_bg_img, (0, 0), no_bg_img)

                # Зберігаємо результат
                bg_resized.save(output_path, format="PNG")

            print(f"Готово: {output_filename}")
            os.remove(input_path)

        except Exception as e:
            print(f"!!! Помилка при обробці {filename}: {e}")
            shutil.move(input_path, os.path.join(FAILED_DIR, filename))
            continue