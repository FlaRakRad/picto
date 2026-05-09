import os
import sys
from aiocryptopay import AioCryptoPay, Networks

# Фікс шляхів
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)
import my_token


# ГЛОБАЛЬНОГО cryptopay = AioCryptoPay(...) ТУТ БУТИ НЕ ПОВИННО!

async def create_crypto_invoice(amount_usd):
    """Створює рахунок у CryptoBot"""
    # Створюємо клієнт прямо всередині функції
    cp = AioCryptoPay(token=my_token.CRYPTO_TOKEN, network=Networks.MAIN_NET)

    invoice = await cp.create_invoice(asset='USDT', amount=amount_usd)

    # Закриваємо сесію клієнта після роботи (дуже важливо!)
    await cp.close()
    return invoice


async def get_invoice_status(invoice_id):
    """Перевіряє чи оплачений рахунок"""
    cp = AioCryptoPay(token=my_token.CRYPTO_TOKEN, network=Networks.MAIN_NET)

    invoices = await cp.get_invoices(invoice_ids=invoice_id)
    await cp.close()

    if invoices and invoices[0].status == 'paid':
        return True
    return False