import sqlite3
from datetime import datetime, timedelta

class Database:
    def __init__(self, path="subscriptions.db"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.cur = self.db.cursor()

        # Таблица активных подписок
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            expiry_date TEXT,
            full_access INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active'
        )
        """)

        # История всех оплат
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

    # ✅ Добавление или продление подписки (только по месяцу или полный доступ)
    def add_or_update_subscription(self, user_id, username, months=1, full_access=False, amount=0, currency="RUB"):
        now = datetime.now()

        # ----- Полный доступ: бессрочно -----
        if full_access:
            expiry = None
            self.cur.execute("""
            INSERT INTO subscriptions (user_id, username, expiry_date, full_access, status)
            VALUES (?, ?, NULL, 1, 'active')
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                full_access=1,
                expiry_date=NULL,
                status='active'
            """, (user_id, username))

        # ----- Месячная подписка (продлеваем) -----
        else:
            self.cur.execute("SELECT expiry_date FROM subscriptions WHERE user_id=?", (user_id,))
            result = self.cur.fetchone()

            if result and result[0]:  # есть старая подписка
                old_expiry = datetime.fromisoformat(result[0])
                if old_expiry > now:
                    expiry = old_expiry + timedelta(days=30 * months)
                else:
                    expiry = now + timedelta(days=30 * months)
            else:
                expiry = now + timedelta(days=30 * months)

            self.cur.execute("""
            INSERT INTO subscriptions (user_id, username, expiry_date, full_access, status)
            VALUES (?, ?, ?, 0, 'active')
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                expiry_date=excluded.expiry_date,
                full_access=0,
                status='active'
            """, (user_id, username, expiry.isoformat()))

        # ----- Записываем платеж (всегда, не стираем историю) -----
        self.cur.execute("""
        INSERT INTO payments (user_id, amount, currency, payment_date, expiry_date, full_access)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, amount, currency, now.isoformat(), expiry.isoformat() if expiry else None, int(full_access)))

        self.db.commit()
        return expiry

    # ✅ Получение окончания подписки
    def get_expiry(self, user_id):
        self.cur.execute("SELECT expiry_date, full_access FROM subscriptions WHERE user_id=?", (user_id,))
        result = self.cur.fetchone()
        if not result:
            return None
        expiry, full_access = result
        if full_access:
            return datetime.max  # бессрочно
        return datetime.fromisoformat(expiry) if expiry else None

    # ✅ Проверка полного доступа
    def has_full_access(self, user_id):
        self.cur.execute("SELECT full_access FROM subscriptions WHERE user_id=?", (user_id,))
        result = self.cur.fetchone()
        return bool(result[0]) if result else False

    # ✅ История всех платежей
    def get_user_payments(self, user_id):
        self.cur.execute("""
        SELECT payment_date, amount, currency, expiry_date, full_access
        FROM payments WHERE user_id=?
        ORDER BY payment_date DESC
        """, (user_id,))
        return self.cur.fetchall()

    # ✅ Все подписки
    def get_all_subscriptions(self):
        self.cur.execute("SELECT user_id, username, expiry_date, full_access, status FROM subscriptions")
        return self.cur.fetchall()

    # ✅ Пометить пользователя как истёкшего
    def expire_user(self, user_id):
        self.cur.execute("UPDATE subscriptions SET status='expired' WHERE user_id=?", (user_id,))
        self.db.commit()
        
    def get_all_payments_with_users(self):
        self.cur.execute("""
        SELECT 
            payments.user_id,
            subscriptions.username,
            payments.payment_date,
            payments.amount,
            payments.currency,
            payments.expiry_date,
            payments.full_access
        FROM payments
        LEFT JOIN subscriptions
        ON payments.user_id = subscriptions.user_id
        ORDER BY payments.payment_date DESC
        """)
        return self.cur.fetchall()
    def get_payments(self, offset=0, limit=20):
         with self.connection:
                return self.cursor.execute("""
								SELECT user_id, username, amount, currency, date, expiry, full_access
								FROM payments
								ORDER BY date DESC
								LIMIT ? OFFSET ?
						""", (limit, offset)).fetchall()
    def count_payments(self):
    	with self.connection:
      	  return self.cursor.execute("SELECT COUNT(*) FROM payments").fetchone()[0]