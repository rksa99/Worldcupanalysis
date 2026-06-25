"""Derived narrative columns: market favorite, expected style, confidence, impact."""

from __future__ import annotations

from .incentives import Motivation
from .models import Match
from .odds import WinProbabilities
from .scores import ScoreModel

NEAR_EVEN_BAND = 0.06  # |P(home) - P(away)| below this => "Near Even"
STRONG_FAVORITE = 0.60
DOMINANT_FAVORITE = 0.68


def market_favorite(match: Match, probs: WinProbabilities) -> str:
    if abs(probs.home - probs.away) < NEAR_EVEN_BAND:
        return "Near Even"
    return match.home if probs.home > probs.away else match.away


def expected_style(
    match: Match,
    model: ScoreModel,
    probs: WinProbabilities,
    home_mot: Motivation,
    away_mot: Motivation,
) -> str:
    total_xg = model.xg_home + model.xg_away
    fav_prob = max(probs.home, probs.away)
    statuses = {home_mot.status, away_mot.status}

    if "must_win" in statuses and ("qualified" in statuses or "eliminated" in statuses):
        return "Must-win pressure — one side has to chase, opening the game"
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

    hungry = {"must_win", "draw_enough", "alive"}

    # Conflict: market backs a side with little to play for while the
    # underdog is desperate — incentives pull against the price.
    if fav_mot.status == "qualified" and opp_mot.status == "must_win":
        return "Low"
    if fav_mot.status == "eliminated":
        return "Low"

    # Agreement: the favored side is also the motivated side, and the
    # opponent has weaker incentives.
    if fav_mot.status in hungry and opp_mot.status in {"eliminated", "qualified"}:
        return "High" if fav_prob >= STRONG_FAVORITE else "Medium"
    if fav_prob >= DOMINANT_FAVORITE and fav_mot.status != "eliminated":
        return "High"
    return "Medium"


def projected_impact(
    match: Match,
    probs: WinProbabilities,
    home_mot: Motivation,
    away_mot: Motivation,
) -> str:
    fav = market_favorite(match, probs)
    statuses = {home_mot.status, away_mot.status}

    if fav == "Near Even":
        if "must_win" in statuses:
            return "Result swings who advances."
        return "Goal difference may become decisive."

    fav_mot = home_mot if fav == match.home else away_mot
    if fav_mot.status == "qualified" and {home_mot.status, away_mot.status} == {"qualified"}:
        return f"Likely decides group winner — {fav} favored for top spot."
    if fav_mot.status in {"draw_enough", "qualified"}:
        return f"{fav} expected to advance."
    if fav_mot.status == "must_win":
        return f"{fav} must win to keep qualification hopes alive."
    return f"{fav} favored to take the points."
