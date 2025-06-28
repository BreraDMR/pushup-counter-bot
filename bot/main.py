"""Телеграм-бот «Счётчик отжиманий».

Пользователь записывает количество отжиманий за подход командой /add,
бот строит красивые графики (как в Excel), считает суммы и хранит всё
в SQLite по каждому пользователю. По желанию можно прислать фото —
оно сохранится локально и привяжется к последнему подходу.
"""

from __future__ import annotations

import logging
import os

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import charts, db

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s", level=logging.INFO
)
log = logging.getLogger("pushup-bot")

PHOTO_DIR = os.environ.get("PHOTO_DIR", "/data/photos")

# Общая цель — 100 000 отжиманий
GOAL = 100_000

HELP = (
    "💪 <b>Счётчик отжиманий</b>\n\n"
    "Команды:\n"
    "• <code>/add 20</code> — записать подход (20 отжиманий)\n"
    "• <code>/today</code> — сколько сегодня\n"
    "• <code>/total</code> — всего за всё время + график\n"
    "• <code>/chart</code> — график по подходам\n"
    "• <code>/days</code> — гистограмма по дням\n"
    "• <code>/stats</code> — сводка цифрами\n"
    "• <code>/top</code> — рейтинг всех участников (% от 100000)\n"
    "• <code>/list</code> — последние записи с их номерами\n"
    "• <code>/edit 12 25</code> — исправить запись №12 на 25\n"
    "• <code>/delete 12</code> — удалить запись №12\n"
    "• <code>/help</code> — эта подсказка\n\n"
    "📷 После подхода можешь прислать фото — оно сохранится и привяжется "
    "к последней записи."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    db.upsert_user(u.id, u.username, u.first_name)
    await update.message.reply_html(HELP)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(HELP)


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    db.upsert_user(u.id, u.username, u.first_name)

    if not context.args:
        await update.message.reply_html(
            "Укажи число: <code>/add 20</code>"
        )
        return
    try:
        count = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Это не число 🤔 Пример: /add 20")
        return
    if count <= 0 or count > 10000:
        await update.message.reply_text("Введи разумное число от 1 до 10000.")
        return

    db.add_set(u.id, count)
    total = db.total_count(u.id)
    today = db.today_count(u.id)
    await update.message.reply_html(
        f"✅ Записал подход: <b>{count}</b>\n"
        f"Сегодня: <b>{today}</b>  ·  Всего: <b>{total}</b>\n"
        f"📷 Можешь прислать фото к этому подходу."
    )


async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    await update.message.reply_html(
        f"Сегодня ты отжался <b>{db.today_count(u.id)}</b> раз 💪"
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    total = db.total_count(u.id)
    n = db.sets_count(u.id)
    days = db.per_day(u.id)
    avg = round(total / n, 1) if n else 0
    best = max((v for _, v in days), default=0)
    await update.message.reply_html(
        f"📊 <b>Статистика</b>\n"
        f"Всего отжиманий: <b>{total}</b>\n"
        f"Подходов: <b>{n}</b>\n"
        f"Тренировочных дней: <b>{len(days)}</b>\n"
        f"Среднее за подход: <b>{avg}</b>\n"
        f"Лучший день: <b>{best}</b>"
    )


async def chart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    data = db.sessions(u.id)
    if not data:
        await update.message.reply_text("Пока нет данных. Запиши подход: /add 20")
        return
    img = charts.line_chart(data, "График отжиманий по подходам")
    await update.message.reply_photo(img, caption="Твои подходы 📈")


async def total_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    data = db.sessions(u.id)
    total = db.total_count(u.id)
    if not data:
        await update.message.reply_text("Пока нет данных. Запиши подход: /add 20")
        return
    img = charts.cumulative_chart(data, total)
    await update.message.reply_photo(img, caption=f"Всего отжиманий: {total} 🔥")


async def days_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    data = db.per_day(u.id)
    if not data:
        await update.message.reply_text("Пока нет данных. Запиши подход: /add 20")
        return
    img = charts.days_bar_chart(data, "Отжимания по дням")
    await update.message.reply_photo(img, caption="Сколько в какой день 📊")


async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    board = db.leaderboard()
    if not board:
        await update.message.reply_text("Пока никто ничего не записал 🙂")
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Рейтинг участников</b>", f"<i>цель — {GOAL:,} отжиманий</i>".replace(",", " "), ""]
    for i, (name, total) in enumerate(board):
        mark = medals[i] if i < 3 else f"{i + 1}."
        pct = total / GOAL * 100
        lines.append(f"{mark} <b>{name}</b> — {total} ({pct:.2f}% от 100000)")
    await update.message.reply_html("\n".join(lines))


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    rows = db.recent_sets(u.id, limit=10)
    if not rows:
        await update.message.reply_text("Пока нет записей. Запиши подход: /add 20")
        return
    lines = ["🗒 <b>Последние записи</b> (для /edit и /delete):", ""]
    for set_id, ts, count in rows:
        when = ts.replace("T", " ")
        lines.append(f"№<b>{set_id}</b> · {when} · <b>{count}</b>")
    lines.append("\nИсправить: <code>/edit 12 25</code> · Удалить: <code>/delete 12</code>")
    await update.message.reply_html("\n".join(lines))


async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    if len(context.args) != 2:
        await update.message.reply_html(
            "Формат: <code>/edit &lt;номер&gt; &lt;новое_число&gt;</code>\n"
            "Номера записей смотри в /list"
        )
        return
    try:
        set_id, count = int(context.args[0]), int(context.args[1])
    except ValueError:
        await update.message.reply_text("Номер и число должны быть целыми. Пример: /edit 12 25")
        return
    if count <= 0 or count > 10000:
        await update.message.reply_text("Введи разумное число от 1 до 10000.")
        return
    owner = db.set_owner(set_id)
    if owner is None:
        await update.message.reply_text(f"Записи №{set_id} не существует.")
        return
    if owner != u.id:
        await update.message.reply_text("Это не твоя запись — редактировать нельзя.")
        return
    db.edit_set(set_id, count)
    await update.message.reply_html(
        f"✏️ Запись №{set_id} изменена на <b>{count}</b>. Всего теперь: <b>{db.total_count(u.id)}</b>"
    )


async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    if len(context.args) != 1:
        await update.message.reply_html(
            "Формат: <code>/delete &lt;номер&gt;</code> (номера в /list)"
        )
        return
    try:
        set_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Номер должен быть целым. Пример: /delete 12")
        return
    owner = db.set_owner(set_id)
    if owner is None:
        await update.message.reply_text(f"Записи №{set_id} не существует.")
        return
    if owner != u.id:
        await update.message.reply_text("Это не твоя запись — удалять нельзя.")
        return
    db.delete_set(set_id)
    await update.message.reply_html(
        f"🗑 Запись №{set_id} удалена. Всего теперь: <b>{db.total_count(u.id)}</b>"
    )


async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    set_id = db.last_set_id(u.id)
    if set_id is None:
        await update.message.reply_text(
            "Сначала запиши подход (/add 20), потом пришли фото."
        )
        return

    user_dir = os.path.join(PHOTO_DIR, str(u.id))
    os.makedirs(user_dir, exist_ok=True)
    path = os.path.join(user_dir, f"set_{set_id}.jpg")

    tg_file = await update.message.photo[-1].get_file()
    await tg_file.download_to_drive(path)
    db.attach_photo(set_id, path)
    await update.message.reply_text("📷 Фото сохранено и привязано к подходу!")


def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("Не задан BOT_TOKEN (см. .env.example)")

    db.init_db()
    os.makedirs(PHOTO_DIR, exist_ok=True)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("today", today_cmd))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("chart", chart_cmd))
    app.add_handler(CommandHandler("total", total_cmd))
    app.add_handler(CommandHandler("days", days_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("edit", edit_cmd))
    app.add_handler(CommandHandler("delete", delete_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, photo))

    log.info("Бот запущен")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
