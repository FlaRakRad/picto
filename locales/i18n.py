# Імпортуємо всі файли мов, які ти створив
from locales import uk, en, de, fr, it, pl, es, pt, tr

# Словник усіх доступних мов
LANGUAGES = {
    'uk': uk.text,
    'en': en.text,
    'de': de.text,
    'fr': fr.text,
    'it': it.text,
    'pl': pl.text,
    'es': es.text,
    'pt': pt.text,
    'tr': tr.text

}

def get_t(lang, key, **kwargs):
    """
    Універсальна функція для отримання тексту.
    lang - код мови (uk, en...)
    key - ключ тексту (btn_profile, processing...)
    kwargs - змінні для вставки (напр. count=10)
    """
    # Якщо мови юзера немає в базі — ставимо англійську
    lang_data = LANGUAGES.get(lang, LANGUAGES['en'])

    # Шукаємо ключ у вибраній мові, якщо немає — беремо з англійської
    text = lang_data.get(key, LANGUAGES['en'].get(key, f"Missing key: {key}"))

    # Якщо передані змінні (напр. {count}), підставляємо їх
    return text.format(**kwargs) if kwargs else text