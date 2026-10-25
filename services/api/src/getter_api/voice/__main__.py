"""python -m getter_api.voice measurements.json [more.json ...]: compare voice setups."""

from __future__ import annotations

import argparse
from pathlib import Path

from getter_api.voice.scorecard import Thresholds, format_table, load, summarize


def main() -> None:
    defaults = Thresholds()
    parser = argparse.ArgumentParser(description="Score voice test calls on delay and cost.")
    parser.add_argument("files", nargs="+", type=Path, help="measurement JSON, one per setup")
    parser.add_argument("--p50-ms", type=float, default=defaults.p50_ms)
    parser.add_argument("--p95-ms", type=float, default=defaults.p95_ms)
    parser.add_argument("--max-inr-per-minute", type=float, default=defaults.max_inr_per_minute)
    args = parser.parse_args()
    limits = Thresholds(
        p50_ms=args.p50_ms, p95_ms=args.p95_ms, max_inr_per_minute=args.max_inr_per_minute
    )
    print(format_table([summarize(load(f), limits) for f in args.files]))


if __name__ == "__main__":
    main()
