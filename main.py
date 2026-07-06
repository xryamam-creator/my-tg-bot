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

# ======================================================
# 2. СОСТОЯНИЯ ДИАЛОГА
# ======================================================

NAME, REASON = range(2)

# ======================================================
# 3. РАБОТА С ФАЙЛАМИ
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
    """Сохраняет заявку в файл и возвращает её индекс (ID)"""
    data = {
        "user_id": user_id,
        "username": username,
        "name": name,
        "reason": reason,
        "date": datetime.now().isoformat(),
        "status": "pending"  # pending, approved, rejected
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
    return len(requests) - 1  # индекс заявки

def update_request_status(index, status):
    """Обновляет статус заявки по индексу"""
    try:
        with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
            requests = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    if 0 <= index < len(requests):
        requests[index]["status"] = status
        with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
            json.dump(requests, f, ensure_ascii=False, indent=2)
        return True
    return False

def get_request_by_user(user_id):
    """Возвращает последнюю активную заявку пользователя (pending)"""
    try:
        with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
            requests = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    # Ищем последнюю pending заявку этого пользователя
    for req in reversed(requests):
        if req["user_id"] == user_id and req["status"] == "pending":
            return req
    return None

# ======================================================
# 4. ОТПРАВКА УВЕДОМЛЕНИЙ АДМИНУ С КНОПКАМИ
# ======================================================

async def notify_admin_with_buttons(context: ContextTypes.DEFAULT_TYPE, user, name, reason, request_index):
    """Отправляет админу уведомление с кнопками Одобрить/Отклонить"""
    text = (
        f"📝 *Новая заявка в вайтлист!*\n"
        f"От: @{user.username or 'нет username'} (ID: `{user.id}`)\n"
        f"Игровой ник: `{name}`\n"
        f"Причина: {reason}\n"
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
# 5. ОБРАБОТКА РЕШЕНИЯ АДМИНА (APPROVE / REJECT)
# ======================================================

async def handle_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # например, "approve_0" или "reject_3"
    
    action, index_str = data.split('_')
    index = int(index_str)
    
    # Обновляем статус заявки
    status = "approved" if action == "approve" else "rejected"
    if not update_request_status(index, status):
        await query.edit_message_text("❌ Ошибка: заявка не найдена.")
        return
    
    # Получаем данные заявки для отправки пользователю
    try:
        with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
            requests = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        await query.edit_message_text("❌ Ошибка: файл заявок повреждён.")
        return
    
    if index >= len(requests):
        await query.edit_message_text("❌ Ошибка: неверный индекс заявки.")
        return
    
    request_data = requests[index]
    user_id = request_data["user_id"]
    name = request_data["name"]
    
    # Отправляем сообщение пользователю
    try:
        if status == "approved":
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ *Поздравляем!* Вы были добавлены в вайтлист под ником `{name}`.\nДобро пожаловать на сервер! 🎉",
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ *К сожалению, ваша заявка в вайтлист была отклонена.*\nПричина: {request_data['reason']}\nВы можете попробовать подать заявку снова.",
                parse_mode="Markdown"
            )
    except Exception as e:
        print(f"Ошибка отправки пользователю: {e}")
        await query.edit_message_text(f"⚠️ Не удалось отправить сообщение пользователю (возможно, он не начал диалог с ботом). Но заявка {status}.")
        # Убираем кнопки, даже если не удалось отправить
        await query.edit_message_reply_markup(reply_markup=None)
        return
    
    # Убираем кнопки из сообщения админа
    await query.edit_message_text(
        text=query.message.text + f"\n\n✅ Заявка **{status}**!",
        parse_mode="Markdown"
    )
    await query.edit_message_reply_markup(reply_markup=None)
    
    # Дополнительное уведомление админу об успехе
    await query.message.reply_text(f"✅ Пользователю отправлено уведомление о {status}.")

# ======================================================
# 6. ПОКАЗ ГЛАВНОГО МЕНЮ
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

# ======================================================
# 7. КОМАНДЫ
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

# ======================================================
# 8. ОБРАБОТЧИК КНОПОК (НЕ WHITELIST)
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
# 9. ВХОДНАЯ ТОЧКА ДЛЯ ЗАЯВКИ (WHITELIST)
# ======================================================

async def whitelist_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_whitelist")]]
    await query.edit_message_text(
        "📝 *Заявка в вайтлист*\n\nВведите ваш игровой никнейм (или нажмите Отмена):",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return NAME

# ======================================================
# 10. ДИАЛОГ ЗАЯВКИ
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

    # Сохраняем заявку и получаем индекс
    request_index = save_whitelist_request(user.id, user.username or "без username", name, reason)

    # Отправляем админу уведомление с кнопками
    await notify_admin_with_buttons(context, user, name, reason, request_index)

    # Подтверждаем пользователю
    await update.message.reply_text("✅ Ваша заявка отправлена на рассмотрение! Администратор скоро ответит.")

    # Показываем главное меню
    await show_main_menu(update.message)
    return ConversationHandler.END

async def whitelist_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.")
    await show_main_menu(update.message)
    return ConversationHandler.END

# ======================================================
# 11. КОМАНДЫ ДЛЯ АДМИНА (ПРОСМОТР ЗАЯВОК)
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
    text = "📋 *Все заявки:*\n\n"
    for i, req in enumerate(requests, 1):
        status_emoji = "🟡" if req.get("status") == "pending" else ("✅" if req.get("status") == "approved" else "❌")
        text += f"{i}. {status_emoji} @{req.get('username', '')} — `{req.get('name', '')}`\n"
        text += f"   {req.get('reason', '')}\n"
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
# 12. ЗАПУСК
# ======================================================

def main():
    application = Application.builder().token(TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("test", test))
    application.add_handler(CommandHandler("update_news", update_news))
    application.add_handler(CommandHandler("view_requests", view_requests))

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

    # Обработчики кнопок меню и решений админа
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(news|ticket|ip|back_to_menu|cancel_whitelist)$"))
    application.add_handler(CallbackQueryHandler(handle_decision, pattern="^(approve|reject)_"))

    print("🚀 Бот запущен и готов к работе!")
    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
