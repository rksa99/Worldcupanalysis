"""Tiny stdlib web server for hosting the dashboard (e.g. on Render).

    python -m worldcup.web

Routes:
    /             HTML dashboard for today (or ?date=YYYY-MM-DD)
    /report.md    markdown version
    /report.json  machine-readable version
    /health       liveness probe

Reports are built on demand and cached in memory (WORLDCUP_CACHE_TTL seconds,
default 900) so odds refresh through the day without hammering the sources.

Environment:
    PORT                 listen port (Render sets this automatically)
    ODDS_API_KEY         The Odds API key for consensus odds (optional)
    WORLDCUP_SOURCE      auto | live | file       (default auto)
    WORLDCUP_FILE        explicit day JSON (file mode)
    WORLDCUP_DATA_DIR    directory of <date>.json fallbacks
    WORLDCUP_SIMS        Monte Carlo runs per group (default 10000)
    WORLDCUP_CACHE_TTL   report cache seconds (default 900)
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import threading
import time
import html as _html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import render, sources
from .report import DEFAULT_SIMS, DailyReport, build_report
from .sources import NoFixtures, SourceError, filesource

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_cache: dict[str, tuple[float, DailyReport]] = {}
_cache_lock = threading.Lock()


def _cache_ttl() -> float:
    return float(os.environ.get("WORLDCUP_CACHE_TTL", "900"))


def _load_day(date: str):
    """Return (DayData, source note) honouring WORLDCUP_SOURCE."""
    mode = os.environ.get("WORLDCUP_SOURCE", "auto")
    explicit = os.environ.get("WORLDCUP_FILE")
    data_dir = os.environ.get("WORLDCUP_DATA_DIR")

    if mode == "file":
        if explicit:
            return filesource.load(explicit), f"file {os.path.basename(explicit)}"
        return filesource.load_for_date(date, data_dir), f"cached {date}.json"

    try:
        return sources.load_live(date), "live (ESPN + consensus odds)"
    except NoFixtures:
        raise  # a rest day is an answer, not a reason to fall back
    except SourceError:
        if mode == "live":
            raise
        return filesource.load_for_date(date, data_dir), f"cached {date}.json"


def get_report(date: str) -> DailyReport:
    now = time.time()
    with _cache_lock:
        hit = _cache.get(date)
        if hit and now - hit[0] < _cache_ttl():
            return hit[1]

    day, note = _load_day(date)
    n_sims = int(os.environ.get("WORLDCUP_SIMS", str(DEFAULT_SIMS)))
    report = build_report(day, n_sims=n_sims, source_note=note)

    with _cache_lock:
        _cache[date] = (now, report)
    return report


class Handler(BaseHTTPRequestHandler):
    server_version = "WorldCupIntelligence/2.0"

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        url = urlparse(self.path)
        route = url.path.rstrip("/") or "/"

        if route == "/health":
            self._send(200, "text/plain; charset=utf-8", "ok")
            return

        if route not in ("/", "/report.md", "/report.json"):
            self._send(404, "text/plain; charset=utf-8", "not found")
            return

        date = parse_qs(url.query).get("date", [_dt.date.today().isoformat()])[0]
        if not _DATE_RE.match(date):
            self._send(400, "text/plain; charset=utf-8", "bad date (want YYYY-MM-DD)")
            return

        try:
            report = get_report(date)
        except NoFixtures:
            self._send_rest_day(route, date)
            return
        except (SourceError, FileNotFoundError) as exc:
            if route == "/":
                self._send(503, "text/html; charset=utf-8", _error_page(date, str(exc)))
            else:
                self._send(
                    503,
                    "text/plain; charset=utf-8",
                    f"No dashboard available for {date}: {exc}",
                )
            return

        if route == "/report.json":
            self._send(200, "application/json; charset=utf-8", render.to_json(report))
        elif route == "/report.md":
            self._send(200, "text/markdown; charset=utf-8", render.to_markdown(report))
        else:
            self._send(200, "text/html; charset=utf-8", render.to_html(report))

    def _send_rest_day(self, route: str, date: str) -> None:
        """A day with no scheduled matches is a valid, cacheable answer."""
        if route == "/report.json":
            body = json.dumps(
                {"date": date, "n_matches": 0, "message": "No matches scheduled."}
            )
            self._send(200, "application/json; charset=utf-8", body)
        elif route == "/report.md":
            self._send(
                200,
                "text/markdown; charset=utf-8",
                f"# Daily World Cup Intelligence — {date}\n\n_No matches scheduled._\n",
            )
        else:
            self._send(200, "text/html; charset=utf-8", _rest_day_page(date))

    def _send(self, status: int, content_type: str, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} - {fmt % args}")


_PAGE_CSS = (
    "body{font:16px/1.6 -apple-system,'Segoe UI',Roboto,sans-serif;"
    "margin:15vh auto;max-width:34rem;padding:0 1rem;text-align:center}"
    ".muted{color:#888;font-size:.9rem}"
)


def _rest_day_page(date: str) -> str:
    d = _html.escape(date)
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><style>{_PAGE_CSS}</style>"
        f"<title>World Cup Intelligence — {d}</title></head><body>"
        f"<h1>No matches on {d}</h1>"
        "<p>It's a rest day — no World Cup matches are scheduled.</p>"
        "<p class='muted'>Try another day: add <code>?date=YYYY-MM-DD</code> "
        "to the URL.</p></body></html>"
    )


def _error_page(date: str, detail: str) -> str:
    d = _html.escape(date)
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><style>{_PAGE_CSS}</style>"
        f"<title>World Cup Intelligence — error</title></head><body>"
        f"<h1>Dashboard unavailable for {d}</h1>"
        "<p>The live data sources could not be reached. This usually passes "
        "in a minute — please refresh.</p>"
        f"<p class='muted'>{_html.escape(detail)}</p></body></html>"
    )


def serve(port: int | None = None) -> None:
    port = port if port is not None else int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Serving World Cup Intelligence on http://0.0.0.0:{port}")
    server.serve_forever()


if __name__ == "__main__":
    serve()
