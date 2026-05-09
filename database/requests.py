import sqlite3 as sq
from datetime import datetime, timedelta

def get_conn():
    conn = sq.connect('picto.db', check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def db_init():
    conn = get_conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS users(
                 user_id INTEGER PRIMARY KEY, user_name TEXT, 
                 cycle_date TEXT, cycle_limit INTEGER DEFAULT 1, 
                 max_cycle_limit INTEGER DEFAULT 1, lang TEXT DEFAULT 'en')""")
    conn.execute("""CREATE TABLE IF NOT EXISTS tasks(
                 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                 file_name TEXT, function TEXT, priority INTEGER DEFAULT 0,
                 status TEXT DEFAULT 'pending', output_name TEXT, batch_id TEXT,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS transactions(
                 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                 amount REAL, currency TEXT, method TEXT, external_id TEXT,
                 status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()

def upsert_user(user_id, name):
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO users (user_id, user_name, cycle_date) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET user_name = excluded.user_name", (user_id, name, now))
    conn.commit()

def get_user_data(user_id):
    cur = get_conn().cursor()
    cur.execute("SELECT cycle_limit, cycle_date, max_cycle_limit, lang FROM users WHERE user_id = ?", (user_id,))
    return cur.fetchone()

def check_reset_limit(user_id):
    conn = get_conn(); cur = conn.cursor()
    data = get_user_data(user_id)
    if not data or not data[1]: return datetime.now()
    last_date = datetime.strptime(data[1], "%Y-%m-%d %H:%M:%S")
    next_cycle = last_date + timedelta(hours=1)
    if datetime.now() >= next_cycle:
        now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE users SET cycle_limit = max_cycle_limit, cycle_date = ? WHERE user_id = ?", (now_s, user_id))
        conn.commit()
        return datetime.now() + timedelta(hours=1)
    return next_cycle

def consume_one(user_id, count=1):
    conn = get_conn(); conn.execute("UPDATE users SET cycle_limit = cycle_limit - ? WHERE user_id = ?", (count, user_id)); conn.commit()

def set_sub(user_id, months, new_limit):
    conn = get_conn()
    conn.execute("UPDATE users SET max_cycle_limit = ?, cycle_limit = ? WHERE user_id = ?", (new_limit, new_limit, user_id))
    conn.commit()

def add_task(user_id, file_name, function, priority, batch_id):
    conn = get_conn(); conn.execute("INSERT INTO tasks (user_id, file_name, function, priority, batch_id) VALUES (?,?,?,?,?)", (user_id, file_name, function, priority, batch_id)); conn.commit()

def add_transaction(u, a, c, m, e):
    conn = get_conn(); conn.execute("INSERT INTO transactions (user_id, amount, currency, method, external_id) VALUES (?,?,?,?,?)", (u,a,c,m,e)); conn.commit()

def update_transaction_status(e, s):
    conn = get_conn(); conn.execute("UPDATE transactions SET status=? WHERE external_id=?", (s, e)); conn.commit()

def set_user_lang(u, l):
    conn = get_conn(); conn.execute("UPDATE users SET lang=? WHERE user_id=?", (l, u)); conn.commit()