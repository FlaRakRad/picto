import sqlite3 as sq
from datetime import datetime, timedelta
import config  # Переконайся, що config.py на місці


def get_conn():
    # Таймаут 30 секунд та WAL-режим для стабільної роботи в декілька потоків
    conn = sq.connect('picto.db', check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def db_init():
    conn = get_conn()

    # 1. СТВОРЕННЯ БАЗОВИХ ТАБЛИЦЬ (ЯКЩО ВЗАГАЛІ НЕМАЄ)
    conn.execute("""CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, user_name TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY AUTOINCREMENT)""")

    # 2. ФУНКЦІЯ ДЛЯ АВТО-МІГРАЦІЙ
    def add_col(table, col, data_type):
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {data_type}")
            print(f"[DB-LOG] Додано колонку {col} в {table}")
        except:
            pass  # Якщо вже є - ігноруємо

    # Оновлення таблиці USERS
    add_col("users", "cycle_date", "TEXT")
    add_col("users", "cycle_limit", f"INTEGER DEFAULT {config.FREE_LIMIT}")
    add_col("users", "max_cycle_limit", f"INTEGER DEFAULT {config.FREE_LIMIT}")
    add_col("users", "lang", "TEXT DEFAULT 'en'")
    add_col("users", "sub_until", "TEXT")
    add_col("users", "total_processed", "INTEGER DEFAULT 0")

    # Оновлення таблиці TASKS
    add_col("tasks", "user_id", "INTEGER")
    add_col("tasks", "file_name", "TEXT")
    add_col("tasks", "function", "TEXT")
    add_col("tasks", "priority", "INTEGER DEFAULT 0")
    add_col("tasks", "status", "TEXT DEFAULT 'pending'")
    add_col("tasks", "output_name", "TEXT")
    add_col("tasks", "batch_id", "TEXT")
    add_col("tasks", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    # Оновлення таблиці TRANSACTIONS
    add_col("transactions", "user_id", "INTEGER")
    add_col("transactions", "amount", "REAL")
    add_col("transactions", "currency", "TEXT")
    add_col("transactions", "method", "TEXT")
    add_col("transactions", "external_id", "TEXT")
    add_col("transactions", "status", "TEXT DEFAULT 'pending'")
    add_col("transactions", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    conn.commit()
    print("[DB] Перевірка бази завершена. WAL активовано.")


# --- РОБОТА З ДАНИМИ ЮЗЕРА ---

def get_user_data(user_id):
    conn = get_conn()
    cur = conn.cursor()
    # ПОРЯДОК МАЄ БУТИ ТАКИМ (збігається з іншими файлами):
    # 0:cycle_limit, 1:cycle_date, 2:max_cycle_limit, 3:lang, 4:sub_until, 5:total_processed
    cur.execute("""SELECT cycle_limit, cycle_date, max_cycle_limit, lang, sub_until, total_processed 
                   FROM users WHERE user_id = ?""", (user_id,))
    return cur.fetchone()


def upsert_user(user_id, name):
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Додаємо нового, або просто оновлюємо ім'я, не зачіпаючи ліміти старого
    conn.execute("""
        INSERT INTO users (user_id, user_name, cycle_date, max_cycle_limit, cycle_limit) 
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET user_name = excluded.user_name
    """, (user_id, name, now, config.FREE_LIMIT, config.FREE_LIMIT))
    conn.commit()


def check_reset_limit(user_id):
    conn = get_conn()
    u = get_user_data(user_id)
    if not u or not u[1]: return datetime.now()

    now = datetime.now()
    last_date = datetime.strptime(u[1], "%Y-%m-%d %H:%M:%S")
    sub_until = u[4]

    # 1. ПЕРЕВІРКА НА ЗАКІНЧЕННЯ VIP
    if sub_until:
        if now > datetime.strptime(sub_until, "%Y-%m-%d %H:%M:%S"):
            conn.execute("UPDATE users SET max_cycle_limit = ?, sub_until = NULL WHERE user_id = ?",
                         (config.FREE_LIMIT, user_id))
            conn.commit()

    # 2. СКИНУТИ ЛІМІТ КОЖНУ ГОДИНУ
    next_reset = last_date + timedelta(hours=1)
    if now >= next_reset:
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        # Отримуємо свіжий макс_ліміт після можливого зльоту підписки
        cur = conn.cursor()
        cur.execute("SELECT max_cycle_limit FROM users WHERE user_id = ?", (user_id,))
        m_lim = cur.fetchone()[0]
        conn.execute("UPDATE users SET cycle_limit = ?, cycle_date = ? WHERE user_id = ?",
                     (m_lim, now_str, user_id))
        conn.commit()
        return now + timedelta(hours=1)

    return next_reset


def consume_one(user_id, count=1):
    conn = get_conn()
    # Списуємо з балансу за годину та додаємо до загального лічильника 'Оброблено всього'
    conn.execute("""UPDATE users SET cycle_limit = cycle_limit - ?, 
                    total_processed = total_processed + ? WHERE user_id = ?""",
                 (count, count, user_id))
    conn.commit()


def set_user_lang(user_id, lang):
    conn = get_conn()
    conn.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()


# --- ФУНКЦІЇ БІЛІНГУ ТА ЧЕРГИ ---

def set_sub(user_id, months):
    now = datetime.now()
    expire_date = (now + timedelta(days=30 * months)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    # При активації VIP відразу даємо макс. кількість фото
    conn.execute("""UPDATE users SET max_cycle_limit = ?, cycle_limit = ?, sub_until = ? 
                 WHERE user_id = ?""", (config.VIP_LIMIT, config.VIP_LIMIT, expire_date, user_id))
    conn.commit()


def add_transaction(user_id, amount, currency, method, external_id):
    conn = get_conn()
    conn.execute("""INSERT INTO transactions (user_id, amount, currency, method, external_id) 
                 VALUES (?,?,?,?,?)""", (user_id, amount, currency, method, external_id))
    conn.commit()


def update_transaction_status(ext_id, status):
    conn = get_conn()
    conn.execute("UPDATE transactions SET status = ? WHERE external_id = ?", (status, ext_id))
    conn.commit()


def add_task(user_id, file_name, function, priority, batch_id):
    conn = get_conn()
    conn.execute("""INSERT INTO tasks (user_id, file_name, function, priority, batch_id) 
                 VALUES (?,?,?,?,?)""", (user_id, file_name, function, priority, batch_id))
    conn.commit()