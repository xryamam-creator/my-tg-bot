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

# ========== КОНФИГ ==========
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан")

ADMIN_CHAT_ID = 1071217435
SERVER_IP = "193.39.168.179:30012"
DISCORD_LINK = "https://discord.gg/JWrnSCq9H"

# ========== РАБОТА С ФАЙЛАМИ ==========
# (здесь все функции те же, что и в предыдущем коде, но я их сократил для краткости,
# предполагая, что они у вас уже есть. В реальном коде они должны быть полностью.
# Но я дам полный код, если нужно.)

# ... (пропущены функции для экономии места, но они должны быть)
