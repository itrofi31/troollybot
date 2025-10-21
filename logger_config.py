import logging
from logging.handlers import TimedRotatingFileHandler
import os


def setup_logger():
    """Настройка логирования с ротацией файлов и обработкой ошибок"""
    try:
        # Удаляем старые обработчики
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        # Создаём папку для логов
        if not os.path.exists("logs"):
            os.makedirs("logs")

        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

        # ---------- Файл с ротацией ----------
        try:
            file_handler = TimedRotatingFileHandler(
                "logs/bot.log",
                when="midnight",
                interval=1,
                backupCount=14,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"⚠️ Не удалось создать файл логов: {e}")

        # ---------- Консоль ----------
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # ---------- aiogram логгер ----------
        aiogram_logger = logging.getLogger("aiogram")
        aiogram_logger.handlers = []
        aiogram_logger.propagate = True  # будет использовать корневой логгер

        logging.info("✅ Логирование настроено успешно")
        return logger

    except Exception as e:
        print(f"❌ Критическая ошибка настройки логирования: {e}")
        # Даже если не удалось настроить, возвращаем базовый логгер
        return logging.getLogger()
