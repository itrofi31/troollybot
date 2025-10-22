import os
import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    LabeledPrice,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils import executor, exceptions
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from dotenv import load_dotenv

from database import Database
from info import about_text
from admin import register_admin_handlers
from logger_config import setup_logger


# ---------- Логирование ----------
setup_logger()

# ---------- Настройки ----------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
SUPPORT_USER_ID = int(os.getenv("SUPPORT_USER_ID"))
DEV_USER_ID = int(os.getenv("DEV_USER_ID"))
MONTH_PRICE = int(os.getenv("MONTH_PRICE", "50000"))
FULL_PRICE = int(os.getenv("FULL_PRICE", "150000"))

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ---------- Инициализация БД ----------
db = Database()
register_admin_handlers(dp, db, SUPPORT_USER_ID, DEV_USER_ID, bot)

# ---------- Меню ----------
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(
    KeyboardButton("Текущий статус"),
    KeyboardButton("ℹ️ О клубе"),
    KeyboardButton("Поддержка"),
    KeyboardButton("💳 Доступ на месяц"),
    KeyboardButton("📚 Полный доступ"),
)

buy_month_inline = InlineKeyboardMarkup().add(
    InlineKeyboardButton("💳 Оплатить месяц", callback_data="buy_month")
)

buy_full_inline = InlineKeyboardMarkup().add(
    InlineKeyboardButton("💳 Оплатить полный доступ", callback_data="buy_full")
)


# ---------- FSM поддержки ----------
class SupportForm(StatesGroup):
    waiting_for_message = State()


class PaymentForm(StatesGroup):
    waiting_for_email = State()


def user_info(user: types.User):
    return f"{user.id} (@{user.username or user.full_name})"


# ---------- Обработка сообщений ----------
@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    try:
        logging.info(f"/start от {user_info(message.from_user)}")
        await message.answer(
            "👋 Привет! Выберите действие из меню 👇", reply_markup=main_menu
        )
    except Exception as e:
        logging.error(
            f"❌ Ошибка в /start для {user_info(message.from_user)}: {e}", exc_info=True
        )


@dp.message_handler()
async def any_message(message: types.Message):
    try:
        if not message.text:
            return

        if message.text.startswith("/"):
            return

        logging.info(f"Сообщение от {user_info(message.from_user)}: {message.text}")

        if message.text == "💳 Доступ на месяц":
            logging.info(
                f"Пользователь {user_info(message.from_user)} открыл оплату месяца"
            )
            await message.answer(
                f"💰 Доступ в книжный клуб на 30 дней: {MONTH_PRICE/100:.2f} ₽\nНажми кнопку ниже, чтобы оплатить 👇",
                reply_markup=buy_month_inline,
            )

        elif message.text == "📚 Полный доступ":
            logging.info(
                f"Пользователь {user_info(message.from_user)} открыл оплату полного доступа"
            )
            await message.answer(
                f"💰 Полный доступ: {FULL_PRICE/100:.2f} ₽\nНажми кнопку ниже, чтобы оплатить 👇",
                reply_markup=buy_full_inline,
            )

        elif message.text == "Текущий статус":
            logging.info(
                f"Пользователь {user_info(message.from_user)} запросил статус подписки"
            )
            expiry = db.get_expiry(message.from_user.id)
            full = db.has_full_access(message.from_user.id)

            info = "📊 Ваш текущий статус подписки:"

            if full:
                info += "\n✅ У вас полный доступ."
                await message.answer(info, reply_markup=main_menu)

            elif expiry and expiry > datetime.now():
                days_left = (expiry - datetime.now()).days
                info += f"\n✅ Ваша подписка активна ещё {days_left} дней."
                await message.answer(info, reply_markup=main_menu)

            else:
                info += "\n❌ Подписка не активна😟."
                await message.answer(info, reply_markup=main_menu)

                # И только теперь — предложения оплатить
                await message.answer(
                    f"💳 Хочешь продлить? 👇", reply_markup=buy_month_inline
                )
                await message.answer(
                    f"📚 Или полный доступ: 👇", reply_markup=buy_full_inline
                )

        elif message.text == "ℹ️ О клубе":
            logging.info(
                f"Пользователь {user_info(message.from_user)} открыл информацию о клубе"
            )
            await message.answer(
                about_text, reply_markup=main_menu, parse_mode="Markdown"
            )

        elif message.text == "Поддержка":
            logging.info(
                f"Пользователь {user_info(message.from_user)} пишет в поддержку"
            )
            await message.answer(
                "📝 Опишите вашу проблему. Я передам её администратору."
            )
            await SupportForm.waiting_for_message.set()

        else:
            await message.answer("Выберите действие из меню 👇", reply_markup=main_menu)

    except Exception as e:
        logging.error(
            f"❌ Ошибка обработки сообщения от {user_info(message.from_user)}: {e}",
            exc_info=True,
        )
        await message.answer(
            "⚠️ Произошла ошибка. Попробуйте ещё раз или обратитесь в поддержку."
        )


# ---------- Callback оплаты ----------
@dp.callback_query_handler(lambda c: c.data in ["buy_month", "buy_full"])
async def process_buy_callback(callback_query: types.CallbackQuery):
    try:
        subscription_type = callback_query.data
        label = (
            "Полный доступ" if subscription_type == "buy_full" else "Месячный доступ"
        )
        amount = FULL_PRICE if subscription_type == "buy_full" else MONTH_PRICE
        prices = [LabeledPrice(label=label, amount=amount)]

        logging.info(
            f"➡️ Пользователь {callback_query.from_user.id} {callback_query.from_user}: нажал {callback_query.data}"
        )

        await bot.send_invoice(
            chat_id=callback_query.from_user.id,
            title=label,
            description=f"{label} в книжный клуб",
            payload=subscription_type,
            provider_token=PROVIDER_TOKEN,
            currency="RUB",
            prices=prices,
            start_parameter=subscription_type,
            need_email=True,
            send_email_to_provider=True,
        )
    except Exception as e:
        logging.error(
            f"❌ Ошибка создания счёта для {callback_query.from_user.id}", exc_info=True
        )
        await callback_query.answer(
            "⚠️ Не удалось создать счёт. Попробуйте позже.", show_alert=True
        )


@dp.pre_checkout_query_handler(lambda q: True)
async def pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    try:
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    except Exception as e:
        logging.error(
            f"❌ Ошибка pre_checkout для {pre_checkout_query.from_user.id}: {e}",
            exc_info=True,
        )


@dp.message_handler(content_types=types.ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    try:
        new_expiry = db.add_or_update_subscription(
            message.from_user.id,
            message.from_user.username,
            months=1,
            full_access=(message.successful_payment.invoice_payload == "buy_full"),
            amount=message.successful_payment.total_amount,
            currency=message.successful_payment.currency,
        )

        invite = await bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)

        expiry_text = (
            new_expiry.strftime("%d.%m.%Y") if new_expiry else "у вас полный доступ✅"
        )

        await message.answer(
            f"✅ Оплата успешно получена!\n"
            f"Подписка активна до: {expiry_text}.\n\n"
            f"Вот ссылка на канал:\n{invite.invite_link}, присоединяйтесь!",
            reply_markup=main_menu,
        )

        pay = message.successful_payment
        logging.info(
            f"✅ УСПЕШНАЯ ОПЛАТА | User {user_info(message.from_user)} | "
            f"{pay.total_amount/100} {pay.currency} | Тип: {pay.invoice_payload}"
        )
    except Exception as e:
        logging.error(
            f"❌ Ошибка при обработке успешной оплаты {user_info(message.from_user)}",
            exc_info=True,
        )
        await message.answer(
            "⚠️ Произошла ошибка при регистрации оплаты. Администратор уже уведомлен."
        )
        await bot.send_message(
            SUPPORT_USER_ID,
            f"📩 Произошла ошибка при регистрации оплаты от {user_info(message.from_user)}",
        )


# ---------- Поддержка ----------
@dp.message_handler(state=SupportForm.waiting_for_message)
async def process_support_message(message: types.Message, state: FSMContext):
    try:
        await bot.send_message(
            SUPPORT_USER_ID,
            f"📩 Запрос от {user_info(message.from_user)}:\n\n{message.text}",
        )
        await message.answer(
            "✅ Ваш запрос отправлен администратору.", reply_markup=main_menu
        )
        logging.info(
            f"📩 Сообщение в поддержку от {user_info(message.from_user)}: {message.text}"
        )
    except exceptions.BotBlocked:
        await message.answer("⚠️ Не удалось отправить запрос администратору.")
        logging.error(
            f"❌ Сообщение в поддержку не отправлено!!! от {user_info(message.from_user)}: {message.text}"
        )
    except Exception as e:
        logging.error(
            f"❌ Ошибка отправки в поддержку от {user_info(message.from_user)}: {e}",
            exc_info=True,
        )
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")
    finally:
        await state.finish()


# ---------- Планировщик подписок ----------
async def check_subscriptions():
    """Проверка подписок с обработкой ошибок"""
    while True:
        try:
            subscriptions = db.get_all_subscriptions()

            for (
                user_id,
                username,
                expiry_date,
                full_access,
                status,
                notified,
            ) in subscriptions:
                try:
                    # Полный доступ не истекает
                    if full_access:
                        continue

                    # Проверяем наличие даты
                    if not expiry_date:
                        continue

                    try:
                        expiry = datetime.fromisoformat(expiry_date)
                    except (ValueError, TypeError) as e:
                        logging.error(
                            f"❌ Некорректная дата для {user_id} ({username}): {expiry_date}"
                        )
                        continue

                    days_left = (expiry - datetime.now()).days

                    # Уведомление за 3 дня
                    if days_left <= 3 and notified == 0:
                        try:
                            await bot.send_message(
                                user_id,
                                "🔔 Ваша подписка заканчивается через 3 дня! Чтобы не потерять доступ в клуб, оплатите ещё один месяц.",
                            )
                            db.mark_notified(user_id)
                            logging.info(
                                f"🔔 Напоминание: у {user_id} ({username}) осталось {days_left} дней подписки"
                            )
                        except exceptions.BotBlocked:
                            logging.warning(
                                f"⚠️ Бот заблокирован пользователем {user_id} ({username})"
                            )
                        except Exception as e:
                            logging.error(
                                f"❌ Ошибка отправки уведомления {user_id} ({username}): {e}"
                            )

                    # Подписка истекла
                    elif expiry < datetime.now() and status == "active":
                        try:
                            await bot.ban_chat_member(CHANNEL_ID, user_id)
                            await bot.unban_chat_member(CHANNEL_ID, user_id)
                            logging.info(
                                f"🚫 Подписка истекла у {user_id} ({username}). Удаляем из канала."
                            )

                            await bot.send_message(
                                user_id,
                                "🚫 Ваш доступ в книжный клуб к сожалению истек. Вы сможете вернуться, оплатив по кнопке ниже👇.",
                            )
                        except exceptions.BotBlocked:
                            logging.warning(
                                f"⚠️ Бот заблокирован пользователем {user_id} ({username})"
                            )
                        except Exception as e:
                            logging.error(
                                f"❌ Ошибка при удалении {user_id} ({username}) из канала: {e}"
                            )

                        db.expire_user(user_id)

                except Exception as e:
                    logging.error(
                        f"❌ Ошибка обработки подписки для {user_id} ({username}): {e}",
                        exc_info=True,
                    )
                    continue

            await asyncio.sleep(86400)  # Проверяем раз в день

        except Exception as e:
            logging.error(
                f"❌ Критическая ошибка в планировщике подписок: {e}", exc_info=True
            )
            await asyncio.sleep(300)  # При ошибке ждём 5 минут и пробуем снова


# ---------- Старт ----------
async def on_startup(dp):
    asyncio.create_task(check_subscriptions())
    logging.info("🌐 Планировщик подписок запущен.")


if __name__ == "__main__":
    logging.info("🚀 Бот запущен и работает 24/7")
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
