"""Data sources.

Live structure (fixtures/results/standings) comes from ESPN's public API;
multi-sportsbook consensus odds from The Odds API when ODDS_API_KEY is set.
File mode reads/writes the cache/demo JSON format.

To add a source, parse its response into the domain models and compose it in
`load_live` (or add an alternative loader) — nothing downstream changes.
"""

from __future__ import annotations

import os
from typing import Optional

from ..domain import DayData
from . import espn, filesource, oddsapi
from .espn import NoFixtures
from .http import SourceError


def load_live(date: str, odds_api_key: Optional[str] = None) -> DayData:
    """Build a DayData for `date` (YYYY-MM-DD) from live sources."""
    day = espn.fetch_day(date)
    key = odds_api_key or os.environ.get("ODDS_API_KEY")
    if key:
        try:
            oddsapi.overlay(day.matches, oddsapi.fetch_events(key))
        except SourceError:
            # Keep ESPN's best-effort odds rather than failing the whole run.
            pass
    return day


__all__ = ["NoFixtures", "SourceError", "espn", "filesource", "oddsapi", "load_live"]
