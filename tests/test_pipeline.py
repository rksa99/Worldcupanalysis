"""Tests for the Daily World Cup Intelligence pipeline (stdlib unittest)."""

import json
import os
import unittest

from worldcup import providers
from worldcup.data import day_to_dict, load_day_file
from worldcup.dashboard import analyze_day, render
from worldcup.incentives import resolve_motivations
from worldcup.models import DayData, Group, Match, Odds, TeamStanding
from worldcup.odds import implied_from_odds
from worldcup.scores import build_score_model

HERE = os.path.dirname(__file__)
SYNTHETIC_DAY = os.path.join(HERE, "..", "examples", "synthetic-day.json")
FIXTURES = os.path.join(HERE, "fixtures")


def _fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return json.load(fh)


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
        day = load_day_file(SYNTHETIC_DAY)
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
        day = load_day_file(SYNTHETIC_DAY)
        out = render(day)
        self.assertIn("Mexico | 9", out)
        self.assertIn("Qualified (1st)", out)


class ProviderTests(unittest.TestCase):
    def test_american_to_decimal(self):
        self.assertAlmostEqual(providers.american_to_decimal(-155), 1.6452, places=3)
        self.assertAlmostEqual(providers.american_to_decimal(450), 5.50, places=3)

    def test_normalize_aliases(self):
        self.assertEqual(
            providers.normalize_team("Czech Republic"),
            providers.normalize_team("Czechia"),
        )
        self.assertEqual(providers.normalize_team("Korea Republic"), "south korea")

    def test_parse_espn_standings_and_scoreboard(self):
        groups, team_group = providers.parse_standings(_fixture("espn_standings.json"))
        self.assertIn("A", groups)
        self.assertEqual(len(groups["A"].standings), 4)
        mex = groups["A"].standing_for("Mexico")
        self.assertEqual(mex.points, 6)
        self.assertEqual(team_group[providers.normalize_team("Mexico")], "A")

        matches = providers.parse_scoreboard(_fixture("espn_scoreboard.json"), team_group)
        self.assertEqual(len(matches), 2)
        kor = next(m for m in matches if m.home == "South Korea")
        self.assertEqual(kor.group, "A")
        # ESPN embedded odds parsed into decimal.
        self.assertIsNotNone(kor.odds)
        self.assertAlmostEqual(kor.odds.away, 5.50, places=2)

    def test_consensus_odds_overlay_with_alias(self):
        groups, team_group = providers.parse_standings(_fixture("espn_standings.json"))
        matches = providers.parse_scoreboard(_fixture("espn_scoreboard.json"), team_group)
        # Mexico vs Czechia had no ESPN odds; Odds API lists it as "Czech Republic".
        n = providers.overlay_consensus_odds(matches, _fixture("odds_api.json"))
        self.assertEqual(n, 2)
        mex = next(m for m in matches if m.home == "Mexico")
        self.assertIsNotNone(mex.odds)
        self.assertAlmostEqual(mex.odds.home, 1.50, places=2)
        kor = next(m for m in matches if m.home == "South Korea")
        # Averaged across two books: (1.66 + 1.70) / 2.
        self.assertAlmostEqual(kor.odds.home, 1.68, places=2)

    def test_live_load_with_mocked_http(self):
        sb = _fixture("espn_scoreboard.json")
        st = _fixture("espn_standings.json")
        odds = _fixture("odds_api.json")

        def fake_get(url, timeout=25):
            if "scoreboard" in url:
                return sb
            if "standings" in url:
                return st
            if "the-odds-api" in url:
                return odds
            raise AssertionError(url)

        original = providers.http_get_json
        providers.http_get_json = fake_get
        try:
            day = providers.load_day_live("2026-06-25", odds_api_key="TESTKEY")
        finally:
            providers.http_get_json = original

        self.assertEqual(day.date, "2026-06-25")
        self.assertEqual(len(day.matches), 2)
        self.assertIn("A", day.groups)
        # Round-trips through the cache serializer.
        self.assertEqual(day_to_dict(day)["date"], "2026-06-25")


if __name__ == "__main__":
    unittest.main()
