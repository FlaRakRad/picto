from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from .keyboards.builder import get_resolution_kb
from image_api import process_image_by_api

router = Router()


@router.message(F.photo)
async def get_photo(message: Message, state: FSMContext):
    # Зберігаємо ID фото в пам'ять бота
    await state.update_data(photo_id=message.photo[-1].file_id)
    await message.answer("Фото отримано! Оберіть розмір:", reply_markup=get_resolution_kb())


@router.callback_query(F.data.startswith("res:"))
async def process_res(callback: CallbackQuery, state: FSMContext):
    resolution = callback.data.split(":")[1]
    data = await state.get_data()
    photo_id = data.get("photo_id")

    await callback.message.edit_text("⏳ Обробляю зображення, зачекайте...")

    # Виклик функції з api_file.py
    result = await process_image_by_api(photo_id, resolution, remove_wm=True)

    if result:
        await callback.message.edit_text("✅ Готово! Зображення збережено.")

    await state.clear()