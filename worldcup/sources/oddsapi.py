"""The Odds API (the-odds-api.com): multi-sportsbook consensus odds.

Requires an API key (ODDS_API_KEY). Prices are averaged across all returned
books into one consensus line per match.
"""

from __future__ import annotations

from typing import Optional

from ..domain import Match, Odds
from . import http
from .names import normalize_team

ODDS_URL = "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/"


def fetch_events(api_key: str, regions: str = "us,uk,eu") -> list[dict]:
    url = f"{ODDS_URL}?regions={regions}&markets=h2h&oddsFormat=decimal&apiKey={api_key}"
    payload = http.get_json(url)
    if not isinstance(payload, list):
        raise http.SourceError("Unexpected Odds API response (expected a list).")
    return payload


def _consensus_for_event(event: dict) -> Optional[Odds]:
    """Average h2h decimal prices across all books in one Odds API event."""
    home_name = normalize_team(event.get("home_team", ""))
    away_name = normalize_team(event.get("away_team", ""))
    home_p: list[float] = []
    draw_p: list[float] = []
    away_p: list[float] = []
    for book in event.get("bookmakers", []):
        for market in book.get("markets", []):
            if market.get("key") != "h2h":
                continue
            for outcome in market.get("outcomes", []):
                name = normalize_team(outcome.get("name", ""))
                price = outcome.get("price")
                if price is None:
                    continue
                if name == home_name:
                    home_p.append(price)
                elif name == away_name:
                    away_p.append(price)
                elif name == "draw":
                    draw_p.append(price)
    if home_p and draw_p and away_p:
        return Odds(
            home=sum(home_p) / len(home_p),
            draw=sum(draw_p) / len(draw_p),
            away=sum(away_p) / len(away_p),
        )
    return None


def overlay(matches: list[Match], events: list[dict]) -> int:
    """Attach consensus odds to matches by team-name match. Returns count set."""
    index: dict[tuple[str, str], Odds] = {}
    for ev in events:
        consensus = _consensus_for_event(ev)
        if consensus is None:
            continue
        key = (normalize_team(ev.get("home_team", "")), normalize_team(ev.get("away_team", "")))
        index[key] = consensus
    n = 0
    for m in matches:
        key = (normalize_team(m.home), normalize_team(m.away))
        if key in index:
            m.odds = index[key]
            n += 1
    return n
