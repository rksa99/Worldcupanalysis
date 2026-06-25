"""Command-line entry point: generate the daily dashboard.

    python -m worldcup.cli                      # today (system date)
    python -m worldcup.cli --date 2026-06-25    # a specific day
    python -m worldcup.cli --date 2026-06-25 --out report.md
    python -m worldcup.cli --file path/to/day.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys

from .data import load_day, load_day_file
from .dashboard import render


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
        "--data-dir",
        default=None,
        help="Directory of <date>.json files (defaults to repo data/).",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="Explicit path to a day JSON file (overrides --date/--data-dir).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Write the dashboard to this file instead of stdout.",
    )
    args = parser.parse_args(argv)

    try:
        day = load_day_file(args.file) if args.file else load_day(args.date, args.data_dir)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

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
