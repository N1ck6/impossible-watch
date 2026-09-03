"""JSON-хранилище привычек и подсчёт стрика."""

import json
from datetime import date, timedelta
from pathlib import Path

from config import DATA_FILE

DATA_PATH = Path(__file__).resolve().parent / DATA_FILE


def load_data() -> dict:
    if DATA_PATH.exists():
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("habits", [])
            data.setdefault("current_index", 0)
            data.setdefault("log", {})
            return data
        except Exception:
            pass
    return {"habits": [], "current_index": 0, "log": {}}


def save_data(data: dict):
    try:
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def streak_for(done_dates, ref_day: date = None) -> int:
    """Длина серии подряд идущих выполненных дней, заканчивающейся ref_day
    (по умолчанию — сегодня). Если ref_day не выполнен, стрик = 0."""
    if ref_day is None:
        ref_day = date.today()
    dates = set(done_dates)
    if ref_day.isoformat() not in dates:
        return 0
    streak = 0
    d = ref_day
    while d.isoformat() in dates:
        streak += 1
        d -= timedelta(days=1)
    return streak
