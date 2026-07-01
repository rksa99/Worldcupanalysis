"""Team-name normalisation — feeds disagree on names ("Czechia" vs "Czech Republic")."""

from __future__ import annotations

import re

_ALIASES = {
    "korea republic": "south korea",
    "ir iran": "iran",
    "republic of ireland": "ireland",
    "usa": "united states",
    "united states of america": "united states",
    "czech republic": "czechia",
    "cabo verde": "cape verde",
    "ivory coast": "cote divoire",
    "côte d'ivoire": "cote divoire",
    "turkiye": "turkey",
    "türkiye": "turkey",
    "curaçao": "curacao",
}


def normalize_team(name: str) -> str:
    n = name.strip().lower()
    n = n.replace("&", "and")
    n = re.sub(r"[.'’]", "", n)
    n = re.sub(r"\s+", " ", n)
    return _ALIASES.get(n, n)
