import sqlite3 as sq
from datetime import datetime, timedelta


def get_conn():
    # check_same_thread=False потрібен для роботи з aiogram
    return sq.connect('picto.db', check_same_thread=False)

def db_init():
    conn = get_conn()
    # Переконайся, що є lang TEXT DEFAULT 'en'
    conn.execute("""CREATE TABLE IF NOT EXISTS users(
                 user_id INTEGER PRIMARY KEY, 
                 user_name TEXT, 
                 cycle_date TEXT, 
                 cycle_limit INTEGER DEFAULT 1, 
                 max_cycle_limit INTEGER DEFAULT 1,
                 sub_until TEXT,
                 lang TEXT DEFAULT 'en')""")
    conn.commit()

def set_user_lang(user_id, lang):
    conn = get_conn()
    conn.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()

def get_user_data(user_id):
    conn = get_conn()
    cur = conn.cursor()
    # ВАЖЛИВО: додаємо lang у вибірку
    cur.execute("SELECT cycle_limit, cycle_date, max_cycle_limit, lang FROM users WHERE user_id = ?", (user_id,))
    return cur.fetchone()


def upsert_user(user_id, name):
    conn = get_conn()
    conn.execute("""
        INSERT INTO users (user_id, user_name) VALUES (?, ?) 
        ON CONFLICT(user_id) DO UPDATE SET user_name = excluded.user_name
    """, (user_id, name))
    conn.commit()


def check_reset_limit(user_id):
    conn = get_conn()
    cur = conn.cursor()
    data = get_user_data(user_id)
    if not data: return

    # Перевірка часу для скидання ліміту (кожні 3 години)
    last_date_str = data[1]
    last_date = datetime.strptime(last_date_str, "%Y-%m-%d %H:%M:%S") if last_date_str else datetime.min

    if datetime.now() - last_date > timedelta(hours=3):
        conn.execute("UPDATE users SET cycle_limit = max_cycle_limit, cycle_date = ? WHERE user_id = ?",
                     (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        conn.commit()


def consume_one(user_id):
    """Списує один ліміт у користувача"""
    conn = get_conn()
    conn.execute("UPDATE users SET cycle_limit = cycle_limit - 1 WHERE user_id = ?", (user_id,))
    conn.commit()


def set_sub(user_id, months):
    limit = 15 # Підписникам даємо 15 фото
    end_date = (datetime.now() + timedelta(days=30 * months)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute("UPDATE users SET max_cycle_limit = ?, cycle_limit = ?, sub_until = ? WHERE user_id = ?",
                 (limit, limit, end_date, user_id))
    conn.commit()