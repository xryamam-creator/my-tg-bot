async def sync_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return

    # Дадим пулу немного освободиться перед запросом
    await asyncio.sleep(0.5)

    try:
        # Уменьшим лимит для снижения нагрузки
        updates = await context.bot.get_updates(limit=50, allowed_updates=["message"])
        restored = 0
        users = get_users()
        for upd in updates:
            if upd.message and upd.message.from_user:
                user = upd.message.from_user
                user_id = user.id
                username = user.username or "восстановлен из истории"
                if str(user_id) not in users:
                    users[str(user_id)] = {
                        "username": username,
                        "first_seen": datetime.now().isoformat()
                    }
                    restored += 1
        save_users(users)
        await update.message.reply_text(f"✅ Восстановлено {restored} пользователей из истории сообщений.")
    except Exception as e:
        # Если ошибка всё же произошла, попробуем через 2 секунды ещё раз (один раз)
        if "Pool timeout" in str(e):
            await update.message.reply_text("⏳ Пул соединений занят, пробую снова через 2 секунды...")
            await asyncio.sleep(2)
            try:
                updates = await context.bot.get_updates(limit=30, allowed_updates=["message"])
                restored = 0
                users = get_users()
                for upd in updates:
                    if upd.message and upd.message.from_user:
                        user = upd.message.from_user
                        user_id = user.id
                        username = user.username or "восстановлен из истории"
                        if str(user_id) not in users:
                            users[str(user_id)] = {
                                "username": username,
                                "first_seen": datetime.now().isoformat()
                            }
                            restored += 1
                save_users(users)
                await update.message.reply_text(f"✅ Повторная попытка: восстановлено {restored} пользователей.")
            except Exception as e2:
                await update.message.reply_text(f"❌ Всё ещё ошибка: {e2}")
        else:
            await update.message.reply_text(f"❌ Ошибка: {e}")
