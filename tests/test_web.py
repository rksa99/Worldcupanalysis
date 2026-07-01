"""Web layer tests: HTML renderer and HTTP server smoke test."""

import json
import os
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from worldcup import web
from worldcup.render import to_html
from worldcup.report import build_report
from worldcup.sources import filesource

SYNTHETIC_DAY = os.path.join(os.path.dirname(__file__), "..", "examples", "synthetic-day.json")


class HtmlRenderTests(unittest.TestCase):
    def test_html_contains_sections_and_escapes(self):
        day = filesource.load(SYNTHETIC_DAY)
        report = build_report(day, n_sims=1500, seed=3)
        page = to_html(report)
        for section in (
            "Daily Match Intelligence Table",
            "Highest Confidence Favorites",
            "Most Likely Draws",
            "Chaos Matches",
            "Projected Final Group Tables",
        ):
            self.assertIn(section, page)
        self.assertIn("<table>", page)
        self.assertIn("Monte Carlo", page)
        # The em dash / non-ASCII content must survive; no raw < from data.
        self.assertNotIn("<script", page.lower())


class WebServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["WORLDCUP_SOURCE"] = "file"
        os.environ["WORLDCUP_FILE"] = SYNTHETIC_DAY
        os.environ["WORLDCUP_SIMS"] = "1500"
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        for var in ("WORLDCUP_SOURCE", "WORLDCUP_FILE", "WORLDCUP_SIMS"):
            os.environ.pop(var, None)

    def _get(self, path):
        # Bypass any configured proxy for loopback traffic.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{self.port}{path}", timeout=10) as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read().decode()

    def test_health(self):
        status, _ctype, body = self._get("/health")
        self.assertEqual((status, body), (200, "ok"))

    def test_html_dashboard(self):
        status, ctype, body = self._get("/?date=2026-06-25")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        self.assertIn("Daily World Cup Intelligence", body)

    def test_json_endpoint(self):
        status, ctype, body = self._get("/report.json?date=2026-06-25")
        self.assertEqual(status, 200)
        self.assertIn("application/json", ctype)
        data = json.loads(body)
        self.assertEqual(data["n_matches"], 6)

    def test_markdown_endpoint(self):
        status, _ctype, body = self._get("/report.md?date=2026-06-25")
        self.assertEqual(status, 200)
        self.assertIn("## Daily Match Intelligence Table", body)

    def test_bad_date_and_404(self):
        try:
            self._get("/?date=nonsense")
            self.fail("expected 400")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
        try:
            self._get("/nope")
            self.fail("expected 404")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)

    def test_cache_returns_same_report(self):
        _s, _c, first = self._get("/report.json?date=2026-06-25")
        _s, _c, second = self._get("/report.json?date=2026-06-25")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
