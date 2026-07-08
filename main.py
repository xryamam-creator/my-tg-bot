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

# ========== КОНФИГ ==========
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан")

ADMIN_CHAT_ID = 1071217435
SERVER_IP = "193.39.168.179:30012"
DISCORD_LINK = "https://discord.gg/JWrnSCq9H"

# Запрещённые слова
BAD_WORDS = ["хуй", "пизда", "бля", "ебан", "залуп", "гандон", "мудила", "петух", "пидор",
             "лох", "шлюха", "курва", "сука", "ублюд", "сволочь", "тварь", "выродок",
             "fuck", "shit", "cunt", "dick", "asshole", "bastard", "whore", "slut", "bitch"]

def contains_bad_word(text):
    if not text: return False
    text_lower = text.lower()
    for word in BAD_WORDS:
        if word in text_lower:
            return True
    return False

# ========== ЭКРАНИРОВАНИЕ ДЛЯ MARKDOWN ==========
def escape_markdown(text):
    """Экранирует специальные символы Markdown (кроме обратных кавычек)."""
    if not text:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(r'([%s])' % re.escape(escape_chars), r'\\\1', text)

# ========== РАБОТА С ФАЙЛАМИ ==========
NEWS_FILE = "news.txt"
WHITELIST_FILE = "whitelist_requests.json"
USERS_FILE = "users.json"
TICKETS_FILE = "tickets.json"
BANNED_FILE = "banned_users.json"

# ---- БАН-ЛИСТ (для бота) ----
def get_banned():
    if not os.path.exists(BANNED_FILE):
        with open(BANNED_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}
    try:
        with open(BANNED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_banned(banned):
    with open(BANNED_FILE, "w", encoding="utf-8") as f:
        json.dump(banned, f, ensure_ascii=False, indent=2)

def is_banned(user_id):
    banned = get_banned()
    return str(user_id) in banned

def add_ban(user_id, reason="Не указана"):
    banned = get_banned()
    banned[str(user_id)] = {
        "reason": reason,
        "date": datetime.now().isoformat()
    }
    save_banned(banned)

def remove_ban(user_id):
    banned = get_banned()
    if str(user_id) in banned:
        del banned[str(user_id)]
        save_banned(banned)
        return True
    return False

# ---- ОСТАЛЬНЫЕ ФУНКЦИИ ----
def get_requests():
    if not os.path.exists(WHITELIST_FILE):
        with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        return []
    try:
        with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_requests(requests):
    with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
        json.dump(requests, f, ensure_ascii=False, indent=2)

def get_users():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def add_user(user_id, username=None):
    users = get_users()
    user_id_str = str(user_id)
    if user_id_str not in users:
        users[user_id_str] = {
            "username": username or "без username",
            "first_seen": datetime.now().isoformat()
        }
        save_users(users)

def get_tickets():
    if not os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}
    try:
        with open(TICKETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_tickets(tickets):
    with open(TICKETS_FILE, "w", encoding="utf-8") as f:
        json.dump(tickets, f, ensure_ascii=False, indent=2)

def add_ticket(user_id, reason):
    tickets = get_tickets()
    ticket_id = str(datetime.now().timestamp()).replace('.', '')
    tickets[ticket_id] = {
        "user_id": user_id,
        "reason": reason,
        "status": "pending",
        "date": datetime.now().isoformat()
    }
    save_tickets(tickets)
    return ticket_id

def update_ticket_status(ticket_id, status, reject_reason=None):
    tickets = get_tickets()
    if ticket_id in tickets:
        tickets[ticket_id]["status"] = status
        if reject_reason:
            tickets[ticket_id]["reject_reason"] = reject_reason
        save_tickets(tickets)
        return True
    return False

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

# ========== УВЕДОМЛЕНИЯ ==========
async def notify_admin_ticket(context, user, reason, ticket_id):
    text = (f"🎫 *Новый тикет!*\nОт: @{escape_markdown(user.username or 'нет username')} (ID: `{user.id}`)\n"
            f"Причина: {escape_markdown(reason)}\n"
            f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    keyboard = [[InlineKeyboardButton("✅ Принять", callback_data=f"ticket_accept_{ticket_id}"),
                 InlineKeyboardButton("❌ Отклонить", callback_data=f"ticket_reject_{ticket_id}")]]
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def notify_admin_whitelist(context, user, name, reason, request_index, is_change=False):
    text = (f"📝 *{'Заявка на изменение ника' if is_change else 'Новая заявка в вайтлист'}!*\n"
            f"От: @{escape_markdown(user.username or 'нет username')} (ID: `{user.id}`)\n"
            f"{'Новый' if is_change else 'Игровой'} ник: `{escape_markdown(name)}`\n"
            f"{'Причина изменения' if is_change else 'Причина'}: {escape_markdown(reason)}\n"
            f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    keyboard = [[InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{request_index}"),
                 InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{request_index}")]]
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ========== ОБРАБОТКА РЕШЕНИЙ ==========
async def handle_ticket_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except: pass
    data = query.data
    parts = data.split('_')
    if len(parts) < 3:
        await query.message.reply_text("❌ Неверный формат.")
        return
    action, ticket_id = parts[1], parts[2]
    tickets = get_tickets()
    if ticket_id not in tickets:
        await query.message.reply_text("❌ Тикет не найден.")
        return
    ticket = tickets[ticket_id]
    user_id = ticket["user_id"]
    reason = ticket["reason"]
    if ticket["status"] != "pending":
        await query.message.reply_text("⚠️ Уже обработан.")
        try: await query.edit_message_reply_markup(reply_markup=None)
        except: pass
        return
    if action == "accept":
        update_ticket_status(ticket_id, "accepted")
        try:
            await context.bot.send_message(chat_id=user_id, text=f"✅ *Ваш тикет принят!*\nПричина: {escape_markdown(reason)}\nАдминистратор свяжется.", parse_mode="Markdown")
            await query.message.reply_text("✅ Тикет принят. Пользователь уведомлён.")
        except Exception as e:
            await query.message.reply_text(f"✅ Принят, но не удалось уведомить: {e}")
        try: await query.edit_message_reply_markup(reply_markup=None)
        except: pass
    elif action == "reject":
        context.user_data['pending_ticket_reject'] = ticket_id
        await query.message.reply_text("❓ Введите причину отклонения (или /cancel_ticket).")
        try: await query.edit_message_reply_markup(reply_markup=None)
        except: pass

async def handle_ticket_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    if 'pending_ticket_reject' not in context.user_data:
        return
    ticket_id = context.user_data.pop('pending_ticket_reject')
    reason_text = update.message.text.strip()
    if not reason_text:
        await update.message.reply_text("❌ Причина не может быть пустой.")
        context.user_data['pending_ticket_reject'] = ticket_id
        return
    update_ticket_status(ticket_id, "rejected", reject_reason=reason_text)
    tickets = get_tickets()
    if ticket_id not in tickets:
        await update.message.reply_text("❌ Тикет не найден.")
        return
    user_id = tickets[ticket_id]["user_id"]
    try:
        await context.bot.send_message(chat_id=user_id, text=f"❌ *Ваш тикет отклонён.*\nПричина: {escape_markdown(reason_text)}", parse_mode="Markdown")
        await update.message.reply_text(f"✅ Пользователь уведомлён: {reason_text}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Не удалось уведомить: {reason_text}")

async def handle_whitelist_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except: pass
    data = query.data
    action, index_str = data.split('_')
    index = int(index_str)
    requests = get_requests()
    if index >= len(requests):
        await query.message.reply_text("❌ Заявка не найдена.")
        return
    req = requests[index]
    user_id = req["user_id"]
    name = req["name"]
    is_change = req.get("is_change", False)
    if req["status"] not in ["pending", "change_request"]:
        await query.message.reply_text("⚠️ Уже обработана.")
        try: await query.edit_message_reply_markup(reply_markup=None)
        except: pass
        return
    if action == "approve":
        if is_change:
            if update_user_name(user_id, name):
                update_request_status(index, "approved")
                user_message = f"✅ Ваш ник обновлён на `{escape_markdown(name)}`!"
            else:
                update_request_status(index, "approved")
                user_message = f"✅ Вы добавлены в вайтлист под ником `{escape_markdown(name)}`!"
        else:
            update_request_status(index, "approved")
            user_message = f"✅ *Поздравляем!* Вы добавлены в вайтлист под ником `{escape_markdown(name)}`!"
        try:
            await context.bot.send_message(chat_id=user_id, text=user_message, parse_mode="Markdown")
            await query.message.reply_text("✅ Заявка одобрена. Пользователь уведомлён.")
        except Exception as e:
            await query.message.reply_text(f"✅ Одобрена, но не удалось уведомить: {e}")
        try: await query.edit_message_reply_markup(reply_markup=None)
        except: pass
    elif action == "reject":
        context.user_data['pending_reject_index'] = index
        await query.message.reply_text("❓ Введите причину отклонения (или /cancel).")
        try: await query.edit_message_reply_markup(reply_markup=None)
        except: pass

async def handle_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    if 'pending_reject_index' not in context.user_data:
        return
    index = context.user_data.pop('pending_reject_index')
    reason_text = update.message.text.strip()
    if not reason_text:
        await update.message.reply_text("❌ Причина не может быть пустой.")
        context.user_data['pending_reject_index'] = index
        return
    update_request_status(index, "rejected", reject_reason=reason_text)
    requests = get_requests()
    if index >= len(requests):
        await update.message.reply_text("❌ Заявка не найдена.")
        return
    user_id = requests[index]["user_id"]
    try:
        await context.bot.send_message(chat_id=user_id, text=f"❌ *Заявка отклонена.*\nПричина: {escape_markdown(reason_text)}", parse_mode="Markdown")
        await update.message.reply_text(f"✅ Пользователь уведомлён: {reason_text}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Не удалось уведомить: {reason_text}")

# ========== ГЛАВНОЕ МЕНЮ ==========
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

# ========== ПРОВЕРКА БАНА ==========
async def check_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and is_banned(user.id):
        banned_info = get_banned().get(str(user.id), {})
        reason = banned_info.get('reason', 'Не указана')
        await update.effective_message.reply_text(
            f"⛔ *Вы забанены в боте!*\nПричина: {escape_markdown(reason)}\n\nОбратитесь к администратору для разблокировки.",
            parse_mode="Markdown"
        )
        return True
    return False

# ========== ОБРАБОТЧИК КНОПОК ==========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    query = update.callback_query
    try: await query.answer()
    except: pass
    data = query.data
    user = query.from_user
    add_user(user.id, user.username)

    if data == "news":
        news_text = get_news()
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_text(f"📰 *Новости:*\n\n{escape_markdown(news_text)}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data == "ip":
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_text(f"🌐 *IP сервера:*\n`{SERVER_IP}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data == "ticket":
        context.user_data['expecting'] = 'ticket_reason'
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_ticket")]]
        await query.edit_message_text("✏️ *Создание тикета*\n\nОпишите причину обращения (или нажмите Отмена):", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data == "whitelist":
        user_id = user.id
        last_req = get_last_user_request(user_id)
        if last_req and last_req["status"] == "pending":
            await query.edit_message_text("⏳ *У вас уже есть заявка на рассмотрении!*", parse_mode="Markdown")
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
            return
        if is_user_approved(user_id):
            current_name = get_user_current_name(user_id)
            context.user_data['expecting'] = 'whitelist_new_name'
            context.user_data['is_change'] = True
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_whitelist")]]
            await query.edit_message_text(f"✏️ *Вы уже в вайтлисте* (текущий ник: `{escape_markdown(current_name)}`).\nВведите **новый никнейм** для изменения:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            context.user_data['expecting'] = 'whitelist_name'
            context.user_data['is_change'] = False
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_whitelist")]]
            await query.edit_message_text("📝 *Заявка в вайтлист*\n\nВведите ваш игровой никнейм:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data == "back_to_menu":
        context.user_data.clear()
        await show_main_menu(query)
    elif data == "cancel_ticket":
        context.user_data.pop('expecting', None)
        await query.edit_message_text("❌ Создание тикета отменено.")
        await show_main_menu(query)
    elif data == "cancel_whitelist":
        context.user_data.pop('expecting', None)
        await query.edit_message_text("❌ Заявка отменена.")
        await show_main_menu(query)

# ========== ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ==========
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    user = update.effective_user
    text = update.message.text.strip()
    expecting = context.user_data.get('expecting')

    add_user(user.id, user.username)

    if expecting == 'ticket_reason':
        if not text:
            await update.message.reply_text("❌ Причина не может быть пустой. Напишите текст:")
            return
        context.user_data['ticket_reason'] = text
        context.user_data['expecting'] = None
        keyboard = [[InlineKeyboardButton("✅ Да, создать", callback_data="confirm_ticket"),
                     InlineKeyboardButton("❌ Нет, отмена", callback_data="cancel_ticket")]]
        await update.message.reply_text(f"✏️ *Вы ввели причину:*\n{escape_markdown(text)}\n\nПодтвердите создание тикета:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif expecting == 'whitelist_name':
        if not text:
            await update.message.reply_text("❌ Никнейм не может быть пустым. Попробуйте снова:")
            return
        if contains_bad_word(text):
            await update.message.reply_text("🚫 *Обнаружены недопустимые слова в никнейме!*", parse_mode="Markdown")
            return
        context.user_data['whitelist_name'] = text
        context.user_data['expecting'] = 'whitelist_reason'
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_whitelist")]]
        await update.message.reply_text("Напишите причину (или нажмите Отмена):", reply_markup=InlineKeyboardMarkup(keyboard))
    elif expecting == 'whitelist_new_name':
        if not text:
            await update.message.reply_text("❌ Никнейм не может быть пустым. Попробуйте снова:")
            return
        if contains_bad_word(text):
            await update.message.reply_text("🚫 *Обнаружены недопустимые слова в никнейме!*", parse_mode="Markdown")
            return
        context.user_data['whitelist_name'] = text
        context.user_data['expecting'] = 'whitelist_new_reason'
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_whitelist")]]
        await update.message.reply_text("Напишите **причину изменения ника** (или нажмите Отмена):", reply_markup=InlineKeyboardMarkup(keyboard))
    elif expecting == 'whitelist_reason' or expecting == 'whitelist_new_reason':
        if not text:
            await update.message.reply_text("❌ Причина не может быть пустой. Попробуйте снова:")
            return
        if contains_bad_word(text):
            await update.message.reply_text("🚫 *Обнаружены недопустимые слова в причине!*", parse_mode="Markdown")
            return
        name = context.user_data.get('whitelist_name')
        is_change = context.user_data.get('is_change', False)
        if not name:
            await update.message.reply_text("❌ Ошибка: никнейм не сохранён. Начните заявку заново.")
            context.user_data.clear()
            await show_main_menu(update.message)
            return
        request_index = save_whitelist_request(user.id, user.username or "без username", name, text, is_change)
        await notify_admin_whitelist(context, user, name, text, request_index, is_change)
        if is_change:
            await update.message.reply_text("✅ Ваша заявка на изменение ника отправлена на рассмотрение!")
        else:
            await update.message.reply_text("✅ Ваша заявка отправлена на рассмотрение! Администратор скоро ответит.")
        context.user_data.clear()
        await show_main_menu(update.message)
    else:
        await show_main_menu(update.message)

# ========== ОБРАБОТЧИК ПОДТВЕРЖДЕНИЯ ТИКЕТА ==========
async def confirm_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    query = update.callback_query
    try: await query.answer()
    except: pass
    data = query.data

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

# ========== КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    add_user(update.effective_user.id, update.effective_user.username)
    context.user_data.clear()
    await show_main_menu(update.message)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    add_user(update.effective_user.id, update.effective_user.username)
    context.user_data.clear()
    await show_main_menu(update.message)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="✅ Тестовое сообщение! Уведомления работают.")
        await update.message.reply_text("✅ Тестовое сообщение отправлено.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def cancel_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    if 'pending_reject_index' in context.user_data:
        context.user_data.pop('pending_reject_index')
        await update.message.reply_text("❌ Отклонение заявки отменено.")
    else:
        await update.message.reply_text("Нет активной операции.")

async def cancel_ticket_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    if 'pending_ticket_reject' in context.user_data:
        context.user_data.pop('pending_ticket_reject')
        await update.message.reply_text("❌ Отклонение тикета отменено.")
    else:
        await update.message.reply_text("Нет активной операции.")

async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    if not context.args:
        await update.message.reply_text("❌ Укажите текст: /announce Текст")
        return
    news_text = " ".join(context.args)
    set_news(news_text)
    users = get_users()
    if not users:
        await update.message.reply_text("❌ Нет пользователей.")
        return
    sent = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 *НОВОСТЬ!*\n\n{escape_markdown(news_text)}", parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await update.message.reply_text(f"✅ Разослано {sent} пользователям.")

async def view_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    requests = get_requests()
    if not requests:
        await update.message.reply_text("📭 Заявок нет.")
        return
    text = "📋 *Все заявки:*\n"
    for i, req in enumerate(requests, 1):
        status_emoji = {"pending":"🟡","approved":"✅","rejected":"❌","change_request":"🔄"}.get(req.get("status"),"⚪")
        text += f"{i}. {status_emoji} @{escape_markdown(req.get('username', ''))} — `{escape_markdown(req.get('name', ''))}`\n   {escape_markdown(req.get('reason', ''))}\n"
        if req.get("reject_reason"):
            text += f"   ❗ {escape_markdown(req['reject_reason'])}\n"
        text += f"   {req.get('date')}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def view_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    tickets = get_tickets()
    if not tickets:
        await update.message.reply_text("📭 Тикетов нет.")
        return
    text = "📋 *Все тикеты:*\n"
    for tid, data in tickets.items():
        status_emoji = {"pending":"🟡","accepted":"✅","rejected":"❌"}.get(data.get("status"),"⚪")
        text += f"ID: `{tid}` {status_emoji} @{data.get('user_id')}\n   Причина: {escape_markdown(data.get('reason', ''))}\n"
        if data.get("reject_reason"):
            text += f"   ❗ {escape_markdown(data['reject_reason'])}\n"
        text += f"   {data.get('date')}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def update_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    if not context.args:
        await update.message.reply_text("❌ Укажите текст: /update_news Текст")
        return
    new_text = " ".join(context.args)
    set_news(new_text)
    await update.message.reply_text("✅ Новости обновлены!")

# ========== ИСПРАВЛЕННАЯ КОМАНДА /users (БЕЗ MARKDOWN) ==========
async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    users = get_users()
    if not users:
        await update.message.reply_text("📭 Нет зарегистрированных пользователей.")
        return
    text = "👥 Список пользователей:\n\n"
    for uid, data in users.items():
        username = data.get('username', 'без username')
        first_seen = data.get('first_seen', 'неизвестно')
        try:
            dt = datetime.fromisoformat(first_seen)
            first_seen = dt.strftime('%d.%m.%Y %H:%M')
        except:
            pass
        text += f"ID: {uid}\nUsername: @{username}\nПервое появление: {first_seen}\n\n"
    await update.message.reply_text(text)  # parse_mode по умолчанию None

# ========== КОМАНДЫ ДЛЯ БАН-ЛИСТА ==========
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    if not context.args:
        await update.message.reply_text("❌ Укажите ID пользователя. Пример: /ban 123456789 Причина")
        return
    try:
        user_id = int(context.args[0])
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Не указана"
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом.")
        return
    if is_banned(user_id):
        await update.message.reply_text(f"⚠️ Пользователь {user_id} уже забанен.")
        return
    add_ban(user_id, reason)
    await update.message.reply_text(f"✅ Пользователь {user_id} забанен.\nПричина: {escape_markdown(reason)}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    if not context.args:
        await update.message.reply_text("❌ Укажите ID пользователя. Пример: /unban 123456789")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом.")
        return
    if not is_banned(user_id):
        await update.message.reply_text(f"⚠️ Пользователь {user_id} не в бане.")
        return
    remove_ban(user_id)
    await update.message.reply_text(f"✅ Пользователь {user_id} разбанен.")

async def banned_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    banned = get_banned()
    if not banned:
        await update.message.reply_text("📭 Нет забаненных пользователей.")
        return
    text = "⛔ Список забаненных пользователей:\n\n"
    for uid, data in banned.items():
        reason = data.get('reason', 'Не указана')
        date = data.get('date', 'неизвестно')
        try:
            dt = datetime.fromisoformat(date)
            date = dt.strftime('%d.%m.%Y %H:%M')
        except:
            pass
        text += f"ID: {uid}\nПричина: {reason}\nДата: {date}\n\n"
    await update.message.reply_text(text)  # parse_mode None

# ========== ЗАПУСК ==========
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("test", test))
    application.add_handler(CommandHandler("update_news", update_news))
    application.add_handler(CommandHandler("view_requests", view_requests))
    application.add_handler(CommandHandler("view_tickets", view_tickets))
    application.add_handler(CommandHandler("cancel", cancel_reject))
    application.add_handler(CommandHandler("cancel_ticket", cancel_ticket_reject))
    application.add_handler(CommandHandler("announce", announce))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("banned", banned_list_command))

    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(news|ip|ticket|whitelist|back_to_menu|cancel_ticket|cancel_whitelist)$"))
    application.add_handler(CallbackQueryHandler(confirm_ticket, pattern="^(confirm_ticket|cancel_ticket)$"))
    application.add_handler(CallbackQueryHandler(handle_ticket_decision, pattern="^ticket_(accept|reject)_"))
    application.add_handler(CallbackQueryHandler(handle_whitelist_decision, pattern="^(approve|reject)_"))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reject_reason))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ticket_reject_reason))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("🚀 Бот запущен и готов к работе!")
    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
