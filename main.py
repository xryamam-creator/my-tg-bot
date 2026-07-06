import asyncio
import json
import os
import warnings
from datetime import datetime
from dotenv import load_dotenv

# ---------- ПОДАВЛЯЕМ ПРЕДУПРЕЖДЕНИЯ ----------
from telegram.warnings import PTBUserWarning
warnings.filterwarnings("ignore", category=PTBUserWarning)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

# ======================================================
# 1. КОНФИГУРАЦИЯ
# ======================================================

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан")

ADMIN_CHAT_ID = 1071217435           # Ваш Telegram ID
SERVER_IP = "193.39.168.179:30012"
DISCORD_LINK = "https://discord.gg/JWrnSCq9H"

# ---------- СПИСОК ЗАПРЕЩЁННЫХ СЛОВ ----------
BAD_WORDS = [
    "хуй", "пизда", "бля", "ебан", "залуп", "гандон", "мудила", "петух", "пидор",
    "лох", "шлюха", "курва", "сука", "ублюд", "сволочь", "тварь", "выродок",
    "fuck", "shit", "cunt", "dick", "asshole", "bastard", "whore", "slut", "bitch"
]

def contains_bad_word(text):
    if not text:
        return False
    text_lower = text.lower()
    for word in BAD_WORDS:
        if word in text_lower:
            return True
    return False

# ======================================================
# 2. РАБОТА С ФАЙЛАМИ (АВТОСОЗДАНИЕ)
# ======================================================

NEWS_FILE = "news.txt"
WHITELIST_FILE = "whitelist_requests.json"

def get_requests():
    """Возвращает список заявок, создаёт файл, если его нет."""
    if not os.path.exists(WHITELIST_FILE):
        with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        return []
    try:
        with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_requests(requests):
    with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
        json.dump(requests, f, ensure_ascii=False, indent=2)

def get_news():
    if os.path.exists(NEWS_FILE):
        with open(NEWS_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "Новостей пока нет."

def set_news(text):
    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        f.write(text)

def save_whitelist_request(user_id, username, name, reason, is_change=False):
    status = "change_request" if is_change else "pending"
    data = {
        "user_id": user_id,
        "username": username,
        "name": name,
        "reason": reason,
        "date": datetime.now().isoformat(),
        "status": status,
        "is_change": is_change
    }
    requests = get_requests()
    requests.append(data)
    save_requests(requests)
    print(f"✅ Заявка сохранена: {data}")
    return len(requests) - 1

def update_request_status(index, status, reject_reason=None):
    requests = get_requests()
    if 0 <= index < len(requests):
        requests[index]["status"] = status
        if reject_reason is not None:
            requests[index]["reject_reason"] = reject_reason
        save_requests(requests)
        return True
    return False

def update_user_name(user_id, new_name):
    requests = get_requests()
    for req in reversed(requests):
        if req["user_id"] == user_id and req["status"] == "approved":
            req["name"] = new_name
            save_requests(requests)
            return True
    return False

def get_last_user_request(user_id):
    requests = get_requests()
    user_requests = [r for r in requests if r["user_id"] == user_id]
    if not user_requests:
        return None
    user_requests.sort(key=lambda x: x["date"], reverse=True)
    return user_requests[0]

def has_pending_request(user_id):
    req = get_last_user_request(user_id)
    return req and req["status"] == "pending"

def is_user_approved(user_id):
    requests = get_requests()
    for req in reversed(requests):
        if req["user_id"] == user_id and req["status"] == "approved":
            return True
    return False

def get_user_current_name(user_id):
    requests = get_requests()
    for req in reversed(requests):
        if req["user_id"] == user_id and req["status"] == "approved":
            return req["name"]
    return None

# ======================================================
# 3. ОТПРАВКА УВЕДОМЛЕНИЙ АДМИНУ
# ======================================================

async def notify_admin_with_buttons(context: ContextTypes.DEFAULT_TYPE, user, name, reason, request_index, is_change=False):
    text = (
        f"📝 *{'Заявка на изменение ника' if is_change else 'Новая заявка в вайтлист'}!*\n"
        f"От: @{user.username or 'нет username'} (ID: `{user.id}`)\n"
        f"{'Новый' if is_change else 'Игровой'} ник: `{name}`\n"
        f"{'Причина изменения' if is_change else 'Причина'}: {reason}\n"
        f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{request_index}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{request_index}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ======================================================
# 4. ОБРАБОТКА РЕШЕНИЯ АДМИНА (ИСПРАВЛЕННАЯ)
# ======================================================

async def handle_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    action, index_str = data.split('_')
    index = int(index_str)

    requests = get_requests()
    if index >= len(requests):
        await query.message.reply_text("❌ Ошибка: заявка не найдена.")
        return

    request_data = requests[index]
    user_id = request_data["user_id"]
    name = request_data["name"]
    is_change = request_data.get("is_change", False)

    if request_data["status"] not in ["pending", "change_request"]:
        await query.message.reply_text("⚠️ Эта заявка уже была обработана.")
        # Убираем кнопки у исходного сообщения
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except:
            pass
        return

    if action == "approve":
        if is_change:
            if update_user_name(user_id, name):
                update_request_status(index, "approved")
                user_message = f"✅ Ваш ник в вайтлисте обновлён на `{name}`!"
            else:
                update_request_status(index, "approved")
                user_message = f"✅ Вы добавлены в вайтлист под ником `{name}`!"
        else:
            update_request_status(index, "approved")
            user_message = f"✅ *Поздравляем!* Вы добавлены в вайтлист под ником `{name}`.\nДобро пожаловать на сервер! 🎉"
        
        try:
            await context.bot.send_message(chat_id=user_id, text=user_message, parse_mode="Markdown")
            await query.message.reply_text(f"✅ Заявка одобрена. Пользователь уведомлён.")
        except Exception as e:
            await query.message.reply_text(f"✅ Заявка одобрена, но не удалось уведомить пользователя (ошибка: {e})")
        # Убираем кнопки
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except:
            pass

    elif action == "reject":
        # Сохраняем индекс и просим причину
        context.user_data['pending_reject_index'] = index
        await query.message.reply_text(
            "Введите причину отклонения для пользователя (или отправьте /cancel, чтобы отменить)."
        )
        # Убираем кнопки у исходного сообщения
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except:
            pass

# ======================================================
# 5. ОБРАБОТЧИК ПРИЧИНЫ ОТКЛОНЕНИЯ (ОТ АДМИНА)
# ======================================================

async def handle_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'pending_reject_index' not in context.user_data:
        return
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    index = context.user_data.pop('pending_reject_index')
    reason_text = update.message.text.strip()
    if not reason_text:
        await update.message.reply_text("❌ Причина не может быть пустой. Отправьте текст или /cancel.")
        context.user_data['pending_reject_index'] = index
        return

    # Обновляем заявку с причиной отклонения
    update_request_status(index, "rejected", reject_reason=reason_text)
    requests = get_requests()
    if index >= len(requests):
        await update.message.reply_text("❌ Заявка не найдена.")
        return
    request_data = requests[index]
    user_id = request_data["user_id"]

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ *Заявка отклонена.*\nПричина: {reason_text}",
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ Пользователь уведомлён об отказе с причиной: {reason_text}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Не удалось уведомить пользователя (он не начал диалог). Заявка отклонена с причиной: {reason_text}")

# ======================================================
# 6. КОМАНДЫ
# ======================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update.message)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update.message)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="✅ Тестовое сообщение от бота! Уведомления работают.")
        await update.message.reply_text("✅ Тестовое сообщение отправлено вам в личку.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}\n\nУбедитесь, что вы написали боту первым (/start).")

async def cancel_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    if 'pending_reject_index' in context.user_data:
        context.user_data.pop('pending_reject_index')
        await update.message.reply_text("❌ Отклонение отменено.")
    else:
        await update.message.reply_text("Нет активной операции отклонения.")

# ======================================================
# 7. ПОКАЗ МЕНЮ И ОБРАБОТЧИК КНОПОК
# ======================================================

async def show_main_menu(target, user=None):
    keyboard = [
        [InlineKeyboardButton("📢 Новости", callback_data="news")],
        [InlineKeyboardButton("🎫 Создать тикет", callback_data="ticket")],
        [InlineKeyboardButton("📝 Заявка в вайтлист", callback_data="whitelist")],
        [InlineKeyboardButton("🌐 IP сервера", callback_data="ip")],
        [InlineKeyboardButton("🔗 Ссылка на Discord", url=DISCORD_LINK)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🏠 *Главное меню*\n\nВыберите нужный раздел:"
    if hasattr(target, 'edit_message_text'):
        await target.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await target.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "news":
        news_text = get_news()
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_text(
            f"📰 *Новости:*\n\n{news_text}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif data == "ip":
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_text(
            f"🌐 *IP сервера:*\n`{SERVER_IP}`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif data == "ticket":
        user = query.from_user
        text = (
            f"🎫 *Новый тикет!*\n"
            f"От: {user.mention_html()} (@{user.username or 'нет username'})\n"
            f"ID: `{user.id}`\n"
            f"Создан: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode="Markdown")
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_text(
            "✅ *Тикет создан!*\n\nАдминистратор уведомлён.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif data == "back_to_menu":
        await show_main_menu(query)
    elif data == "cancel_whitelist":
        await show_main_menu(query)

# ======================================================
# 8. ВХОДНАЯ ТОЧКА ДЛЯ ЗАЯВКИ (С ПРОВЕРКОЙ)
# ======================================================

async def whitelist_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_id = user.id

    last_req = get_last_user_request(user_id)
    if last_req and last_req["status"] == "pending":
        await query.edit_message_text(
            "⏳ *У вас уже есть заявка на рассмотрении!*\nПожалуйста, дождитесь ответа администратора.",
            parse_mode="Markdown"
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    if is_user_approved(user_id):
        current_name = get_user_current_name(user_id)
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_whitelist")]]
        await query.edit_message_text(
            f"✏️ *Вы уже в вайтлисте* (текущий ник: `{current_name}`).\n"
            "Если хотите изменить ник, введите **новый никнейм** (или нажмите Отмена):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["is_change"] = True
        return NAME
    else:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_whitelist")]]
        await query.edit_message_text(
            "📝 *Заявка в вайтлист*\n\nВведите ваш игровой никнейм (или нажмите Отмена):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["is_change"] = False
        return NAME

# ======================================================
# 9. ДИАЛОГ ЗАЯВКИ (С ФИЛЬТРОМ ОСКОРБЛЕНИЙ)
# ======================================================

async def whitelist_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("❌ Никнейм не может быть пустым. Попробуйте снова:")
        return NAME
    if contains_bad_word(name):
        await update.message.reply_text(
            "🚫 *Обнаружены недопустимые слова в никнейме!*\n"
            "Пожалуйста, используйте корректный никнейм без оскорблений.",
            parse_mode="Markdown"
        )
        return NAME
    context.user_data["whitelist_name"] = name
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_whitelist")]]
    if context.user_data.get("is_change", False):
        await update.message.reply_text(
            "Напишите **причину изменения ника** (или нажмите Отмена):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            "Напишите причину (или нажмите Отмена):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    return REASON

async def whitelist_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    if not reason:
        await update.message.reply_text("❌ Причина не может быть пустой. Попробуйте снова:")
        return REASON
    if contains_bad_word(reason):
        await update.message.reply_text(
            "🚫 *Обнаружены недопустимые слова в причине!*\n"
            "Пожалуйста, переформулируйте причину без оскорблений.",
            parse_mode="Markdown"
        )
        return REASON

    name = context.user_data["whitelist_name"]
    user = update.effective_user
    is_change = context.user_data.get("is_change", False)

    request_index = save_whitelist_request(user.id, user.username or "без username", name, reason, is_change)
    await notify_admin_with_buttons(context, user, name, reason, request_index, is_change)

    if is_change:
        await update.message.reply_text("✅ Ваша заявка на изменение ника отправлена на рассмотрение!")
    else:
        await update.message.reply_text("✅ Ваша заявка отправлена на рассмотрение! Администратор скоро ответит.")

    await show_main_menu(update.message)
    return ConversationHandler.END

async def whitelist_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.")
    await show_main_menu(update.message)
    return ConversationHandler.END

# ======================================================
# 10. КОМАНДЫ ДЛЯ АДМИНА (ПРОСМОТР ЗАЯВОК, ОБНОВЛЕНИЕ НОВОСТЕЙ)
# ======================================================

async def view_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    requests = get_requests()
    if not requests:
        await update.message.reply_text("📭 Заявок нет.")
        return
    text = "📋 *Все заявки:*\n\n"
    for i, req in enumerate(requests, 1):
        status_emoji = {
            "pending": "🟡",
            "approved": "✅",
            "rejected": "❌",
            "change_request": "🔄"
        }.get(req.get("status"), "⚪")
        text += f"{i}. {status_emoji} @{req.get('username', '')} — `{req.get('name', '')}`\n"
        text += f"   {req.get('reason', '')}\n"
        if req.get("reject_reason"):
            text += f"   ❗ Причина отказа: {req['reject_reason']}\n"
        text += f"   {req.get('date', '')}\n\n"
    
    if len(text) > 4000:
        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
            await update.message.reply_text(chunk, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

async def update_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    if not context.args:
        await update.message.reply_text("❌ Укажите текст. Пример: /update_news Текст")
        return
    new_text = " ".join(context.args)
    set_news(new_text)
    await update.message.reply_text(f"✅ Новости обновлены!")

# ======================================================
# 11. ЗАПУСК
# ======================================================

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("test", test))
    application.add_handler(CommandHandler("update_news", update_news))
    application.add_handler(CommandHandler("view_requests", view_requests))
    application.add_handler(CommandHandler("cancel", cancel_reject))

    # ConversationHandler для заявки
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(whitelist_entry, pattern="^whitelist$")],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, whitelist_name)],
            REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, whitelist_reason)],
        },
        fallbacks=[
            CommandHandler("cancel", whitelist_cancel),
            CallbackQueryHandler(button_handler, pattern="^cancel_whitelist$")
        ],
    )
    application.add_handler(conv_handler)

    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(news|ticket|ip|back_to_menu|cancel_whitelist)$"))
    application.add_handler(CallbackQueryHandler(handle_decision, pattern="^(approve|reject)_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reject_reason))

    print("🚀 Бот запущен и готов к работе!")
    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
