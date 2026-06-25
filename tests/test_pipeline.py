"""Tests for the Daily World Cup Intelligence pipeline (stdlib unittest)."""

import unittest

from worldcup.data import load_day
from worldcup.dashboard import analyze_day, render
from worldcup.incentives import resolve_motivations
from worldcup.models import DayData, Group, Match, Odds, TeamStanding
from worldcup.odds import implied_from_odds
from worldcup.scores import build_score_model

SAMPLE_DATE = "2026-06-25"


class OddsTests(unittest.TestCase):
    def test_devig_sums_to_one(self):
        probs = implied_from_odds(Odds(home=1.65, draw=3.70, away=5.50))
        self.assertAlmostEqual(probs.home + probs.draw + probs.away, 1.0, places=9)
        self.assertGreater(probs.home, probs.away)

    def test_pct_sums_to_100(self):
        probs = implied_from_odds(Odds(home=2.40, draw=3.10, away=3.20))
        h, d, a = probs.as_pct()
        self.assertEqual(h + d + a, 100)


class ScoreTests(unittest.TestCase):
    def test_top_scores_and_probs(self):
        match = Match(home="A", away="B", group="X", odds=Odds(1.50, 4.0, 6.5))
        model = build_score_model(match)
        self.assertEqual(len(model.top_scores), 3)
        # Probabilities form a valid distribution.
        p = model.probabilities
        self.assertAlmostEqual(p.home + p.draw + p.away, 1.0, places=6)

    def test_authored_xg_respected(self):
        match = Match(home="A", away="B", group="X", xg_home=2.0, xg_away=0.5)
        model = build_score_model(match)
        self.assertEqual(model.xg_home, 2.0)
        self.assertGreater(model.probabilities.home, model.probabilities.away)


class IncentiveTests(unittest.TestCase):
    def _group(self):
        return Group(
            name="A",
            standings=[
                TeamStanding("Mexico", 2, 2, 0, 0, 5, 1),
                TeamStanding("South Korea", 2, 1, 0, 1, 3, 2),
                TeamStanding("South Africa", 2, 1, 0, 1, 2, 2),
                TeamStanding("Czechia", 2, 0, 1, 1, 1, 2),
            ],
        )

    def test_final_matchday_incentives(self):
        group = self._group()
        matches = [
            Match("South Korea", "South Africa", "A"),
            Match("Mexico", "Czechia", "A"),
        ]
        m = resolve_motivations(group, matches)
        self.assertEqual(m["Mexico"].status, "qualified")
        self.assertEqual(m["South Korea"].status, "draw_enough")
        self.assertEqual(m["South Africa"].status, "must_win")


class DashboardTests(unittest.TestCase):
    def test_sample_day_renders(self):
        day = load_day(SAMPLE_DATE)
        self.assertIsInstance(day, DayData)
        analyses = analyze_day(day)
        self.assertEqual(len(analyses), 6)
        out = render(day)
        for section in (
            "Daily Match Intelligence Table",
            "Highest Confidence Favorites",
            "Most Likely Draws",
            "Chaos Matches",
            "Projected Final Group Tables",
        ):
            self.assertIn(section, out)

    def test_projection_qualifies_leaders(self):
        day = load_day(SAMPLE_DATE)
        out = render(day)
        self.assertIn("Mexico | 9", out)
        self.assertIn("Qualified (1st)", out)


if __name__ == "__main__":
    unittest.main()
