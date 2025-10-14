import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import LabeledPrice, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor, exceptions
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from dotenv import load_dotenv

# Загружаем конфигурацию
load_dotenv()

# Validate required environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
SUPPORT_USER_ID = os.getenv("SUPPORT_USER_ID")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")
if not PROVIDER_TOKEN:
    raise ValueError("PROVIDER_TOKEN environment variable is required")
if not CHANNEL_ID:
    raise ValueError("CHANNEL_ID environment variable is required")
if not SUPPORT_USER_ID:
    raise ValueError("SUPPORT_USER_ID environment variable is required")

CHANNEL_ID = int(CHANNEL_ID)
SUPPORT_USER_ID = int(SUPPORT_USER_ID)
PRICE = int(os.getenv("PRICE", "30000"))  # цена в копейках

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ---------- Меню снизу (ReplyKeyboard) ----------
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(
    KeyboardButton("💳 Купить доступ"),
    KeyboardButton("ℹ️ О канале")
)
main_menu.add(KeyboardButton("📞 Поддержка"))

# ---------- FSM для поддержки ----------
class SupportForm(StatesGroup):
    waiting_for_message = State()

# ---------- Inline-кнопка оплаты ----------
buy_inline = InlineKeyboardMarkup()
buy_inline.add(InlineKeyboardButton("💳 Оплатить доступ", callback_data="buy"))

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    print("user_id:", message.from_user.id)
    await message.answer(f"Ваш Telegram ID: {message.from_user.id}")
    
# ---------- Показываем меню при любом сообщении ----------
@dp.message_handler()
async def any_message(message: types.Message):
    if message.text == "💳 Купить доступ":
        await message.answer(
            "💰 Подписка на канал: 300 ₽ / месяц\nНажми кнопку ниже, чтобы оплатить 👇",
            reply_markup=buy_inline
        )
    elif message.text == "ℹ️ О канале":
        await message.answer(
            "📘 Это закрытый канал с эксклюзивным контентом.\nПосле оплаты ты получишь мгновенный доступ.",
            reply_markup=main_menu
        )
    elif message.text == "📞 Поддержка":
        await message.answer(
            "📝 Опишите вашу проблему или вопрос. Я перешлю это моему администратору.",
            reply_markup=None  # скрываем меню, пока пользователь вводит текст
        )
        await SupportForm.waiting_for_message.set()
    else:
        # Меню всегда показывается
        await message.answer("Выберите действие из меню 👇", reply_markup=main_menu)

# ---------- Inline-кнопка оплаты ----------
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
    invite = await bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)
    await message.answer(
        "✅ Оплата успешно получена!\n\n"
        f"Вот твоя ссылка для входа в канал:\n{invite.invite_link}",
        reply_markup=main_menu
    )
    
        # ---------- Приём сообщений от пользователя для поддержки ----------
@dp.message_handler(state=SupportForm.waiting_for_message)
async def process_support_message(message: types.Message, state: FSMContext):
    try:
         print(f"Отправка админу: {SUPPORT_USER_ID}")
         print(f"Текст: {message.text}")
         await bot.send_message(
            SUPPORT_USER_ID,
            f"Новый запрос от @{message.from_user.username or message.from_user.full_name} (ID {message.from_user.id}):\n\n{message.text}"
        )
         await message.answer(
            "✅ Ваш запрос отправлен администратору, спасибо!",
            reply_markup=main_menu
        )
    except exceptions.BotBlocked:
        await message.answer(
            "⚠️ Не удалось отправить запрос администратору."
        )
    await state.finish()


async def on_startup(dp):
    from aiohttp import web
    
    async def handle(request):
        return web.Response(text="Bot is alive!")
    
    app = web.Application()
    app.router.add_get("/", handle)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8080)
    await site.start()
    print("🌐 Uptime server started on port 8080")

if __name__ == "__main__":
    print("🚀 Бот запущен и работает 24/7")
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)