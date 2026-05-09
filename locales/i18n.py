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
    lang_data = LANGUAGES.get(lang, LANGUAGES['en'])
    text = lang_data.get(key, LANGUAGES['en'].get(key, f"Missing key: {key}"))

    try:
        # Спробуємо підставити змінні
        return text.format(**kwargs) if kwargs else text
    except KeyError as e:
        # Якщо в тексті є {змінна}, якої немає в коді - повертаємо просто сирий текст
        print(f"[LANG ERROR] У перекладі '{key}' бракує змінної: {e}")
        return text