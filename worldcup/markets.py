"""Betting-market math: de-vig, odds-format conversion, consensus averaging."""

from __future__ import annotations

from dataclasses import dataclass

from .domain import Odds


@dataclass
class WinProbabilities:
    """Fair (overround-removed) 1X2 probabilities."""

    home: float
    draw: float
    away: float

    def as_pct(self) -> tuple[int, int, int]:
        """Rounded percentages that always sum to 100."""
        raw = [self.home * 100, self.draw * 100, self.away * 100]
        floors = [int(x) for x in raw]
        remainder = 100 - sum(floors)
        fracs = sorted(range(3), key=lambda i: raw[i] - floors[i], reverse=True)
        for i in range(remainder):
            floors[fracs[i % 3]] += 1
        return floors[0], floors[1], floors[2]

    def pct_string(self) -> str:
        h, d, a = self.as_pct()
        return f"{h}% / {d}% / {a}%"


def implied_from_odds(odds: Odds) -> WinProbabilities:
    """De-vig decimal odds via proportional (multiplicative) normalisation."""
    inv = (1.0 / odds.home, 1.0 / odds.draw, 1.0 / odds.away)
    overround = sum(inv)
    return WinProbabilities(home=inv[0] / overround, draw=inv[1] / overround, away=inv[2] / overround)


def american_to_decimal(ml: float) -> float:
    if ml > 0:
        return 1.0 + ml / 100.0
    return 1.0 + 100.0 / abs(ml)


def consensus(prices: list[Odds]) -> Odds:
    """Average decimal prices across books into one consensus line."""
    n = len(prices)
    if n == 0:
        raise ValueError("consensus() needs at least one price")
    return Odds(
        home=sum(p.home for p in prices) / n,
        draw=sum(p.draw for p in prices) / n,
        away=sum(p.away for p in prices) / n,
    )
