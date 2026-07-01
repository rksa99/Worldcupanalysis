"""Build a typed DailyReport from a day's data.

The report is plain data (strings and numbers only) so any renderer — markdown,
JSON, HTML, a bot message — can consume it without re-running analysis.
"""

from __future__ import annotations

import random
import zlib
from dataclasses import dataclass, field
from typing import Optional

from . import narrative
from .domain import DayData
from .markets import WinProbabilities
from .poisson import MatchModel, build_match_model
from .simulate import GroupOutlook, TeamOutlook, simulate_group

DEFAULT_SIMS = 10_000


@dataclass
class MatchRow:
    match: str
    group: str
    situation: str
    motivation: str
    favorite: str
    probs_pct: str
    prob_home: float
    prob_draw: float
    prob_away: float
    likely_scores: str
    style: str
    confidence: str
    impact: str


@dataclass
class FavoriteRow:
    rank: int
    team: str
    reason: str


@dataclass
class DrawRow:
    match: str
    reason: str


@dataclass
class ChaosRow:
    match: str
    why: str


@dataclass
class TableRow:
    team: str
    exp_points: float
    exp_gd: float
    p_top2: float
    status: str


@dataclass
class DailyReport:
    date: str
    n_matches: int
    rows: list[MatchRow]
    favorites: list[FavoriteRow]
    draws: list[DrawRow]
    chaos: list[ChaosRow]
    tables: dict[str, list[TableRow]] = field(default_factory=dict)
    n_sims: int = DEFAULT_SIMS
    seed: int = 0
    source_note: Optional[str] = None


@dataclass
class _MatchContext:
    """Internal per-match bundle used while assembling sections."""

    model: MatchModel
    probs: WinProbabilities
    home_mot: narrative.Motivation
    away_mot: narrative.Motivation
    home_out: Optional[TeamOutlook]
    away_out: Optional[TeamOutlook]
    favorite: str
    confidence: str


def build_report(
    day: DayData,
    n_sims: int = DEFAULT_SIMS,
    seed: Optional[int] = None,
    source_note: Optional[str] = None,
) -> DailyReport:
    # Deterministic per day unless a seed is given: same morning, same report.
    if seed is None:
        seed = zlib.crc32(day.date.encode("utf-8"))
    rng = random.Random(seed)

    models = [build_match_model(m) for m in day.matches]
    models_by_group: dict[str, list[MatchModel]] = {}
    for model in models:
        models_by_group.setdefault(model.match.group, []).append(model)

    outlooks: dict[str, GroupOutlook] = {}
    for group_name, group_models in models_by_group.items():
        group = day.groups.get(group_name)
        if group is not None:
            outlooks[group_name] = simulate_group(group, group_models, n_sims, rng)

    contexts: list[_MatchContext] = []
    rows: list[MatchRow] = []
    for model in models:
        match = model.match
        group = day.groups.get(match.group)
        is_knockout = group is None  # "KO" or any group we have no table for
        group_outlook = outlooks.get(match.group)
        home_out = group_outlook.outlooks.get(match.home) if group_outlook else None
        away_out = group_outlook.outlooks.get(match.away) if group_outlook else None

        probs = model.probs
        if is_knockout:
            home_mot = narrative.Motivation(
                match.home_motivation or "Win or go home", narrative.ALIVE
            )
            away_mot = narrative.Motivation(
                match.away_motivation or "Win or go home", narrative.ALIVE
            )
        else:
            home_mot = narrative.derive_motivation(home_out, match.home_motivation)
            away_mot = narrative.derive_motivation(away_out, match.away_motivation)
        favorite = narrative.market_favorite(match, probs)
        conf = narrative.confidence(match, probs, home_mot, away_mot)

        contexts.append(
            _MatchContext(
                model=model,
                probs=probs,
                home_mot=home_mot,
                away_mot=away_mot,
                home_out=home_out,
                away_out=away_out,
                favorite=favorite,
                confidence=conf,
            )
        )
        if is_knockout:
            situation = match.situation or "Knockout round — loser goes home."
            impact = narrative.knockout_impact(match, probs)
        else:
            situation = narrative.situation_sentence(match, group)
            impact = narrative.projected_impact(
                match, probs, home_out, away_out, home_mot, away_mot
            )
        rows.append(
            MatchRow(
                match=match.label,
                group="KO" if is_knockout else match.group,
                situation=situation,
                motivation=f"{match.home}: {home_mot.label}; {match.away}: {away_mot.label}",
                favorite=favorite,
                probs_pct=probs.pct_string(),
                prob_home=round(probs.home, 4),
                prob_draw=round(probs.draw, 4),
                prob_away=round(probs.away, 4),
                likely_scores=model.top_scores_string,
                style=narrative.expected_style(match, model, probs, home_mot, away_mot),
                confidence=conf,
                impact=impact,
            )
        )

    return DailyReport(
        date=day.date,
        n_matches=len(rows),
        rows=rows,
        favorites=_favorites(contexts),
        draws=_draws(contexts),
        chaos=_chaos(contexts),
        tables=_tables(outlooks),
        n_sims=n_sims,
        seed=seed,
        source_note=source_note,
    )


def _favorites(contexts: list[_MatchContext]) -> list[FavoriteRow]:
    conf_rank = {"High": 0, "Medium": 1, "Low": 2}
    ranked = [
        c
        for c in contexts
        if c.favorite != "Near Even" and c.confidence in ("High", "Medium")
    ]
    ranked.sort(
        key=lambda c: (conf_rank[c.confidence], -max(c.probs.home, c.probs.away))
    )
    out: list[FavoriteRow] = []
    for i, c in enumerate(ranked[:5], 1):
        h_pct, _, a_pct = c.probs.as_pct()
        is_home = c.favorite == c.model.match.home
        fav_pct = h_pct if is_home else a_pct
        fav_mot = c.home_mot if is_home else c.away_mot
        fav_out = c.home_out if is_home else c.away_out
        reason = f"{fav_pct}% market edge; {fav_mot.label[0].lower()}{fav_mot.label[1:]}"
        if fav_out is not None and fav_out.p_top2 < 0.995:
            reason += f"; advances in {round(fav_out.p_top2 * 100)}% of sims"
        out.append(FavoriteRow(rank=i, team=c.favorite, reason=reason))
    return out


def _draws(contexts: list[_MatchContext]) -> list[DrawRow]:
    out: list[DrawRow] = []
    for c in contexts:
        modal_draw = c.probs.draw >= c.probs.home and c.probs.draw >= c.probs.away
        if modal_draw:
            out.append(
                DrawRow(
                    match=c.model.match.label,
                    reason=f"Draw most likely ({round(c.probs.draw * 100)}%)",
                )
            )
        elif c.favorite == "Near Even":
            out.append(
                DrawRow(match=c.model.match.label, reason="Evenly matched — fine margins")
            )
    return out


def _chaos(contexts: list[_MatchContext]) -> list[ChaosRow]:
    out: list[ChaosRow] = []
    for c in contexts:
        statuses = {c.home_mot.status, c.away_mot.status}
        why = None
        if narrative.MUST_WIN in statuses and statuses != {narrative.MUST_WIN}:
            why = "One side must attack — asymmetric incentives open the game up"
        elif statuses == {narrative.MUST_WIN}:
            why = "Both teams must win — wide-open shootout likely"
        elif c.favorite == "Near Even":
            why = "Too close to call — small events swing it"
        elif c.confidence == "Low":
            why = "Market and incentives conflict"
        if why:
            out.append(ChaosRow(match=c.model.match.label, why=why))
    return out


def _tables(outlooks: dict[str, GroupOutlook]) -> dict[str, list[TableRow]]:
    tables: dict[str, list[TableRow]] = {}
    for group_name in sorted(outlooks):
        rows: list[TableRow] = []
        for o in outlooks[group_name].table_order():
            rows.append(
                TableRow(
                    team=o.team,
                    exp_points=round(o.exp_points, 1),
                    exp_gd=round(o.exp_gd, 1),
                    p_top2=round(o.p_top2, 4),
                    status=narrative.table_status(o),
                )
            )
        tables[group_name] = rows
    return tables
