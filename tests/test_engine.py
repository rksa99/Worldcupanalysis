"""Engine tests: markets, poisson, simulate, narrative."""

import random
import unittest

from worldcup.domain import Group, Match, Odds, TeamStanding
from worldcup.markets import american_to_decimal, consensus, implied_from_odds
from worldcup.narrative import (
    ELIMINATED,
    MUST_WIN,
    QUALIFIED,
    derive_motivation,
    market_favorite,
)
from worldcup.poisson import build_match_model, calibrate_xg
from worldcup.simulate import simulate_group


def _group_a() -> Group:
    return Group(
        name="A",
        standings=[
            TeamStanding("Mexico", 2, 2, 0, 0, 5, 1),
            TeamStanding("South Korea", 2, 1, 0, 1, 3, 2),
            TeamStanding("South Africa", 2, 1, 0, 1, 2, 2),
            TeamStanding("Czechia", 2, 0, 1, 1, 1, 2),
        ],
    )


def _final_matchday_models():
    m1 = Match("South Korea", "South Africa", "A", odds=Odds(1.65, 3.70, 5.50))
    m2 = Match("Mexico", "Czechia", "A", odds=Odds(1.50, 4.00, 6.50))
    return [build_match_model(m1), build_match_model(m2)]


class MarketsTests(unittest.TestCase):
    def test_devig_sums_to_one(self):
        p = implied_from_odds(Odds(1.65, 3.70, 5.50))
        self.assertAlmostEqual(p.home + p.draw + p.away, 1.0, places=9)
        self.assertGreater(p.home, p.away)

    def test_pct_sums_to_100(self):
        h, d, a = implied_from_odds(Odds(2.40, 3.10, 3.20)).as_pct()
        self.assertEqual(h + d + a, 100)

    def test_american_to_decimal(self):
        self.assertAlmostEqual(american_to_decimal(-155), 1.6452, places=3)
        self.assertAlmostEqual(american_to_decimal(450), 5.50, places=3)

    def test_consensus_average(self):
        c = consensus([Odds(1.66, 3.70, 5.40), Odds(1.70, 3.60, 5.20)])
        self.assertAlmostEqual(c.home, 1.68, places=6)


class PoissonTests(unittest.TestCase):
    def test_calibration_matches_market(self):
        market = implied_from_odds(Odds(1.65, 3.70, 5.50))
        xh, xa = calibrate_xg(market)
        model = build_match_model(
            Match("A", "B", "X", xg_home=xh, xg_away=xa)
        )
        # Poisson outcome split should sit close to the de-vigged market.
        self.assertAlmostEqual(model.model_probs.home, market.home, delta=0.02)
        self.assertAlmostEqual(model.model_probs.draw, market.draw, delta=0.02)

    def test_market_preferred_over_model(self):
        model = build_match_model(Match("A", "B", "X", odds=Odds(1.50, 4.00, 6.50)))
        market = implied_from_odds(Odds(1.50, 4.00, 6.50))
        self.assertAlmostEqual(model.probs.home, market.home, places=9)

    def test_top_scores_and_authored_xg(self):
        model = build_match_model(Match("A", "B", "X", xg_home=2.0, xg_away=0.5))
        self.assertEqual(len(model.top_scores), 3)
        self.assertEqual(model.xg_home, 2.0)
        self.assertGreater(model.model_probs.home, model.model_probs.away)


class SimulateTests(unittest.TestCase):
    def setUp(self):
        rng = random.Random(42)
        self.outlook = simulate_group(_group_a(), _final_matchday_models(), 4000, rng)

    def test_guaranteed_qualifier_detected(self):
        # Mexico (6 pts) cannot be caught by two teams: only one of SK/SA can
        # reach 6 points (they play each other), Czechia tops out at 4.
        self.assertEqual(self.outlook.outlooks["Mexico"].p_top2, 1.0)

    def test_conditional_qualification(self):
        sa = self.outlook.outlooks["South Africa"]
        # South Africa winning guarantees 6 points and second place.
        self.assertEqual(sa.p_qual_if["win"], 1.0)
        # A draw leaves South Africa needing tie-break luck at best.
        self.assertLess(sa.p_qual_if["draw"], 0.5)

    def test_probabilities_form_distribution(self):
        for o in self.outlook.outlooks.values():
            self.assertAlmostEqual(sum(o.p_positions.values()), 1.0, places=9)

    def test_deterministic_with_seed(self):
        again = simulate_group(_group_a(), _final_matchday_models(), 4000, random.Random(42))
        self.assertEqual(
            again.outlooks["South Korea"].p_top2,
            self.outlook.outlooks["South Korea"].p_top2,
        )


class NarrativeTests(unittest.TestCase):
    def setUp(self):
        rng = random.Random(42)
        self.outlooks = simulate_group(_group_a(), _final_matchday_models(), 4000, rng).outlooks

    def test_motivation_statuses(self):
        self.assertEqual(derive_motivation(self.outlooks["Mexico"]).status, QUALIFIED)
        self.assertEqual(derive_motivation(self.outlooks["South Africa"]).status, MUST_WIN)

    def test_eliminated_or_best_third(self):
        mot = derive_motivation(self.outlooks["Czechia"])
        # Czechia can reach at most 4 points; top two is out of reach.
        self.assertIn(mot.status, (ELIMINATED, "alive"))
        self.assertNotEqual(mot.status, QUALIFIED)

    def test_authored_override_keeps_status(self):
        mot = derive_motivation(self.outlooks["South Africa"], authored="Custom label")
        self.assertEqual(mot.label, "Custom label")
        self.assertEqual(mot.status, MUST_WIN)

    def test_market_favorite_band(self):
        m = Match("A", "B", "X")
        p = implied_from_odds(Odds(2.70, 3.00, 2.80))
        self.assertEqual(market_favorite(m, p), "Near Even")


if __name__ == "__main__":
    unittest.main()
