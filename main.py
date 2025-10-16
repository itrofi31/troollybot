import os
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import LabeledPrice, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor, exceptions
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from dotenv import load_dotenv

from database import Database  # Работа с БД вынесена в отдельный файл database.py

# ---------- Настройки ----------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
SUPPORT_USER_ID = int(os.getenv("SUPPORT_USER_ID"))
PRICE = int(os.getenv("PRICE", "30000"))      # Месячный доступ
FULL_PRICE = int(os.getenv("FULL_PRICE", "50000"))  # Полный доступ

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ---------- Инициализация БД ----------
db = Database()

# ---------- Меню ----------
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(
    KeyboardButton("💳 Купить доступ на месяц"),
    KeyboardButton("📚 Купить полный доступ"),
    KeyboardButton("ℹ️ О клубе")
)
main_menu.add(KeyboardButton("📞 Поддержка"))

buy_month_inline = InlineKeyboardMarkup().add(
    InlineKeyboardButton("💳 Оплатить месяц", callback_data="buy_month")
)
buy_full_inline = InlineKeyboardMarkup().add(
    InlineKeyboardButton("💳 Оплатить полный доступ", callback_data="buy_full")
)

# ---------- FSM поддержки ----------
class SupportForm(StatesGroup):
    waiting_for_message = State()

# ---------- Обработка сообщений ----------
@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    await message.answer("👋 Привет! Выберите действие из меню 👇", reply_markup=main_menu)

@dp.message_handler()
async def any_message(message: types.Message):
    if message.text.startswith("/"):
        return

    if message.text == "💳 Купить доступ на месяц":
        await message.answer(
            f"💰 Месячный доступ: {PRICE/100:.2f} ₽\nНажми кнопку ниже, чтобы оплатить 👇",
            reply_markup=buy_month_inline
        )
    elif message.text == "📚 Купить полный доступ":
        await message.answer(
            f"💰 Полный доступ: {FULL_PRICE/100:.2f} ₽\nНажми кнопку ниже, чтобы оплатить 👇",
            reply_markup=buy_full_inline
        )
    elif message.text == "ℹ️ О клубе":
        info = "📘 Добро пожаловать в книжный клуб! После оплаты вы получите доступ к эксклюзивному контенту."
        expiry = db.get_expiry(message.from_user.id)
        full = db.has_full_access(message.from_user.id)
        if full:
            info += "\n✅ У вас полный доступ."
        elif expiry and expiry > datetime.now():
            days_left = (expiry - datetime.now()).days
            info += f"\n✅ Ваша подписка активна ещё {days_left} дней."
        await message.answer(info, reply_markup=main_menu)
    elif message.text == "📞 Поддержка":
        await message.answer("📝 Опишите вашу проблему. Я передам её администратору.")
        await SupportForm.waiting_for_message.set()
    else:
        await message.answer("Выберите действие из меню 👇", reply_markup=main_menu)

# ---------- Callback оплаты ----------
@dp.callback_query_handler(lambda c: c.data in ["buy_month", "buy_full"])
async def process_buy_callback(callback_query: types.CallbackQuery):
    if callback_query.data == "buy_month":
        label = "Доступ на 1 месяц"
        amount = PRICE
        payload = "subscription_1m"
    else:
        label = "Полный доступ"
        amount = FULL_PRICE
        payload = "subscription_full"

    prices = [LabeledPrice(label=label, amount=amount)]
    await bot.send_invoice(
        callback_query.from_user.id,
        title=label,
        description=f"{label} в книжный клуб",
        payload=payload,
        provider_token=PROVIDER_TOKEN,
        currency="RUB",
        prices=prices,
        start_parameter=payload
    )

@dp.pre_checkout_query_handler(lambda q: True)
async def pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message_handler(content_types=types.ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload

    if payload == "subscription_1m":
        new_expiry = db.add_or_update_subscription(message.from_user.id, message.from_user.username, months=1)
    elif payload == "subscription_full":
        new_expiry = db.add_or_update_subscription(message.from_user.id, message.from_user.username, full_access=True)

    invite = await bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)
    expiry = {new_expiry.strftime('%d.%m.%Y')}
    await message.answer(
        f"✅ Оплата успешно получена!\n"
        f"{'Полный доступ' if payload == 'subscription_full' else f'Подписка до {expiry}'}\n\n"
        f"Ссылка на канал:\n{invite.invite_link}",
        reply_markup=main_menu
    )

    # Логирование
    with open("payments.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M}] {message.from_user.id} @{message.from_user.username} — {payload}\n")

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
        for user_id, username, expiry_date, full_access, status in db.get_all_subscriptions():
            if full_access:
                continue  # Полный доступ не истекает
            expiry = datetime.fromisoformat(expiry_date)
            days_left = (expiry - datetime.now()).days
            if days_left == 3:
                try:
                    await bot.send_message(user_id, "🔔 Ваша подписка заканчивается через 3 дня! Чтобы не потерять доступ в клуб, оплатите ещё один месяц, или нажмите кнопку 📞 Поддержка, и мы с вами свяжемся!")
                except exceptions.BotBlocked:
                    pass
            elif expiry < datetime.now() and status == "active":
                try:
                    await bot.send_message(user_id, "🚫 Ваш доступ в книжный клуб к сожалению истек.  Вы сможете вернуться, оплатив по кнопке ниже👇.")
                    await bot.ban_chat_member(CHANNEL_ID, user_id)
                    await bot.unban_chat_member(CHANNEL_ID, user_id)
                except Exception as e:
                    print(f"⚠️ Ошибка при удалении {user_id}: {e}")
                db.expire_user(user_id)
        await asyncio.sleep(3600)  # Проверяем каждый час

# ---------- Старт ----------
async def on_startup(dp):
    asyncio.create_task(check_subscriptions())
    print("🌐 Планировщик подписок запущен.")

if __name__ == "__main__":
    print("🚀 Бот запущен и работает 24/7")
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)