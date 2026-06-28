"""Слой работы с базой данных (SQLite).

Хранит пользователей и их подходы отжиманий. Каждый подход может иметь
привязанное локально сохранённое фото (путь к файлу).
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
from typing import Iterator, Optional

DB_PATH = os.environ.get("DB_PATH", "/data/pushups.db")


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Создаёт таблицы, если их ещё нет."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                first_name  TEXT,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                count       INTEGER NOT NULL,
                created_at  TEXT NOT NULL,
                photo_path  TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_sets_user ON sets(user_id, created_at);
            """
        )


def upsert_user(user_id: int, username: Optional[str], first_name: Optional[str]) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, username, first_name, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
            """,
            (user_id, username, first_name, datetime.now().isoformat(timespec="seconds")),
        )


def add_set(user_id: int, count: int) -> int:
    """Записывает подход и возвращает его id."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO sets (user_id, count, created_at) VALUES (?, ?, ?)",
            (user_id, count, datetime.now().isoformat(timespec="seconds")),
        )
        return int(cur.lastrowid)


def attach_photo(set_id: int, photo_path: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE sets SET photo_path = ? WHERE id = ?", (photo_path, set_id))


def last_set_id(user_id: int) -> Optional[int]:
    """id последнего подхода пользователя (для привязки фото)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM sets WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        return int(row["id"]) if row else None


def total_count(user_id: int) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(count), 0) AS total FROM sets WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return int(row["total"])


def today_count(user_id: int) -> int:
    today = date.today().isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(count), 0) AS total FROM sets "
            "WHERE user_id = ? AND substr(created_at, 1, 10) = ?",
            (user_id, today),
        ).fetchone()
        return int(row["total"])


def sets_count(user_id: int) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM sets WHERE user_id = ?", (user_id,)
        ).fetchone()
        return int(row["c"])


def per_day(user_id: int) -> list[tuple[str, int]]:
    """Сумма отжиманий по дням: [(YYYY-MM-DD, count), ...] по возрастанию даты."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT substr(created_at, 1, 10) AS day, SUM(count) AS total "
            "FROM sets WHERE user_id = ? GROUP BY day ORDER BY day",
            (user_id,),
        ).fetchall()
        return [(r["day"], int(r["total"])) for r in rows]


def sessions(user_id: int) -> list[tuple[str, int]]:
    """Все подходы по порядку: [(timestamp, count), ...]."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT created_at, count FROM sets WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
        return [(r["created_at"], int(r["count"])) for r in rows]


def leaderboard() -> list[tuple[str, int]]:
    """Рейтинг всех пользователей: [(имя, всего_отжиманий), ...] по убыванию."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT u.user_id,
                   COALESCE(u.first_name, u.username, 'Аноним') AS name,
                   COALESCE(SUM(s.count), 0) AS total
            FROM users u
            LEFT JOIN sets s ON s.user_id = u.user_id
            GROUP BY u.user_id
            HAVING total > 0
            ORDER BY total DESC
            """
        ).fetchall()
        return [(r["name"], int(r["total"])) for r in rows]


def recent_sets(user_id: int, limit: int = 10) -> list[tuple[int, str, int]]:
    """Последние подходы пользователя: [(id, timestamp, count), ...] — свежие сверху."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, count FROM sets "
            "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [(int(r["id"]), r["created_at"], int(r["count"])) for r in rows]


def set_owner(set_id: int) -> Optional[int]:
    """user_id владельца подхода, либо None если подхода нет."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT user_id FROM sets WHERE id = ?", (set_id,)
        ).fetchone()
        return int(row["user_id"]) if row else None


def edit_set(set_id: int, count: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE sets SET count = ? WHERE id = ?", (count, set_id))


def delete_set(set_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sets WHERE id = ?", (set_id,))
