"""Command-line entry point: generate the daily dashboard from live data.

    python -m worldcup.cli                       # today, live (ESPN + odds)
    python -m worldcup.cli --date 2026-06-25     # a specific day, live
    python -m worldcup.cli --source file --file examples/synthetic-day.json
    python -m worldcup.cli --out report.md --cache   # write report + cache data

Live structure (fixtures/results/standings) comes from ESPN's public API.
Set ODDS_API_KEY to pull multi-sportsbook consensus odds from The Odds API;
otherwise ESPN's embedded odds are used as a best-effort fallback.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys

from .data import load_day, load_day_file, save_day, DATA_DIR
from .dashboard import render
from .models import DayData
from .providers import ProviderError, load_day_live


def _load(args) -> DayData:
    if args.source == "file" or args.file:
        return load_day_file(args.file) if args.file else load_day(args.date, args.data_dir)

    # live or auto
    try:
        return load_day_live(args.date)
    except ProviderError as exc:
        if args.source == "live":
            raise
        # auto: fall back to a cached/local file for the date.
        print(
            f"warning: live fetch failed ({exc}); falling back to cached data.",
            file=sys.stderr,
        )
        return load_day(args.date, args.data_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="worldcup",
        description="Generate the Daily World Cup Intelligence dashboard.",
    )
    parser.add_argument(
        "--date",
        default=_dt.date.today().isoformat(),
        help="Match day (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--source",
        choices=("live", "auto", "file"),
        default="auto",
        help="Where to get data: live (ESPN+odds), file, or auto (live then "
        "cached file). Default: auto.",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Directory of <date>.json files for file/fallback mode.",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="Explicit path to a day JSON file (implies --source file).",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help="After a live fetch, write the data to data/<date>.json.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Write the dashboard to this file instead of stdout.",
    )
    args = parser.parse_args(argv)

    try:
        day = _load(args)
    except (FileNotFoundError, ProviderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.cache:
        cache_path = os.path.join(args.data_dir or DATA_DIR, f"{day.date}.json")
        save_day(day, cache_path)
        print(f"Cached live data to {cache_path}", file=sys.stderr)

    output = render(day)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(output)
        print(f"Wrote dashboard to {args.out}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
