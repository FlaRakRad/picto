import sqlite3 as sq
from datetime import datetime, timedelta


def get_conn():
    # check_same_thread=False дозволяє одночасно звертатися з бота і воркерів
    return sq.connect('picto.db', check_same_thread=False)


def db_init():
    conn = get_conn()

    # 1. ТАБЛИЦЯ КОРИСТУВАЧІВ (твоя база)
    conn.execute("""CREATE TABLE IF NOT EXISTS users(
                 user_id INTEGER PRIMARY KEY, 
                 user_name TEXT, 
                 cycle_date TEXT, 
                 cycle_limit INTEGER DEFAULT 1, 
                 max_cycle_limit INTEGER DEFAULT 1,
                 sub_until TEXT,
                 lang TEXT DEFAULT 'en')""")

    # 2. ТАБЛИЦЯ ЧЕРГИ ЗАВДАНЬ (для модульної обробки)
    conn.execute("""CREATE TABLE IF NOT EXISTS tasks(
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER,
                 file_name TEXT,      -- Назва в tmp/queue/
                 function TEXT,       -- Яку папку обрав (upscale, eraser...)
                 priority INTEGER DEFAULT 0,
                 status TEXT DEFAULT 'pending', -- pending, processing, done, error
                 output_name TEXT,    -- Назва готового файлу
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    conn.commit()


# --- ФУНКЦІЇ ДЛЯ КОРИСТУВАЧІВ ---

def upsert_user(user_id, name):
    conn = get_conn()
    conn.execute("""
        INSERT INTO users (user_id, user_name) VALUES (?, ?) 
        ON CONFLICT(user_id) DO UPDATE SET user_name = excluded.user_name
    """, (user_id, name))
    conn.commit()


def set_user_lang(user_id, lang):
    conn = get_conn()
    conn.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()


def get_user_data(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT cycle_limit, cycle_date, max_cycle_limit, lang FROM users WHERE user_id = ?", (user_id,))
    return cur.fetchone()


def check_reset_limit(user_id):
    conn = get_conn()
    cur = conn.cursor()
    data = get_user_data(user_id)
    if not data: return

    last_date_str = data[1]
    last_date = datetime.strptime(last_date_str, "%Y-%m-%d %H:%M:%S") if last_date_str else datetime.min

    if datetime.now() - last_date > timedelta(hours=3):
        conn.execute("UPDATE users SET cycle_limit = max_cycle_limit, cycle_date = ? WHERE user_id = ?",
                     (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        conn.commit()


def consume_one(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET cycle_limit = cycle_limit - 1 WHERE user_id = ?", (user_id,))
    conn.commit()   


def set_sub(user_id, months):
    limit = 15
    end_date = (datetime.now() + timedelta(days=30 * months)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute("UPDATE users SET max_cycle_limit = ?, cycle_limit = ?, sub_until = ? WHERE user_id = ?",
                 (limit, limit, end_date, user_id))
    conn.commit()


# --- ФУНКЦІЇ ДЛЯ ЧЕРГИ (ДЛЯ МОДУЛІВ) ---

def add_task(user_id, file_name, function, priority):
    """Бот додає окреме фото в чергу"""
    conn = get_conn()
    conn.execute("INSERT INTO tasks (user_id, file_name, function, priority) VALUES (?, ?, ?, ?)",
                 (user_id, file_name, function, priority))
    conn.commit()


def get_next_task(function_name):
    """Воркер забирає пріоритетне завдання своєї папки"""
    conn = get_conn()
    cur = conn.cursor()
    # Беремо VIP першими (priority DESC), а потім по часу (created_at ASC)
    cur.execute("""SELECT id, file_name, user_id FROM tasks 
                   WHERE function = ? AND status = 'pending' 
                   ORDER BY priority DESC, created_at ASC LIMIT 1""", (function_name,))
    task = cur.fetchone()
    if task:
        # Ставимо статус 'processing', щоб ніхто інший не взяв
        conn.execute("UPDATE tasks SET status = 'processing' WHERE id = ?", (task[0],))
        conn.commit()
    return task


def finish_task(task_id, output_name):
    """Воркер завершує обробку"""
    conn = get_conn()
    conn.execute("UPDATE tasks SET status = 'done', output_name = ? WHERE id = ?", (output_name, task_id))
    conn.commit()