import os
import sys
import uuid
from aiocryptopay import AioCryptoPay, Networks
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
import my_token
# Фікс шляхів, щоб воркер бачив корінь проекту

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from database.requests import (
    get_user_data,
    set_sub,
    add_transaction,
    update_transaction_status
)
from keyboards.photo import get_payment_methods_kb, get_check_crypto_kb
from locales.i18n import get_t
from modules.billing_utils import create_crypto_invoice, get_invoice_status

router = Router()

# ЦІНИ: plan_id (місяці): ціна в доларах для крипти
CRYPTO_PRICES = {1: 5.0, 3: 12.0, 6: 22.0, 12: 40.0}

# ЦІНИ: plan_id (місяці): ціна в Telegram Stars (1 USD ~ 50 Stars)
STARS_PRICES = {1: 1, 3: 1.5, 6: 1000, 12: 1900}
LIMITS_CONFIG = {
    1: 10,   # 1 місяць = 10 фото за цикл
    3: 15,   # 3 місяці = 15 фото за цикл
    6: 25,   # 6 місяців = 25 фото за цикл
    12: 50   # 12 місяців = 50 фото за цикл
}

# --- 1. ВИБІР МЕТОДУ ОПЛАТИ ---
@router.callback_query(F.data.startswith("buy:"))
async def choose_payment_method(callback: CallbackQuery):
    plan_id = callback.data.split(":")[1]  # Отримуємо "1", "3" тощо
    u = get_user_data(callback.from_user.id)
    lang = u[3] if u else 'en'

    await callback.message.edit_text(
        get_t(lang, 'pay_method'),
        reply_markup=get_payment_methods_kb(plan_id)
    )
    await callback.answer()


# --- 2. ОПЛАТА КРИПТОЮ (USDT/TON/BTC) ---
@router.callback_query(F.data.startswith("meth:crypto:"))
async def process_crypto_pay(callback: CallbackQuery):
    plan_id = int(callback.data.split(":")[2])
    uid = callback.from_user.id
    amount = CRYPTO_PRICES.get(plan_id, 5.0)

    await callback.message.edit_text("⏳ Створюю унікальний рахунок у блокчейні...")

    # Створюємо рахунок через наш шлюз
    invoice = await create_crypto_invoice(amount)

    # ЛОГУЄМО ТРАНЗАКЦІЮ В БД (pending)
    add_transaction(
        user_id=uid,
        amount=amount,
        currency="USDT",
        method="crypto",
        external_id=str(invoice.invoice_id)
    )

    await callback.message.edit_text(
        f"⚡ **Крипто-оплата (USDT/TON/BTC)**\n\n"
        f"Сума: `{amount} USDT`\n"
        f"Ваш ID транзакції: `{invoice.invoice_id}`\n\n"
        "Натисніть кнопку нижче, щоб перейти в додаток для оплати. "
        "Після завершення переказу натисніть «Перевірити».",
        reply_markup=get_check_crypto_kb(invoice.invoice_id, plan_id, invoice.bot_invoice_url)
    )


# КНОПКА: ПЕРЕВІРКА КРИПТО-ПЛАТЕЖУ
@router.callback_query(F.data.startswith("check_crypto:"))
async def check_crypto_payment(callback: CallbackQuery):
    _, inv_id, plan_id = callback.data.split(":")
    is_paid = await get_invoice_status(int(inv_id))

    if is_paid:
        months = int(plan_id)
        # ТАК САМО ВИЗНАЧАЄМО ЛІМІТ
        LIMITS_CONFIG = {1: 10, 3: 15, 6: 25, 12: 50}
        new_limit = LIMITS_CONFIG.get(months, 10)

        update_transaction_status(inv_id, 'completed')
        # ПЕРЕДАЄМО 3 АРГУМЕНТИ
        set_sub(callback.from_user.id, months, new_limit)

        await callback.message.edit_text(f"🎉 Крипта отримана! Ваш ліміт тепер: {new_limit} фото/год.")
    else:
        await callback.answer("⏳ Оплата поки не підтверджена...", show_alert=True)

# --- 3. ОПЛАТА ТЕЛЕГРАМ-ЗІРКАМИ ---
@router.callback_query(F.data.startswith("meth:stars:"))
async def process_stars_pay(callback: CallbackQuery):
    plan_id = int(callback.data.split(":")[2])
    amount = STARS_PRICES.get(plan_id, 1)
    uid = callback.from_user.id

    # 1. Геруємо наш унікальний ID
    internal_id = f"stars_{uuid.uuid4().hex[:6]}"

    # 2. Реєструємо транзакцію ПЕРЕД виставленням рахунку
    add_transaction(uid, amount, "XTR", "stars", internal_id)

    await callback.message.answer_invoice(
        title="PICТО VIP (Test Mode)",
        description=f"План на {plan_id} міс. — TEST",
        prices=[LabeledPrice(label="⭐ XTR", amount=amount)],
        provider_token="",
        currency="XTR",
        # ВАЖЛИВО: ми передаємо наш internal_id і plan_id в payload через розділювач
        payload=f"order:{internal_id}:{plan_id}"
    )
    await callback.answer()


# --- 4. ПІДТВЕРДЖЕННЯ ТЕЛЕГРАМ ПЛАТЕЖІВ (Stars/Cards) ---
@router.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    # Кажемо системі, що ми готові забрати зірочки/гроші
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def success_pay(message: Message):
    uid = message.from_user.id

    # Дістаємо дані з нашого нового payload: "order:stars_xxxxxx:1"
    payload_parts = message.successful_payment.invoice_payload.split(":")
    internal_id = payload_parts[1]
    months = int(payload_parts[2])

    new_limit = LIMITS_CONFIG.get(months, 10)

    # 1. Оновлюємо статус транзакції саме за ТИМ ідентифікатором, що в базі!
    update_transaction_status(internal_id, 'completed')

    # 2. Видаємо VIP ліміти
    set_sub(uid, months, new_limit)

    u_data = get_user_data(uid)
    lang = u_data[3] if u_data else 'en'

    print(f"💰 ОПЛАТА ПІДТВЕРДЖЕНА! ID: {internal_id}")

    await message.answer(
        f"✅ **Оплата пройшла успішно!**\n"
        f"VIP активовано. Новий ліміт: **{new_limit} фото** за цикл."
    )