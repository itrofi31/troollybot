# admin.py
from aiogram import types

def register_admin_handlers(dp, db, support_id, dev_id):
    @dp.message_handler(commands=["admin_payments"])
    async def admin_payments(message: types.Message):
        if message.from_user.id not in [support_id, dev_id]:
            return await message.answer("⛔ У вас нет прав на эту команду.")

        payments = db.get_all_payments_with_users()
        if not payments:
            return await message.answer("📂 Платежей пока нет.")

        chunk = []
        for i, p in enumerate(payments, start=1):
            chunk.append(
                f"👤 ID: `{p[0]}` | @{p[1] or '—'}\n"
                f"💵 {p[3] / 100:.2f} {p[4]}\n"
                f"📅 Оплата: {p[2][:16]}\n"
                f"📆 До: {p[5] or 'бессрочно'}\n"
                f"🔓 {'Полный доступ' if p[6] else '1 месяц'}\n"
                f"— — — — —\n"
            )
            if i % 20 == 0 or i == len(payments):
                await message.answer("".join(chunk), parse_mode="Markdown")
                chunk = []

    @dp.message_handler(commands=["admin_users"])
    async def admin_users(message: types.Message):
        if message.from_user.id not in [support_id, dev_id]:
            return await message.answer("⛔ У вас нет прав на эту команду.")

        users = db.get_all_subscriptions()
        if not users:
            return await message.answer("📂 Нет ни одной подписки.")

        text = "👥 *Все подписчики:*\n\n"
        for u in users:
            user_id, username, expiry, full, status = u
            if full:
                status_text = "🔓 Полный доступ"
                expiry_text = "бессрочно"
            else:
                status_text = "📅 Месяц"
                expiry_text = expiry if expiry else "не указано"

            text += (
                f"• ID `{user_id}` | @{username or '—'}\n"
                f"  {status_text}, до: {expiry_text}\n"
            )

        await message.answer(text, parse_mode="Markdown")