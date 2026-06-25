"""Projected final group tables.

Each of today's matches is projected to its most likely outcome; points and a
representative scoreline are added to the current standings to produce a
projected final table with a qualification status per team.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Group, Match, TeamStanding
from .odds import WinProbabilities
from .scores import ScoreModel

ADVANCE_SLOTS = 2


@dataclass
class ProjectedRow:
    team: str
    points: int
    gd: int
    gf: int
    status: str


def _modal_outcome(probs: WinProbabilities) -> str:
    best = max(("H", probs.home), ("D", probs.draw), ("A", probs.away), key=lambda x: x[1])
    return best[0]


def _representative_score(outcome: str, model: ScoreModel) -> tuple[int, int]:
    for h, a in model.top_scores:
        if outcome == "H" and h > a:
            return h, a
        if outcome == "D" and h == a:
            return h, a
        if outcome == "A" and a > h:
            return h, a
    # Fallback if no listed top score matches the modal outcome.
    return {"H": (2, 1), "D": (1, 1), "A": (1, 2)}[outcome]


def project_group(
    group: Group,
    predictions: list[tuple[Match, ScoreModel, WinProbabilities]],
) -> list[ProjectedRow]:
    table = {s.team: s.copy() for s in group.standings}

    for match, model, probs in predictions:
        outcome = _modal_outcome(probs)
        hs, as_ = _representative_score(outcome, model)
        home = table.get(match.home)
        away = table.get(match.away)
        if home is None or away is None:
            continue
        home.gf += hs
        home.ga += as_
        away.gf += as_
        away.ga += hs
        home.played += 1
        away.played += 1
        if outcome == "H":
            home.won += 1
            away.lost += 1
        elif outcome == "A":
            away.won += 1
            home.lost += 1
        else:
            home.drawn += 1
            away.drawn += 1

    ordered = sorted(
        table.values(), key=lambda s: (s.points, s.gd, s.gf), reverse=True
    )
    rows: list[ProjectedRow] = []
    for i, s in enumerate(ordered):
        if i < ADVANCE_SLOTS:
            status = f"Qualified ({_ordinal(i + 1)})"
        elif i == ADVANCE_SLOTS:
            status = "Best-3rd contention"
        else:
            status = "Eliminated"
        rows.append(
            ProjectedRow(team=s.team, points=s.points, gd=s.gd, gf=s.gf, status=status)
        )
    return rows


def _ordinal(n: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(n, f"{n}th")
