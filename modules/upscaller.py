import subprocess
import os

BASE_DIR = "/home/tabarejka/picto/" #!!!!!!!!!!!!!!!!!!!!

input = os.path.join(BASE_DIR, "tmp/input/input.jpg")
output = os.path.join(BASE_DIR, "tmp/output/output.png")
modelname = "realesr-animevideov3-x4"
scale = 4


command = [
    "realesrgan-ncnn-vulkan",
    "-i", input,
    "-o", output,
    "-n", modelname,
    "-s", str(scale)
]



try:
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    print("Команда виконана успішно!")
    os.remove(input)
except subprocess.CalledProcessError as e:
    print(f"Помилка: {e.stderr}")
