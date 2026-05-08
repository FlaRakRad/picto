import sqlite3 as sq
from datetime import datetime, timedelta

def get_conn():
    # timeout=30 і WAL-режим дозволяють боту, воркеру і сендеру писати одночасно
    conn = sq.connect('picto.db', check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def db_init():
    conn = get_conn()
    # 1. ТАБЛИЦЯ КОРИСТУВАЧІВ
    conn.execute("""CREATE TABLE IF NOT EXISTS users(
                 user_id INTEGER PRIMARY KEY, user_name TEXT, 
                 cycle_date TEXT, cycle_limit INTEGER DEFAULT 1, 
                 max_cycle_limit INTEGER DEFAULT 1, sub_until TEXT,
                 lang TEXT DEFAULT 'en')""")

    # 2. ТАБЛИЦЯ ЗАВДАНЬ (додано batch_id)
    conn.execute("""CREATE TABLE IF NOT EXISTS tasks(
                 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                 file_name TEXT, function TEXT, priority INTEGER DEFAULT 0,
                 status TEXT DEFAULT 'pending', output_name TEXT,
                 batch_id TEXT, -- Унікальний ідентифікатор пачки
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()

# --- ФУНКЦІЇ ДЛЯ КОРИСТУВАЧІВ ---

def upsert_user(user_id, name):
    conn = get_conn()
    conn.execute("INSERT INTO users (user_id, user_name) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET user_name = excluded.user_name", (user_id, name))
    conn.commit()

def get_user_data(user_id):
    cur = get_conn().cursor()
    cur.execute("SELECT cycle_limit, cycle_date, max_cycle_limit, lang FROM users WHERE user_id = ?", (user_id,))
    return cur.fetchone()

def consume_one(user_id, count=1):
    conn = get_conn()
    conn.execute("UPDATE users SET cycle_limit = cycle_limit - ? WHERE user_id = ?", (count, user_id))
    conn.commit()

# --- ФУНКЦІЇ ДЛЯ ЗАВДАНЬ ---

def add_task(user_id, file_name, function, priority, batch_id):
    conn = get_conn()
    conn.execute("INSERT INTO tasks (user_id, file_name, function, priority, batch_id) VALUES (?, ?, ?, ?, ?)",
                 (user_id, file_name, function, priority, batch_id))
    conn.commit()

# Додай ці для воркерів
def set_user_lang(user_id, lang):
    conn = get_conn(); conn.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id)); conn.commit()

def set_sub(user_id, months):
    limit = 15
    end_date = (datetime.now() + timedelta(days=30 * months)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn(); conn.execute("UPDATE users SET max_cycle_limit = ?, cycle_limit = ?, sub_until = ? WHERE user_id = ?", (limit, limit, end_date, user_id)); conn.commit()