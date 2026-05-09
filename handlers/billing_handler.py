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


# Допоміжна функція для отримання мови
async def get_lang(uid, callback=None):
    u = get_user_data(uid)
    if not u:
        name = callback.from_user.first_name if callback else "User"
        upsert_user(uid, name)
        u = get_user_data(uid)
    return u[3] if u else 'en'


@router.callback_query(F.data.startswith("buy:"))
async def choose_method(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id, callback)
    plan_id = callback.data.split(":")[1]

    await callback.message.edit_text(
        get_t(lang, 'pay_method'),
        reply_markup=get_payment_methods_kb(plan_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("meth:crypto:"))
async def pay_crypto(callback: CallbackQuery):
    uid = callback.from_user.id
    lang = await get_lang(uid, callback)
    plan_id = int(callback.data.split(":")[2])
    amount = config.CRYPTO_PRICES.get(plan_id, 5.0)

    cp = AioCryptoPay(token=my_token.CRYPTO_TOKEN, network=Networks.MAIN_NET)
    inv = await cp.create_invoice(asset='USDT', amount=amount)
    await cp.close()

    add_transaction(uid, amount, "USDT", "crypto", str(inv.invoice_id))

    msg_text = get_t(lang, 'pay_crypto_desc', amount=amount, invoice_id=inv.invoice_id)
    await callback.message.edit_text(
        msg_text,
        reply_markup=get_check_crypto_kb(inv.invoice_id, plan_id, inv.bot_invoice_url)
    )


@router.callback_query(F.data.startswith("check_crypto:"))
async def check_crypto(callback: CallbackQuery):
    uid = callback.from_user.id
    lang = await get_lang(uid, callback)
    _, inv_id, plan_id = callback.data.split(":")

    cp = AioCryptoPay(token=my_token.CRYPTO_TOKEN, network=Networks.MAIN_NET)
    invs = await cp.get_invoices(invoice_ids=int(inv_id))
    await cp.close()

    is_paid = invs and invs[0].status == 'paid'

    if is_paid:
        update_transaction_status(inv_id, 'completed')
        set_sub(uid, int(plan_id))

        await callback.message.edit_text(
            get_t(lang, 'sub_active_msg', limit=config.VIP_LIMIT)
        )
    else:
        await callback.answer(get_t(lang, 'pay_wait_crypto'), show_alert=True)


@router.message(F.successful_payment)
async def success_pay(message: Message):
    uid = message.from_user.id
    lang = await get_lang(uid)

    payload = message.successful_payment.invoice_payload.split(":")
    internal_id = payload[1]
    months = int(payload[2])

    set_sub(uid, months)
    update_transaction_status(internal_id, 'completed')

    await message.answer(
        get_t(lang, 'sub_active_msg', limit=config.VIP_LIMIT)
    )


@router.callback_query(F.data.startswith("meth:stars:"))
async def pay_stars(callback: CallbackQuery):
    uid = callback.from_user.id
    lang = await get_lang(uid, callback)
    plan_id = int(callback.data.split(":")[2])

    amount = config.STARS_PRICES.get(plan_id, 250)
    internal_id = f"st_{uuid.uuid4().hex[:6]}"

    add_transaction(uid, amount, "XTR", "stars", internal_id)

    await callback.message.answer_invoice(
        title=get_t(lang, 'stars_bill_title'),
        description=get_t(lang, 'stars_bill_desc', months=plan_id),
        prices=[LabeledPrice(label="⭐ XTR", amount=amount)],
        provider_token="",
        currency="XTR",
        payload=f"order:{internal_id}:{plan_id}"
    )
    await callback.answer()


@router.pre_checkout_query()
async def process_pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)