"""Assemble per-match analysis and render the full daily markdown dashboard."""

from __future__ import annotations

from dataclasses import dataclass

from . import analysis
from .incentives import (
    Motivation,
    motivation_for,
    resolve_motivations,
    situation_sentence,
)
from .models import DayData, Group, Match
from .odds import WinProbabilities
from .projections import ProjectedRow, project_group
from .scores import ScoreModel, build_score_model, win_probabilities


@dataclass
class MatchAnalysis:
    match: Match
    group: str
    situation: str
    motivation: str
    favorite: str
    probs: WinProbabilities
    model: ScoreModel
    style: str
    confidence: str
    impact: str
    home_mot: Motivation
    away_mot: Motivation


def _group_matches(day: DayData, group_name: str) -> list[Match]:
    return [m for m in day.matches if m.group == group_name]


def analyze_day(day: DayData) -> list[MatchAnalysis]:
    # Pre-compute motivations per group (depends on all of the group's matches).
    motivations_by_group: dict[str, dict[str, Motivation]] = {}
    for name, group in day.groups.items():
        motivations_by_group[name] = resolve_motivations(group, _group_matches(day, name))

    results: list[MatchAnalysis] = []
    for match in day.matches:
        group = day.groups.get(match.group)
        motivations = motivations_by_group.get(match.group, {})
        home_mot = motivations.get(match.home, Motivation("—", "alive"))
        away_mot = motivations.get(match.away, Motivation("—", "alive"))

        model = build_score_model(match)
        probs = win_probabilities(match, model)

        results.append(
            MatchAnalysis(
                match=match,
                group=match.group,
                situation=(
                    situation_sentence(match, group) if group else f"{match.label}."
                ),
                motivation=motivation_for(match, motivations),
                favorite=analysis.market_favorite(match, probs),
                probs=probs,
                model=model,
                style=analysis.expected_style(match, model, probs, home_mot, away_mot),
                confidence=analysis.confidence(match, probs, home_mot, away_mot),
                impact=analysis.projected_impact(match, probs, home_mot, away_mot),
                home_mot=home_mot,
                away_mot=away_mot,
            )
        )
    return results


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _main_table(analyses: list[MatchAnalysis]) -> str:
    header = [
        "Match",
        "Group",
        "Current Situation",
        "Team Motivation",
        "Market Favorite",
        "Win Probabilities (H/D/A)",
        "Most Likely Scores",
        "Expected Style",
        "Confidence",
        "Projected Impact",
    ]
    lines = [_row(header), _row(["---"] * len(header))]
    for a in analyses:
        lines.append(
            _row(
                [
                    a.match.label,
                    a.group,
                    a.situation,
                    a.motivation,
                    a.favorite,
                    a.probs.pct_string(),
                    a.model.top_scores_string,
                    a.style,
                    a.confidence,
                    a.impact,
                ]
            )
        )
    return "\n".join(lines)


def _highest_confidence(analyses: list[MatchAnalysis]) -> str:
    ranked = [a for a in analyses if a.favorite != "Near Even"]
    conf_rank = {"High": 0, "Medium": 1, "Low": 2}
    ranked.sort(
        key=lambda a: (
            conf_rank.get(a.confidence, 3),
            -(max(a.probs.home, a.probs.away)),
        )
    )
    ranked = [a for a in ranked if a.confidence in ("High", "Medium")][:5]
    if not ranked:
        return "_No standout favorites today._"

    lines = ["| Rank | Team | Reason |", "| --- | --- | --- |"]
    for i, a in enumerate(ranked, 1):
        h_pct, _d_pct, a_pct = a.probs.as_pct()
        fav_pct = h_pct if a.favorite == a.match.home else a_pct
        fav_mot = a.home_mot if a.favorite == a.match.home else a.away_mot
        reason = f"{fav_pct}% market edge; {fav_mot.label.lower()}"
        lines.append(_row([str(i), a.favorite, reason]))
    return "\n".join(lines)


def _likely_draws(analyses: list[MatchAnalysis]) -> str:
    draws = []
    for a in analyses:
        # Draw is the single most likely outcome, or a near-even tie.
        is_modal_draw = a.probs.draw >= a.probs.home and a.probs.draw >= a.probs.away
        near_even = a.favorite == "Near Even"
        if is_modal_draw or near_even:
            draws.append(a)
    if not draws:
        return "_No matches lean toward a draw today._"

    lines = ["| Match | Reason |", "| --- | --- |"]
    for a in draws:
        if a.probs.draw >= max(a.probs.home, a.probs.away):
            reason = f"Draw most likely ({round(a.probs.draw * 100)}%)"
        else:
            reason = "Evenly matched — fine margins"
        lines.append(_row([a.match.label, reason]))
    return "\n".join(lines)


def _chaos_matches(analyses: list[MatchAnalysis]) -> str:
    chaos = []
    for a in analyses:
        statuses = {a.home_mot.status, a.away_mot.status}
        reason = None
        if "must_win" in statuses and statuses != {"must_win"}:
            reason = "One side must attack — asymmetric incentives open the game up"
        elif statuses == {"must_win"}:
            reason = "Both teams must win — wide-open shootout likely"
        elif a.favorite == "Near Even":
            reason = "Too close to call — small events swing it"
        elif a.confidence == "Low":
            reason = "Market and incentives conflict"
        if reason:
            chaos.append((a, reason))
    if not chaos:
        return "_No chaos flags today._"

    lines = ["| Match | Why |", "| --- | --- |"]
    for a, reason in chaos:
        lines.append(_row([a.match.label, reason]))
    return "\n".join(lines)


def _projected_tables(day: DayData, analyses: list[MatchAnalysis]) -> str:
    by_group: dict[str, list[tuple]] = {}
    for a in analyses:
        by_group.setdefault(a.group, []).append((a.match, a.model, a.probs))

    blocks: list[str] = []
    for group_name in sorted(by_group):
        group: Group | None = day.groups.get(group_name)
        if group is None:
            continue
        rows: list[ProjectedRow] = project_group(group, by_group[group_name])
        block = [f"#### Group {group_name}", "", "| Team | Projected Points | GD | Status |", "| --- | --- | --- | --- |"]
        for r in rows:
            gd = f"+{r.gd}" if r.gd > 0 else str(r.gd)
            block.append(_row([r.team, str(r.points), gd, r.status]))
        blocks.append("\n".join(block))
    return "\n\n".join(blocks)


def render(day: DayData) -> str:
    analyses = analyze_day(day)
    parts: list[str] = []
    parts.append(f"# Daily World Cup Intelligence — {day.date}")
    parts.append("")
    n = len(analyses)
    parts.append(
        f"_{n} match{'es' if n != 1 else ''} scheduled. "
        "Read each row in ~30 seconds: who is favored, why, what they need, "
        "expected behavior, likely scores, confidence, and qualification impact._"
    )
    parts.append("")
    parts.append("## Daily Match Intelligence Table")
    parts.append("")
    parts.append(_main_table(analyses))
    parts.append("")
    parts.append("## Highest Confidence Favorites")
    parts.append("")
    parts.append(_highest_confidence(analyses))
    parts.append("")
    parts.append("## Most Likely Draws")
    parts.append("")
    parts.append(_likely_draws(analyses))
    parts.append("")
    parts.append("## Chaos Matches")
    parts.append("")
    parts.append("_Matches where incentives may cause unusual behavior._")
    parts.append("")
    parts.append(_chaos_matches(analyses))
    parts.append("")
    parts.append("## Projected Final Group Tables")
    parts.append("")
    parts.append("_Only groups that play today._")
    parts.append("")
    parts.append(_projected_tables(day, analyses))
    parts.append("")
    return "\n".join(parts)
