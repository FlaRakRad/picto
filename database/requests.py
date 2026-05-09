import sqlite3 as sq
from datetime import datetime, timedelta

def get_conn():
    # Таймаут та WAL режим для паралельної роботи
    conn = sq.connect('picto.db', check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def db_init():
    conn = get_conn()
    # 1. ТАБЛИЦЯ ЮЗЕРІВ
    conn.execute("""CREATE TABLE IF NOT EXISTS users(
                 user_id INTEGER PRIMARY KEY, 
                 user_name TEXT, 
                 cycle_date TEXT, 
                 cycle_limit INTEGER DEFAULT 1, 
                 max_cycle_limit INTEGER DEFAULT 1,
                 sub_until TEXT,
                 lang TEXT DEFAULT 'en')""")

    # 2. ТАБЛИЦЯ ЗАВДАНЬ
    conn.execute("""CREATE TABLE IF NOT EXISTS tasks(
                 id INTEGER PRIMARY KEY AUTOINCREMENT, 
                 user_id INTEGER,
                 file_name TEXT, function TEXT, priority INTEGER DEFAULT 0,
                 status TEXT DEFAULT 'pending', output_name TEXT, batch_id TEXT,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()

def upsert_user(user_id, name):
    conn = get_conn()
    # ТУТ ВИПРАВЛЕНО: Ми не затираємо cycle_date та ліміти при кожному старті
    # Ми використовуємо DEFAULT значення для нових, а для старих тільки UPDATE ім'я
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""
        INSERT INTO users (user_id, user_name, cycle_date) VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET user_name = excluded.user_name
    """, (user_id, name, now))
    conn.commit()

def get_user_data(user_id):
    cur = get_conn().cursor()
    cur.execute("SELECT cycle_limit, cycle_date, max_cycle_limit, lang FROM users WHERE user_id = ?", (user_id,))
    return cur.fetchone()

def check_reset_limit(user_id):
    conn = get_conn()
    data = get_user_data(user_id)
    if not data or not data[1]: return

    last_date = datetime.strptime(data[1], "%Y-%m-%d %H:%M:%S")
    # Перевірка: чи минуло 3 години з останнього оновлення?
    if datetime.now() - last_date > timedelta(hours=3):
        # Оновлюємо ліміти до МАКСИМАЛЬНИХ (щоб VIP не ставали Free)
        conn.execute("""UPDATE users SET cycle_limit = max_cycle_limit, cycle_date = ? 
                     WHERE user_id = ?""", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        conn.commit()
        print(f"[DB] Ліміти оновлено для {user_id}")

def consume_one(user_id, count=1):
    conn = get_conn()
    # Списуємо за кількістю фото в альбомі
    conn.execute("UPDATE users SET cycle_limit = cycle_limit - ? WHERE user_id = ?", (count, user_id))
    conn.commit()

def set_sub(user_id, months):
    limit = 15 # План для підписників
    end_date = (datetime.now() + timedelta(days=30 * months)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute("""UPDATE users SET max_cycle_limit = ?, cycle_limit = ?, sub_until = ? 
                 WHERE user_id = ?""", (limit, limit, end_date, user_id))
    conn.commit()

def add_task(user_id, file_name, function, priority, batch_id):
    conn = get_conn()
    conn.execute("""INSERT INTO tasks (user_id, file_name, function, priority, batch_id) 
                 VALUES (?, ?, ?, ?, ?)""", (user_id, file_name, function, priority, batch_id))
    conn.commit()

def set_user_lang(user_id, lang):
    conn = get_conn(); conn.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id)); conn.commit()