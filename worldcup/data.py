"""Load a day's data from JSON.

A real deployment would replace `load_day` with a provider that pulls live
standings, results, H2H and aggregated sportsbook odds. The rest of the pipeline
only depends on the `DayData` model, so swapping the source is the only change.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from .models import DayData

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_day_file(path: str) -> DayData:
    with open(path, "r", encoding="utf-8") as fh:
        return DayData.from_dict(json.load(fh))


def load_day(date: str, data_dir: Optional[str] = None) -> DayData:
    """Load `<data_dir>/<date>.json` (defaults to the repo's data/ folder)."""
    directory = data_dir or DATA_DIR
    path = os.path.join(directory, f"{date}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No data file for {date} (looked for {path}). "
            "Add a JSON file or point --data-dir at your source."
        )
    return load_day_file(path)
