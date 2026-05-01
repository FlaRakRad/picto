import sqlite3
from datetime import datetime, timedelta

def hard_reset_all_limits():
    # Цей файл "пробігає" по всім юзерам і якщо минуло 3 години, дає нові спроби
    conn = sqlite3.connect('picto.db')
    cursor = conn.cursor()
    # Скидаємо для всіх, у кого ліміт < макс
    cursor.execute("""
        UPDATE users SET cycle_limit = max_cycle_limit 
        WHERE (julianday('now') - julianday(cycle_date)) * 24 > 3
    """)
    conn.commit()
    print("🧹 БД очищена!")
    conn.close()

if __name__ == "__main__":
    hard_reset_all_limits()