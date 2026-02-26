import logging
import json
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")
DATA_FILE = "data.json"

# ─── Хранилище данных ────────────────────────────────────────────────────────

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"users": {}, "votes": {}, "settings": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── Вспомогательные функции ────────────────────────────────────────────────

def get_week_dates(offset=0):
    """Получить даты текущей недели (пн-вс) со смещением offset недель"""
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    return [monday + timedelta(days=i) for i in range(7)]

def fmt_date(d):
    days_ru = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return f"{days_ru[d.weekday()]} {d.strftime('%d.%m')}"

def status_emoji(status):
    return {"free": "🟢", "busy": "🔴", "maybe": "🟡"}.get(status, "⬜")

def status_text(status):
    return {"free": "Свободен", "busy": "Занят", "maybe": "Может быть"}.get(status, "Не указано")

# ─── Команды ────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = str(update.effective_user.id)
    name = update.effective_user.first_name

    if uid not in data["users"]:
        data["users"][uid] = {"name": name, "schedule": {}, "notify": True}
        save_data(data)

    text = (
        f"👋 Привет, {name}!\n\n"
        "Я помогу вашей компании координировать расписание.\n\n"
        "📋 *Команды:*\n"
        "/schedule — мой график на неделю\n"
        "/view — расписание всей компании\n"
        "/free — когда все свободны\n"
        "/vote — голосование за дату встречи\n"
        "/notify — включить/выключить напоминания\n"
        "/help — помощь"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Как пользоваться ботом:*\n\n"
        "1️⃣ /schedule — открыть свой график\n"
        "   Нажимайте на дни чтобы отметить статус:\n"
        "   🟢 Свободен | 🔴 Занят | 🟡 Может быть\n\n"
        "2️⃣ /view — посмотреть расписание всех\n\n"
        "3️⃣ /free — найти дни когда все свободны\n\n"
        "4️⃣ /vote — запустить голосование за дату\n\n"
        "5️⃣ /notify — вкл/выкл напоминания по пятницам"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать свой график с кнопками для редактирования"""
    data = load_data()
    uid = str(update.effective_user.id)

    if uid not in data["users"]:
        data["users"][uid] = {
            "name": update.effective_user.first_name,
            "schedule": {}, "notify": True
        }
        save_data(data)

    offset = int(context.args[0]) if context.args else 0
    dates = get_week_dates(offset)

    keyboard = []
    for d in dates:
        ds = d.isoformat()
        status = data["users"][uid]["schedule"].get(ds, "none")
        emoji = status_emoji(status)
        label = f"{emoji} {fmt_date(d)}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"day|{ds}|{offset}")])

    # Навигация по неделям
    nav = [
        InlineKeyboardButton("◀ Прошлая", callback_data=f"week|{offset-1}"),
        InlineKeyboardButton("Следующая ▶", callback_data=f"week|{offset+1}")
    ]
    keyboard.append(nav)

    week_start = dates[0].strftime("%d.%m")
    week_end = dates[6].strftime("%d.%m")

    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"📅 *Мой график* ({week_start} – {week_end})\n\nНажмите на день чтобы изменить статус:"

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def view_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расписание всей компании"""
    data = load_data()
    offset = int(context.args[0]) if context.args else 0
    dates = get_week_dates(offset)

    week_start = dates[0].strftime("%d.%m")
    week_end = dates[6].strftime("%d.%m")
    text = f"👥 *Расписание компании* ({week_start} – {week_end})\n\n"

    if not data["users"]:
        text += "Пока никто не зарегистрировался. Попросите друзей написать /start боту."
    else:
        for d in dates:
            ds = d.isoformat()
            text += f"*{fmt_date(d)}*\n"
            for uid, udata in data["users"].items():
                status = udata["schedule"].get(ds, "none")
                emoji = status_emoji(status)
                name = udata["name"]
                if status != "none":
                    text += f"  {emoji} {name}: {status_text(status)}\n"
                else:
                    text += f"  ⬜ {name}: не указано\n"
            text += "\n"

    keyboard = [[
        InlineKeyboardButton("◀ Прошлая", callback_data=f"view|{offset-1}"),
        InlineKeyboardButton("Следующая ▶", callback_data=f"view|{offset+1}")
    ]]

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def find_free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Найти дни когда все свободны"""
    data = load_data()
    offset = int(context.args[0]) if context.args else 0
    dates = get_week_dates(offset)

    week_start = dates[0].strftime("%d.%m")
    week_end = dates[6].strftime("%d.%m")
    text = f"🟢 *Общие свободные дни* ({week_start} – {week_end})\n\n"

    users = data["users"]
    if not users:
        text += "Никто ещё не зарегистрировался."
    else:
        found = False
        for d in dates:
            ds = d.isoformat()
            statuses = [u["schedule"].get(ds, "none") for u in users.values()]
            free_count = statuses.count("free")
            maybe_count = statuses.count("maybe")
            busy_count = statuses.count("busy")
            total = len(users)

            if busy_count == 0 and free_count == total:
                text += f"🟢 *{fmt_date(d)}* — все свободны!\n"
                found = True
            elif busy_count == 0 and free_count + maybe_count == total and free_count > 0:
                text += f"🟡 *{fmt_date(d)}* — {free_count} свободны, {maybe_count} «может быть»\n"
                found = True
            elif free_count >= total // 2:
                text += f"🔵 *{fmt_date(d)}* — {free_count}/{total} свободны\n"
                found = True

        if not found:
            text += "На этой неделе нет дней когда все свободны 😕\n"
            text += "Попросите друзей заполнить расписание!"

    keyboard = [[
        InlineKeyboardButton("◀ Прошлая", callback_data=f"free|{offset-1}"),
        InlineKeyboardButton("Следующая ▶", callback_data=f"free|{offset+1}")
    ]]

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def vote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запустить голосование за дату встречи"""
    data = load_data()
    offset = 0
    dates = get_week_dates(offset)

    # Найти дни когда хотя бы половина свободна
    users = data["users"]
    candidates = []
    for d in dates:
        ds = d.isoformat()
        free = sum(1 for u in users.values() if u["schedule"].get(ds) in ["free", "maybe"])
        if free > 0:
            candidates.append((d, free))

    if not candidates:
        await update.message.reply_text(
            "😕 Нет подходящих дат для голосования.\n"
            "Сначала попросите всех заполнить расписание (/schedule)."
        )
        return

    # Создать новое голосование
    vote_id = datetime.now().strftime("%Y%m%d%H%M%S")
    data["votes"][vote_id] = {
        "creator": str(update.effective_user.id),
        "votes": {},
        "dates": [d.isoformat() for d, _ in candidates[:6]]
    }
    save_data(data)

    keyboard = []
    for d, free_count in candidates[:6]:
        ds = d.isoformat()
        keyboard.append([InlineKeyboardButton(
            f"📅 {fmt_date(d)} (🟢 {free_count} чел.)",
            callback_data=f"vote|{vote_id}|{ds}"
        )])

    await update.message.reply_text(
        "🗳 *Голосование за дату встречи!*\n\n"
        "Выберите удобную дату (можно несколько):",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def notify_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Включить/выключить напоминания"""
    data = load_data()
    uid = str(update.effective_user.id)

    if uid not in data["users"]:
        await update.message.reply_text("Сначала напишите /start")
        return

    current = data["users"][uid].get("notify", True)
    data["users"][uid]["notify"] = not current
    save_data(data)

    if not current:
        await update.message.reply_text(
            "🔔 Напоминания *включены*!\n"
            "Каждую пятницу буду напоминать заполнить расписание на следующую неделю.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "🔕 Напоминания *выключены*.",
            parse_mode="Markdown"
        )

# ─── Обработка кнопок ───────────────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data_parts = query.data.split("|")
    action = data_parts[0]

    if action == "day":
        # Выбор дня для изменения статуса
        _, date_str, offset = data_parts
        keyboard = [
            [InlineKeyboardButton("🟢 Свободен", callback_data=f"set|{date_str}|free|{offset}")],
            [InlineKeyboardButton("🔴 Занят", callback_data=f"set|{date_str}|busy|{offset}")],
            [InlineKeyboardButton("🟡 Может быть", callback_data=f"set|{date_str}|maybe|{offset}")],
            [InlineKeyboardButton("⬜ Сбросить", callback_data=f"set|{date_str}|none|{offset}")],
            [InlineKeyboardButton("◀ Назад", callback_data=f"week|{offset}")]
        ]
        d = datetime.fromisoformat(date_str).date()
        await query.edit_message_text(
            f"📅 *{fmt_date(d)}*\n\nВыберите статус:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif action == "set":
        # Сохранить статус
        _, date_str, status, offset = data_parts
        data = load_data()
        uid = str(query.from_user.id)
        if uid not in data["users"]:
            data["users"][uid] = {"name": query.from_user.first_name, "schedule": {}, "notify": True}
        if status == "none":
            data["users"][uid]["schedule"].pop(date_str, None)
        else:
            data["users"][uid]["schedule"][date_str] = status
        save_data(data)

        # Вернуться к расписанию
        context.args = [offset]
        update.message = None
        update.callback_query = query
        await schedule(update, context)

    elif action == "week":
        offset = int(data_parts[1])
        context.args = [offset]
        update.message = None
        update.callback_query = query
        await schedule(update, context)

    elif action == "view":
        offset = int(data_parts[1])
        context.args = [offset]
        update.message = None
        update.callback_query = query
        await view_all(update, context)

    elif action == "free":
        offset = int(data_parts[1])
        context.args = [offset]
        update.message = None
        update.callback_query = query
        await find_free(update, context)

    elif action == "vote":
        # Голосование
        _, vote_id, date_str = data_parts
        data = load_data()
        uid = str(query.from_user.id)
        name = query.from_user.first_name

        if vote_id not in data["votes"]:
            await query.answer("Голосование устарело", show_alert=True)
            return

        votes = data["votes"][vote_id]["votes"]
        if uid not in votes:
            votes[uid] = []

        if date_str in votes[uid]:
            votes[uid].remove(date_str)
            action_text = "убрали голос"
        else:
            votes[uid].append(date_str)
            action_text = "проголосовали"

        save_data(data)

        # Показать текущие результаты
        result_text = f"🗳 *Результаты голосования:*\n\n"
        date_votes = {}
        for user_votes in votes.values():
            for ds in user_votes:
                date_votes[ds] = date_votes.get(ds, 0) + 1

        for ds, count in sorted(date_votes.items(), key=lambda x: -x[1]):
            d = datetime.fromisoformat(ds).date()
            result_text += f"📅 {fmt_date(d)}: {count} голос(ов)\n"

        await query.answer(f"Вы {action_text}!")
        await query.edit_message_text(result_text, parse_mode="Markdown",
                                       reply_markup=query.message.reply_markup)

# ─── Напоминания ────────────────────────────────────────────────────────────

async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Отправить напоминания по пятницам"""
    data = load_data()
    for uid, udata in data["users"].items():
        if udata.get("notify", True):
            try:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=(
                        "📅 *Пятница — время планировать!*\n\n"
                        "Не забудь заполнить расписание на следующую неделю.\n"
                        "Напиши /schedule чтобы открыть свой график."
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить напоминание {uid}: {e}")

# ─── Запуск ─────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("schedule", schedule))
    app.add_handler(CommandHandler("view", view_all))
    app.add_handler(CommandHandler("free", find_free))
    app.add_handler(CommandHandler("vote", vote_cmd))
    app.add_handler(CommandHandler("notify", notify_toggle))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Напоминания каждую пятницу в 18:00
    import datetime as dt, pytz
    app.job_queue.run_daily(
        send_reminders,
        time=dt.time(hour=18, minute=0, tzinfo=pytz.utc),
        days=(4,)  # 4 = пятница
    )

    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
