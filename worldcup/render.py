"""Renderers: DailyReport -> markdown, JSON, or HTML.

Renderers are pure functions of the report; they never touch the engine.
"""

from __future__ import annotations

import dataclasses
import html
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


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #

_CSS = """
:root { color-scheme: light dark; }
body { font: 15px/1.5 -apple-system, "Segoe UI", Roboto, sans-serif;
       margin: 2rem auto; max-width: 1200px; padding: 0 1rem; }
h1 { font-size: 1.5rem; } h2 { font-size: 1.15rem; margin-top: 2rem; }
h3 { font-size: 1rem; margin-top: 1.2rem; }
table { border-collapse: collapse; width: 100%; margin: .6rem 0; }
th, td { border: 1px solid #8884; padding: .35rem .55rem; text-align: left;
         vertical-align: top; }
th { background: #8881; }
.conf-High { color: #1a7f37; font-weight: 600; }
.conf-Medium { color: #9a6700; font-weight: 600; }
.conf-Low { color: #cf222e; font-weight: 600; }
.muted { color: #888; font-size: .85rem; }
nav a { margin-right: 1rem; }
"""


def _h(text: str) -> str:
    return html.escape(text, quote=True)


def _html_table(header: list[str], body: list[list[str]], classes: list[str] | None = None) -> str:
    out = ["<table>", "<tr>" + "".join(f"<th>{_h(c)}</th>" for c in header) + "</tr>"]
    for i, cells in enumerate(body):
        row_cls = f' class="{classes[i]}"' if classes and classes[i] else ""
        out.append(
            f"<tr{row_cls}>" + "".join(f"<td>{_h(c)}</td>" for c in cells) + "</tr>"
        )
    out.append("</table>")
    return "\n".join(out)


def to_html(report: DailyReport) -> str:
    n = report.n_matches
    parts: list[str] = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>World Cup Intelligence — {_h(report.date)}</title>",
        f"<style>{_CSS}</style></head><body>",
        f"<h1>Daily World Cup Intelligence — {_h(report.date)}</h1>",
        '<nav class="muted"><a href="report.md">markdown</a>'
        '<a href="report.json">json</a></nav>',
        f"<p><em>{n} match{'es' if n != 1 else ''} scheduled. Read each row in "
        "~30 seconds: who is favored, why, what they need, expected behavior, "
        "likely scores, confidence, and qualification impact.</em></p>",
        "<h2>Daily Match Intelligence Table</h2>",
    ]

    match_header = [
        "Match", "Group", "Current Situation", "Team Motivation",
        "Market Favorite", "Win Prob. (H/D/A)", "Most Likely Scores",
        "Expected Style", "Confidence", "Projected Impact",
    ]
    match_rows = []
    for r in report.rows:
        match_rows.append([
            r.match, r.group, r.situation, r.motivation, r.favorite,
            r.probs_pct, r.likely_scores, r.style, r.confidence, r.impact,
        ])
    # Colour the confidence cell per row.
    table_html = _html_table(match_header, match_rows)
    for level in ("High", "Medium", "Low"):
        table_html = table_html.replace(
            f"<td>{level}</td>", f'<td class="conf-{level}">{level}</td>'
        )
    parts.append(table_html)

    parts.append("<h2>Highest Confidence Favorites</h2>")
    if report.favorites:
        parts.append(_html_table(
            ["Rank", "Team", "Reason"],
            [[str(f.rank), f.team, f.reason] for f in report.favorites],
        ))
    else:
        parts.append('<p class="muted">No standout favorites today.</p>')

    parts.append("<h2>Most Likely Draws</h2>")
    if report.draws:
        parts.append(_html_table(
            ["Match", "Reason"], [[d.match, d.reason] for d in report.draws]
        ))
    else:
        parts.append('<p class="muted">No matches lean toward a draw today.</p>')

    parts.append("<h2>Chaos Matches</h2>")
    parts.append('<p class="muted">Matches where incentives may cause unusual behavior.</p>')
    if report.chaos:
        parts.append(_html_table(
            ["Match", "Why"], [[c.match, c.why] for c in report.chaos]
        ))
    else:
        parts.append('<p class="muted">No chaos flags today.</p>')

    parts.append("<h2>Projected Final Group Tables</h2>")
    parts.append('<p class="muted">Only groups that play today. Points and goal '
                 "difference are simulation averages; Top-2 is the qualification "
                 "probability.</p>")
    for group_name, rows in report.tables.items():
        parts.append(f"<h3>Group {_h(group_name)}</h3>")
        parts.append(_html_table(
            ["Team", "Proj. Points", "Proj. GD", "Top-2", "Status"],
            [
                [r.team, f"{r.exp_points:g}", _signed(r.exp_gd),
                 f"{round(r.p_top2 * 100)}%", r.status]
                for r in rows
            ],
        ))

    meta = f"Model: {report.n_sims:,} Monte Carlo simulations (seed {report.seed})"
    if report.source_note:
        meta += f"; data: {report.source_note}"
    parts.append(f'<p class="muted">{_h(meta)}.</p>')
    parts.append("</body></html>")
    return "\n".join(parts)
