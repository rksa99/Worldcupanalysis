"""Incentive / motivation engine.

For the final group matchday, the two remaining matches in a group are played
simultaneously. We enumerate every win/draw/loss combination of those matches to
work out, for each team, which of its own results still produce a top-two finish.
That drives a concise motivation label and the one-line "current situation".

This is a heuristic (it reasons over result outcomes, with current goal
difference as the tie-break). Authored overrides in the data file always win.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Optional

from .models import Group, Match, TeamStanding

# How many teams advance directly from a group (top two in the 2026 format).
ADVANCE_SLOTS = 2

_RESULTS = ("H", "D", "A")  # home win, draw, away win


def _ordinal(n: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(n, f"{n}th")


def _position_map(group: Group) -> dict[str, int]:
    ordered = sorted(
        group.standings,
        key=lambda s: (s.points, s.gd, s.gf),
        reverse=True,
    )
    return {s.team: i + 1 for i, s in enumerate(ordered)}


@dataclass
class Motivation:
    label: str
    # Final-table hint used by the projection/confidence layers.
    status: str  # "qualified" | "must_win" | "draw_enough" | "alive" | "eliminated"


def _award(result: str) -> tuple[int, int]:
    """Points awarded to (home, away) for a result code."""
    return {"H": (3, 0), "D": (1, 1), "A": (0, 3)}[result]


def _finish_position(team: str, pts: dict[str, int], base: dict[str, TeamStanding]) -> int:
    order = sorted(
        base.keys(),
        key=lambda t: (pts[t], base[t].gd, base[t].gf),
        reverse=True,
    )
    return order.index(team) + 1  # 1-based


def _finishes_top(team: str, pts: dict[str, int], base: dict[str, TeamStanding]) -> bool:
    return _finish_position(team, pts, base) <= ADVANCE_SLOTS


def analyze_group(group: Group, group_matches: list[Match]) -> dict[str, Motivation]:
    """Return a Motivation for each team in the group."""
    base = {s.team: s for s in group.standings}
    cur_pts = {t: base[t].points for t in base}

    # Map each team to the (match index, side) it plays today.
    play_today: dict[str, tuple[int, str]] = {}
    for idx, m in enumerate(group_matches):
        play_today[m.home] = (idx, "home")
        play_today[m.away] = (idx, "away")

    # For each team, which of its own results yield a top-two finish, and the
    # full set of finishing positions reachable across all scenarios.
    qualifies_on: dict[str, set[str]] = {t: set() for t in base}
    reachable_positions: dict[str, set[int]] = {t: set() for t in base}

    if group_matches:
        combos = list(product(_RESULTS, repeat=len(group_matches)))
        for combo in combos:
            pts = dict(cur_pts)
            for idx, res in enumerate(combo):
                m = group_matches[idx]
                hp, ap = _award(res)
                pts[m.home] += hp
                pts[m.away] += ap
            for team in base:
                if team not in play_today:
                    continue
                midx, side = play_today[team]
                own = combo[midx]
                own_result = (
                    "win"
                    if (own == "H" and side == "home") or (own == "A" and side == "away")
                    else "loss"
                    if own in ("H", "A")
                    else "draw"
                )
                reachable_positions[team].add(_finish_position(team, pts, base))
                if _finishes_top(team, pts, base):
                    qualifies_on[team].add(own_result)

    motivations: dict[str, Motivation] = {}
    for team in base:
        if team not in play_today:
            # Not playing today; classify purely on current safety.
            motivations[team] = _static_motivation(team, group)
            continue
        q = qualifies_on[team]
        best_pos = min(reachable_positions[team]) if reachable_positions[team] else 4
        if q == {"win", "draw", "loss"}:
            motivations[team] = Motivation("Already qualified", "qualified")
        elif not q:
            # Can't reach the top two — but 3rd place can still advance as one of
            # the best third-placed teams in the 2026 format.
            if best_pos == 3:
                motivations[team] = Motivation(
                    "Fighting for a best-third spot", "alive"
                )
            else:
                motivations[team] = Motivation("Eliminated — pride only", "eliminated")
        elif "win" in q and "draw" not in q and "loss" not in q:
            motivations[team] = Motivation("Must win", "must_win")
        elif "draw" in q and "win" in q and "loss" not in q:
            # A draw is enough in every drawing scenario?
            label = "A draw is enough" if _draw_always(team, group_matches, base, cur_pts, play_today) else "Draw may be enough"
            motivations[team] = Motivation(label, "draw_enough")
        elif "loss" in q:
            motivations[team] = Motivation("Likely through — protect goal difference", "qualified")
        else:
            motivations[team] = Motivation("Win to advance", "alive")
    return motivations


def _draw_always(
    team: str,
    group_matches: list[Match],
    base: dict[str, TeamStanding],
    cur_pts: dict[str, int],
    play_today: dict[str, tuple[int, str]],
) -> bool:
    """True if the team finishes top-two in *every* scenario where it draws."""
    midx, _side = play_today[team]
    for combo in product(_RESULTS, repeat=len(group_matches)):
        if combo[midx] != "D":
            continue
        pts = dict(cur_pts)
        for idx, res in enumerate(combo):
            m = group_matches[idx]
            hp, ap = _award(res)
            pts[m.home] += hp
            pts[m.away] += ap
        if not _finishes_top(team, pts, base):
            return False
    return True


def _static_motivation(team: str, group: Group) -> Motivation:
    pos = _position_map(group).get(team, 4)
    if pos <= ADVANCE_SLOTS:
        return Motivation("Already qualified", "qualified")
    return Motivation("Chasing qualification", "alive")


def resolve_motivations(group: Group, group_matches: list[Match]) -> dict[str, Motivation]:
    return analyze_group(group, group_matches)


def situation_sentence(match: Match, group: Group) -> str:
    """One-sentence standings summary for the match's two teams."""
    if match.situation:
        return match.situation
    pos = _position_map(group)
    ph = pos.get(match.home)
    pa = pos.get(match.away)
    if ph is None or pa is None:
        return f"{match.home} vs {match.away}."
    return f"{match.home} {_ordinal(ph)}, {match.away} {_ordinal(pa)}."


def motivation_for(match: Match, motivations: dict[str, Motivation]) -> str:
    """Combine both teams' incentives into the table's Team Motivation cell."""
    home = match.home_motivation or motivations.get(
        match.home, Motivation("—", "alive")
    ).label
    away = match.away_motivation or motivations.get(
        match.away, Motivation("—", "alive")
    ).label
    return f"{match.home}: {home}; {match.away}: {away}"
