import sqlite3 as sq
from datetime import datetime, timedelta
import config

def get_conn():
    conn = sq.connect('picto.db', check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def db_check():
    conn = get_conn()
    conn.execute("PRAGMA journal_mode=WAL;")

    # 1. Створюємо базові таблиці (якщо їх взагалі немає)
    conn.execute("""CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, user_name TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY AUTOINCREMENT)""")

    # 2. АВТО-МІГРАЦІЯ (Додаємо відсутні колонки автоматично)
    def add_col(table, col, data_type):
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {data_type}")
            print(f"[DB] Додано колонку {col} в таблицю {table}")
        except:
            pass  # Якщо колонка вже є, SQLite видасть помилку, ми її ігноруємо

    # Колонки для USERS
    add_col("users", "user_name", "TEXT")
    add_col("users", "cycle_date", "TEXT")
    add_col("users", "cycle_limit", "INTEGER DEFAULT 1")
    add_col("users", "max_cycle_limit", "INTEGER DEFAULT 1")
    add_col("users", "lang", "TEXT DEFAULT 'en'")
    add_col("users", "sub_until", "TEXT")
    add_col("users", "total_processed", "INTEGER DEFAULT 0")

    # Колонки для TASKS
    add_col("tasks", "user_id", "INTEGER")
    add_col("tasks", "file_name", "TEXT")
    add_col("tasks", "function", "TEXT")
    add_col("tasks", "priority", "INTEGER DEFAULT 0")
    add_col("tasks", "status", "TEXT DEFAULT 'pending'")
    add_col("tasks", "output_name", "TEXT")
    add_col("tasks", "batch_id", "TEXT")

    # Колонки для TRANSACTIONS
    add_col("transactions", "user_id", "INTEGER")
    add_col("transactions", "amount", "REAL")
    add_col("transactions", "currency", "TEXT")
    add_col("transactions", "method", "TEXT")
    add_col("transactions", "external_id", "TEXT")
    add_col("transactions", "status", "TEXT DEFAULT 'pending'")

    conn.commit()
    print("[DB] Перевірка структури бази завершена. Дані в безпеці.")

def db_init():
    conn = get_conn()
    conn.execute("PRAGMA journal_mode=WAL;")

    # 1. ТАБЛИЦЯ ЮЗЕРІВ (Додав sub_until)
    conn.execute("""CREATE TABLE IF NOT EXISTS users(
                 user_id INTEGER PRIMARY KEY, 
                 user_name TEXT, 
                 cycle_date TEXT, 
                 cycle_limit INTEGER DEFAULT 1, 
                 max_cycle_limit INTEGER DEFAULT 1, 
                 lang TEXT DEFAULT 'en',
                 sub_until TEXT)""")  # <--- ОСЬ ЦЕЙ ВАЖЛИВИЙ РЯДОК

    # 2. ТАБЛИЦЯ ЗАВДАНЬ
    conn.execute("""CREATE TABLE IF NOT EXISTS tasks(
                 id INTEGER PRIMARY KEY AUTOINCREMENT, 
                 user_id INTEGER,
                 file_name TEXT, 
                 function TEXT, 
                 priority INTEGER DEFAULT 0,
                 status TEXT DEFAULT 'pending', 
                 output_name TEXT, 
                 batch_id TEXT,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    # 3. ТАБЛИЦЯ ТРАНЗАКЦІЙ
    conn.execute("""CREATE TABLE IF NOT EXISTS transactions(
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER,
                 amount REAL,
                 currency TEXT,
                 method TEXT,      
                 external_id TEXT, 
                 status TEXT DEFAULT 'pending', 
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    conn.commit()
    print("[DB] Всі таблиці (users, tasks, transactions) успішно ініціалізовані.")

def get_user_data(user_id):
    conn = get_conn()
    cur = conn.cursor()
    # Цей список полів має бути ТАКИМ, бо інакше у тебе вискочить IndexError: tuple index out of range
    cur.execute("""
        SELECT cycle_limit, cycle_date, max_cycle_limit, lang, sub_until, total_processed 
        FROM users 
        WHERE user_id = ?
    """, (user_id,))
    return cur.fetchone()

def check_reset_limit(user_id):
    conn = get_conn()
    # Беремо всі дані юзера
    cur = conn.cursor()
    cur.execute("SELECT cycle_limit, cycle_date, max_cycle_limit, lang, sub_until FROM users WHERE user_id = ?",
                (user_id,))
    u = cur.fetchone()

    if not u: return datetime.now()

    limit, last_date_str, max_limit, lang, sub_until = u
    now = datetime.now()

    # --- ПЕРЕВІРКА НА ЗАКІНЧЕННЯ ПІДПИСКИ ---
    if sub_until:
        sub_end_dt = datetime.strptime(sub_until, "%Y-%m-%d %H:%M:%S")
        if now > sub_end_dt:
            # ПІДПИСКА ЗАКІНЧИЛАСЬ: вертаємо на Free ліміт
            print(f"[EXPIRE] VIP закінчився для {user_id}")
            conn.execute("UPDATE users SET max_cycle_limit = ?, sub_until = NULL WHERE user_id = ?",
                         (config.FREE_LIMIT, user_id))
            conn.commit()
            max_limit = config.FREE_LIMIT

    # --- ЗВИЧАЙНА ПЕРЕВІРКА ГОДИННОГО ЦИКЛУ ---
    last_date = datetime.strptime(last_date_str, "%Y-%m-%d %H:%M:%S") if last_date_str else datetime.min
    next_cycle = last_date + timedelta(hours=1)

    if now >= next_cycle:
        # Поповнюємо фото (насипаємо max_limit)
        conn.execute("UPDATE users SET cycle_limit = max_cycle_limit, cycle_date = ? WHERE user_id = ?",
                     (now.strftime("%Y-%m-%d %H:%M:%S"), user_id))
        conn.commit()
        return now + timedelta(hours=1)

    return next_cycle


# 2. ОНОВЛЕНА ФУНКЦІЯ ПІДПИСКИ (set_sub)
def set_sub(user_id, months):
    now = datetime.now()
    # Рахуємо дату закінчення (зараз + місяці)
    expire_date = (now + timedelta(days=30 * months)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn()
    # Даємо VIP ліміт і записуємо дату "До коли"
    conn.execute("""
        UPDATE users 
        SET max_cycle_limit = ?, 
            cycle_limit = ?, 
            sub_until = ? 
        WHERE user_id = ?
    """, (config.VIP_LIMIT, config.VIP_LIMIT, expire_date, user_id))
    conn.commit()
def consume_one(user_id, count=1):
    conn = get_conn(); conn.execute("UPDATE users SET cycle_limit = cycle_limit - ? WHERE user_id = ?", (count, user_id)); conn.commit()





# ВАЖЛИВО: upsert_user для нового юзера має ставити безкоштовний ліміт з конфігу
def upsert_user(user_id, name):
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Для нового юзера ставимо max_cycle_limit = FREE_LIMIT
    conn.execute("""
        INSERT INTO users (user_id, user_name, cycle_date, max_cycle_limit, cycle_limit) 
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET user_name = excluded.user_name
    """, (user_id, name, now, config.FREE_LIMIT, config.FREE_LIMIT))
    conn.commit()

def add_task(user_id, file_name, function, priority, batch_id):
    conn = get_conn(); conn.execute("INSERT INTO tasks (user_id, file_name, function, priority, batch_id) VALUES (?,?,?,?,?)", (user_id, file_name, function, priority, batch_id)); conn.commit()

def add_transaction(u, a, c, m, e):
    conn = get_conn(); conn.execute("INSERT INTO transactions (user_id, amount, currency, method, external_id) VALUES (?,?,?,?,?)", (u,a,c,m,e)); conn.commit()

def update_transaction_status(e, s):
    conn = get_conn(); conn.execute("UPDATE transactions SET status=? WHERE external_id=?", (s, e)); conn.commit()

def set_user_lang(u, l):
    conn = get_conn(); conn.execute("UPDATE users SET lang=? WHERE user_id=?", (l, u)); conn.commit()