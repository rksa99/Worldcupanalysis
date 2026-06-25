"""Data models for the Daily World Cup Intelligence dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Odds:
    """Decimal (European) odds for a 1X2 market."""

    home: float
    draw: float
    away: float

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional["Odds"]:
        if not d:
            return None
        return cls(home=float(d["home"]), draw=float(d["draw"]), away=float(d["away"]))


@dataclass
class TeamStanding:
    """A single row of a group table."""

    team: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    gf: int = 0
    ga: int = 0

    @property
    def points(self) -> int:
        return self.won * 3 + self.drawn

    @property
    def gd(self) -> int:
        return self.gf - self.ga

    @classmethod
    def from_dict(cls, d: dict) -> "TeamStanding":
        return cls(
            team=d["team"],
            played=int(d.get("played", 0)),
            won=int(d.get("won", d.get("w", 0))),
            drawn=int(d.get("drawn", d.get("d", 0))),
            lost=int(d.get("lost", d.get("l", 0))),
            gf=int(d.get("gf", 0)),
            ga=int(d.get("ga", 0)),
        )

    def copy(self) -> "TeamStanding":
        return TeamStanding(
            team=self.team,
            played=self.played,
            won=self.won,
            drawn=self.drawn,
            lost=self.lost,
            gf=self.gf,
            ga=self.ga,
        )


@dataclass
class Group:
    """A group: its teams and current standings."""

    name: str
    standings: list[TeamStanding] = field(default_factory=list)

    @property
    def teams(self) -> list[str]:
        return [s.team for s in self.standings]

    def standing_for(self, team: str) -> Optional[TeamStanding]:
        for s in self.standings:
            if s.team == team:
                return s
        return None

    @classmethod
    def from_dict(cls, name: str, d: dict) -> "Group":
        rows = [TeamStanding.from_dict(r) for r in d.get("standings", [])]
        return cls(name=name, standings=rows)


@dataclass
class Match:
    """A scheduled match with optional market odds and expected-goals priors."""

    home: str
    away: str
    group: str
    kickoff: Optional[str] = None
    odds: Optional[Odds] = None
    xg_home: Optional[float] = None
    xg_away: Optional[float] = None
    h2h: Optional[str] = None
    # Optional authored overrides (a real deployment can leave these blank and
    # rely on the heuristic engine).
    situation: Optional[str] = None
    home_motivation: Optional[str] = None
    away_motivation: Optional[str] = None

    @property
    def label(self) -> str:
        return f"{self.home} vs {self.away}"

    @classmethod
    def from_dict(cls, d: dict) -> "Match":
        xg = d.get("xg") or {}
        return cls(
            home=d["home"],
            away=d["away"],
            group=d["group"],
            kickoff=d.get("kickoff"),
            odds=Odds.from_dict(d.get("odds")),
            xg_home=(float(xg["home"]) if "home" in xg else None),
            xg_away=(float(xg["away"]) if "away" in xg else None),
            h2h=d.get("h2h"),
            situation=d.get("situation"),
            home_motivation=(d.get("motivation") or {}).get("home"),
            away_motivation=(d.get("motivation") or {}).get("away"),
        )


@dataclass
class DayData:
    """Everything needed to build a day's dashboard."""

    date: str
    groups: dict[str, Group]
    matches: list[Match]

    @classmethod
    def from_dict(cls, d: dict) -> "DayData":
        groups = {
            name: Group.from_dict(name, gd) for name, gd in d.get("groups", {}).items()
        }
        matches = [Match.from_dict(m) for m in d.get("matches", [])]
        return cls(date=d["date"], groups=groups, matches=matches)
