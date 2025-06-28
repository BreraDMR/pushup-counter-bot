"""Построение красивых графиков (стиль «как в Excel») через matplotlib.

Каждая функция возвращает PNG в виде BytesIO, готовый к отправке в Telegram.
"""

from __future__ import annotations

import io
from datetime import datetime

import matplotlib

matplotlib.use("Agg")  # без GUI, рендер в файл
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

# Палитра в духе Excel
ACCENT = "#2E75B6"   # синий
ACCENT2 = "#ED7D31"  # оранжевый
GRID = "#D9D9D9"
TEXT = "#404040"

plt.rcParams.update(
    {
        "font.size": 11,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT,
        "text.color": TEXT,
        "xtick.color": TEXT,
        "ytick.color": TEXT,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)


def _finish(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def line_chart(sessions: list[tuple[str, int]], title: str) -> io.BytesIO:
    """Линейный график отжиманий по подходам (с заливкой области)."""
    x = [datetime.fromisoformat(ts) for ts, _ in sessions]
    y = [c for _, c in sessions]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(x, y, color=ACCENT, linewidth=2.2, marker="o", markersize=5,
            markerfacecolor="white", markeredgecolor=ACCENT, markeredgewidth=1.6)
    ax.fill_between(x, y, color=ACCENT, alpha=0.12)

    for xi, yi in zip(x, y):
        ax.annotate(str(yi), (xi, yi), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=9, color=ACCENT)

    ax.set_title(title, fontsize=15, fontweight="bold", pad=14)
    ax.set_ylabel("Отжиманий за подход")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M"))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    fig.autofmt_xdate(rotation=30)
    ax.spines[["top", "right"]].set_visible(False)
    ax.margins(y=0.18)
    return _finish(fig)


def cumulative_chart(sessions: list[tuple[str, int]], total: int) -> io.BytesIO:
    """Накопительный график: сколько всего отжался к каждому моменту."""
    x = [datetime.fromisoformat(ts) for ts, _ in sessions]
    cum, running = [], 0
    for _, c in sessions:
        running += c
        cum.append(running)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(x, cum, color=ACCENT2, linewidth=2.6)
    ax.fill_between(x, cum, color=ACCENT2, alpha=0.18)

    ax.set_title(f"Всего отжиманий: {total}", fontsize=16, fontweight="bold", pad=14)
    ax.set_ylabel("Накопительно")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    fig.autofmt_xdate(rotation=30)
    ax.spines[["top", "right"]].set_visible(False)
    ax.margins(y=0.12)
    return _finish(fig)


def days_bar_chart(days: list[tuple[str, int]], title: str) -> io.BytesIO:
    """Гистограмма (столбики) по дням: сколько отжиманий в какой день."""
    labels = [datetime.fromisoformat(d).strftime("%d.%m") for d, _ in days]
    values = [v for _, v in days]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(labels, values, color=ACCENT, width=0.62, edgecolor="white")

    # выделяем лучший день
    if values:
        best = max(range(len(values)), key=lambda i: values[i])
        bars[best].set_color(ACCENT2)

    for rect, v in zip(bars, values):
        ax.annotate(str(v), (rect.get_x() + rect.get_width() / 2, rect.get_height()),
                    textcoords="offset points", xytext=(0, 5), ha="center",
                    fontsize=9, fontweight="bold")

    ax.set_title(title, fontsize=15, fontweight="bold", pad=14)
    ax.set_ylabel("Отжиманий за день")
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", visible=False)
    ax.margins(y=0.18)
    fig.autofmt_xdate(rotation=30)
    return _finish(fig)
