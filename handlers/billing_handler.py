import os, sys, uuid
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiocryptopay import AioCryptoPay, Networks

# Фікс шляхів
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)
import my_token
from database.requests import get_user_data, set_sub, add_transaction, update_transaction_status, upsert_user
from keyboards.photo import get_payment_methods_kb, get_check_crypto_kb
from locales.i18n import get_t

router = Router()

# КОНФІГУРАЦІЯ
LIMITS_CONFIG = {1: 10, 3: 15, 6: 25, 12: 50}
CRYPTO_PRICES = {1: 0.1, 3: 0.2, 6: 0.5, 12: 1.0}  # ТЕСТ USDT
STARS_PRICES = {1: 1, 3: 2, 6: 5, 12: 10}  # ТЕСТ STARS


@router.callback_query(F.data.startswith("buy:"))
async def choose_method(callback: CallbackQuery):
    uid = callback.from_user.id
    u = get_user_data(uid)
    if not u: upsert_user(uid, callback.from_user.first_name); u = get_user_data(uid)

    plan_id = callback.data.split(":")[1]
    lang = u[3] if u else 'en'

    await callback.message.edit_text(get_t(lang, 'pay_method'), reply_markup=get_payment_methods_kb(plan_id))
    await callback.answer()


@router.callback_query(F.data.startswith("meth:crypto:"))
async def pay_crypto(callback: CallbackQuery):
    plan_id = int(callback.data.split(":")[2])
    amount = CRYPTO_PRICES.get(plan_id, 0.1)

    # Створюємо клієнт тільки всередині (Фікс для Arch Linux)
    cp = AioCryptoPay(token=my_token.CRYPTO_TOKEN, network=Networks.MAIN_NET)
    invoice = await cp.create_invoice(asset='USDT', amount=amount)
    await cp.close()

    add_transaction(callback.from_user.id, amount, "USDT", "crypto", str(invoice.invoice_id))

    await callback.message.edit_text(
        f"⚡ **Crypto Pay**: `{amount} USDT`\nID: `{invoice.invoice_id}`",
        reply_markup=get_check_crypto_kb(invoice.invoice_id, plan_id, invoice.bot_invoice_url)
    )


@router.callback_query(F.data.startswith("check_crypto:"))
async def check_crypto(callback: CallbackQuery):
    _, inv_id, plan_id = callback.data.split(":")
    cp = AioCryptoPay(token=my_token.CRYPTO_TOKEN, network=Networks.MAIN_NET)
    invs = await cp.get_invoices(invoice_ids=int(inv_id))
    await cp.close()

    if invs and invs[0].status == 'paid':
        update_transaction_status(inv_id, 'completed')
        set_sub(callback.from_user.id, int(plan_id), LIMITS_CONFIG.get(int(plan_id), 10))
        await callback.message.edit_text("✅ VIP АКТИВОВАНО! Дякуємо за оплату!")
    else:
        await callback.answer("⏳ Оплата не знайдена. Зачекайте 1-2 хвилини.", show_alert=True)


@router.callback_query(F.data.startswith("meth:stars:"))
async def pay_stars(callback: CallbackQuery):
    plan_id = int(callback.data.split(":")[2])
    amount = STARS_PRICES.get(plan_id, 1)
    internal_id = f"st_{uuid.uuid4().hex[:6]}"

    add_transaction(callback.from_user.id, amount, "XTR", "stars", internal_id)

    await callback.message.answer_invoice(
        title="PictoBot VIP Access",
        description=f"План на {plan_id} міс.",
        prices=[LabeledPrice(label="XTR", amount=amount)],
        provider_token="",  # Обов'язково пусто для зірок
        currency="XTR",
        payload=f"order:{internal_id}:{plan_id}"
    )
    await callback.answer()


@router.pre_checkout_query()
async def process_pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def success_pay(message: Message):
    uid = message.from_user.id
    payload = message.successful_payment.invoice_payload.split(":")
    internal_id = payload[1]
    months = int(payload[2])

    new_limit = LIMITS_CONFIG.get(months, 10)
    set_sub(uid, months, new_limit)
    update_transaction_status(internal_id, 'completed')

    u_data = get_user_data(uid)
    await message.answer(get_t(u_data[3], 'sub_success'))