import asyncio
import json
import os
import re
import warnings
from datetime import datetime
from dotenv import load_dotenv
from telegram.warnings import PTBUserWarning
warnings.filterwarnings("ignore", category=PTBUserWarning)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан")

ADMIN_CHAT_ID = 1071217435
SERVER_IP = "193.39.168.179:30012"
DISCORD_LINK = "https://discord.gg/JWrnSCq9H"

# ---- Работа с файлами ----
USERS_FILE = "users.json"
TICKETS_FILE = "tickets.json"
WHITELIST_FILE = "whitelist_requests.json"
BANNED_FILE = "banned_users.json"
NEWS_FILE = "news.txt"

def get_users():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w") as f:
            json.dump({}, f)
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(u):
    with open(USERS_FILE, "w") as f:
        json.dump(u, f, indent=2)

def add_user(user_id, username=None):
    u = get_users()
    if str(user_id) not in u:
        u[str(user_id)] = {"username": username or "без username", "first_seen": datetime.now().isoformat()}
        save_users(u)

def get_tickets():
    if not os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, "w") as f:
            json.dump({}, f)
        return {}
    with open(TICKETS_FILE, "r") as f:
        return json.load(f)

def save_tickets(t):
    with open(TICKETS_FILE, "w") as f:
        json.dump(t, f, indent=2)

def add_ticket(user_id, reason):
    tickets = get_tickets()
    tid = str(datetime.now().timestamp()).replace('.', '')
    tickets[tid] = {"user_id": user_id, "reason": reason, "status": "pending", "date": datetime.now().isoformat()}
    save_tickets(tickets)
    return tid

def update_ticket_status(tid, status, reject_reason=None):
    tickets = get_tickets()
    if tid in tickets:
        tickets[tid]["status"] = status
        if reject_reason:
            tickets[tid]["reject_reason"] = reject_reason
        save_tickets(tickets)
        return True
    return False

def get_whitelist_requests():
    if not os.path.exists(WHITELIST_FILE):
        with open(WHITELIST_FILE, "w") as f:
            json.dump([], f)
        return []
    with open(WHITELIST_FILE, "r") as f:
        return json.load(f)

def save_whitelist_requests(reqs):
    with open(WHITELIST_FILE, "w") as f:
        json.dump(reqs, f, indent=2)

def add_whitelist_request(user_id, username, name, reason, is_change=False):
    reqs = get_whitelist_requests()
    data = {"user_id": user_id, "username": username, "name": name, "reason": reason,
            "date": datetime.now().isoformat(), "status": "pending", "is_change": is_change}
    reqs.append(data)
    save_whitelist_requests(reqs)
    return len(reqs) - 1

def update_whitelist_request(index, status, reject_reason=None):
    reqs = get_whitelist_requests()
    if 0 <= index < len(reqs):
        reqs[index]["status"] = status
        if reject_reason:
            reqs[index]["reject_reason"] = reject_reason
        save_whitelist_requests(reqs)
        return True
    return False

def get_news():
    if os.path.exists(NEWS_FILE):
        with open(NEWS_FILE, "r") as f:
            return f.read().strip()
    return "Новостей пока нет."

def set_news(text):
    with open(NEWS_FILE, "w") as f:
        f.write(text)

def is_banned(user_id):
    if not os.path.exists(BANNED_FILE):
        return False
    with open(BANNED_FILE, "r") as f:
        banned = json.load(f)
    return str(user_id) in banned

def escape_markdown(text):
    if not text:
        return ""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

# ---- Команды ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_user(update.effective_user.id, update.effective_user.username)
    await show_main_menu(update.message)

async def show_main_menu(target, user=None):
    keyboard = [
        [InlineKeyboardButton("📢 Новости", callback_data="news")],
        [InlineKeyboardButton("🎫 Создать тикет", callback_data="ticket")],
        [InlineKeyboardButton("📝 Заявка в вайтлист", callback_data="whitelist")],
        [InlineKeyboardButton("🌐 IP сервера", callback_data="ip")],
        [InlineKeyboardButton("🔊 Скачать мод", url="https://modrinth.com/mod/plasmo-voice")],
        [InlineKeyboardButton("🔗 Ссылка на Discord", url=DISCORD_LINK)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🏠 *Главное меню*\n\nВыберите нужный раздел:"
    if hasattr(target, 'edit_message_text'):
        await target.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await target.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# ---- Обработчик кнопок ----
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    data = query.data
    user = query.from_user
    add_user(user.id, user.username)

    print(f"🔘 Нажата кнопка: {data} (user={user.id})")

    if data == "news":
        news_text = get_news()
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_text(f"📰 *Новости:*\n\n{escape_markdown(news_text)}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data == "ip":
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_text(f"🌐 *IP сервера:*\n`{SERVER_IP}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data == "ticket":
        print("🔵 Устанавливаем expecting = ticket_reason")
        context.user_data['expecting'] = 'ticket_reason'
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_ticket")]]
        await query.edit_message_text("✏️ *Создание тикета*\n\nОпишите причину обращения (или нажмите Отмена):", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data == "whitelist":
        print("🔵 Устанавливаем expecting = whitelist_name")
        # проверка на уже существующую заявку
        reqs = get_whitelist_requests()
        for r in reqs:
            if r["user_id"] == user.id and r["status"] == "pending":
                await query.edit_message_text("⏳ *У вас уже есть заявка на рассмотрении!*", parse_mode="Markdown")
                keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
                await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
                return
        context.user_data['expecting'] = 'whitelist_name'
        context.user_data['is_change'] = False
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_whitelist")]]
        await query.edit_message_text("📝 *Заявка в вайтлист*\n\nВведите ваш игровой никнейм:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data == "back_to_menu":
        context.user_data.clear()
        await show_main_menu(query)
    elif data in ("cancel_ticket", "cancel_whitelist"):
        context.user_data.pop('expecting', None)
        await query.edit_message_text("❌ Отменено.")
        await show_main_menu(query)

# ---- Обработчик текстовых сообщений (один на всё) ----
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    expecting = context.user_data.get('expecting')

    add_user(user.id, user.username)

    print(f"📩 Получено сообщение от {user.id}, текст='{text[:30]}', expecting='{expecting}'")

    if expecting == 'ticket_reason':
        if not text:
            await update.message.reply_text("❌ Причина не может быть пустой. Напишите текст:")
            return
        context.user_data['ticket_reason'] = text
        context.user_data['expecting'] = None  # сбрасываем, чтобы не мешать
        keyboard = [[InlineKeyboardButton("✅ Да, создать", callback_data="confirm_ticket"),
                     InlineKeyboardButton("❌ Нет, отмена", callback_data="cancel_ticket")]]
        await update.message.reply_text(f"✏️ *Вы ввели причину:*\n{escape_markdown(text)}\n\nПодтвердите создание тикета:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif expecting == 'whitelist_name':
        if not text:
            await update.message.reply_text("❌ Никнейм не может быть пустым. Попробуйте снова:")
            return
        # здесь можно добавить фильтр оскорблений
        context.user_data['whitelist_name'] = text
        context.user_data['expecting'] = 'whitelist_reason'
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_whitelist")]]
        await update.message.reply_text("Напишите причину (или нажмите Отмена):", reply_markup=InlineKeyboardMarkup(keyboard))
    elif expecting == 'whitelist_reason':
        if not text:
            await update.message.reply_text("❌ Причина не может быть пустой. Попробуйте снова:")
            return
        name = context.user_data.get('whitelist_name')
        if not name:
            await update.message.reply_text("❌ Ошибка: никнейм не сохранён. Начните заново.")
            context.user_data.clear()
            await show_main_menu(update.message)
            return
        # Сохраняем заявку
        index = add_whitelist_request(user.id, user.username or "без username", name, text, is_change=False)
        # Уведомляем админа
        await notify_admin_whitelist(context, user, name, text, index)
        await update.message.reply_text("✅ Ваша заявка отправлена на рассмотрение!")
        context.user_data.clear()
        await show_main_menu(update.message)
    else:
        # Если нет ожидания, показываем меню
        await show_main_menu(update.message)

# ---- Обработчик подтверждения тикета ----
async def confirm_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    data = query.data
    print(f"🔄 Подтверждение тикета: {data}")

    if data == "confirm_ticket":
        reason = context.user_data.get('ticket_reason', "Не указана")
        user = query.from_user
        ticket_id = add_ticket(user.id, reason)
        await notify_admin_ticket(context, user, reason, ticket_id)
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_text("✅ *Тикет создан!*\n\nАдминистратор рассмотрит ваше обращение.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        context.user_data.clear()
    elif data == "cancel_ticket":
        await query.edit_message_text("❌ Создание тикета отменено.")
        context.user_data.clear()
        await show_main_menu(query)

# ---- Уведомления админа ----
async def notify_admin_whitelist(context, user, name, reason, index):
    text = (f"📝 *Новая заявка в вайтлист!*\nОт: @{escape_markdown(user.username or 'нет username')} (ID: `{user.id}`)\n"
            f"Игровой ник: `{escape_markdown(name)}`\nПричина: {escape_markdown(reason)}\nДата: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    keyboard = [[InlineKeyboardButton("✅ Одобрить", callback_data=f"wl_approve_{index}"),
                 InlineKeyboardButton("❌ Отклонить", callback_data=f"wl_reject_{index}")]]
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def notify_admin_ticket(context, user, reason, ticket_id):
    text = (f"🎫 *Новый тикет!*\nОт: @{escape_markdown(user.username or 'нет username')} (ID: `{user.id}`)\n"
            f"Причина: {escape_markdown(reason)}\nДата: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    keyboard = [[InlineKeyboardButton("✅ Принять", callback_data=f"ticket_accept_{ticket_id}"),
                 InlineKeyboardButton("❌ Отклонить", callback_data=f"ticket_reject_{ticket_id}")]]
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ---- Обработчики решений админа ----
async def handle_whitelist_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except: pass
    data = query.data
    _, action, index_str = data.split('_')
    index = int(index_str)
    reqs = get_whitelist_requests()
    if index >= len(reqs):
        await query.message.reply_text("❌ Заявка не найдена.")
        return
    req = reqs[index]
    if req["status"] != "pending":
        await query.message.reply_text("⚠️ Уже обработана.")
        return
    if action == "approve":
        update_whitelist_request(index, "approved")
        await query.message.reply_text("✅ Заявка одобрена.")
        try:
            await context.bot.send_message(chat_id=req["user_id"], text="✅ *Поздравляем!* Вы добавлены в вайтлист!", parse_mode="Markdown")
        except:
            pass
    else:
        update_whitelist_request(index, "rejected", reject_reason="Отклонено администратором")
        await query.message.reply_text("❌ Заявка отклонена.")
        try:
            await context.bot.send_message(chat_id=req["user_id"], text="❌ Заявка отклонена.", parse_mode="Markdown")
        except:
            pass
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

async def handle_ticket_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except: pass
    data = query.data
    _, action, ticket_id = data.split('_')
    tickets = get_tickets()
    if ticket_id not in tickets:
        await query.message.reply_text("❌ Тикет не найден.")
        return
    ticket = tickets[ticket_id]
    if ticket["status"] != "pending":
        await query.message.reply_text("⚠️ Уже обработан.")
        return
    if action == "accept":
        update_ticket_status(ticket_id, "accepted")
        await query.message.reply_text("✅ Тикет принят.")
        try:
            await context.bot.send_message(chat_id=ticket["user_id"], text="✅ *Ваш тикет принят!* Администратор свяжется.", parse_mode="Markdown")
        except:
            pass
    else:
        update_ticket_status(ticket_id, "rejected", reject_reason="Отклонён администратором")
        await query.message.reply_text("❌ Тикет отклонён.")
        try:
            await context.bot.send_message(chat_id=ticket["user_id"], text="❌ Тикет отклонён.", parse_mode="Markdown")
        except:
            pass
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

# ---- Команды админа ----
async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    if not context.args:
        await update.message.reply_text("❌ Укажите текст: /announce Текст")
        return
    news_text = " ".join(context.args)
    set_news(news_text)
    users = get_users()
    sent = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 *НОВОСТЬ!*\n\n{escape_markdown(news_text)}", parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await update.message.reply_text(f"✅ Разослано {sent} пользователям.")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    users = get_users()
    if not users:
        await update.message.reply_text("📭 Нет пользователей.")
        return
    text = "👥 Список пользователей:\n"
    for uid, data in users.items():
        text += f"ID: {uid} (@{data.get('username', 'без username')}) - {data.get('first_seen', '')}\n"
    await update.message.reply_text(text)

async def show_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    await update.message.reply_text(f"context.user_data: {context.user_data}")

# ---- Запуск ----
def main():
    request = HTTPXRequest(
        connection_pool_size=200,
        pool_timeout=60.0,
        read_timeout=60.0,
        write_timeout=60.0,
        connect_timeout=60.0
    )
    application = Application.builder().token(TOKEN).request(request).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("announce", announce))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("show_state", show_state))

    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(news|ip|ticket|whitelist|back_to_menu|cancel_ticket|cancel_whitelist)$"))
    application.add_handler(CallbackQueryHandler(confirm_ticket, pattern="^(confirm_ticket|cancel_ticket)$"))
    application.add_handler(CallbackQueryHandler(handle_whitelist_decision, pattern="^wl_(approve|reject)_\d+$"))
    application.add_handler(CallbackQueryHandler(handle_ticket_decision, pattern="^ticket_(accept|reject)_\d+$"))

    # Единственный обработчик всех текстовых сообщений (кроме команд)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("🚀 Бот запущен и готов к работе!")
    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
