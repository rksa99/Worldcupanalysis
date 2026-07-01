"""Monte Carlo group simulator — the single engine behind the dashboard.

For each group playing today we simulate the remaining fixtures thousands of
times, sampling actual scorelines from each match's Poisson matrix. One pass
yields, per team:

- qualification probability (top-two finish), with goal difference simulated
  properly rather than frozen,
- the full finishing-position distribution,
- expected points and expected goal difference,
- conditional qualification probabilities given the team's own result today
  (P(top two | win / draw / loss)) — the basis for motivation labels.

Tie-breaks: points, goal difference, goals for, then random (a stand-in for
FIFA's later criteria — head-to-head record and fair play are not modelled).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .domain import Group
from .poisson import MatchModel

ADVANCE_SLOTS = 2
RESULTS = ("win", "draw", "loss")
_INVERSE = {"win": "loss", "draw": "draw", "loss": "win"}


@dataclass
class TeamOutlook:
    """Simulation summary for one team."""

    team: str
    exp_points: float
    exp_gd: float
    p_positions: dict[int, float]  # finishing position (1-4) -> probability
    p_top2: float
    # P(top-two | own result today); None when the team does not play today or
    # a result never occurred in the sample.
    p_qual_if: Optional[dict[str, Optional[float]]] = None

    @property
    def p_win_group(self) -> float:
        return self.p_positions.get(1, 0.0)


@dataclass
class GroupOutlook:
    group: str
    n_sims: int
    outlooks: dict[str, TeamOutlook] = field(default_factory=dict)

    def table_order(self) -> list[TeamOutlook]:
        """Teams ordered as the projected final table."""
        return sorted(
            self.outlooks.values(),
            key=lambda o: (o.exp_points, o.p_top2, o.exp_gd),
            reverse=True,
        )


def simulate_group(
    group: Group,
    models: list[MatchModel],
    n_sims: int,
    rng: random.Random,
) -> GroupOutlook:
    teams = group.teams
    base = {s.team: (s.points, s.gf, s.ga) for s in group.standings}

    # Only simulate fixtures whose teams both belong to this group.
    fixtures = [m for m in models if m.match.home in base and m.match.away in base]
    samplers = [m.sampler() for m in fixtures]
    playing = {m.match.home for m in fixtures} | {m.match.away for m in fixtures}

    pos_counts = {t: [0, 0, 0, 0, 0] for t in teams}  # index by rank 1..4
    pts_sum = {t: 0.0 for t in teams}
    gd_sum = {t: 0.0 for t in teams}
    res_count = {t: {r: 0 for r in RESULTS} for t in playing}
    res_top2 = {t: {r: 0 for r in RESULTS} for t in playing}

    for _ in range(n_sims):
        pts = {t: base[t][0] for t in teams}
        gf = {t: base[t][1] for t in teams}
        ga = {t: base[t][2] for t in teams}
        result: dict[str, str] = {}

        for model, sampler in zip(fixtures, samplers):
            h, a = sampler.sample(rng)
            home, away = model.match.home, model.match.away
            gf[home] += h
            ga[home] += a
            gf[away] += a
            ga[away] += h
            if h > a:
                pts[home] += 3
                result[home], result[away] = "win", "loss"
            elif h < a:
                pts[away] += 3
                result[home], result[away] = "loss", "win"
            else:
                pts[home] += 1
                pts[away] += 1
                result[home] = result[away] = "draw"

        order = sorted(
            teams,
            key=lambda t: (pts[t], gf[t] - ga[t], gf[t], rng.random()),
            reverse=True,
        )
        rank = {t: i + 1 for i, t in enumerate(order)}
        for t in teams:
            pos_counts[t][rank[t]] += 1
            pts_sum[t] += pts[t]
            gd_sum[t] += gf[t] - ga[t]
        for t, res in result.items():
            res_count[t][res] += 1
            if rank[t] <= ADVANCE_SLOTS:
                res_top2[t][res] += 1

    outlooks: dict[str, TeamOutlook] = {}
    for t in teams:
        p_positions = {r: pos_counts[t][r] / n_sims for r in range(1, 5)}
        p_qual_if = None
        if t in playing:
            p_qual_if = {
                r: (res_top2[t][r] / res_count[t][r] if res_count[t][r] else None)
                for r in RESULTS
            }
        outlooks[t] = TeamOutlook(
            team=t,
            exp_points=pts_sum[t] / n_sims,
            exp_gd=gd_sum[t] / n_sims,
            p_positions=p_positions,
            p_top2=p_positions[1] + p_positions[2],
            p_qual_if=p_qual_if,
        )
    return GroupOutlook(group=group.name, n_sims=n_sims, outlooks=outlooks)
