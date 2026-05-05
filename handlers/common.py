from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from database.requests import upsert_user, check_reset_limit, get_user_data
from keyboards.main_menu import get_main_menu
from keyboards.subscription import get_sub_kb

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    uid = message.from_user.id
    upsert_user(uid, message.from_user.first_name)
    await message.answer(
        f"Привіт, {message.from_user.first_name}! Я PictoBot.\n"
        "Надішли мені фото, щоб почати покращення, або скористайся меню нижче.",
        reply_markup=get_main_menu()
    )

@router.message(F.text == "📊 Мій профіль")
@router.message(Command("menu"))
async def cmd_menu(message: Message):
    uid = message.from_user.id
    check_reset_limit(uid)
    data = get_user_data(uid)
    if data:
        limit, _, max_limit = data
        await message.answer(f"📊 Стан лімітів:\nЗалишилось: {limit} з {max_limit}")

@router.message(F.text == "💎 Підписка")
@router.message(Command("subscribe"))
async def cmd_sub(message: Message):
    await message.answer("Обери термін підписки для розширення лімітів:", reply_markup=get_sub_kb())

@router.message(F.text == "ℹ️ Допомога")
@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer("Просто надішли фото, обери бажану якість, і я його покращу!")

@router.message(F.text == "🖼 Обробка фото")
async def process_photo_hint(message: Message):
    await message.answer("Просто надішли мені файл фотографії (як фото або як документ).")