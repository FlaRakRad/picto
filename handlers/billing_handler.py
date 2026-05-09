import os, sys, uuid
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiocryptopay import AioCryptoPay, Networks
import config
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
    amount = config.CRYPTO_PRICES.get(plan_id, 5.0)  # Беремо з конфігу

    cp = AioCryptoPay(token=my_token.CRYPTO_TOKEN, network=Networks.MAIN_NET)
    inv = await cp.create_invoice(asset='USDT', amount=amount)
    await cp.close()

    add_transaction(callback.from_user.id, amount, "USDT", "crypto", str(inv.invoice_id))
    await callback.message.edit_text(f"💸 `{amount} USDT`",
                                     reply_markup=get_check_crypto_kb(inv.invoice_id, plan_id, inv.bot_invoice_url))


@router.callback_query(F.data.startswith("check_crypto:"))
async def check_crypto(callback: CallbackQuery):
    _, inv_id, plan_id = callback.data.split(":")

    # 1. СТВОРЮЄМО КЛІЄНТ (фікс для Arch/Linux)
    cp = AioCryptoPay(token=my_token.CRYPTO_TOKEN, network=Networks.MAIN_NET)

    # 2. ТУТ МИ ВИЗНАЧАЄМО is_paid (опитуємо блокчейн)
    # Цей рядок МАЄ бути перед if
    invs = await cp.get_invoices(invoice_ids=int(inv_id))
    await cp.close()

    is_paid = invs and invs[0].status == 'paid'

    # 3. ТЕПЕР Твій IF ЗАПРАЦЮЄ
    if is_paid:
        update_transaction_status(inv_id, 'completed')
        # set_sub тепер бере тільки 2 аргументи (id та місяці)
        set_sub(callback.from_user.id, int(plan_id))

        await callback.message.edit_text(f"✅ VIP OK! Ліміт: {config.VIP_LIMIT} фото/год.")
    else:
        await callback.answer("⏳ Оплата поки не знайдена... Спробуйте через 1 хв.", show_alert=True)

@router.message(F.successful_payment)
async def success_pay(message: Message):
    uid = message.from_user.id
    payload = message.successful_payment.invoice_payload.split(":")
    months = int(payload[2])

    set_sub(uid, months)  # Більше не треба передавати ліміт сюди
    update_transaction_status(payload[1], 'completed')
    await message.answer(f"✅ VIP активовано на {months} міс! Твій ліміт тепер: {config.VIP_LIMIT} фото.")





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


