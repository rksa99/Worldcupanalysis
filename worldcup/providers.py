"""Live data providers.

The app is live-first. Structure (fixtures, results, standings) comes from
ESPN's public soccer API (no API key required). Betting odds come from The Odds
API (https://the-odds-api.com), which aggregates multiple sportsbooks — set the
ODDS_API_KEY environment variable to enable it. ESPN's own embedded odds are
used as a best-effort fallback when no key is configured.

Everything maps into the same `DayData` model the rest of the pipeline consumes,
so the analysis/render layers never change.

Network note: these endpoints must be reachable from wherever the app runs.
Some managed/CI sandboxes restrict outbound egress; run on a normal network (or
allowlist the hosts below) for live data.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import urllib.error
import urllib.request
from typing import Optional

from .models import DayData, Group, Match, Odds, TeamStanding

ESPN_SCOREBOARD = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
)
ESPN_STANDINGS = (
    "https://site.api.espn.com/apis/v2/sports/soccer/fifa.world/standings"
)
ODDS_API_URL = (
    "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/"
)

_USER_AGENT = (
    "Mozilla/5.0 (compatible; WorldCupIntelligence/1.0; +https://github.com)"
)


class ProviderError(RuntimeError):
    """Raised when a live source cannot be reached or parsed."""


def http_get_json(url: str, timeout: int = 25) -> dict:
    """GET a URL and parse JSON, honouring proxy/CA settings from the env."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    context = ssl.create_default_context()
    cafile = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if cafile and os.path.exists(cafile):
        context.load_verify_locations(cafile)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, ssl.SSLError) as exc:
        raise ProviderError(f"GET {url} failed: {exc}") from exc


# --------------------------------------------------------------------------- #
# Team-name normalisation (ESPN <-> The Odds API names differ)
# --------------------------------------------------------------------------- #

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
    "curacao": "curacao",
    "curaçao": "curacao",
}


def normalize_team(name: str) -> str:
    n = name.strip().lower()
    n = n.replace("&", "and")
    n = re.sub(r"[.'’]", "", n)
    n = re.sub(r"\s+", " ", n)
    return _ALIASES.get(n, n)


# --------------------------------------------------------------------------- #
# Odds helpers
# --------------------------------------------------------------------------- #

def american_to_decimal(ml: float) -> float:
    if ml > 0:
        return 1.0 + ml / 100.0
    return 1.0 + 100.0 / abs(ml)


# --------------------------------------------------------------------------- #
# ESPN: fixtures, results, standings
# --------------------------------------------------------------------------- #

_STAT_KEYS = {
    "played": ("gamesPlayed", "games", "gamesplayed"),
    "won": ("wins", "win"),
    "drawn": ("ties", "draws", "draw"),
    "lost": ("losses", "loss"),
    "gf": ("pointsFor", "goalsFor", "for"),
    "ga": ("pointsAgainst", "goalsAgainst", "against"),
}


def _stat(entry_stats: list[dict], field: str) -> int:
    wanted = _STAT_KEYS[field]
    for s in entry_stats:
        if s.get("name") in wanted or s.get("type") in wanted:
            try:
                return int(round(float(s.get("value", 0))))
            except (TypeError, ValueError):
                return 0
    return 0


def _group_letter(name: str) -> str:
    m = re.search(r"group\s+([A-L])", name, re.IGNORECASE)
    return m.group(1).upper() if m else name.strip()


def parse_standings(payload: dict) -> tuple[dict[str, Group], dict[str, str]]:
    """Return (groups_by_letter, team_name -> group_letter)."""
    groups: dict[str, Group] = {}
    team_group: dict[str, str] = {}
    for child in payload.get("children", []):
        letter = _group_letter(child.get("name", child.get("abbreviation", "")))
        rows: list[TeamStanding] = []
        for entry in child.get("standings", {}).get("entries", []):
            team_name = entry.get("team", {}).get("displayName") or entry.get(
                "team", {}
            ).get("name", "")
            stats = entry.get("stats", [])
            rows.append(
                TeamStanding(
                    team=team_name,
                    played=_stat(stats, "played"),
                    won=_stat(stats, "won"),
                    drawn=_stat(stats, "drawn"),
                    lost=_stat(stats, "lost"),
                    gf=_stat(stats, "gf"),
                    ga=_stat(stats, "ga"),
                )
            )
            team_group[normalize_team(team_name)] = letter
        if rows:
            groups[letter] = Group(name=letter, standings=rows)
    return groups, team_group


def _espn_event_odds(competition: dict) -> Optional[Odds]:
    """Best-effort 3-way decimal odds from an ESPN competition object."""
    for o in competition.get("odds", []):
        home = o.get("homeTeamOdds", {})
        away = o.get("awayTeamOdds", {})
        draw = o.get("drawOdds", {})
        try:
            h = american_to_decimal(float(home["moneyLine"]))
            a = american_to_decimal(float(away["moneyLine"]))
            # Draw may be given as a decimal value or an American moneyline.
            if "value" in draw and float(draw["value"]) > 1.01:
                d = float(draw["value"])
            else:
                d = american_to_decimal(float(draw["moneyLine"]))
            return Odds(home=h, draw=d, away=a)
        except (KeyError, TypeError, ValueError):
            continue
    return None


def parse_scoreboard(
    payload: dict, team_group: dict[str, str]
) -> list[Match]:
    matches: list[Match] = []
    for event in payload.get("events", []):
        comps = event.get("competitions", [])
        if not comps:
            continue
        comp = comps[0]
        competitors = comp.get("competitors", [])
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home or not away:
            continue
        home_name = home.get("team", {}).get("displayName", "")
        away_name = away.get("team", {}).get("displayName", "")
        group = team_group.get(normalize_team(home_name)) or team_group.get(
            normalize_team(away_name), "?"
        )
        matches.append(
            Match(
                home=home_name,
                away=away_name,
                group=group,
                kickoff=comp.get("date") or event.get("date"),
                odds=_espn_event_odds(comp),
            )
        )
    return matches


# --------------------------------------------------------------------------- #
# The Odds API: multi-sportsbook consensus
# --------------------------------------------------------------------------- #

def fetch_consensus_odds(api_key: str, regions: str = "us,uk,eu") -> list[dict]:
    url = (
        f"{ODDS_API_URL}?regions={regions}&markets=h2h&oddsFormat=decimal"
        f"&apiKey={api_key}"
    )
    payload = http_get_json(url)
    if not isinstance(payload, list):
        raise ProviderError("Unexpected Odds API response (expected a list).")
    return payload


def _consensus_for_event(event: dict) -> Optional[Odds]:
    """Average h2h decimal prices across all books in one Odds API event."""
    home_name = normalize_team(event.get("home_team", ""))
    away_name = normalize_team(event.get("away_team", ""))
    home_p, draw_p, away_p = [], [], []
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


def overlay_consensus_odds(matches: list[Match], odds_events: list[dict]) -> int:
    """Attach consensus odds to matches by team-name match. Returns count set."""
    index: dict[tuple[str, str], Odds] = {}
    for ev in odds_events:
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


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def load_day_live(date: str, odds_api_key: Optional[str] = None) -> DayData:
    """Build a DayData for `date` (YYYY-MM-DD) from live sources."""
    yyyymmdd = date.replace("-", "")
    standings_payload = http_get_json(ESPN_STANDINGS)
    groups, team_group = parse_standings(standings_payload)

    scoreboard_payload = http_get_json(f"{ESPN_SCOREBOARD}?dates={yyyymmdd}")
    matches = parse_scoreboard(scoreboard_payload, team_group)

    if not matches:
        raise ProviderError(f"No fixtures found for {date} from ESPN.")

    key = odds_api_key or os.environ.get("ODDS_API_KEY")
    if key:
        try:
            overlay_consensus_odds(matches, fetch_consensus_odds(key))
        except ProviderError:
            # Keep ESPN's best-effort odds rather than failing the whole run.
            pass

    # Only keep groups that actually play today.
    active = {m.group for m in matches}
    groups = {g: grp for g, grp in groups.items() if g in active}

    return DayData(date=date, groups=groups, matches=matches)
