from datetime import datetime, timedelta

FIRST_MONTH_START = datetime(2025, 11, 3)


def calculate_expiry(old_expiry, months=1) -> datetime:
    now = datetime.now()
    if old_expiry and old_expiry > now:
        # Активная подписка → продлеваем от её окончания
        return old_expiry + timedelta(days=30 * months)

    # Новая/истекшая подписка
    # Если покупка до старта → стартуем с даты запуска
    if now < FIRST_MONTH_START:
        return FIRST_MONTH_START + timedelta(days=30 * months)

    # После запуска → обычные 30 дней
    return now + timedelta(days=30 * months)
