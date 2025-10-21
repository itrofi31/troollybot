from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import logging

PAGE_SIZE = 20


def register_admin_handlers(dp, db, support_user_id, dev_user_id, bot):
    """Регистрация всех админ-хэндлеров"""

    # Правильная проверка админа
    admin_ids = {support_user_id, dev_user_id}

    def is_admin(user_id):
        return user_id in admin_ids

    # -------------------- Пользователи --------------------
    async def send_users_page(chat_id, page, users, title="Пользователи"):
        try:
            total = len(users)

            if total == 0:
                await bot.send_message(chat_id, "Нет пользователей.")
                return

            pages = (total - 1) // PAGE_SIZE + 1
            offset = page * PAGE_SIZE
            slice_users = users[offset : offset + PAGE_SIZE]

            if not slice_users:
                await bot.send_message(chat_id, "Нет пользователей на этой странице.")
                return

            text = f"📊 {title} (страница {page+1}/{pages})\n\n"

            for u in slice_users:
                uid, username, expiry, full_access = u

                if full_access:
                    access = "бессрочно (полный)"
                elif expiry:
                    try:
                        exp_date = datetime.fromisoformat(expiry).strftime("%d.%m.%Y")
                        access = f"до {exp_date}"
                    except (ValueError, TypeError):
                        access = "ошибка даты"
                else:
                    access = "нет подписки"

                text += f"👤 ID: {uid}\n @{username}\n ✅ {access}\n\n"

            kb = InlineKeyboardMarkup()

            if page > 0:
                kb.add(
                    InlineKeyboardButton(
                        "⬅ Назад", callback_data=f"{title}_page_{page-1}"
                    )
                )

            if page < pages - 1:
                kb.add(
                    InlineKeyboardButton(
                        "Вперёд ➡", callback_data=f"{title}_page_{page+1}"
                    )
                )

            await bot.send_message(chat_id, text, reply_markup=kb)

        except Exception as e:
            logging.error(
                f"❌ Ошибка отправки страницы пользователей: {e}", exc_info=True
            )
            await bot.send_message(chat_id, "⚠️ Ошибка загрузки данных.")

    # -------------------- Пользователи по категориям --------------------
    @dp.message_handler(commands=["admin_users"])
    async def admin_users(message: types.Message):
        try:
            if not is_admin(message.from_user.id):
                return

            users = db.get_all_users()
            await send_users_page(message.chat.id, 0, users, title="all_users")
        except Exception as e:
            logging.error(f"❌ Ошибка в admin_users: {e}", exc_info=True)
            await message.answer("⚠️ Ошибка получения списка пользователей.")

    @dp.message_handler(commands=["admin_active"])
    async def admin_active(message: types.Message):
        try:
            if not is_admin(message.from_user.id):
                return

            users = db.get_active_users()
            await send_users_page(message.chat.id, 0, users, title="active_users")
        except Exception as e:
            logging.error(f"❌ Ошибка в admin_active: {e}", exc_info=True)
            await message.answer("⚠️ Ошибка получения списка активных пользователей.")

    @dp.message_handler(commands=["admin_full"])
    async def admin_full(message: types.Message):
        try:
            if not is_admin(message.from_user.id):
                return

            users = db.get_full_access_users()
            await send_users_page(message.chat.id, 0, users, title="full_users")
        except Exception as e:
            logging.error(f"❌ Ошибка в admin_full: {e}", exc_info=True)
            await message.answer(
                "⚠️ Ошибка получения списка пользователей с полным доступом."
            )

    @dp.message_handler(commands=["admin_expired"])
    async def admin_expired(message: types.Message):
        try:
            if not is_admin(message.from_user.id):
                return

            users = db.get_expired_users()
            await send_users_page(message.chat.id, 0, users, title="expired_users")
        except Exception as e:
            logging.error(f"❌ Ошибка в admin_expired: {e}", exc_info=True)
            await message.answer("⚠️ Ошибка получения списка истёкших пользователей.")

    # -------------------- Детальный просмотр пользователя --------------------
    @dp.message_handler(commands=["user"])
    async def admin_user(message: types.Message):
        try:
            if not is_admin(message.from_user.id):
                return

            parts = message.text.split()

            if len(parts) < 2:
                await message.answer("Укажи ID пользователя: /user <user_id>")
                return

            try:
                uid = int(parts[1])
            except ValueError:
                await message.answer("⚠️ ID должен быть числом.")
                return

            user = db.get_user(uid)

            if not user:
                await message.answer("Пользователь не найден.")
                return

            uid, username, expiry, full_access = user

            if full_access:
                access = "бессрочно (полный)"
            elif expiry:
                try:
                    exp_date = datetime.fromisoformat(expiry).strftime("%d.%m.%Y")
                    access = f"до {exp_date}"
                except (ValueError, TypeError):
                    access = "ошибка даты"
            else:
                access = "нет подписки"

            await message.answer(
                f"👤 ID: {uid}\n" f"@{username}\n" f"✅ Статус: {access}"
            )

        except Exception as e:
            logging.error(f"❌ Ошибка в admin_user: {e}", exc_info=True)
            await message.answer("⚠️ Ошибка получения информации о пользователе.")

    # -------------------- История оплат --------------------
    async def send_payments_page(chat_id, page, payments):
        try:
            total = len(payments)

            if total == 0:
                await bot.send_message(chat_id, "Нет оплат.")
                return

            pages = (total - 1) // PAGE_SIZE + 1
            offset = page * PAGE_SIZE
            slice_payments = payments[offset : offset + PAGE_SIZE]

            if not slice_payments:
                await bot.send_message(chat_id, "Нет оплат на этой странице.")
                return

            text = f"📊 История оплат (страница {page+1}/{pages})\n\n"

            for p in slice_payments:
                uid, username, amount, currency, date_str, expiry, full = p

                try:
                    date = datetime.fromisoformat(date_str).strftime("%d.%m.%Y %H:%M")
                except (ValueError, TypeError):
                    date = "ошибка даты"

                if full:
                    access = "бессрочно (полный)"
                elif expiry:
                    try:
                        exp_date = datetime.fromisoformat(expiry).strftime("%d.%m.%Y")
                        access = f"до {exp_date}"
                    except (ValueError, TypeError):
                        access = "ошибка даты"
                else:
                    access = "нет подписки"

                text += (
                    f"👤 ID: {uid}\n"
                    f"  @{username}\n"
                    f"  💳 {amount/100:.2f} {currency}\n"
                    f"  ⏰ {date}\n"
                    f"  ✅ {access}\n\n"
                )

            kb = InlineKeyboardMarkup()

            if page > 0:
                kb.add(
                    InlineKeyboardButton(
                        "⬅ Назад", callback_data=f"payments_page_{page-1}"
                    )
                )

            if page < pages - 1:
                kb.add(
                    InlineKeyboardButton(
                        "Вперёд ➡", callback_data=f"payments_page_{page+1}"
                    )
                )

            await bot.send_message(chat_id, text, reply_markup=kb)

        except Exception as e:
            logging.error(f"❌ Ошибка отправки страницы платежей: {e}", exc_info=True)
            await bot.send_message(chat_id, "⚠️ Ошибка загрузки данных.")

    @dp.message_handler(commands=["admin_payments"])
    async def admin_payments(message: types.Message):
        try:
            if not is_admin(message.from_user.id):
                return

            payments = db.get_payments(offset=0, limit=1000)
            await send_payments_page(message.chat.id, 0, payments)
        except Exception as e:
            logging.error(f"❌ Ошибка в admin_payments: {e}", exc_info=True)
            await message.answer("⚠️ Ошибка получения истории оплат.")

    # -------------------- Callback постранично --------------------
    @dp.callback_query_handler(lambda c: "_page_" in c.data)
    async def page_callback(call: types.CallbackQuery):
        try:
            if not is_admin(call.from_user.id):
                return

            data = call.data

            # Пользователи
            if any(
                data.startswith(prefix)
                for prefix in [
                    "all_users",
                    "active_users",
                    "full_users",
                    "expired_users",
                ]
            ):
                title, _, page_str = data.rpartition("_page_")

                try:
                    page = int(page_str)
                except ValueError:
                    await call.answer("⚠️ Ошибка: неверный номер страницы")
                    return

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

            # Платежи
            elif data.startswith("payments_page_"):
                parts = data.split("_")

                if len(parts) < 3:
                    await call.answer("⚠️ Ошибка: неверный формат")
                    return

                try:
                    page = int(parts[-1])
                except ValueError:
                    await call.answer("⚠️ Ошибка: неверный номер страницы")
                    return

                payments = db.get_payments(offset=0, limit=1000)
                await call.message.delete()
                await send_payments_page(call.message.chat.id, page, payments)

        except Exception as e:
            logging.error(f"❌ Ошибка в page_callback: {e}", exc_info=True)
            await call.answer("⚠️ Произошла ошибка", show_alert=True)
