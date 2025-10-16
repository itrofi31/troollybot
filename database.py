import sqlite3
from datetime import datetime, timedelta


class Database:
    def __init__(self, path="subscriptions.db"):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.cur = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        # Главная таблица активных подписок
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            expiry_date TEXT,
            status TEXT DEFAULT 'active',
            last_payment TEXT
        )
        """)

        # Таблица истории оплат
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            amount INTEGER,
            currency TEXT,
            payment_date TEXT,
            expiry_date TEXT,
            FOREIGN KEY (user_id) REFERENCES subscriptions (user_id)
        )
        """)

        self.conn.commit()

    # ---------- Работа с подписками ----------
    def get_expiry(self, user_id: int):
        self.cur.execute("SELECT expiry_date FROM subscriptions WHERE user_id=?", (user_id,))
        result = self.cur.fetchone()
        if result:
            return datetime.fromisoformat(result[0])
        return None

    def add_or_update_subscription(self, user_id: int, username: str, amount: int = 0, currency: str = "RUB"):
        expiry_old = self.get_expiry(user_id)
        if expiry_old and expiry_old > datetime.now():
            new_expiry = expiry_old + timedelta(days=30)
        else:
            new_expiry = datetime.now() + timedelta(days=30)

        now = datetime.now().isoformat()

        # Обновляем таблицу подписок
        self.cur.execute("""
        INSERT OR REPLACE INTO subscriptions (user_id, username, expiry_date, status, last_payment)
        VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, new_expiry.isoformat(), "active", now))

        # Добавляем запись в историю оплат
        self.cur.execute("""
        INSERT INTO payments (user_id, username, amount, currency, payment_date, expiry_date)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, username, amount, currency, now, new_expiry.isoformat()))

        self.conn.commit()
        return new_expiry

    def get_all_subscriptions(self):
        self.cur.execute("SELECT user_id, username, expiry_date, status FROM subscriptions")
        return self.cur.fetchall()

    def expire_user(self, user_id: int):
        self.cur.execute("UPDATE subscriptions SET status='expired' WHERE user_id=?", (user_id,))
        self.conn.commit()

    def delete_user(self, user_id: int):
        self.cur.execute("DELETE FROM subscriptions WHERE user_id=?", (user_id,))
        self.conn.commit()

    # ---------- История оплат ----------
    def get_user_payments(self, user_id: int):
        self.cur.execute("""
        SELECT payment_date, amount, currency, expiry_date FROM payments
        WHERE user_id=? ORDER BY payment_date DESC
        """, (user_id,))
        return self.cur.fetchall()

    def get_last_payment(self, user_id: int):
        self.cur.execute("""
        SELECT payment_date, amount, currency FROM payments
        WHERE user_id=? ORDER BY payment_date DESC LIMIT 1
        """, (user_id,))
        return self.cur.fetchone()