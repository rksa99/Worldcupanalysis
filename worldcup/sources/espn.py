"""ESPN public soccer API: fixtures, results, standings, embedded odds.

No API key required. League id `fifa.world` is the FIFA World Cup.
"""

from __future__ import annotations

import re
from typing import Optional

from ..domain import DayData, Group, Match, Odds, TeamStanding
from ..markets import american_to_decimal
from . import http
from .names import normalize_team

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/soccer/fifa.world/standings"

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
    """Return (groups_by_letter, normalized team name -> group letter)."""
    groups: dict[str, Group] = {}
    team_group: dict[str, str] = {}
    for child in payload.get("children", []):
        letter = _group_letter(child.get("name", child.get("abbreviation", "")))
        rows: list[TeamStanding] = []
        for entry in child.get("standings", {}).get("entries", []):
            team = entry.get("team", {})
            team_name = team.get("displayName") or team.get("name", "")
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


def _event_odds(competition: dict) -> Optional[Odds]:
    """Best-effort 3-way decimal odds from an ESPN competition object."""
    for o in competition.get("odds", []):
        home = o.get("homeTeamOdds", {})
        away = o.get("awayTeamOdds", {})
        draw = o.get("drawOdds", {})
        try:
            h = american_to_decimal(float(home["moneyLine"]))
            a = american_to_decimal(float(away["moneyLine"]))
            if "value" in draw and float(draw["value"]) > 1.01:
                d = float(draw["value"])
            else:
                d = american_to_decimal(float(draw["moneyLine"]))
            return Odds(home=h, draw=d, away=a)
        except (KeyError, TypeError, ValueError):
            continue
    return None


def parse_scoreboard(payload: dict, team_group: dict[str, str]) -> list[Match]:
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
        # A group label only makes sense when both teams share one; otherwise
        # this is a knockout (or unmapped) tie — mark it "KO" so the group
        # simulator skips it and the report styles it as a knockout.
        home_g = team_group.get(normalize_team(home_name))
        away_g = team_group.get(normalize_team(away_name))
        group = home_g if (home_g and home_g == away_g) else "KO"
        matches.append(
            Match(
                home=home_name,
                away=away_name,
                group=group,
                kickoff=comp.get("date") or event.get("date"),
                odds=_event_odds(comp),
            )
        )
    return matches


class NoFixtures(http.SourceError):
    """The sources are reachable but no matches are scheduled for the date."""


def fetch_day(date: str) -> DayData:
    """Fetch standings + fixtures for `date` (YYYY-MM-DD)."""
    groups, team_group = parse_standings(http.get_json(STANDINGS_URL))
    matches = parse_scoreboard(
        http.get_json(f"{SCOREBOARD_URL}?dates={date.replace('-', '')}"), team_group
    )
    if not matches:
        raise NoFixtures(f"No matches scheduled for {date}.")
    # Only keep groups that actually play today.
    active = {m.group for m in matches}
    return DayData(
        date=date,
        groups={g: grp for g, grp in groups.items() if g in active},
        matches=matches,
    )
