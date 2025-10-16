import sqlite3
from datetime import datetime, timedelta

class Database:
    def __init__(self, path="subscriptions.db"):
        self.db = sqlite3.connect(path)
        self.cur = self.db.cursor()

        # Таблица подписок
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            expiry_date TEXT,
            full_access INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active'
        )
        """)

        # Таблица истории оплат
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            currency TEXT,
            payment_date TEXT,
            expiry_date TEXT,
            full_access INTEGER DEFAULT 0
        )
        """)

        self.db.commit()

    # ---------- Подписка ----------
    def add_or_update_subscription(self, user_id, username, months=1, full_access=False, amount=0, currency="RUB"):
        now = datetime.now()

        if full_access:
            expiry = None  # полная подписка бессрочная
            self.cur.execute("""
            INSERT OR REPLACE INTO subscriptions (user_id, username, expiry_date, full_access, status)
            VALUES (?, ?, ?, 1, 'active')
            """, (user_id, username, expiry))
        else:
            # продлеваем месячную подписку
            self.cur.execute("SELECT expiry_date FROM subscriptions WHERE user_id=?", (user_id,))
            result = self.cur.fetchone()
            if result and result[0]:
                old_expiry = datetime.fromisoformat(result[0])
                if old_expiry > now:
                    expiry = old_expiry + timedelta(days=30*months)
                else:
                    expiry = now + timedelta(days=30*months)
            else:
                expiry = now + timedelta(days=30*months)

            self.cur.execute("""
            INSERT OR REPLACE INTO subscriptions (user_id, username, expiry_date, full_access, status)
            VALUES (?, ?, ?, 0, 'active')
            """, (user_id, username, expiry.isoformat()))

        # ---------- Лог оплаты ----------
        payment_expiry = expiry.isoformat() if expiry else None
        self.cur.execute("""
        INSERT INTO payments (user_id, amount, currency, payment_date, expiry_date, full_access)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, amount, currency, now.isoformat(), payment_expiry, int(full_access)))

        self.db.commit()
        return expiry

    # ---------- Получить дату окончания подписки ----------
    def get_expiry(self, user_id):
        self.cur.execute("SELECT expiry_date, full_access FROM subscriptions WHERE user_id=?", (user_id,))
        result = self.cur.fetchone()
        if not result:
            return None
        expiry, full_access = result
        if full_access:
            return datetime.max  # полная подписка бессрочная
        return datetime.fromisoformat(expiry) if expiry else None

    # ---------- История оплат ----------
    def get_user_payments(self, user_id):
        self.cur.execute("""
        SELECT payment_date, amount, currency, expiry_date, full_access
        FROM payments WHERE user_id=?
        ORDER BY payment_date DESC
        """, (user_id,))
        return self.cur.fetchall()

    # ---------- Все подписки ----------
    def get_all_subscriptions(self):
        self.cur.execute("""
        SELECT user_id, username, expiry_date, full_access, status
        FROM subscriptions
        """)
        return self.cur.fetchall()

    # ---------- Истекшая подписка ----------
    def expire_user(self, user_id):
        self.cur.execute("""
        UPDATE subscriptions SET status='expired' WHERE user_id=?
        """, (user_id,))
        self.db.commit()