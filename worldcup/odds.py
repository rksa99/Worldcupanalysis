"""Convert bookmaker odds into clean (vig-free) probabilities."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Odds


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
        # Distribute the rounding remainder to the largest fractional parts.
        fracs = sorted(range(3), key=lambda i: raw[i] - floors[i], reverse=True)
        for i in range(remainder):
            floors[fracs[i % 3]] += 1
        return floors[0], floors[1], floors[2]

    def pct_string(self) -> str:
        h, d, a = self.as_pct()
        return f"{h}% / {d}% / {a}%"


def implied_from_odds(odds: Odds) -> WinProbabilities:
    """De-vig decimal odds via proportional (multiplicative) normalisation."""
    inv_home = 1.0 / odds.home
    inv_draw = 1.0 / odds.draw
    inv_away = 1.0 / odds.away
    overround = inv_home + inv_draw + inv_away
    return WinProbabilities(
        home=inv_home / overround,
        draw=inv_draw / overround,
        away=inv_away / overround,
    )
