import os
import sys
from aiocryptopay import AioCryptoPay, Networks

# Фікс шляхів, щоб бачити корінь проекту
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

import my_token

# Використовуємо твій CRYPTO_TOKEN
cryptopay = AioCryptoPay(
    token=my_token.CRYPTO_TOKEN,
    network=Networks.MAIN_NET  # Для справжніх грошей. Якщо хочеш тест - Networks.TEST_NET
)
async def create_crypto_invoice(amount_usd):
    # Створюємо рахунок в USDT
    invoice = await cryptopay.create_invoice(asset='USDT', amount=amount_usd)
    return invoice

async def get_invoice_status(invoice_id):
    # Питаємо CryptoBot, чи прийшли бабки
    invoices = await cryptopay.get_invoices(invoice_ids=invoice_id)
    if invoices and invoices[0].status == 'paid':
        return True
    return False