"""Source tests: ESPN/Odds API parsing against recorded payload shapes."""

import json
import os
import unittest

from worldcup import sources
from worldcup.sources import espn, filesource, http, oddsapi
from worldcup.sources.names import normalize_team

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
SYNTHETIC_DAY = os.path.join(os.path.dirname(__file__), "..", "examples", "synthetic-day.json")


def _fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return json.load(fh)


class NamesTests(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(normalize_team("Czech Republic"), normalize_team("Czechia"))
        self.assertEqual(normalize_team("Korea Republic"), "south korea")
        self.assertEqual(normalize_team("Türkiye"), "turkey")


class EspnTests(unittest.TestCase):
    def test_parse_standings_and_scoreboard(self):
        groups, team_group = espn.parse_standings(_fixture("espn_standings.json"))
        self.assertIn("A", groups)
        self.assertEqual(len(groups["A"].standings), 4)
        self.assertEqual(groups["A"].standing_for("Mexico").points, 6)
        self.assertEqual(team_group[normalize_team("Mexico")], "A")

        matches = espn.parse_scoreboard(_fixture("espn_scoreboard.json"), team_group)
        self.assertEqual(len(matches), 2)
        kor = next(m for m in matches if m.home == "South Korea")
        self.assertEqual(kor.group, "A")
        self.assertIsNotNone(kor.odds)  # embedded American odds -> decimal
        self.assertAlmostEqual(kor.odds.away, 5.50, places=2)


class KnockoutTests(unittest.TestCase):
    def test_cross_group_match_labelled_ko(self):
        _groups, team_group = espn.parse_standings(_fixture("espn_standings.json"))
        payload = {
            "events": [
                {
                    "date": "2026-07-01T20:00Z",
                    "competitions": [
                        {
                            "date": "2026-07-01T20:00Z",
                            "competitors": [
                                {"homeAway": "home", "team": {"displayName": "Canada"}},
                                {"homeAway": "away", "team": {"displayName": "South Korea"}},
                            ],
                            "odds": [],
                        }
                    ],
                }
            ]
        }
        matches = espn.parse_scoreboard(payload, team_group)
        self.assertEqual(matches[0].group, "KO")

    def test_empty_scoreboard_raises_no_fixtures(self):
        standings = _fixture("espn_standings.json")

        def fake_get(url, timeout=25):
            return standings if "standings" in url else {"events": []}

        original = http.get_json
        http.get_json = fake_get
        try:
            with self.assertRaises(sources.NoFixtures):
                espn.fetch_day("2026-07-06")
        finally:
            http.get_json = original


class OddsApiTests(unittest.TestCase):
    def test_overlay_with_alias(self):
        _groups, team_group = espn.parse_standings(_fixture("espn_standings.json"))
        matches = espn.parse_scoreboard(_fixture("espn_scoreboard.json"), team_group)
        # Odds API lists Czechia as "Czech Republic"; alias must reconcile.
        n = oddsapi.overlay(matches, _fixture("odds_api.json"))
        self.assertEqual(n, 2)
        mex = next(m for m in matches if m.home == "Mexico")
        self.assertAlmostEqual(mex.odds.home, 1.50, places=2)
        kor = next(m for m in matches if m.home == "South Korea")
        self.assertAlmostEqual(kor.odds.home, 1.68, places=2)  # (1.66+1.70)/2


class LiveLoadTests(unittest.TestCase):
    def test_load_live_with_mocked_http(self):
        payloads = {
            "scoreboard": _fixture("espn_scoreboard.json"),
            "standings": _fixture("espn_standings.json"),
            "the-odds-api": _fixture("odds_api.json"),
        }

        def fake_get(url, timeout=25):
            for key, payload in payloads.items():
                if key in url:
                    return payload
            raise AssertionError(url)

        original = http.get_json
        http.get_json = fake_get
        try:
            day = sources.load_live("2026-06-25", odds_api_key="TESTKEY")
        finally:
            http.get_json = original

        self.assertEqual(day.date, "2026-06-25")
        self.assertEqual(len(day.matches), 2)
        self.assertEqual(set(day.groups), {"A"})
        # Consensus odds overlaid on top of ESPN's embedded line.
        kor = next(m for m in day.matches if m.home == "South Korea")
        self.assertAlmostEqual(kor.odds.home, 1.68, places=2)


class FileSourceTests(unittest.TestCase):
    def test_load_and_roundtrip(self):
        day = filesource.load(SYNTHETIC_DAY)
        self.assertEqual(day.date, "2026-06-25")
        d = day.to_dict()
        self.assertEqual(d["date"], "2026-06-25")
        self.assertEqual(len(d["matches"]), 6)
        self.assertIn("odds", d["matches"][0])


if __name__ == "__main__":
    unittest.main()
