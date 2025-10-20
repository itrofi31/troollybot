import logging
from logging.handlers import TimedRotatingFileHandler
import os

def setup_logger():
    # Создаём папку для логов
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # Общий логгер
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    # ---------- INFO ----------
    info_handler = TimedRotatingFileHandler(
        "logs/info.log", when="midnight", interval=1, backupCount=7, encoding="utf-8"
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    logger.addHandler(info_handler)

    # ---------- WARNING ----------
    warning_handler = TimedRotatingFileHandler(
        "logs/warning.log", when="midnight", interval=1, backupCount=7, encoding="utf-8"
    )
    warning_handler.setLevel(logging.WARNING)
    warning_handler.setFormatter(formatter)
    logger.addHandler(warning_handler)

    # ---------- ERROR ----------
    error_handler = TimedRotatingFileHandler(
        "logs/error.log", when="midnight", interval=1, backupCount=14, encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    # ---------- Вывод в консоль ----------
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)

    return logger