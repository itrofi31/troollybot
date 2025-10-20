# admin.py
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

PAGE_SIZE = 20

def register_admin_handlers(dp, db, support_user_id, dev_user_id, bot):
    """Регистрация всех админ-хэндлеров"""

    def is_admin(user_id):
        return str(user_id) in [str(support_user_id), str(dev_user_id)]

    # -------------------- Пользователи --------------------
    async def send_users_page(chat_id, page, users, title="Пользователи"):
        total = len(users)
        pages = (total - 1) // PAGE_SIZE + 1
        offset = page * PAGE_SIZE
        slice_users = users[offset:offset+PAGE_SIZE]

        if not slice_users:
            await bot.send_message(chat_id, "Нет пользователей.")
            return

        text = f"📊 {title} (страница {page+1}/{pages})\n\n"
        for u in slice_users:
            uid, username, expiry, full_access = u
            access = "бессрочно (полный)" if full_access else (expiry if expiry else "нет подписки")
            text += f"👤 ID: {uid}\n   @{username}\n   ✅ {access}\n\n"

        kb = InlineKeyboardMarkup()
        if page > 0:
            kb.add(InlineKeyboardButton("⬅ Назад", callback_data=f"{title}_page_{page-1}"))
        if page < pages - 1:
            kb.add(InlineKeyboardButton("Вперёд ➡", callback_data=f"{title}_page_{page+1}"))

        await bot.send_message(chat_id, text, reply_markup=kb)

    # -------------------- Все пользователи --------------------
    @dp.message_handler(commands=['admin_users'])
    async def admin_users(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        users = db.get_all_users()
        await send_users_page(message.chat.id, 0, users, title="all_users")

    # -------------------- Активные --------------------
    @dp.message_handler(commands=['admin_active'])
    async def admin_active(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        users = db.get_active_users()
        await send_users_page(message.chat.id, 0, users, title="active_users")

    # -------------------- Полные --------------------
    @dp.message_handler(commands=['admin_full'])
    async def admin_full(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        users = db.get_full_access_users()
        await send_users_page(message.chat.id, 0, users, title="full_users")

    # -------------------- Истёкшие --------------------
    @dp.message_handler(commands=['admin_expired'])
    async def admin_expired(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        users = db.get_expired_users()
        await send_users_page(message.chat.id, 0, users, title="expired_users")

    # -------------------- Детальный просмотр --------------------
    @dp.message_handler(commands=['user'])
    async def admin_user(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("Укажи ID пользователя: /user <id>")
            return
        uid = parts[1]
        user = db.get_user(uid)
        if not user:
            await message.answer("Пользователь не найден.")
            return
        uid, username, expiry, full_access = user
        access = "бессрочно (полный)" if full_access else (expiry if expiry else "нет подписки")
        await message.answer(
            f"👤 ID: {uid}\n"
            f"@{username}\n"
            f"✅ Статус: {access}"
        )

    # -------------------- История оплат --------------------
    async def send_payments_page(chat_id, page, payments):
        total = len(payments)
        pages = (total - 1) // PAGE_SIZE + 1
        offset = page * PAGE_SIZE
        slice_payments = payments[offset:offset+PAGE_SIZE]

        if not slice_payments:
            await bot.send_message(chat_id, "Нет оплат.")
            return

        text = f"📊 История оплат (страница {page+1}/{pages})\n\n"
        for p in slice_payments:
            uid, username, amount, currency, date, expiry, full = p
            access = "бессрочно (полный)" if full else f"до {expiry}"
            text += (f"👤 ID: {uid}\n"
                     f"   @{username}\n"
                     f"   💳 {amount/100:.2f} {currency}\n"
                     f"   ⏰ {date}\n"
                     f"   ✅ {access}\n\n")

        kb = InlineKeyboardMarkup()
        if page > 0:
            kb.add(InlineKeyboardButton("⬅ Назад", callback_data=f"payments_page_{page-1}"))
        if page < pages - 1:
            kb.add(InlineKeyboardButton("Вперёд ➡", callback_data=f"payments_page_{page+1}"))

        await bot.send_message(chat_id, text, reply_markup=kb)

    @dp.message_handler(commands=['admin_payments'])
    async def admin_payments(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        payments = db.get_payments()
        await send_payments_page(message.chat.id, 0, payments)

    # -------------------- Callback постранично --------------------
    @dp.callback_query_handler(lambda c: c.data.endswith("_page_0") or "_page_" in c.data)
    async def page_callback(call: types.CallbackQuery):
        if not is_admin(call.from_user.id):
            return
        data = call.data
        if data.startswith("all_users") or data.startswith("active_users") or data.startswith("full_users") or data.startswith("expired_users"):
            title, _, page = data.rpartition("_page_")
            page = int(page)
            if title == "all_users":
                users = db.get_all_users()
            elif title == "active_users":
                users = db.get_active_users()
            elif title == "full_users":
                users = db.get_full_access_users()
            else:
                users = db.get_expired_users()
            await call.message.delete()
            await send_users_page(call.message.chat.id, page, users, title=title)
        elif data.startswith("payments_page_"):
            page = int(data.split("_")[-1])
            payments = db.get_payments()
            await call.message.delete()
            await send_payments_page(call.message.chat.id, page, payments)