"""Poisson score model for a single match.

Produces a full scoreline probability matrix per match. When a match has market
odds but no authored xG, we calibrate an xG pair whose Poisson outcome split
matches the de-vigged market, so scorelines, probabilities, and simulations all
tell one consistent story.
"""

from __future__ import annotations

import bisect
import math
import random
from dataclasses import dataclass

from .domain import Match
from .markets import WinProbabilities, implied_from_odds

MAX_GOALS = 9
DEFAULT_XG = (1.3, 1.1)  # mild home edge when we know nothing at all


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def score_matrix(xg_home: float, xg_away: float) -> list[list[float]]:
    hp = [_poisson_pmf(i, xg_home) for i in range(MAX_GOALS + 1)]
    ap = [_poisson_pmf(j, xg_away) for j in range(MAX_GOALS + 1)]
    return [[hp[i] * ap[j] for j in range(MAX_GOALS + 1)] for i in range(MAX_GOALS + 1)]


def outcome_probs(matrix: list[list[float]]) -> WinProbabilities:
    home = draw = away = total = 0.0
    for i, row in enumerate(matrix):
        for j, p in enumerate(row):
            total += p
            if i > j:
                home += p
            elif i == j:
                draw += p
            else:
                away += p
    return WinProbabilities(home=home / total, draw=draw / total, away=away / total)


def top_scores(matrix: list[list[float]], n: int = 3) -> list[tuple[int, int]]:
    cells = [((i, j), matrix[i][j]) for i in range(len(matrix)) for j in range(len(matrix[i]))]
    cells.sort(key=lambda c: c[1], reverse=True)
    return [score for score, _ in cells[:n]]


def _grid_best(market: WinProbabilities, lo: float, hi: float, step: float) -> tuple[float, float]:
    best = (lo, lo)
    best_err = float("inf")
    h = lo
    while h <= hi + 1e-9:
        a = lo
        while a <= hi + 1e-9:
            p = outcome_probs(score_matrix(h, a))
            err = (
                (p.home - market.home) ** 2
                + (p.draw - market.draw) ** 2
                + (p.away - market.away) ** 2
            )
            if err < best_err:
                best_err, best = err, (h, a)
            a += step
        h += step
    return best


def calibrate_xg(market: WinProbabilities) -> tuple[float, float]:
    """Two-stage grid search: coarse over the plausible range, fine around it."""
    h, a = _grid_best(market, 0.2, 3.6, 0.2)
    lo_h, hi_h = max(0.1, h - 0.2), h + 0.2
    lo_a, hi_a = max(0.1, a - 0.2), a + 0.2
    # Fine pass restricted to the coarse winner's neighbourhood.
    best = (h, a)
    best_err = float("inf")
    x = lo_h
    while x <= hi_h + 1e-9:
        y = lo_a
        while y <= hi_a + 1e-9:
            p = outcome_probs(score_matrix(x, y))
            err = (
                (p.home - market.home) ** 2
                + (p.draw - market.draw) ** 2
                + (p.away - market.away) ** 2
            )
            if err < best_err:
                best_err, best = err, (x, y)
            y += 0.05
        x += 0.05
    return round(best[0], 2), round(best[1], 2)


class ScoreSampler:
    """Draw a (home, away) scoreline from a match's probability matrix."""

    def __init__(self, matrix: list[list[float]]):
        self._cum: list[float] = []
        self._scores: list[tuple[int, int]] = []
        c = 0.0
        for i, row in enumerate(matrix):
            for j, p in enumerate(row):
                c += p
                self._cum.append(c)
                self._scores.append((i, j))
        self._total = c

    def sample(self, rng: random.Random) -> tuple[int, int]:
        k = bisect.bisect_left(self._cum, rng.random() * self._total)
        return self._scores[min(k, len(self._scores) - 1)]


@dataclass
class MatchModel:
    """Everything the engine needs about one match, derived once."""

    match: Match
    xg_home: float
    xg_away: float
    matrix: list[list[float]]
    model_probs: WinProbabilities
    top_scores: list[tuple[int, int]]

    @property
    def top_scores_string(self) -> str:
        return ", ".join(f"{h}-{a}" for h, a in self.top_scores)

    @property
    def probs(self) -> WinProbabilities:
        """Market probabilities when odds exist, else the Poisson model's."""
        if self.match.odds is not None:
            return implied_from_odds(self.match.odds)
        return self.model_probs

    def sampler(self) -> ScoreSampler:
        return ScoreSampler(self.matrix)


def build_match_model(match: Match) -> MatchModel:
    if match.xg_home is not None and match.xg_away is not None:
        xh, xa = match.xg_home, match.xg_away
    elif match.odds is not None:
        xh, xa = calibrate_xg(implied_from_odds(match.odds))
    else:
        xh, xa = DEFAULT_XG
    matrix = score_matrix(xh, xa)
    return MatchModel(
        match=match,
        xg_home=xh,
        xg_away=xa,
        matrix=matrix,
        model_probs=outcome_probs(matrix),
        top_scores=top_scores(matrix, 3),
    )
