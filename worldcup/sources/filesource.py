"""File source: read/write the day-JSON format (offline mode and live cache)."""

from __future__ import annotations

import json
import os

from ..domain import DayData

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data"
)


def load(path: str) -> DayData:
    with open(path, "r", encoding="utf-8") as fh:
        return DayData.from_dict(json.load(fh))


def load_for_date(date: str, data_dir: str | None = None) -> DayData:
    directory = data_dir or DATA_DIR
    path = os.path.join(directory, f"{date}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No data file for {date} (looked for {path}). "
            "Add a JSON file or point --data-dir at your source."
        )
    return load(path)


def save(day: DayData, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(day.to_dict(), fh, indent=2, ensure_ascii=False)
