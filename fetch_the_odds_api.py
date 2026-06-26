#!/usr/bin/env python3
"""Fetch or replay Odds API payloads into enriched market context CSV rows."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from the_odds_api import (
    DEFAULT_API_BASE,
    DEFAULT_DATE_FORMAT,
    DEFAULT_MARKETS,
    DEFAULT_ODDS_FORMAT,
    DEFAULT_PREFERRED_BOOKMAKERS,
    DEFAULT_REGIONS,
    build_market_rows,
    fetch_json_payload,
    load_events_from_path,
    load_fixture_rows,
    write_market_rows_csv,
)


def _parse_csv_list(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _resolve_env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value.strip()
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture-csv", required=True, help="Template CSV with home and away columns.")
    ap.add_argument("--output-csv", required=True, help="Write the enriched CSV to this path.")
    ap.add_argument(
        "--fixture-json",
        help="Recorded Odds API JSON payload. When set, no live request is made.",
    )
    ap.add_argument(
        "--api-key",
        help="Odds API key for live requests. Defaults to ODDS_API_KEY / THE_ODDS_API_KEY / WORLD_CUP_2026_ODDS_API_KEY.",
    )
    ap.add_argument(
        "--sport-key",
        help="Odds API sport key for live requests. Defaults to ODDS_API_SPORT_KEY / WORLD_CUP_2026_ODDS_API_SPORT_KEY.",
    )
    ap.add_argument("--regions", default=DEFAULT_REGIONS)
    ap.add_argument("--markets", default=DEFAULT_MARKETS)
    ap.add_argument("--odds-format", default=DEFAULT_ODDS_FORMAT)
    ap.add_argument("--date-format", default=DEFAULT_DATE_FORMAT)
    ap.add_argument("--bookmakers", help="Comma-separated bookmaker filter for live requests.")
    ap.add_argument("--api-base", default=DEFAULT_API_BASE)
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--cache-dir", help="Optional cache directory for live requests.")
    ap.add_argument(
        "--cache-ttl-seconds",
        type=int,
        default=1800,
        help="Cache lifetime for live requests. Set to 0 to refresh every run.",
    )
    ap.add_argument(
        "--preferred-bookmakers",
        default=",".join(DEFAULT_PREFERRED_BOOKMAKERS),
        help="Comma-separated bookmaker preference order.",
    )
    args = ap.parse_args()

    fixture_rows = load_fixture_rows(args.fixture_csv)
    preferred_bookmakers = _parse_csv_list(args.preferred_bookmakers)

    if args.fixture_json:
        events = load_events_from_path(args.fixture_json)
        source_desc = f"fixture-json:{Path(args.fixture_json).name}"
    else:
        api_key = args.api_key or _resolve_env(
            "ODDS_API_KEY",
            "THE_ODDS_API_KEY",
            "WORLD_CUP_2026_ODDS_API_KEY",
        )
        sport_key = args.sport_key or _resolve_env(
            "ODDS_API_SPORT_KEY",
            "WORLD_CUP_2026_ODDS_API_SPORT_KEY",
        )
        if not api_key:
            ap.error("missing Odds API key; pass --api-key or set ODDS_API_KEY/the supported env vars")
        if not sport_key:
            ap.error("missing Odds API sport key; pass --sport-key or set ODDS_API_SPORT_KEY")
        events = fetch_json_payload(
            sport_key,
            api_key,
            regions=args.regions,
            markets=args.markets,
            odds_format=args.odds_format,
            date_format=args.date_format,
            bookmakers=args.bookmakers,
            api_base=args.api_base,
            timeout=args.timeout,
            cache_dir=args.cache_dir,
            cache_ttl_seconds=args.cache_ttl_seconds,
        )
        source_desc = f"live:{sport_key}"

    rows, report = build_market_rows(fixture_rows, events, preferred_bookmakers=preferred_bookmakers)
    write_market_rows_csv(rows, args.output_csv)

    print(
        f"Odds API enrichment complete | source={source_desc} | "
        f"matched={report['matched']}/{report['total']} | missing={report['missing']} | "
        f"output={args.output_csv}"
    )


if __name__ == "__main__":
    main()
