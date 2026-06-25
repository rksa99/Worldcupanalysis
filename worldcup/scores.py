"""Poisson scoreline model.

Given expected goals (xG) for each side, produce the most likely scorelines and
the model-implied win/draw/loss probabilities. When a match has bookmaker odds
but no authored xG, we solve for an xG pair whose Poisson outcome split matches
the market — keeping scores and probabilities consistent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .models import Match
from .odds import WinProbabilities, implied_from_odds

MAX_GOALS = 9  # goals 0..9 per side is plenty for football


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


@dataclass
class ScoreModel:
    xg_home: float
    xg_away: float
    probabilities: WinProbabilities
    top_scores: list[tuple[int, int]]

    @property
    def top_scores_string(self) -> str:
        return ", ".join(f"{h}-{a}" for h, a in self.top_scores)


def _score_matrix(xg_home: float, xg_away: float) -> list[list[float]]:
    home_pmf = [_poisson_pmf(i, xg_home) for i in range(MAX_GOALS + 1)]
    away_pmf = [_poisson_pmf(j, xg_away) for j in range(MAX_GOALS + 1)]
    return [[home_pmf[i] * away_pmf[j] for j in range(MAX_GOALS + 1)] for i in range(MAX_GOALS + 1)]


def _outcome_probs(matrix: list[list[float]]) -> WinProbabilities:
    home = draw = away = 0.0
    total = 0.0
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


def _top_scores(matrix: list[list[float]], n: int = 3) -> list[tuple[int, int]]:
    cells = [
        ((i, j), matrix[i][j])
        for i in range(len(matrix))
        for j in range(len(matrix[i]))
    ]
    cells.sort(key=lambda c: c[1], reverse=True)
    return [score for score, _ in cells[:n]]


def _xg_from_odds(market: WinProbabilities) -> tuple[float, float]:
    """Search a small grid of (home xG, away xG) for the best market match.

    Total goals in modern World Cup matches average ~2.6; we scan plausible xG
    splits and pick the pair whose Poisson outcome probabilities are closest to
    the de-vigged market.
    """
    best: tuple[float, float] | None = None
    best_err = float("inf")
    h = 0.3
    while h <= 3.5:
        a = 0.3
        while a <= 3.5:
            probs = _outcome_probs(_score_matrix(h, a))
            err = (
                (probs.home - market.home) ** 2
                + (probs.draw - market.draw) ** 2
                + (probs.away - market.away) ** 2
            )
            if err < best_err:
                best_err = err
                best = (h, a)
            a += 0.1
        h += 0.1
    assert best is not None
    return round(best[0], 2), round(best[1], 2)


def build_score_model(match: Match) -> ScoreModel:
    """Resolve xG (authored, else derived from odds, else a neutral default)."""
    if match.xg_home is not None and match.xg_away is not None:
        xg_home, xg_away = match.xg_home, match.xg_away
    elif match.odds is not None:
        xg_home, xg_away = _xg_from_odds(implied_from_odds(match.odds))
    else:
        xg_home, xg_away = 1.3, 1.1  # mild home edge as a last resort

    matrix = _score_matrix(xg_home, xg_away)
    return ScoreModel(
        xg_home=xg_home,
        xg_away=xg_away,
        probabilities=_outcome_probs(matrix),
        top_scores=_top_scores(matrix, 3),
    )


def win_probabilities(match: Match, model: ScoreModel) -> WinProbabilities:
    """Prefer the market (de-vigged) when available; else the Poisson model."""
    if match.odds is not None:
        return implied_from_odds(match.odds)
    return model.probabilities
