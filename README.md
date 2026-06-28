<div align="center">

# 💪 Pushup Counter Bot

**A Telegram bot that turns "I'll do pushups" into a habit you can actually see — log sets in two taps, watch your progress on charts, and compete with friends on a shared leaderboard.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white&style=for-the-badge)](requirements.txt)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-21.x%20async-2CA5E0?logo=telegram&logoColor=white&style=for-the-badge)](requirements.txt)
[![matplotlib](https://img.shields.io/badge/matplotlib-charts-11557C?style=for-the-badge)](bot/charts.py)
[![SQLite](https://img.shields.io/badge/SQLite-storage-003B57?logo=sqlite&logoColor=white&style=for-the-badge)](bot/db.py)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white&style=for-the-badge)](docker-compose.yml)

</div>

A Telegram bot for counting pushups. It's fully interactive: everything is driven
by **on-screen buttons** and step-by-step dialogs (the bot asks, you answer), so
you never have to remember syntax. See clean Excel-style charts, compete with
other people on a shared leaderboard, and attach a photo to a set. All data lives
in SQLite, kept **separately per user**. Slash commands work too, as a shortcut.

## The problems it solves

- **Tracking workouts in your head doesn't stick.** Each set — just a number — is
  logged in a guided chat flow ("Log a set" → type how many you did), so the
  record takes seconds and there's no app to install beyond Telegram.
- **A bare count isn't motivating.** The bot renders **charts** (`matplotlib`):
  pushups per set, a cumulative "how many in total" curve, and a per-day histogram
  that highlights your record day — so progress is something you can actually look at.
- **Doing it alone is easy to drop.** A shared **leaderboard** (`/top`) ranks
  every participant by their total and their percentage toward a common 100,000
  goal, turning it into a friendly competition.
- **Mistakes happen when you log fast.** You can **edit or delete** your own
  entries from a button list (delete asks for confirmation) — you can only touch
  your own records.
- **One bot, many users.** All data is isolated by `user_id`, so a group of
  friends can share the same bot without seeing each other's raw entries.

## Features

- **Registration with a name** — on the first `/start` the bot asks how to list
  you on the leaderboard (changeable later via "Change name").
- **Logging sets** — "Log a set" button: the bot asks how many pushups you did and
  you type the number (or `/add 20`).
- **Charts:**
  - `/chart` — line chart of pushups per set;
  - `/total` — cumulative "total pushups so far" chart;
  - `/days` — per-day histogram (with the record day highlighted).
- **Stats** — `/today`, `/stats` (total, sets, days, average, best day).
- **Leaderboard** — `/top`: all participants, their totals and % of the 100,000 goal.
- **Edit & delete** — "Edit entries" button: the bot shows your recent entries as
  buttons; pick one, then "✏️ Change number" or "🗑 Delete entry" (delete with
  confirmation). You can only edit your own entries; `/edit` works too.
- **Photos (optional)** — send a photo after a set and it's saved locally
  (`data/photos/<user_id>/`) and attached to the last entry.
- **Multi-user** — data isolated per `user_id`.

## Commands

Buttons are usually enough, but everything is available as a command too:

| Command | Description |
|---|---|
| `/start` | register (asks your name) and open the main menu |
| `/setname` | change your leaderboard name |
| `/add` (or `/add 20`) | log a set — asks for the number, or set it inline |
| `/today` | how many pushups today |
| `/total` | all-time total + cumulative chart |
| `/chart` | pushups-per-set chart |
| `/days` | per-day histogram |
| `/stats` | numeric summary |
| `/top` | leaderboard (% of 100,000) |
| `/edit` | pick an entry and fix/delete it |
| `/cancel` | cancel the current dialog |
| `/help` | help |

## Tech

- Python 3.12
- [python-telegram-bot](https://docs.python-telegram-bot.org) 21.x (async)
- matplotlib — chart rendering
- SQLite — storage
- Docker / docker-compose — deployment

## Running

### 1. Token

Get a token from [@BotFather](https://t.me/BotFather), copy the example config and
paste the token in:

```bash
cp .env.example .env
# edit .env → BOT_TOKEN=...
```

### 2. Docker (recommended)

```bash
docker compose up -d --build
docker compose logs -f
```

The database and photos are stored in the local `./data` folder (mounted to
`/data` inside the container) and survive restarts.

### 3. Locally without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN=... DB_PATH=./data/pushups.db PHOTO_DIR=./data/photos
python -m bot.main
```

## Structure

```
bot/
  main.py     — command handlers and bot startup
  db.py       — SQLite layer (users, sets, photos)
  charts.py   — chart rendering (matplotlib)
Dockerfile
docker-compose.yml
requirements.txt
.env.example
```

## Data

- `data/pushups.db` — the SQLite database.
- `data/photos/<user_id>/set_<id>.jpg` — set photos.

The `data/` folder and `.env` are excluded from git (`.gitignore`) — the token and
personal data never end up in the repository.
