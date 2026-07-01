"""Renderers: DailyReport -> markdown or JSON.

Renderers are pure functions of the report; they never touch the engine.
"""

from __future__ import annotations

import dataclasses
import json

from .report import DailyReport


def to_json(report: DailyReport) -> str:
    return json.dumps(dataclasses.asdict(report), indent=2, ensure_ascii=False)


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _table(header: list[str], body: list[list[str]]) -> str:
    lines = [_row(header), _row(["---"] * len(header))]
    lines.extend(_row(cells) for cells in body)
    return "\n".join(lines)


def _signed(x: float) -> str:
    return f"+{x:g}" if x > 0 else f"{x:g}"


def to_markdown(report: DailyReport) -> str:
    parts: list[str] = []
    parts.append(f"# Daily World Cup Intelligence — {report.date}")
    parts.append("")
    n = report.n_matches
    parts.append(
        f"_{n} match{'es' if n != 1 else ''} scheduled. "
        "Read each row in ~30 seconds: who is favored, why, what they need, "
        "expected behavior, likely scores, confidence, and qualification impact._"
    )

    parts.append("")
    parts.append("## Daily Match Intelligence Table")
    parts.append("")
    parts.append(
        _table(
            [
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
            ],
            [
                [
                    r.match,
                    r.group,
                    r.situation,
                    r.motivation,
                    r.favorite,
                    r.probs_pct,
                    r.likely_scores,
                    r.style,
                    r.confidence,
                    r.impact,
                ]
                for r in report.rows
            ],
        )
    )

    parts.append("")
    parts.append("## Highest Confidence Favorites")
    parts.append("")
    if report.favorites:
        parts.append(
            _table(
                ["Rank", "Team", "Reason"],
                [[str(f.rank), f.team, f.reason] for f in report.favorites],
            )
        )
    else:
        parts.append("_No standout favorites today._")

    parts.append("")
    parts.append("## Most Likely Draws")
    parts.append("")
    if report.draws:
        parts.append(
            _table(["Match", "Reason"], [[d.match, d.reason] for d in report.draws])
        )
    else:
        parts.append("_No matches lean toward a draw today._")

    parts.append("")
    parts.append("## Chaos Matches")
    parts.append("")
    parts.append("_Matches where incentives may cause unusual behavior._")
    parts.append("")
    if report.chaos:
        parts.append(
            _table(["Match", "Why"], [[c.match, c.why] for c in report.chaos])
        )
    else:
        parts.append("_No chaos flags today._")

    parts.append("")
    parts.append("## Projected Final Group Tables")
    parts.append("")
    parts.append("_Only groups that play today. Points and goal difference are "
                 "simulation averages; Top-2 is the qualification probability._")
    for group_name, rows in report.tables.items():
        parts.append("")
        parts.append(f"#### Group {group_name}")
        parts.append("")
        parts.append(
            _table(
                ["Team", "Proj. Points", "Proj. GD", "Top-2", "Status"],
                [
                    [
                        r.team,
                        f"{r.exp_points:g}",
                        _signed(r.exp_gd),
                        f"{round(r.p_top2 * 100)}%",
                        r.status,
                    ]
                    for r in rows
                ],
            )
        )

    parts.append("")
    meta = f"_Model: {report.n_sims:,} Monte Carlo simulations (seed {report.seed})"
    if report.source_note:
        meta += f"; data: {report.source_note}"
    meta += "._"
    parts.append(meta)
    parts.append("")
    return "\n".join(parts)
