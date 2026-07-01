"""Turn simulation numbers into the dashboard's words.

Every label here is backed by a simulated probability — motivation comes from
P(top two | own result), impact from P(advance) / P(win group), confidence from
the alignment of market price and incentive.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .domain import Group, Match
from .markets import WinProbabilities
from .poisson import MatchModel
from .simulate import TeamOutlook

NEAR_EVEN_BAND = 0.06
STRONG_FAVORITE = 0.60
DOMINANT_FAVORITE = 0.68

# Motivation statuses (drive style/confidence/chaos logic).
QUALIFIED = "qualified"
MUST_WIN = "must_win"
DRAW_ENOUGH = "draw_enough"
ALIVE = "alive"
ELIMINATED = "eliminated"


@dataclass
class Motivation:
    label: str
    status: str


def _pct(p: float) -> str:
    return f"{round(p * 100)}%"


def derive_motivation(outlook: Optional[TeamOutlook], authored: Optional[str] = None) -> Motivation:
    if outlook is None:
        return Motivation(authored or "—", ALIVE)

    q = outlook.p_qual_if
    if q is None:  # not playing today
        status = QUALIFIED if outlook.p_top2 >= 0.995 else ALIVE
        return Motivation(authored or ("Already through" if status == QUALIFIED else "Chasing qualification"), status)

    vals = [v for v in q.values() if v is not None]
    lo = min(vals) if vals else 0.0
    hi = max(vals) if vals else 0.0
    qw, qd, ql = q.get("win"), q.get("draw"), q.get("loss")

    if lo >= 0.995:
        mot = Motivation("Already through", QUALIFIED)
    elif hi <= 0.005:
        if outlook.p_positions.get(3, 0.0) >= 0.35:
            mot = Motivation("Out of the top two — best-third hopes only", ALIVE)
        else:
            mot = Motivation("Eliminated — pride only", ELIMINATED)
    elif ql is not None and ql >= 0.9:
        mot = Motivation(f"Virtually through — advances in {_pct(ql)} even of losses", QUALIFIED)
    elif qd is not None and qd >= 0.95:
        mot = Motivation("A draw is enough", DRAW_ENOUGH)
    elif qd is not None and qd >= 0.5:
        mot = Motivation(f"A draw is probably enough ({_pct(qd)})", DRAW_ENOUGH)
    elif qw is not None and qw >= 0.25 and (qd or 0.0) < 0.25:
        mot = Motivation(f"Must win (through in {_pct(qw)} of wins)", MUST_WIN)
    elif qw is not None and qw < 0.1:
        mot = Motivation("Needs a win plus big swings elsewhere", ALIVE)
    else:
        mot = Motivation(f"Win and likely through ({_pct(qw or 0.0)})", ALIVE)

    if authored:
        mot = Motivation(authored, mot.status)
    return mot


def _ordinal(n: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(n, f"{n}th")


def situation_sentence(match: Match, group: Optional[Group]) -> str:
    if match.situation:
        return match.situation
    if group is None:
        return f"{match.home} vs {match.away}."
    ordered = sorted(group.standings, key=lambda s: (s.points, s.gd, s.gf), reverse=True)
    pos = {s.team: i + 1 for i, s in enumerate(ordered)}
    ph, pa = pos.get(match.home), pos.get(match.away)
    if ph is None or pa is None:
        return f"{match.home} vs {match.away}."
    return f"{match.home} {_ordinal(ph)}, {match.away} {_ordinal(pa)}."


def market_favorite(match: Match, probs: WinProbabilities) -> str:
    if abs(probs.home - probs.away) < NEAR_EVEN_BAND:
        return "Near Even"
    return match.home if probs.home > probs.away else match.away


def expected_style(
    match: Match,
    model: MatchModel,
    probs: WinProbabilities,
    home_mot: Motivation,
    away_mot: Motivation,
) -> str:
    total_xg = model.xg_home + model.xg_away
    fav_prob = max(probs.home, probs.away)
    statuses = {home_mot.status, away_mot.status}

    if MUST_WIN in statuses and (QUALIFIED in statuses or ELIMINATED in statuses):
        return "Must-win pressure — one side has to chase, opening the game"
    if statuses == {MUST_WIN}:
        return "Both must win — open, high-risk football"
    if abs(probs.home - probs.away) < NEAR_EVEN_BAND:
        return "Tight, evenly matched — fine margins decide"
    if fav_prob >= DOMINANT_FAVORITE:
        return "Favorite controls possession; underdog defends deep"
    if total_xg >= 2.8:
        return "Open game with end-to-end transitions"
    if total_xg <= 2.1:
        return "Low-scoring tactical match"
    return "Balanced game; favorite edges territory"


def confidence(
    match: Match,
    probs: WinProbabilities,
    home_mot: Motivation,
    away_mot: Motivation,
) -> str:
    """High when market and incentives agree; Low when they conflict."""
    fav = market_favorite(match, probs)
    if fav == "Near Even":
        return "Low"

    fav_mot = home_mot if fav == match.home else away_mot
    opp_mot = away_mot if fav == match.home else home_mot
    fav_prob = probs.home if fav == match.home else probs.away
    hungry = {MUST_WIN, DRAW_ENOUGH, ALIVE}

    if fav_mot.status == QUALIFIED and opp_mot.status == MUST_WIN:
        return "Low"
    if fav_mot.status == ELIMINATED:
        return "Low"
    if fav_mot.status in hungry and opp_mot.status in {ELIMINATED, QUALIFIED}:
        return "High" if fav_prob >= STRONG_FAVORITE else "Medium"
    if fav_prob >= DOMINANT_FAVORITE and fav_mot.status != ELIMINATED:
        return "High"
    return "Medium"


def projected_impact(
    match: Match,
    probs: WinProbabilities,
    home_out: Optional[TeamOutlook],
    away_out: Optional[TeamOutlook],
    home_mot: Motivation,
    away_mot: Motivation,
) -> str:
    fav = market_favorite(match, probs)
    statuses = {home_mot.status, away_mot.status}

    if fav == "Near Even":
        if MUST_WIN in statuses or DRAW_ENOUGH in statuses:
            return "Qualification swings on this result."
        return "Small margins — goal difference could decide."

    fav_out = home_out if fav == match.home else away_out
    if fav_out is None:
        return f"{fav} favored to take the points."
    if fav_out.p_top2 >= 0.995:
        return f"{fav} wins the group in {_pct(fav_out.p_win_group)} of simulations."
    return f"{fav} advances in {_pct(fav_out.p_top2)} of simulations."


def knockout_impact(match: Match, probs: WinProbabilities) -> str:
    """Impact line for a knockout tie (1X2 probabilities cover 90 minutes)."""
    fav = market_favorite(match, probs)
    if fav == "Near Even":
        return "Coin flip — extra time a real possibility."
    fav_prob = probs.home if fav == match.home else probs.away
    return f"{fav} favored to advance ({_pct(fav_prob)} to win in 90 minutes)."


def table_status(outlook: TeamOutlook) -> str:
    """Status cell for the projected final group table."""
    if outlook.p_top2 >= 0.995:
        return "Qualified"
    if outlook.p_top2 <= 0.005:
        if outlook.p_positions.get(3, 0.0) >= 0.5:
            return "3rd — best-third contention"
        return "Eliminated"
    return f"Top-two in {_pct(outlook.p_top2)}"
