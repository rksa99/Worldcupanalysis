"""Command-line entry point: generate the daily dashboard from live data.

    python -m worldcup.cli                        # today, live (ESPN + odds)
    python -m worldcup.cli --date 2026-06-25      # a specific day, live
    python -m worldcup.cli --format json          # machine-readable output
    python -m worldcup.cli --source file --file examples/synthetic-day.json
    python -m worldcup.cli --out report.md --cache

Set ODDS_API_KEY for multi-sportsbook consensus odds (The Odds API); otherwise
ESPN's embedded odds are used as a best-effort fallback.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys

from . import render, sources
from .domain import DayData
from .report import DEFAULT_SIMS, build_report
from .sources import SourceError, filesource


def _load(args) -> tuple[DayData, str]:
    """Return (day, source note)."""
    if args.source == "file" or args.file:
        if args.file:
            return filesource.load(args.file), f"file {os.path.basename(args.file)}"
        return filesource.load_for_date(args.date, args.data_dir), f"cached {args.date}.json"

    try:
        return sources.load_live(args.date), "live (ESPN + consensus odds)"
    except SourceError as exc:
        if args.source == "live":
            raise
        print(
            f"warning: live fetch failed ({exc}); falling back to cached data.",
            file=sys.stderr,
        )
        return filesource.load_for_date(args.date, args.data_dir), f"cached {args.date}.json"


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
        help="live (ESPN+odds), file, or auto (live then cached file). Default: auto.",
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
        help="After loading, write the data snapshot to data/<date>.json.",
    )
    parser.add_argument(
        "--format",
        choices=("md", "json"),
        default="md",
        help="Output format. Default: md (markdown).",
    )
    parser.add_argument(
        "--sims",
        type=int,
        default=DEFAULT_SIMS,
        help=f"Monte Carlo simulations per group (default {DEFAULT_SIMS}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed. Defaults to a value derived from the date (reproducible).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Write the dashboard to this file instead of stdout.",
    )
    args = parser.parse_args(argv)

    try:
        day, source_note = _load(args)
    except (FileNotFoundError, SourceError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.cache:
        cache_path = os.path.join(args.data_dir or filesource.DATA_DIR, f"{day.date}.json")
        filesource.save(day, cache_path)
        print(f"Cached data snapshot to {cache_path}", file=sys.stderr)

    report = build_report(day, n_sims=args.sims, seed=args.seed, source_note=source_note)
    output = render.to_json(report) if args.format == "json" else render.to_markdown(report)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(output)
        print(f"Wrote dashboard to {args.out}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
