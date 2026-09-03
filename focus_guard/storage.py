import json
from pathlib import Path

from config import DATA_FILE

DATA_PATH = Path(__file__).resolve().parent / DATA_FILE


def load_data() -> dict:
    if DATA_PATH.exists():
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
            d.setdefault("sites", [])
            d.setdefault("apps", [])
            d.setdefault("session_min", 60)
            return d
        except Exception:
            pass
    return {"sites": [], "apps": [], "session_min": 60}


def save_data(data: dict):
    try:
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
