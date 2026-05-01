import sqlite3 as sq
from datetime import datetime, timedelta


def get_conn():
    return sq.connect('picto.db', check_same_thread=False)


def db_init():
    conn = get_conn()
    # Додали max_cycle_limit для підписки
    conn.execute("""CREATE TABLE IF NOT EXISTS users(
                 user_id INTEGER PRIMARY KEY, 
                 user_name TEXT, 
                 cycle_date TEXT, 
                 cycle_limit INTEGER DEFAULT 1, 
                 max_cycle_limit INTEGER DEFAULT 1,
                 sub_until TEXT)""")
    conn.commit()


def upsert_user(user_id, name):
    conn = get_conn()
    conn.execute("""
        INSERT INTO users (user_id, user_name) VALUES (?, ?) 
        ON CONFLICT(user_id) DO UPDATE SET user_name = excluded.user_name
    """, (user_id, name))
    conn.commit()


def get_user_data(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT cycle_limit, cycle_date, max_cycle_limit FROM users WHERE user_id = ?", (user_id,))
    return cur.fetchone()


def check_reset_limit(user_id):
    conn = get_conn()
    cur = conn.cursor()
    data = get_user_data(user_id)
    if not data: return

    last_date = datetime.strptime(data[1], "%Y-%m-%d %H:%M:%S") if data[1] else datetime.min
    if datetime.now() - last_date > timedelta(hours=3):
        conn.execute("UPDATE users SET cycle_limit = max_cycle_limit, cycle_date = ? WHERE user_id = ?",
                     (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        conn.commit()


def consume_one(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET cycle_limit = cycle_limit - 1, cycle_date = ? WHERE user_id = ?",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
    conn.commit()


def set_sub(user_id, months):
    limit = 15
    end_date = (datetime.now() + timedelta(days=30 * months)).strftime("%Y-%m-%d")
    conn = get_conn()
    conn.execute("UPDATE users SET max_cycle_limit = ?, cycle_limit = ?, sub_until = ? WHERE user_id = ?",
                 (limit, limit, end_date, user_id))
    conn.commit()


