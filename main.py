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

# ======================================================
# 1. КОНФИГУРАЦИЯ (ЗАМЕНИТЕ НА СВОИ ДАННЫЕ)
# ======================================================

# Токен загружается из переменной окружения BOT_TOKEN (настройте на хостинге)
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения")

# Ваши данные
ADMIN_CHAT_ID = 1071217435           # Ваш Telegram ID (узнайте через @userinfobot)
SERVER_IP = "193.39.168.179:30012"   # IP сервера
DISCORD_LINK = "https://discord.gg/JWrnSCq9H"  # Ссылка на Discord

# ======================================================
# 2. СОСТОЯНИЯ ДЛЯ ДИАЛОГА
# ======================================================

NAME, REASON = range(2)

# ======================================================
# 3. РАБОТА С ФАЙЛАМИ (НОВОСТИ И ЗАЯВКИ)
# ======================================================

NEWS_FILE = "news.txt"
WHITELIST_FILE = "whitelist_requests.json"

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
# 4. ОТПРАВКА УВЕДОМЛЕНИЙ АДМИНИСТРАТОРУ
# ======================================================

async def notify_admin(context: ContextTypes.DEFAULT_TYPE, text: str, reply_to_message=None):
    try:
        if reply_to_message:
            # Пересылаем сообщение пользователя (ник или причина)
            await context.bot.forward_message(
                chat_id=ADMIN_CHAT_ID,
                from_chat_id=reply_to_message.chat.id,
                message_id=reply_to_message.message_id
            )
        # Отправляем текстовое уведомление
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode="Markdown")
        print("✅ Уведомление отправлено админу")
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления: {e}")

# ======================================================
# 5. ГЛАВНОЕ МЕНЮ
# ======================================================

async def show_main_menu(target, user=None):
    """Показывает главное меню (может принимать message или query)"""
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
        # Это CallbackQuery
        await target.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        # Это Message
        await target.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# ======================================================
# 6. КОМАНДЫ /start и /menu
# ======================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update.message)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update.message)

# ======================================================
# 7. ТЕСТОВАЯ КОМАНДА /test (для проверки уведомлений)
# ======================================================

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="✅ Это тестовое сообщение от бота! Если вы его видите, уведомления работают.")
        await update.message.reply_text("✅ Тестовое сообщение отправлено вам в личку.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}\n\nВозможно, вы не написали боту первым. Напишите ему /start в личку и повторите.")

# ======================================================
# 8. ОБРАБОТЧИК КНОПОК (ВКЛЮЧАЯ КНОПКИ "НАЗАД" И "ОТМЕНА")
# ======================================================

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
        await notify_admin(context, text)
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_text(
            "✅ *Тикет создан!*\n\nАдминистратор уведомлён.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data == "whitelist":
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_whitelist")]]
        await query.edit_message_text(
            "📝 *Заявка в вайтлист*\n\nВведите ваш игровой никнейм (или нажмите Отмена):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        # Здесь начинается диалог, который перехватывает ConversationHandler

    elif data == "back_to_menu":
        await show_main_menu(query)

    elif data == "cancel_whitelist":
        # Отмена диалога и возврат в меню
        await show_main_menu(query)

# ======================================================
# 9. ДИАЛОГ ЗАЯВКИ В ВАЙТЛИСТ
# ======================================================

async def whitelist_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    # Отправляем уведомление админу с пересылкой сообщений пользователя
    print(f"🔔 Отправляю уведомление админу {ADMIN_CHAT_ID}: {text}")
    # Пересылаем сообщение с ником (оно было в предыдущем шаге, но его нет в текущем update)
    # Поэтому перешлём текущее сообщение с причиной (это текст причины)
    await notify_admin(context, text, reply_to_message=update.message)

    # Подтверждаем пользователю
    await update.message.reply_text("✅ Заявка отправлена!")

    # Показываем главное меню
    await show_main_menu(update.message)
    return ConversationHandler.END

async def whitelist_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Обработчик команды /cancel
    await update.message.reply_text("❌ Отменено.")
    await show_main_menu(update.message)
    return ConversationHandler.END

# ======================================================
# 10. КОМАНДЫ ДЛЯ АДМИНА
# ======================================================

async def update_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    if not context.args:
        await update.message.reply_text("❌ Укажите текст. Пример: /update_news Текст новости")
        return
    new_text = " ".join(context.args)
    set_news(new_text)
    await update.message.reply_text(f"✅ Новости обновлены!")

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
# 11. ЗАПУСК
# ======================================================

def main():
    application = Application.builder().token(TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("test", test))
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
        # per_message=False (по умолчанию) – оставляем, чтобы избежать предупреждений
    )
    application.add_handler(conv_handler)

    # Обработчик остальных кнопок (кроме whitelist, который уже в entry_points)
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(news|ticket|ip|back_to_menu|cancel_whitelist)$"))

    print("🚀 Бот запущен и готов к работе!")
    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
