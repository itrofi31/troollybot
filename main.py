import os
import asyncio
import logging
from datetime import datetime

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


# ---------- Асинхронный вызов синхронной БД ----------
async def run_db(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


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


# ---------- Утилита для логов ----------
def user_info(user: types.User):
    return f"{user.id} (@{user.username or user.full_name})"


# ---------- Хэндлер /start ----------
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


# ---------- Хэндлер "Текущий статус" ----------
@dp.message_handler(text="Текущий статус")
async def current_status(message: types.Message):
    try:
        logging.info(
            f"Пользователь {user_info(message.from_user)} запросил статус подписки"
        )
        user_id = message.from_user.id

        expiry = await run_db(db.get_expiry, user_id)
        full = await run_db(db.has_full_access, user_id)

        info = "📊 Ваш текущий статус подписки:"

        if full:
            info += "\n✅ У вас полный доступ."
        elif expiry and expiry > datetime.now():
            days_left = (expiry - datetime.now()).days
            info += f"\n✅ Ваша подписка активна ещё {days_left} дней."
        else:
            info += "\n❌ Подписка не активна😟."

        # Сначала статус
        await message.answer(info, reply_markup=main_menu)

        # Потом кнопки оплаты (если нет подписки)
        if not full and (not expiry or expiry < datetime.now()):
            await message.answer(
                f"💰 Доступ в книжный клуб на 30 дней: {MONTH_PRICE/100:.2f} ₽\n",
                reply_markup=buy_month_inline,
            )
            await message.answer(
                f"💰 Полный доступ: {FULL_PRICE/100:.2f} ₽\n",
                reply_markup=buy_full_inline,
            )

    except Exception as e:
        logging.error(
            f"❌ Ошибка current_status для {user_info(message.from_user)}: {e}",
            exc_info=True,
        )
        await message.answer("⚠️ Произошла ошибка. Попробуйте ещё раз.")


# ---------- Хэндлеры других кнопок ----------
@dp.message_handler(text="ℹ️ О клубе")
async def info_club(message: types.Message):
    try:
        logging.info(
            f"Пользователь {user_info(message.from_user)} открыл информацию о клубе"
        )
        await message.answer(about_text, reply_markup=main_menu, parse_mode="Markdown")
    except Exception as e:
        logging.error(
            f"❌ Ошибка info_club для {user_info(message.from_user)}: {e}",
            exc_info=True,
        )


@dp.message_handler(text="💳 Доступ на месяц")
async def buy_month(message: types.Message):
    try:
        logging.info(
            f"Пользователь {user_info(message.from_user)} открыл оплату месяца"
        )
        await message.answer(
            f"💰 Доступ в книжный клуб на 30 дней: {MONTH_PRICE/100:.2f} ₽\nНажми кнопку ниже, чтобы оплатить 👇",
            reply_markup=buy_month_inline,
        )
    except Exception as e:
        logging.error(
            f"❌ Ошибка buy_month для {user_info(message.from_user)}: {e}",
            exc_info=True,
        )


@dp.message_handler(text="📚 Полный доступ")
async def buy_full(message: types.Message):
    try:
        logging.info(
            f"Пользователь {user_info(message.from_user)} открыл оплату полного доступа"
        )
        await message.answer(
            f"💰 Полный доступ: {FULL_PRICE/100:.2f} ₽\nНажми кнопку ниже, чтобы оплатить 👇",
            reply_markup=buy_full_inline,
        )
    except Exception as e:
        logging.error(
            f"❌ Ошибка buy_full для {user_info(message.from_user)}: {e}", exc_info=True
        )


@dp.message_handler(text="Поддержка")
async def support(message: types.Message):
    try:
        logging.info(f"Пользователь {user_info(message.from_user)} пишет в поддержку")
        await message.answer("📝 Опишите вашу проблему. Я передам её администратору.")
        await SupportForm.waiting_for_message.set()
    except Exception as e:
        logging.error(
            f"❌ Ошибка support для {user_info(message.from_user)}: {e}", exc_info=True
        )


# ---------- FSM Поддержка ----------
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
            f"➡️ Пользователь {user_info(callback_query.from_user)} нажал {callback_query.data}"
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
            f"❌ Ошибка создания счёта для {user_info(callback_query.from_user)}: {e}",
            exc_info=True,
        )
        await callback_query.answer(
            "⚠️ Не удалось создать счёт. Попробуйте позже.", show_alert=True
        )


# ---------- Успешная оплата ----------
@dp.message_handler(content_types=types.ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    try:
        full_access = message.successful_payment.invoice_payload == "buy_full"
        new_expiry = await run_db(
            db.add_or_update_subscription,
            message.from_user.id,
            message.from_user.username,
            months=1,
            full_access=full_access,
            amount=message.successful_payment.total_amount,
            currency=message.successful_payment.currency,
        )

        invite = await bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)
        expiry_text = new_expiry.strftime("%d.%m.%Y") if new_expiry else "бессрочно"

        await message.answer(
            f"✅ Оплата успешно получена!\nПодписка активна до {expiry_text}.\n\nВот ссылка на канал:\n{invite.invite_link}",
            reply_markup=main_menu,
        )

        pay = message.successful_payment
        logging.info(
            f"✅ УСПЕШНАЯ ОПЛАТА | User {user_info(message.from_user)} | "
            f"{pay.total_amount/100} {pay.currency} | Тип: {pay.invoice_payload}"
        )
    except Exception as e:
        logging.error(
            f"❌ Ошибка успешной оплаты {user_info(message.from_user)}: {e}",
            exc_info=True,
        )
        await message.answer(
            "⚠️ Произошла ошибка при регистрации оплаты. Администратор уже уведомлен."
        )


# ---------- Планировщик подписок ----------
async def check_subscriptions():
    while True:
        try:
            subscriptions = await run_db(db.get_all_subscriptions)

            for (
                user_id,
                username,
                expiry_date,
                full_access,
                status,
                notified,
            ) in subscriptions:
                try:
                    if full_access or not expiry_date:
                        continue
                    expiry = datetime.fromisoformat(expiry_date)
                    days_left = (expiry - datetime.now()).days

                    # Напоминание за 3 дня
                    if days_left == 3 and notified == 0:
                        try:
                            await bot.send_message(
                                user_id,
                                "🔔 Ваша подписка заканчивается через 3 дня! Чтобы не потерять доступ в клуб, оплатите ещё один месяц.",
                            )
                            await run_db(db.mark_notified, user_id)
                            logging.info(
                                f"🔔 Напоминание: у {user_info(types.User(id=user_id, username=username, is_bot=False))} осталось 3 дня подписки"
                            )
                        except exceptions.BotBlocked:
                            logging.warning(
                                f"⚠️ Бот заблокирован пользователем {user_id}"
                            )
                        except Exception as e:
                            logging.error(
                                f"❌ Ошибка отправки уведомления {user_id}: {e}"
                            )

                    # Подписка истекла
                    elif expiry < datetime.now() and status == "active":
                        try:
                            await bot.ban_chat_member(CHANNEL_ID, user_id)
                            await bot.unban_chat_member(CHANNEL_ID, user_id)
                            logging.info(
                                f"🚫 Подписка истекла у {user_id}. Удаляем из канала."
                            )
                            await bot.send_message(
                                user_id,
                                "🚫 Ваш доступ в книжный клуб к сожалению истек. Вы сможете вернуться, оплатив по кнопке ниже👇.",
                            )
                        except exceptions.BotBlocked:
                            logging.warning(
                                f"⚠️ Бот заблокирован пользователем {user_id}"
                            )
                        except Exception as e:
                            logging.error(
                                f"❌ Ошибка при удалении {user_id} из канала: {e}"
                            )

                        await run_db(db.expire_user, user_id)

                except Exception as e:
                    logging.error(
                        f"❌ Ошибка обработки подписки для {user_id}: {e}",
                        exc_info=True,
                    )
                    continue

            await asyncio.sleep(86400)  # Проверяем раз в день

        except Exception as e:
            logging.error(
                f"❌ Критическая ошибка планировщика подписок: {e}", exc_info=True
            )
            await asyncio.sleep(300)


# ---------- Старт ----------
async def on_startup(dp):
    asyncio.create_task(check_subscriptions())
    logging.info("🌐 Планировщик подписок запущен.")


if __name__ == "__main__":
    logging.info("🚀 Бот запущен и работает 24/7")
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
