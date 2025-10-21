import sqlite3
import logging
from datetime import datetime, timedelta


class Database:
    def __init__(self, path="subscriptions.db"):
        try:
            self.db = sqlite3.connect(path, check_same_thread=False)
            self.cur = self.db.cursor()

            # Таблица активных подписок
            self.cur.execute(
                """
                CREATE TABLE IF NOT EXISTS subscriptions (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    expiry_date TEXT,
                    full_access INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    notified_3days INTEGER DEFAULT 0
                )
                """
            )

            # История всех оплат
            self.cur.execute(
                """
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount INTEGER,
                    currency TEXT,
                    payment_date TEXT,
                    expiry_date TEXT,
                    full_access INTEGER DEFAULT 0
                )
                """
            )

            self.db.commit()
            logging.info("✅ База данных инициализирована успешно")
        except Exception as e:
            logging.error(f"❌ Ошибка инициализации БД: {e}", exc_info=True)
            raise

    def add_or_update_subscription(
        self, user_id, username, months=1, full_access=False, amount=0, currency="RUB"
    ):
        """Добавление или продление подписки с полной обработкой ошибок"""
        try:
            now = datetime.now()

            # Валидация входных данных
            if not user_id or not isinstance(user_id, int):
                raise ValueError(f"Некорректный user_id: {user_id}")

            if months < 1:
                raise ValueError(f"Некорректное количество месяцев: {months}")

            # ----- Полный доступ: бессрочно -----
            if full_access:
                expiry = None
                self.cur.execute(
                    """
                    INSERT INTO subscriptions (user_id, username, expiry_date, full_access, status, notified_3days)
                    VALUES (?, ?, NULL, 1, 'active', 0)
                    ON CONFLICT(user_id) DO UPDATE SET
                        username=excluded.username,
                        full_access=1,
                        expiry_date=NULL,
                        status='active',
                        notified_3days=0
                    """,
                    (user_id, username),
                )
                logging.info(f"✅ Полный доступ выдан пользователю {user_id}")

            # ----- Месячная подписка (продлеваем) -----
            else:
                self.cur.execute(
                    "SELECT expiry_date FROM subscriptions WHERE user_id=?", (user_id,)
                )
                result = self.cur.fetchone()

                if result and result[0]:  # есть старая подписка
                    try:
                        old_expiry = datetime.fromisoformat(result[0])
                        if old_expiry > now:
                            expiry = old_expiry + timedelta(days=30 * months)
                        else:
                            expiry = now + timedelta(days=30 * months)
                    except (ValueError, TypeError) as e:
                        logging.warning(
                            f"⚠️ Ошибка парсинга старой даты для {user_id}: {e}"
                        )
                        expiry = now + timedelta(days=30 * months)
                else:
                    expiry = now + timedelta(days=30 * months)

                self.cur.execute(
                    """
                    INSERT INTO subscriptions (user_id, username, expiry_date, full_access, status, notified_3days)
                    VALUES (?, ?, ?, 0, 'active', 0)
                    ON CONFLICT(user_id) DO UPDATE SET
                        username=excluded.username,
                        expiry_date=excluded.expiry_date,
                        full_access=0,
                        status='active',
                        notified_3days=0
                    """,
                    (user_id, username, expiry.isoformat()),
                )
                logging.info(
                    f"✅ Подписка на {months} мес. добавлена для {user_id} до {expiry.strftime('%d.%m.%Y')}"
                )

            # ----- Записываем платеж (всегда, не стираем историю) -----
            self.cur.execute(
                """
                INSERT INTO payments (user_id, amount, currency, payment_date, expiry_date, full_access)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    amount,
                    currency,
                    now.isoformat(),
                    expiry.isoformat() if expiry else None,
                    int(full_access),
                ),
            )

            self.db.commit()
            return expiry

        except Exception as e:
            logging.error(
                f"❌ Ошибка добавления подписки для {user_id}: {e}", exc_info=True
            )
            self.db.rollback()
            raise

    def get_expiry(self, user_id):
        """Получение окончания подписки с проверкой None"""
        try:
            self.cur.execute(
                "SELECT expiry_date, full_access FROM subscriptions WHERE user_id=?",
                (user_id,),
            )
            result = self.cur.fetchone()

            if not result:
                return None

            expiry, full_access = result

            if full_access:
                return datetime.max  # бессрочно

            if not expiry:
                return None

            try:
                return datetime.fromisoformat(expiry)
            except (ValueError, TypeError) as e:
                logging.error(f"❌ Ошибка парсинга даты для {user_id}: {e}")
                return None

        except Exception as e:
            logging.error(
                f"❌ Ошибка получения expiry для {user_id}: {e}", exc_info=True
            )
            return None

    def has_full_access(self, user_id):
        """Проверка полного доступа"""
        try:
            self.cur.execute(
                "SELECT full_access FROM subscriptions WHERE user_id=?", (user_id,)
            )
            result = self.cur.fetchone()
            return bool(result[0]) if result else False
        except Exception as e:
            logging.error(
                f"❌ Ошибка проверки full_access для {user_id}: {e}", exc_info=True
            )
            return False

    def get_user_payments(self, user_id):
        """История всех платежей пользователя"""
        try:
            self.cur.execute(
                """
                SELECT payment_date, amount, currency, expiry_date, full_access
                FROM payments WHERE user_id=?
                ORDER BY payment_date DESC
                """,
                (user_id,),
            )
            return self.cur.fetchall()
        except Exception as e:
            logging.error(
                f"❌ Ошибка получения платежей для {user_id}: {e}", exc_info=True
            )
            return []

    def get_all_subscriptions(self):
        """Все подписки"""
        try:
            self.cur.execute(
                "SELECT user_id, username, expiry_date, full_access, status, notified_3days FROM subscriptions"
            )
            return self.cur.fetchall()
        except Exception as e:
            logging.error(f"❌ Ошибка получения всех подписок: {e}", exc_info=True)
            return []

    def mark_notified(self, user_id):
        """Уведомление за 3 дня (только 1 раз)"""
        try:
            self.cur.execute(
                "UPDATE subscriptions SET notified_3days=1 WHERE user_id=?", (user_id,)
            )
            self.db.commit()
        except Exception as e:
            logging.error(
                f"❌ Ошибка пометки уведомления для {user_id}: {e}", exc_info=True
            )

    def expire_user(self, user_id):
        """Пометить пользователя как истёкшего"""
        try:
            self.cur.execute(
                "UPDATE subscriptions SET status='expired' WHERE user_id=?", (user_id,)
            )
            self.db.commit()
        except Exception as e:
            logging.error(
                f"❌ Ошибка пометки истечения для {user_id}: {e}", exc_info=True
            )

    def get_all_payments_with_users(self):
        """Все платежи с данными пользователей"""
        try:
            self.cur.execute(
                """
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
                """
            )
            return self.cur.fetchall()
        except Exception as e:
            logging.error(f"❌ Ошибка получения всех платежей: {e}", exc_info=True)
            return []

    def get_payments(self, offset=0, limit=20):
        """Платежи с пагинацией"""
        try:
            self.cur.execute(
                """
                SELECT
                    payments.user_id,
                    subscriptions.username,
                    payments.amount,
                    payments.currency,
                    payments.payment_date,
                    payments.expiry_date,
                    payments.full_access
                FROM payments
                LEFT JOIN subscriptions
                ON payments.user_id = subscriptions.user_id
                ORDER BY payments.payment_date DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            return self.cur.fetchall()
        except Exception as e:
            logging.error(f"❌ Ошибка получения платежей: {e}", exc_info=True)
            return []

    def count_payments(self):
        """Количество платежей"""
        try:
            self.cur.execute("SELECT COUNT(*) FROM payments")
            result = self.cur.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logging.error(f"❌ Ошибка подсчета платежей: {e}", exc_info=True)
            return 0

    def get_all_users(self):
        """Все пользователи"""
        try:
            self.cur.execute(
                "SELECT user_id, username, expiry_date, full_access FROM subscriptions"
            )
            return self.cur.fetchall()
        except Exception as e:
            logging.error(f"❌ Ошибка получения всех пользователей: {e}", exc_info=True)
            return []

    def get_active_users(self):
        """Активные пользователи (месячная подписка)"""
        try:
            self.cur.execute(
                "SELECT user_id, username, expiry_date, full_access FROM subscriptions WHERE status='active' AND full_access=0"
            )
            return self.cur.fetchall()
        except Exception as e:
            logging.error(
                f"❌ Ошибка получения активных пользователей: {e}", exc_info=True
            )
            return []

    def get_full_access_users(self):
        """Пользователи с полным доступом"""
        try:
            self.cur.execute(
                "SELECT user_id, username, expiry_date, full_access FROM subscriptions WHERE full_access=1"
            )
            return self.cur.fetchall()
        except Exception as e:
            logging.error(
                f"❌ Ошибка получения пользователей с полным доступом: {e}",
                exc_info=True,
            )
            return []

    def get_expired_users(self):
        """Пользователи с истекшей подпиской"""
        try:
            self.cur.execute(
                "SELECT user_id, username, expiry_date, full_access FROM subscriptions WHERE status='expired'"
            )
            return self.cur.fetchall()
        except Exception as e:
            logging.error(
                f"❌ Ошибка получения истекших пользователей: {e}", exc_info=True
            )
            return []

    def get_user(self, user_id):
        """Получить данные пользователя"""
        try:
            self.cur.execute(
                "SELECT user_id, username, expiry_date, full_access FROM subscriptions WHERE user_id=?",
                (user_id,),
            )
            return self.cur.fetchone()
        except Exception as e:
            logging.error(
                f"❌ Ошибка получения пользователя {user_id}: {e}", exc_info=True
            )
            return None
