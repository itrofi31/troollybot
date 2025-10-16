import os
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import LabeledPrice, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor, exceptions
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from dotenv import load_dotenv

from database import Database  # ← импортируем наш новый класс БД

# ---------- Настройки ----------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
SUPPORT_USER_ID = int(os.getenv("SUPPORT_USER_ID"))
PRICE = int(os.getenv("PRICE", "30000"))  # 300 руб

if not all([BOT_TOKEN, PROVIDER_TOKEN, CHANNEL_ID, SUPPORT_USER_ID]):
    raise ValueError("❌ Не заданы переменные окружения!")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ---------- Инициализация БД ----------
db = Database()

# ---------- Меню ----------
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(KeyboardButton("💳 Купить доступ"), KeyboardButton("ℹ️ О канале"))
main_menu.add(KeyboardButton("📞 Поддержка"))

buy_inline = InlineKeyboardMarkup().add(
    InlineKeyboardButton("💳 Оплатить доступ", callback_data="buy")
)

# ---------- FSM поддержки ----------
class SupportForm(StatesGroup):
    waiting_for_message = State()

# ---------- Команды ----------
@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    await message.answer(
        "👋 Привет! Добро пожаловать в наш бот.\nВыберите действие из меню 👇",
        reply_markup=main_menu
    )
    
# ---------- История оплат ----------
@dp.message_handler(commands=["payments"])
async def payments_history(message: types.Message):
    # Получаем все платежи пользователя
    await message.answer("Получаем ваши платежи...")

    payments = db.get_user_payments(message.from_user.id)
    
    if not payments:
        await message.answer("❌ У вас пока нет оплат.")
        return

    text = "💳 История оплат:\n\n"
    for payment_date, amount, currency, expiry_date in payments[:10]:  # последние 10
        amount_rub = amount / 100  # если в копейках
        expiry_str = datetime.fromisoformat(expiry_date).strftime("%d.%m.%Y")
        text += f"📅 {payment_date[:16]} — {amount_rub:.2f} {currency} — до {expiry_str}\n"

    await message.answer(text)

@dp.message_handler()
async def any_message(message: types.Message):
    if message.text == "💳 Купить доступ":
        await message.answer(
            f"💰 Подписка: {PRICE/100:.2f} ₽ / месяц\nНажми кнопку ниже, чтобы оплатить 👇",
            reply_markup=buy_inline
        )
    elif message.text == "ℹ️ О канале":
        expiry = db.get_expiry(message.from_user.id)
        if expiry and expiry > datetime.now():
            remain = (expiry - datetime.now()).days
            await message.answer(
                f"✅ Ваша подписка активна ещё {remain} дней.",
                reply_markup=main_menu
            )
        else:
            await message.answer(
                "📘 Это закрытый канал. После оплаты вы получите доступ.",
                reply_markup=main_menu
            )
    elif message.text == "📞 Поддержка":
        await message.answer("📝 Опишите вашу проблему. Я передам её администратору.")
        await SupportForm.waiting_for_message.set()
    else:
        await message.answer("Выберите действие из меню 👇", reply_markup=main_menu)

# ---------- Оплата ----------
@dp.callback_query_handler(lambda c: c.data == "buy")
async def process_buy_callback(callback_query: types.CallbackQuery):
    prices = [LabeledPrice(label="Доступ на 1 месяц", amount=PRICE)]
    await bot.send_invoice(
        callback_query.from_user.id,
        title="Подписка на канал",
        description="Доступ к закрытому Telegram-каналу на 1 месяц",
        payload="subscription_1m",
        provider_token=PROVIDER_TOKEN,
        currency="RUB",
        prices=prices,
        start_parameter="subscription"
    )

@dp.pre_checkout_query_handler(lambda q: True)
async def pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message_handler(content_types=types.ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    new_expiry = db.add_or_update_subscription(message.from_user.id, message.from_user.username)

    invite = await bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)
    await message.answer(
        f"✅ Оплата успешно получена!\n"
        f"Подписка активна до {new_expiry.strftime('%d.%m.%Y')}.\n\n"
        f"Вот ссылка на канал:\n{invite.invite_link}",
        reply_markup=main_menu
    )

    # логируем оплату
    with open("payments.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M}] {message.from_user.id} @{message.from_user.username} — оплата до {new_expiry}\n")

# ---------- Поддержка ----------
@dp.message_handler(state=SupportForm.waiting_for_message)
async def process_support_message(message: types.Message, state: FSMContext):
    try:
        await bot.send_message(
            SUPPORT_USER_ID,
            f"📩 Запрос от @{message.from_user.username or message.from_user.full_name} (ID {message.from_user.id}):\n\n{message.text}"
        )
        await message.answer("✅ Ваш запрос отправлен администратору.", reply_markup=main_menu)
    except exceptions.BotBlocked:
        await message.answer("⚠️ Не удалось отправить запрос администратору.")
    await state.finish()

# ---------- Планировщик подписок ----------
async def check_subscriptions():
    while True:
        for user_id, username, expiry_date, status in db.get_all_subscriptions():
            expiry = datetime.fromisoformat(expiry_date)
            days_left = (expiry - datetime.now()).days

            if days_left == 3:
                try:
                    await bot.send_message(user_id, "🔔 Ваша подписка заканчивается через 3 дня!")
                except exceptions.BotBlocked:
                    pass
            elif expiry < datetime.now() and status == "active":
                try:
                    await bot.send_message(user_id, "🚫 Подписка истекла. Для продления оплатите заново.")
                    await bot.ban_chat_member(CHANNEL_ID, user_id)
                    await bot.unban_chat_member(CHANNEL_ID, user_id)
                except Exception as e:
                    print(f"⚠️ Ошибка при удалении {user_id}: {e}")
                db.expire_user(user_id)
        await asyncio.sleep(3600)  # проверяем каждый час

# ---------- Старт ----------
async def on_startup(dp):
    asyncio.create_task(check_subscriptions())
    print("🌐 Планировщик подписок запущен.")

if __name__ == "__main__":
    print("🚀 Бот запущен и работает 24/7")
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)