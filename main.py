import asyncio
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# ----- БЛОК ДЛЯ ПОДАВЛЕНИЯ ПРЕДУПРЕЖДЕНИЙ -----
import warnings
from telegram.warnings import PTBUserWarning
warnings.filterwarnings("ignore", message="If 'per_message=False'", category=PTBUserWarning)
# -----------------------------------------------

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

# ---------- ЗАГРУЖАЕМ ТОКЕН ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ----------
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
# ... остальной код
import asyncio
import json
import os
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

# ---------- ЗАГРУЖАЕМ ТОКЕН ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ----------
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан")

# ---------- ВАШ ТЕЛЕГРАМ ID (узнайте через @userinfobot) ----------
ADMIN_CHAT_ID = 1071217435  # Ваш ID

# ---------- СОСТОЯНИЯ ДЛЯ ДИАЛОГА ЗАЯВКИ ----------
NAME, REASON = range(2)

# ---------- ПУТИ К ФАЙЛАМ ----------
NEWS_FILE = "news.txt"
WHITELIST_FILE = "whitelist_requests.json"

# ---------- ФУНКЦИИ ДЛЯ РАБОТЫ С НОВОСТЯМИ ----------
def get_news():
    if os.path.exists(NEWS_FILE):
        with open(NEWS_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "Новостей пока нет."

def set_news(text):
    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        f.write(text)

# ---------- ФУНКЦИЯ ДЛЯ СОХРАНЕНИЯ ЗАЯВКИ ----------
def save_whitelist_request(user_id, username, name, reason):
    data = {
        "user_id": user_id,
        "username": username,
        "name": name,
        "reason": reason,
        "date": datetime.now().isoformat()
    }
    try:
        with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
            requests = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        requests = []
    requests.append(data)
    with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
        json.dump(requests, f, ensure_ascii=False, indent=2)
    print(f"✅ Заявка сохранена: {data}")

# ---------- УВЕДОМЛЕНИЕ АДМИНИСТРАТОРУ ----------
async def notify_admin(context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode="Markdown")
        print("✅ Уведомление отправлено админу")
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления: {e}")

# ---------- КОМАНДА /START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📢 Новости", callback_data="news")],
        [InlineKeyboardButton("🎫 Создать тикет", callback_data="ticket")],
        [InlineKeyboardButton("📝 Заявка в вайтлист", callback_data="whitelist")],
        [InlineKeyboardButton("🌐 IP сервера", callback_data="ip")],
        [InlineKeyboardButton("🔗 Ссылка на Discord", url="https://discord.gg/JWrnSCq9H")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🏠 *Главное меню*\n\nВыберите нужный раздел:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ---------- ОБРАБОТЧИК КНОПОК ----------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "news":
        news_text = get_news()
        await query.edit_message_text(
            f"📰 *Новости:*\n\n{news_text}",
            parse_mode="Markdown"
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "ip":
        await query.edit_message_text(
            "🌐 *IP сервера:*\n`193.39.168.179:30012`",
            parse_mode="Markdown"
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "ticket":
        user = query.from_user
        text = (
            f"🎫 *Новый тикет!*\n"
            f"От: {user.mention_html()} (@{user.username or 'нет username'})\n"
            f"ID: `{user.id}`\n"
            f"Создан: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await notify_admin(context, text)
        await query.edit_message_text(
            "✅ *Тикет создан!*\n\nАдминистратор уведомлён.",
            parse_mode="Markdown"
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "whitelist":
        await query.edit_message_text(
            "📝 *Заявка в вайтлист*\n\nВведите ваш игровой никнейм:",
            parse_mode="Markdown"
        )

    elif data == "back_to_menu":
        await show_menu(query)

async def show_menu(query):
    keyboard = [
        [InlineKeyboardButton("📢 Новости", callback_data="news")],
        [InlineKeyboardButton("🎫 Создать тикет", callback_data="ticket")],
        [InlineKeyboardButton("📝 Заявка в вайтлист", callback_data="whitelist")],
        [InlineKeyboardButton("🌐 IP сервера", callback_data="ip")],
        [InlineKeyboardButton("🔗 Ссылка на Discord", url="https://discord.gg/JWrnSCq9H")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "🏠 *Главное меню*\n\nВыберите нужный раздел:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ---------- ДИАЛОГ ЗАЯВКИ В ВАЙТЛИСТ ----------
async def whitelist_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите ваш игровой никнейм:")
    return NAME

async def whitelist_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["whitelist_name"] = update.message.text
    await update.message.reply_text("Напишите причину:")
    return REASON

async def whitelist_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data["whitelist_name"]
    reason = update.message.text
    user = update.effective_user

    save_whitelist_request(user.id, user.username or "без username", name, reason)

    text = (
        f"📝 *Новая заявка в вайтлист!*\n"
        f"От: @{user.username or 'нет username'}\n"
        f"Игровой ник: `{name}`\n"
        f"Причина: {reason}\n"
        f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    await notify_admin(context, text)

    await update.message.reply_text("✅ Заявка отправлена!")

    keyboard = [
        [InlineKeyboardButton("📢 Новости", callback_data="news")],
        [InlineKeyboardButton("🎫 Создать тикет", callback_data="ticket")],
        [InlineKeyboardButton("📝 Заявка в вайтлист", callback_data="whitelist")],
        [InlineKeyboardButton("🌐 IP сервера", callback_data="ip")],
        [InlineKeyboardButton("🔗 Ссылка на Discord", url="https://discord.gg/JWrnSCq9H")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🏠 *Главное меню*\n\nВыберите нужный раздел:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def whitelist_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END

# ---------- КОМАНДА ОБНОВЛЕНИЯ НОВОСТЕЙ ----------
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

# ---------- КОМАНДА ПРОСМОТРА ЗАЯВОК ----------
async def view_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    try:
        with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
            requests = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        requests = []
    if not requests:
        await update.message.reply_text("📭 Заявок нет.")
        return
    text = "📋 *Заявки:*\n\n"
    for i, req in enumerate(requests, 1):
        text += f"{i}. @{req.get('username', '')} — `{req.get('name', '')}`\n"
        text += f"   {req.get('reason', '')}\n"
        text += f"   {req.get('date', '')}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# ---------- ЗАПУСК ----------
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("update_news", update_news))
    application.add_handler(CommandHandler("view_requests", view_requests))

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^whitelist$")],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, whitelist_name)],
            REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, whitelist_reason)],
        },
        fallbacks=[CommandHandler("cancel", whitelist_cancel)],
        per_message=True,   # добавлено, чтобы убрать предупреждение
    )
    application.add_handler(conv_handler)

    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(news|ticket|ip|back_to_menu)$"))

    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
