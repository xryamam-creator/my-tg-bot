import asyncio
import json
import os
import warnings
from datetime import datetime
from dotenv import load_dotenv

# ---------- ПОДАВЛЯЕМ ПРЕДУПРЕЖДЕНИЯ PTB ----------
from telegram.warnings import PTBUserWarning
warnings.filterwarnings("ignore", category=PTBUserWarning)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

# ---------- ЗАГРУЖАЕМ ТОКЕН ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ----------
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения")

# ---------- ВАШИ ДАННЫЕ ----------
ADMIN_CHAT_ID = 1071217435           # Ваш Telegram ID
SERVER_IP = "193.39.168.179:30012"   # IP сервера
DISCORD_LINK = "https://discord.gg/JWrnSCq9H"  # Ссылка на Discord

# ---------- СОСТОЯНИЯ ДЛЯ ДИАЛОГА ----------
NAME, REASON = range(2)

# ---------- ПУТИ К ФАЙЛАМ ----------
NEWS_FILE = "news.txt"
WHITELIST_FILE = "whitelist_requests.json"

# ======================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ФАЙЛАМИ
# ======================================================

def get_news():
    if os.path.exists(NEWS_FILE):
        with open(NEWS_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "Новостей пока нет."

def set_news(text):
    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        f.write(text)

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

# ======================================================
# УВЕДОМЛЕНИЕ АДМИНИСТРАТОРУ
# ======================================================

async def notify_admin(context: ContextTypes.DEFAULT_TYPE, text: str, reply_to_message=None):
    try:
        if reply_to_message:
            # Пересылаем сообщение пользователя админу (чтобы видеть, что он написал)
            await context.bot.forward_message(
                chat_id=ADMIN_CHAT_ID,
                from_chat_id=reply_to_message.chat.id,
                message_id=reply_to_message.message_id
            )
            # Затем отправляем текстовое уведомление
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode="Markdown")
        print("✅ Уведомление отправлено админу")
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления: {e}")

# ======================================================
# КОМАНДА /start и /menu (показывают главное меню)
# ======================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update.message, update.effective_user)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update.message, update.effective_user)

async def show_main_menu(message, user):
    keyboard = [
        [InlineKeyboardButton("📢 Новости", callback_data="news")],
        [InlineKeyboardButton("🎫 Создать тикет", callback_data="ticket")],
        [InlineKeyboardButton("📝 Заявка в вайтлист", callback_data="whitelist")],
        [InlineKeyboardButton("🌐 IP сервера", callback_data="ip")],
        [InlineKeyboardButton("🔗 Ссылка на Discord", url=DISCORD_LINK)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text(
        "🏠 *Главное меню*\n\nВыберите нужный раздел:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ======================================================
# ОБРАБОТЧИК КНОПОК
# ======================================================

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
            f"🌐 *IP сервера:*\n`{SERVER_IP}`",
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
        # Показываем приглашение ввести никнейм с кнопкой "Отмена"
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_whitelist")]]
        await query.edit_message_text(
            "📝 *Заявка в вайтлист*\n\nВведите ваш игровой никнейм (или нажмите Отмена):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        # Возврат управления диалогу

    elif data == "back_to_menu":
        # Возврат в главное меню из любого места (используется после новостей, IP, тикета)
        await show_main_menu_from_query(query)

    elif data == "cancel_whitelist":
        # Отмена диалога и возврат в меню
        await show_main_menu_from_query(query)

# ======================================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ПОКАЗА МЕНЮ ИЗ QUERY
# ======================================================

async def show_main_menu_from_query(query):
    keyboard = [
        [InlineKeyboardButton("📢 Новости", callback_data="news")],
        [InlineKeyboardButton("🎫 Создать тикет", callback_data="ticket")],
        [InlineKeyboardButton("📝 Заявка в вайтлист", callback_data="whitelist")],
        [InlineKeyboardButton("🌐 IP сервера", callback_data="ip")],
        [InlineKeyboardButton("🔗 Ссылка на Discord", url=DISCORD_LINK)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "🏠 *Главное меню*\n\nВыберите нужный раздел:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ======================================================
# ДИАЛОГ ЗАЯВКИ В ВАЙТЛИСТ
# ======================================================

async def whitelist_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Этот обработчик не используется напрямую, т.к. мы входим через CallbackQuery
    # но он нужен для ConversationHandler
    await update.message.reply_text("Введите ваш игровой никнейм (или нажмите Отмена):")
    return NAME

async def whitelist_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сохраняем ник, просим причину с кнопкой "Отмена"
    context.user_data["whitelist_name"] = update.message.text
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_whitelist")]]
    await update.message.reply_text(
        "Напишите причину (или нажмите Отмена):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return REASON

async def whitelist_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data["whitelist_name"]
    reason = update.message.text
    user = update.effective_user

    # Сохраняем заявку
    save_whitelist_request(user.id, user.username or "без username", name, reason)

    # Формируем текст уведомления
    text = (
        f"📝 *Новая заявка в вайтлист!*\n"
        f"От: @{user.username or 'нет username'}\n"
        f"Игровой ник: `{name}`\n"
        f"Причина: {reason}\n"
        f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    # Отправляем уведомление админу с пересылкой сообщения пользователя
    print(f"🔔 Отправляю уведомление админу {ADMIN_CHAT_ID}: {text}")
    await notify_admin(context, text, reply_to_message=update.message)

    # Подтверждаем пользователю
    await update.message.reply_text("✅ Заявка отправлена!")

    # Показываем главное меню
    await show_main_menu(update.message, user)
    return ConversationHandler.END

async def whitelist_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Обработчик команды /cancel
    await update.message.reply_text("❌ Отменено.")
    await show_main_menu(update.message, update.effective_user)
    return ConversationHandler.END

# ======================================================
# КОМАНДА ОБНОВЛЕНИЯ НОВОСТЕЙ (только для админа)
# ======================================================

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
# КОМАНДА ПРОСМОТРА ЗАЯВОК (только для админа)
# ======================================================

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
    
    if len(text) > 4000:
        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
            await update.message.reply_text(chunk, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

# ======================================================
# ЗАПУСК
# ======================================================

def main():
    application = Application.builder().token(TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("update_news", update_news))
    application.add_handler(CommandHandler("view_requests", view_requests))

    # ConversationHandler для заявки в вайтлист
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^whitelist$")],
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

    # Обработчик остальных кнопок (кроме whitelist, который уже обработан в entry_points)
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(news|ticket|ip|back_to_menu|cancel_whitelist)$"))

    print("🚀 Бот запущен и готов к работе!")
    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
