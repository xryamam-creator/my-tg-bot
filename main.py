import asyncio
import json
import os
import warnings
from datetime import datetime
from dotenv import load_dotenv

from telegram.warnings import PTBUserWarning
warnings.filterwarnings("ignore", category=PTBUserWarning)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

# ========== КОНФИГ ==========
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан")

ADMIN_CHAT_ID = 1071217435
SERVER_IP = "193.39.168.179:30012"
DISCORD_LINK = "https://discord.gg/JWrnSCq9H"

# Состояния для диалогов
NAME, REASON = range(2)
TICKET_REASON, TICKET_CONFIRM = range(2, 4)

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

# ========== РАБОТА С ФАЙЛАМИ ==========
NEWS_FILE = "news.txt"
WHITELIST_FILE = "whitelist_requests.json"
USERS_FILE = "users.json"
TICKETS_FILE = "tickets.json"

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
            json.dump([], f)
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def add_user(user_id):
    users = get_users()
    if user_id not in users:
        users.append(user_id)
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
    text = (f"🎫 *Новый тикет!*\nОт: @{user.username or 'нет username'} (ID: `{user.id}`)\n"
            f"Причина: {reason}\nДата: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    keyboard = [[InlineKeyboardButton("✅ Принять", callback_data=f"ticket_accept_{ticket_id}"),
                 InlineKeyboardButton("❌ Отклонить", callback_data=f"ticket_reject_{ticket_id}")]]
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def notify_admin_whitelist(context, user, name, reason, request_index, is_change=False):
    text = (f"📝 *{'Заявка на изменение ника' if is_change else 'Новая заявка в вайтлист'}!*\n"
            f"От: @{user.username or 'нет username'} (ID: `{user.id}`)\n"
            f"{'Новый' if is_change else 'Игровой'} ник: `{name}`\n"
            f"{'Причина изменения' if is_change else 'Причина'}: {reason}\n"
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
            await context.bot.send_message(chat_id=user_id, text=f"✅ *Ваш тикет принят!*\nПричина: {reason}\nАдминистратор свяжется.", parse_mode="Markdown")
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
    if 'pending_ticket_reject' not in context.user_data or update.effective_user.id != ADMIN_CHAT_ID:
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
        await context.bot.send_message(chat_id=user_id, text=f"❌ *Ваш тикет отклонён.*\nПричина: {reason_text}", parse_mode="Markdown")
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
                user_message = f"✅ Ваш ник обновлён на `{name}`!"
            else:
                update_request_status(index, "approved")
                user_message = f"✅ Вы добавлены в вайтлист под ником `{name}`!"
        else:
            update_request_status(index, "approved")
            user_message = f"✅ *Поздравляем!* Вы добавлены в вайтлист под ником `{name}`!"
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
    if 'pending_reject_index' not in context.user_data or update.effective_user.id != ADMIN_CHAT_ID:
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
        await context.bot.send_message(chat_id=user_id, text=f"❌ *Заявка отклонена.*\nПричина: {reason_text}", parse_mode="Markdown")
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

# ========== ОБРАБОТЧИК КНОПОК (кроме ticket и whitelist) ==========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except: pass
    data = query.data
    add_user(query.from_user.id)

    if data == "news":
        news_text = get_news()
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_text(f"📰 *Новости:*\n\n{news_text}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data == "ip":
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_text(f"🌐 *IP сервера:*\n`{SERVER_IP}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data == "back_to_menu":
        # Выход из любого состояния – очищаем user_data и показываем меню
        # Но это обрабатывается в самом диалоге, здесь только для кнопок вне диалога
        await show_main_menu(query)
    elif data == "cancel_whitelist":
        # Эта кнопка используется внутри диалога вайтлиста, но обрабатывается в fallback
        # Чтобы не дублировать, просто покажем меню
        await show_main_menu(query)
    elif data == "cancel_ticket":
        await show_main_menu(query)

# ========== ВХОДНЫЕ ТОЧКИ ДЛЯ ДИАЛОГОВ ==========
async def ticket_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except: pass
    add_user(query.from_user.id)
    # Очищаем старые данные
    context.user_data.pop('ticket_reason', None)
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_ticket")]]
    await query.edit_message_text("✏️ *Создание тикета*\n\nОпишите причину обращения:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return TICKET_REASON

async def whitelist_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except: pass
    user = query.from_user
    user_id = user.id
    add_user(user_id)
    # Очищаем старые данные
    context.user_data.pop('whitelist_name', None)
    context.user_data.pop('is_change', None)

    last_req = get_last_user_request(user_id)
    if last_req and last_req["status"] == "pending":
        await query.edit_message_text("⏳ *У вас уже есть заявка на рассмотрении!*", parse_mode="Markdown")
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    if is_user_approved(user_id):
        current_name = get_user_current_name(user_id)
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_whitelist")]]
        await query.edit_message_text(f"✏️ *Вы уже в вайтлисте* (текущий ник: `{current_name}`).\nВведите **новый никнейм** для изменения:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        context.user_data["is_change"] = True
        return NAME
    else:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_whitelist")]]
        await query.edit_message_text("📝 *Заявка в вайтлист*\n\nВведите ваш игровой никнейм:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        context.user_data["is_change"] = False
        return NAME

# ========== ДИАЛОГ ТИКЕТА ==========
async def ticket_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_user(update.effective_user.id)
    reason_text = update.message.text.strip()
    if not reason_text:
        await update.message.reply_text("❌ Причина не может быть пустой. Напишите текст:")
        return TICKET_REASON
    context.user_data["ticket_reason"] = reason_text
    keyboard = [[InlineKeyboardButton("✅ Да, создать", callback_data="confirm_ticket"),
                 InlineKeyboardButton("❌ Нет, отмена", callback_data="cancel_ticket")]]
    await update.message.reply_text(f"✏️ *Вы ввели причину:*\n{reason_text}\n\nПодтвердите создание тикета:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return TICKET_CONFIRM

async def ticket_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except: pass
    data = query.data
    if data == "confirm_ticket":
        reason = context.user_data.get("ticket_reason", "Не указана")
        user = query.from_user
        ticket_id = add_ticket(user.id, reason)
        await notify_admin_ticket(context, user, reason, ticket_id)
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        await query.edit_message_text("✅ *Тикет создан!*\n\nАдминистратор рассмотрит ваше обращение.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        # Чистим данные и завершаем диалог
        context.user_data.pop('ticket_reason', None)
        return ConversationHandler.END
    elif data == "cancel_ticket":
        await query.edit_message_text("❌ Создание тикета отменено.")
        context.user_data.pop('ticket_reason', None)
        await show_main_menu(query)
        return ConversationHandler.END

async def ticket_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Создание тикета отменено.")
    context.user_data.pop('ticket_reason', None)
    await show_main_menu(update.message)
    return ConversationHandler.END

# ========== ДИАЛОГ ВАЙТЛИСТА ==========
async def whitelist_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_user(update.effective_user.id)
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("❌ Никнейм не может быть пустым. Попробуйте снова:")
        return NAME
    if contains_bad_word(name):
        await update.message.reply_text("🚫 *Обнаружены недопустимые слова!*", parse_mode="Markdown")
        return NAME
    context.user_data["whitelist_name"] = name
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_whitelist")]]
    if context.user_data.get("is_change", False):
        await update.message.reply_text("Напишите **причину изменения ника** (или нажмите Отмена):", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("Напишите причину (или нажмите Отмена):", reply_markup=InlineKeyboardMarkup(keyboard))
    return REASON

async def whitelist_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_user(update.effective_user.id)
    reason = update.message.text.strip()
    if not reason:
        await update.message.reply_text("❌ Причина не может быть пустой. Попробуйте снова:")
        return REASON
    if contains_bad_word(reason):
        await update.message.reply_text("🚫 *Обнаружены недопустимые слова!*", parse_mode="Markdown")
        return REASON

    name = context.user_data["whitelist_name"]
    user = update.effective_user
    is_change = context.user_data.get("is_change", False)

    request_index = save_whitelist_request(user.id, user.username or "без username", name, reason, is_change)
    await notify_admin_whitelist(context, user, name, reason, request_index, is_change)

    if is_change:
        await update.message.reply_text("✅ Ваша заявка на изменение ника отправлена на рассмотрение!")
    else:
        await update.message.reply_text("✅ Ваша заявка отправлена на рассмотрение! Администратор скоро ответит.")
    # Чистим данные
    context.user_data.pop('whitelist_name', None)
    context.user_data.pop('is_change', None)
    await show_main_menu(update.message)
    return ConversationHandler.END

async def whitelist_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.")
    context.user_data.pop('whitelist_name', None)
    context.user_data.pop('is_change', None)
    await show_main_menu(update.message)
    return ConversationHandler.END

# ========== КОМАНДЫ ДЛЯ АДМИНА И ПОЛЬЗОВАТЕЛЯ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_user(update.effective_user.id)
    # Принудительно завершаем любой активный диалог
    context.user_data.clear()
    await show_main_menu(update.message)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_user(update.effective_user.id)
    context.user_data.clear()
    await show_main_menu(update.message)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="✅ Тестовое сообщение! Уведомления работают.")
        await update.message.reply_text("✅ Тестовое сообщение отправлено.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def cancel_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    if 'pending_reject_index' in context.user_data:
        context.user_data.pop('pending_reject_index')
        await update.message.reply_text("❌ Отклонение заявки отменено.")
    else:
        await update.message.reply_text("Нет активной операции.")

async def cancel_ticket_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    if 'pending_ticket_reject' in context.user_data:
        context.user_data.pop('pending_ticket_reject')
        await update.message.reply_text("❌ Отклонение тикета отменено.")
    else:
        await update.message.reply_text("Нет активной операции.")

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
    if not users:
        await update.message.reply_text("❌ Нет пользователей.")
        return
    sent = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 *НОВОСТЬ!*\n\n{news_text}", parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await update.message.reply_text(f"✅ Разослано {sent} пользователям.")

async def view_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        text += f"{i}. {status_emoji} @{req.get('username')} — `{req.get('name')}`\n   {req.get('reason')}\n"
        if req.get("reject_reason"):
            text += f"   ❗ {req['reject_reason']}\n"
        text += f"   {req.get('date')}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def view_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        text += f"ID: `{tid}` {status_emoji} @{data.get('user_id')}\n   Причина: {data.get('reason')}\n"
        if data.get("reject_reason"):
            text += f"   ❗ {data['reject_reason']}\n"
        text += f"   {data.get('date')}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def update_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    if not context.args:
        await update.message.reply_text("❌ Укажите текст: /update_news Текст")
        return
    new_text = " ".join(context.args)
    set_news(new_text)
    await update.message.reply_text("✅ Новости обновлены!")

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

    # WHITELIST
    conv_whitelist = ConversationHandler(
        entry_points=[CallbackQueryHandler(whitelist_entry, pattern="^whitelist$")],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, whitelist_name)],
            REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, whitelist_reason)],
        },
        fallbacks=[
            CommandHandler("cancel", whitelist_cancel),
            CommandHandler("start", start),  # принудительный выход
            CommandHandler("menu", menu),
            CallbackQueryHandler(button_handler, pattern="^cancel_whitelist$")
        ],
    )
    application.add_handler(conv_whitelist)

    # TICKET
    conv_ticket = ConversationHandler(
        entry_points=[CallbackQueryHandler(ticket_entry, pattern="^ticket$")],
        states={
            TICKET_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, ticket_reason)],
            TICKET_CONFIRM: [CallbackQueryHandler(ticket_confirm, pattern="^(confirm_ticket|cancel_ticket)$")],
        },
        fallbacks=[
            CommandHandler("cancel", ticket_cancel),
            CommandHandler("start", start),
            CommandHandler("menu", menu),
            CallbackQueryHandler(button_handler, pattern="^cancel_ticket$")
        ],
    )
    application.add_handler(conv_ticket)

    # Остальные кнопки (не конфликтуют с entry_points)
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(news|ip|back_to_menu)$"))
    # Решения админа
    application.add_handler(CallbackQueryHandler(handle_whitelist_decision, pattern="^(approve|reject)_"))
    application.add_handler(CallbackQueryHandler(handle_ticket_decision, pattern="^ticket_(accept|reject)_"))
    # Причины отклонений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reject_reason))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ticket_reject_reason))

    print("🚀 Бот запущен и готов к работе!")
    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
