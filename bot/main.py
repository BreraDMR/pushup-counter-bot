"""Телеграм-бот «Счётчик отжиманий» — интерактивный, с кнопками.

Управление кнопками внизу экрана и пошаговыми диалогами: бот спрашивает —
пользователь отвечает. Команды через «/» тоже работают как дубль.

Возможности: запись подходов, красивые графики (как в Excel), статистика,
рейтинг участников (% от цели 100000), редактирование/удаление записей,
фото к подходу. Данные в SQLite по каждому пользователю.
"""

from __future__ import annotations

import logging
import os

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from . import charts, db

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s", level=logging.INFO
)
log = logging.getLogger("pushup-bot")

PHOTO_DIR = os.environ.get("PHOTO_DIR", "/data/photos")
GOAL = 100_000  # общая цель — 100 000 отжиманий

# ── Кнопки (подписи) ─────────────────────────────────────────────
BTN_ADD = "💪 Записать подход"
BTN_CHART = "📈 График подходов"
BTN_TOTAL = "🔥 Всего отжиманий"
BTN_DAYS = "📊 По дням"
BTN_STATS = "📋 Статистика"
BTN_TOP = "🏆 Рейтинг"
BTN_EDIT = "✏️ Изменить записи"
BTN_NAME = "🙍 Сменить имя"
BTN_HELP = "ℹ️ Помощь"
BTN_CANCEL = "❌ Отмена"
BTN_SKIP = "⏭ Пропустить"

MAIN_KB = ReplyKeyboardMarkup(
    [
        [BTN_ADD],
        [BTN_CHART, BTN_TOTAL],
        [BTN_DAYS, BTN_STATS],
        [BTN_TOP, BTN_EDIT],
        [BTN_NAME, BTN_HELP],
    ],
    resize_keyboard=True,
)
CANCEL_KB = ReplyKeyboardMarkup([[BTN_CANCEL]], resize_keyboard=True)
SKIP_KB = ReplyKeyboardMarkup([[BTN_SKIP]], resize_keyboard=True)

# ── Состояния диалогов ───────────────────────────────────────────
ADD_COUNT, NAME, EDIT_VALUE = range(3)

HELP = (
    "💪 <b>Счётчик отжиманий</b>\n\n"
    "Пользуйся кнопками внизу 👇\n\n"
    "• <b>Записать подход</b> — бот спросит, сколько раз ты отжался\n"
    "• <b>График подходов</b> — линейный график по подходам\n"
    "• <b>Всего отжиманий</b> — накопительный график «сколько уже всего»\n"
    "• <b>По дням</b> — гистограмма: сколько в какой день\n"
    "• <b>Статистика</b> — сводка цифрами\n"
    "• <b>Рейтинг</b> — все участники и % от цели в 100000\n"
    "• <b>Изменить записи</b> — выбрать запись и исправить/удалить\n"
    "• <b>Сменить имя</b> — как тебя показывать в рейтинге\n\n"
    "📷 После подхода можешь прислать фото — оно сохранится и привяжется "
    "к последней записи."
)


# ── Регистрация / смена имени ────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    is_new = not db.user_exists(u.id)
    db.upsert_user(u.id, u.username, u.first_name)
    if is_new:
        await update.message.reply_html(
            "Привет! 👋 Я считаю твои отжимания.\n\n"
            "Как тебя записать в рейтинге? Напиши имя "
            "или нажми «Пропустить», чтобы оставить имя из Telegram.",
            reply_markup=SKIP_KB,
        )
        return NAME
    name = db.get_display_name(u.id) or u.first_name
    await update.message.reply_html(
        f"С возвращением, <b>{name}</b>! 💪\n\n{HELP}", reply_markup=MAIN_KB
    )
    return ConversationHandler.END


async def setname_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username, u.first_name)
    current = db.get_display_name(u.id) or u.first_name
    await update.message.reply_html(
        f"Сейчас ты записан как <b>{current}</b>.\n"
        "Напиши новое имя или нажми «Пропустить».",
        reply_markup=SKIP_KB,
    )
    return NAME


async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    text = (update.message.text or "").strip()
    if text == BTN_SKIP:
        name = db.get_display_name(u.id) or u.first_name
        await update.message.reply_html(
            f"Ок, оставил имя <b>{name}</b>. 👍\n\n{HELP}", reply_markup=MAIN_KB
        )
        return ConversationHandler.END
    if not text or len(text) > 32:
        await update.message.reply_text(
            "Имя должно быть от 1 до 32 символов. Попробуй ещё раз.",
            reply_markup=SKIP_KB,
        )
        return NAME
    db.set_display_name(u.id, text)
    await update.message.reply_html(
        f"Готово! Теперь ты — <b>{text}</b>. 🎉\n\n{HELP}", reply_markup=MAIN_KB
    )
    return ConversationHandler.END


# ── Добавление подхода (диалог) ──────────────────────────────────
async def add_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username, u.first_name)
    await update.message.reply_html(
        "Сколько раз ты отжался за этот подход? 💪\nНапиши число:",
        reply_markup=CANCEL_KB,
    )
    return ADD_COUNT


async def add_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    text = (update.message.text or "").strip()
    if text == BTN_CANCEL:
        return await cancel(update, context)
    try:
        count = int(text)
    except ValueError:
        await update.message.reply_text(
            "Это не число 🤔 Напиши, сколько раз отжался (например, 20), "
            "или нажми «Отмена».",
            reply_markup=CANCEL_KB,
        )
        return ADD_COUNT
    if count <= 0 or count > 10000:
        await update.message.reply_text(
            "Введи разумное число от 1 до 10000.", reply_markup=CANCEL_KB
        )
        return ADD_COUNT

    db.add_set(u.id, count)
    total = db.total_count(u.id)
    today = db.today_count(u.id)
    await update.message.reply_html(
        f"✅ Записал подход: <b>{count}</b>\n"
        f"Сегодня: <b>{today}</b>  ·  Всего: <b>{total}</b>\n"
        f"📷 Можешь прислать фото к этому подходу.",
        reply_markup=MAIN_KB,
    )
    return ConversationHandler.END


# ── Редактирование (диалог: выбор кнопкой → новое значение) ───────
async def edit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    rows = db.recent_sets(u.id, limit=10)
    if not rows:
        await update.message.reply_text(
            "Пока нет записей. Сначала запиши подход 💪", reply_markup=MAIN_KB
        )
        return ConversationHandler.END

    buttons = []
    for set_id, ts, count in rows:
        when = ts.replace("T", " ")[5:16]  # MM-DD HH:MM
        buttons.append(
            [InlineKeyboardButton(f"№{set_id} · {when} · {count} раз",
                                  callback_data=f"pick:{set_id}:{count}")]
        )
    await update.message.reply_text(
        "Какую запись изменить? Выбери её:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    await update.message.reply_text(
        "…или нажми «Отмена».", reply_markup=CANCEL_KB
    )
    return EDIT_VALUE  # ждём либо нажатие кнопки, либо отмену


async def edit_picked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, set_id, count = query.data.split(":")
    set_id = int(set_id)

    if db.set_owner(set_id) != query.from_user.id:
        await query.edit_message_text("Это не твоя запись 🙅")
        return ConversationHandler.END

    context.user_data["edit_id"] = set_id
    await query.edit_message_text(
        f"Запись №{set_id} (сейчас: {count} раз).\n\n"
        "Напиши новое число, либо слово «удалить», чтобы убрать запись."
    )
    return EDIT_VALUE


async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    text = (update.message.text or "").strip().lower()
    if text == BTN_CANCEL.lower():
        return await cancel(update, context)

    set_id = context.user_data.get("edit_id")
    if set_id is None:
        # пользователь написал текст, не выбрав запись кнопкой
        await update.message.reply_text(
            "Сначала выбери запись кнопкой выше 👆 или нажми «Отмена».",
            reply_markup=CANCEL_KB,
        )
        return EDIT_VALUE

    if db.set_owner(set_id) != u.id:
        await update.message.reply_text("Это не твоя запись 🙅", reply_markup=MAIN_KB)
        context.user_data.pop("edit_id", None)
        return ConversationHandler.END

    if text in ("удалить", "удали", "delete"):
        db.delete_set(set_id)
        context.user_data.pop("edit_id", None)
        await update.message.reply_html(
            f"🗑 Запись №{set_id} удалена. Всего теперь: <b>{db.total_count(u.id)}</b>",
            reply_markup=MAIN_KB,
        )
        return ConversationHandler.END

    try:
        count = int(text)
    except ValueError:
        await update.message.reply_text(
            "Напиши новое число или слово «удалить».", reply_markup=CANCEL_KB
        )
        return EDIT_VALUE
    if count <= 0 or count > 10000:
        await update.message.reply_text(
            "Введи разумное число от 1 до 10000.", reply_markup=CANCEL_KB
        )
        return EDIT_VALUE

    db.edit_set(set_id, count)
    context.user_data.pop("edit_id", None)
    await update.message.reply_html(
        f"✏️ Запись №{set_id} изменена на <b>{count}</b>. "
        f"Всего теперь: <b>{db.total_count(u.id)}</b>",
        reply_markup=MAIN_KB,
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("edit_id", None)
    await update.message.reply_text("Отменил. 👌", reply_markup=MAIN_KB)
    return ConversationHandler.END


# ── Информационные действия (кнопки и команды) ───────────────────
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(HELP, reply_markup=MAIN_KB)


async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await update.message.reply_html(
        f"Сегодня ты отжался <b>{db.today_count(u.id)}</b> раз 💪",
        reply_markup=MAIN_KB,
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    total = db.total_count(u.id)
    n = db.sets_count(u.id)
    days = db.per_day(u.id)
    avg = round(total / n, 1) if n else 0
    best = max((v for _, v in days), default=0)
    pct = total / GOAL * 100
    await update.message.reply_html(
        f"📊 <b>Статистика</b>\n"
        f"Всего отжиманий: <b>{total}</b> ({pct:.2f}% от 100000)\n"
        f"Подходов: <b>{n}</b>\n"
        f"Тренировочных дней: <b>{len(days)}</b>\n"
        f"Среднее за подход: <b>{avg}</b>\n"
        f"Лучший день: <b>{best}</b>",
        reply_markup=MAIN_KB,
    )


async def chart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    data = db.sessions(u.id)
    if not data:
        await update.message.reply_text(
            "Пока нет данных. Нажми «Записать подход» 💪", reply_markup=MAIN_KB
        )
        return
    img = charts.line_chart(data, "График отжиманий по подходам")
    await update.message.reply_photo(img, caption="Твои подходы 📈")


async def total_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    data = db.sessions(u.id)
    total = db.total_count(u.id)
    if not data:
        await update.message.reply_text(
            "Пока нет данных. Нажми «Записать подход» 💪", reply_markup=MAIN_KB
        )
        return
    img = charts.cumulative_chart(data, total)
    await update.message.reply_photo(img, caption=f"Всего отжиманий: {total} 🔥")


async def days_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    data = db.per_day(u.id)
    if not data:
        await update.message.reply_text(
            "Пока нет данных. Нажми «Записать подход» 💪", reply_markup=MAIN_KB
        )
        return
    img = charts.days_bar_chart(data, "Отжимания по дням")
    await update.message.reply_photo(img, caption="Сколько в какой день 📊")


async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    board = db.leaderboard()
    if not board:
        await update.message.reply_text(
            "Пока никто ничего не записал 🙂", reply_markup=MAIN_KB
        )
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Рейтинг участников</b>", "<i>цель — 100 000 отжиманий</i>", ""]
    for i, (name, total) in enumerate(board):
        mark = medals[i] if i < 3 else f"{i + 1}."
        pct = total / GOAL * 100
        lines.append(f"{mark} <b>{name}</b> — {total} ({pct:.2f}% от 100000)")
    await update.message.reply_html("\n".join(lines), reply_markup=MAIN_KB)


async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    set_id = db.last_set_id(u.id)
    if set_id is None:
        await update.message.reply_text(
            "Сначала запиши подход, потом пришли фото 💪", reply_markup=MAIN_KB
        )
        return
    user_dir = os.path.join(PHOTO_DIR, str(u.id))
    os.makedirs(user_dir, exist_ok=True)
    path = os.path.join(user_dir, f"set_{set_id}.jpg")
    tg_file = await update.message.photo[-1].get_file()
    await tg_file.download_to_drive(path)
    db.attach_photo(set_id, path)
    await update.message.reply_text(
        "📷 Фото сохранено и привязано к подходу!", reply_markup=MAIN_KB
    )


def _btn(label: str) -> filters.BaseFilter:
    """Точное совпадение текста кнопки."""
    import re
    return filters.Regex(f"^{re.escape(label)}$")


def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("Не задан BOT_TOKEN (см. .env.example)")

    db.init_db()
    os.makedirs(PHOTO_DIR, exist_ok=True)

    app = Application.builder().token(token).build()

    # Регистрация / смена имени
    name_conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("setname", setname_entry),
            MessageHandler(_btn(BTN_NAME), setname_entry),
        ],
        states={NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_received)]},
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_btn(BTN_CANCEL), cancel)],
    )

    # Добавление подхода
    add_conv = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_entry),
            MessageHandler(_btn(BTN_ADD), add_entry),
        ],
        states={ADD_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_count)]},
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_btn(BTN_CANCEL), cancel)],
    )

    # Редактирование
    edit_conv = ConversationHandler(
        entry_points=[
            CommandHandler("edit", edit_entry),
            MessageHandler(_btn(BTN_EDIT), edit_entry),
        ],
        states={
            EDIT_VALUE: [
                CallbackQueryHandler(edit_picked, pattern=r"^pick:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_btn(BTN_CANCEL), cancel)],
    )

    app.add_handler(name_conv)
    app.add_handler(add_conv)
    app.add_handler(edit_conv)

    # Информационные кнопки + команды-дубли
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(_btn(BTN_HELP), help_cmd))
    app.add_handler(CommandHandler("today", today_cmd))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(_btn(BTN_STATS), stats))
    app.add_handler(CommandHandler("chart", chart_cmd))
    app.add_handler(MessageHandler(_btn(BTN_CHART), chart_cmd))
    app.add_handler(CommandHandler("total", total_cmd))
    app.add_handler(MessageHandler(_btn(BTN_TOTAL), total_cmd))
    app.add_handler(CommandHandler("days", days_cmd))
    app.add_handler(MessageHandler(_btn(BTN_DAYS), days_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(MessageHandler(_btn(BTN_TOP), top_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, photo))

    log.info("Бот запущен")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
