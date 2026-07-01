"""Report assembly and renderer tests."""

import json
import os
import unittest

from worldcup.render import to_json, to_markdown
from worldcup.report import build_report
from worldcup.sources import filesource

SYNTHETIC_DAY = os.path.join(os.path.dirname(__file__), "..", "examples", "synthetic-day.json")

SECTIONS = (
    "Daily Match Intelligence Table",
    "Highest Confidence Favorites",
    "Most Likely Draws",
    "Chaos Matches",
    "Projected Final Group Tables",
)


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.day = filesource.load(SYNTHETIC_DAY)
        cls.report = build_report(cls.day, n_sims=3000, seed=7)

    def test_report_shape(self):
        self.assertEqual(self.report.n_matches, 6)
        self.assertEqual(len(self.report.rows), 6)
        self.assertEqual(set(self.report.tables), {"A", "E", "F"})
        for rows in self.report.tables.values():
            self.assertEqual(len(rows), 4)

    def test_deterministic(self):
        again = build_report(self.day, n_sims=3000, seed=7)
        self.assertEqual(to_json(again), to_json(self.report))

    def test_markdown_sections(self):
        md = to_markdown(self.report)
        for section in SECTIONS:
            self.assertIn(section, md)
        self.assertIn("Monte Carlo simulations", md)

    def test_json_roundtrip(self):
        data = json.loads(to_json(self.report))
        self.assertEqual(data["date"], "2026-06-25")
        self.assertEqual(len(data["rows"]), 6)
        self.assertIn("A", data["tables"])
        # Probabilities are exposed as raw numbers for machine consumers.
        row = data["rows"][0]
        self.assertAlmostEqual(
            row["prob_home"] + row["prob_draw"] + row["prob_away"], 1.0, places=2
        )

    def test_guaranteed_qualifier_in_table(self):
        table_a = self.report.tables["A"]
        mexico = next(r for r in table_a if r.team == "Mexico")
        self.assertEqual(mexico.status, "Qualified")
        self.assertEqual(mexico.p_top2, 1.0)

    def test_impact_cites_simulation(self):
        row = next(r for r in self.report.rows if "South Korea" in r.match)
        self.assertIn("simulations", row.impact)


if __name__ == "__main__":
    unittest.main()
