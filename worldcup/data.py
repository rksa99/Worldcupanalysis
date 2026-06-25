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


def day_to_dict(day: DayData) -> dict:
    """Serialize a DayData back to the on-disk JSON shape (used for caching)."""
    groups = {}
    for letter, group in day.groups.items():
        groups[letter] = {
            "standings": [
                {
                    "team": s.team,
                    "played": s.played,
                    "won": s.won,
                    "drawn": s.drawn,
                    "lost": s.lost,
                    "gf": s.gf,
                    "ga": s.ga,
                }
                for s in group.standings
            ]
        }
    matches = []
    for m in day.matches:
        row: dict = {"home": m.home, "away": m.away, "group": m.group}
        if m.kickoff:
            row["kickoff"] = m.kickoff
        if m.odds:
            row["odds"] = {
                "home": round(m.odds.home, 3),
                "draw": round(m.odds.draw, 3),
                "away": round(m.odds.away, 3),
            }
        if m.xg_home is not None and m.xg_away is not None:
            row["xg"] = {"home": m.xg_home, "away": m.xg_away}
        if m.h2h:
            row["h2h"] = m.h2h
        matches.append(row)
    return {"date": day.date, "groups": groups, "matches": matches}


def save_day(day: DayData, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(day_to_dict(day), fh, indent=2, ensure_ascii=False)
