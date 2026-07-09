#!/usr/bin/env python3
"""Create JSON or CSV context templates for market odds and overrides."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from datetime import datetime, timezone
import sys

from competition_state import competition_state_payload, match_state_from_motivation
from match_context import context_key
from worldcup_2026_data import BATCH_SPLITS, JUNE_25_MATCHES, MATCHES_54, matches_for_batches
from worldcup_2026_data_jun26 import JUNE_26_COMPETITION_STATE, JUNE_26_MATCHES


def _base_payload(
    notes: str = "",
    odds=None,
    market_method: str = "proportional",
    competition_state=None,
    source_key: str | None = None,
) -> dict:
    return {
        "market_odds": list(odds) if odds else None,
        "market_method": market_method,
        "lineup_home": 1.0,
        "lineup_away": 1.0,
        "weather_scale": 1.0,
        "kickoff_at_utc": None,
        "weather_checked_at_utc": None,
        "weather_source": None,
        "weather_evidence_type": None,
        "weather_decision": "none",
        "market_confidence": 1.0,
        "competition_state": competition_state,
        "source_key": source_key,
        "notes": notes,
    }


def _csv_rows(matches: dict[str, dict]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for key, payload in sorted(matches.items()):
        home, away = key.split("|", 1)
        odds = payload.get("market_odds") or ()
        if len(odds) == 3:
            odds_text = "/".join(f"{value}" for value in odds)
            market_home, market_draw, market_away = odds
        else:
            odds_text = ""
            market_home = market_draw = market_away = ""
        rows.append(
            {
                "home": home,
                "away": away,
                "source_key": payload.get("source_key") or key,
                "market_odds": odds_text,
                "market_home": market_home,
                "market_draw": market_draw,
                "market_away": market_away,
                "market_method": payload.get("market_method", "proportional"),
                "lineup_home": payload.get("lineup_home", 1.0),
                "lineup_away": payload.get("lineup_away", 1.0),
                "weather_scale": payload.get("weather_scale", 1.0),
                "kickoff_at_utc": payload.get("kickoff_at_utc") or "",
                "weather_checked_at_utc": payload.get("weather_checked_at_utc") or "",
                "weather_source": payload.get("weather_source") or "",
                "weather_evidence_type": payload.get("weather_evidence_type") or "",
                "weather_decision": payload.get("weather_decision", "none"),
                "market_confidence": payload.get("market_confidence", 1.0),
                "competition_state": (
                    json.dumps(payload.get("competition_state"), ensure_ascii=False)
                    if payload.get("competition_state") is not None
                    else ""
                ),
                "notes": payload.get("notes", ""),
            }
        )
    return rows


def _write_csv(matches: dict[str, dict], handle) -> None:
    fieldnames = [
        "home",
        "away",
        "source_key",
        "market_odds",
        "market_home",
        "market_draw",
        "market_away",
        "market_method",
        "lineup_home",
        "lineup_away",
        "weather_scale",
        "kickoff_at_utc",
        "weather_checked_at_utc",
        "weather_source",
        "weather_evidence_type",
        "weather_decision",
        "market_confidence",
        "competition_state",
        "notes",
    ]
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(_csv_rows(matches))


def _add_match(
    out: dict,
    home: str,
    away: str,
    notes: str = "",
    odds=None,
    market_method: str = "proportional",
    competition_state=None,
) -> None:
    key = context_key(home, away)
    out[key] = _base_payload(
        notes=notes,
        odds=odds,
        market_method=market_method,
        competition_state=competition_state,
        source_key=key,
    )


def _from_jun25(market_method: str) -> dict:
    matches = {}
    for home, away, _, heat, mot_home, mot_away, note in JUNE_25_MATCHES:
        _add_match(
            matches,
            home,
            away,
            notes=f"{note}; heat={heat}; mot={mot_home}/{mot_away}",
            market_method=market_method,
            competition_state=competition_state_payload(
                match_state_from_motivation(mot_home, mot_away)
            ),
        )
    return matches


def _from_jun26(market_method: str) -> dict:
    matches = {}
    for home, away, _, heat, mot_home, mot_away, note in JUNE_26_MATCHES:
        _add_match(
            matches,
            home,
            away,
            notes=f"{note}; heat={heat}; mot={mot_home}/{mot_away}",
            market_method=market_method,
            competition_state=JUNE_26_COMPETITION_STATE.get(context_key(home, away)),
        )
    return matches


def _from_stryktipset(include_existing_odds: bool, market_method: str) -> dict:
    from predict_stryktipset_8 import M

    matches = {}
    for team1, team2, _, _, _, _, _, odds, note in M:
        _add_match(
            matches,
            team1,
            team2,
            notes=note,
            odds=odds if include_existing_odds else None,
            market_method=market_method,
        )
    return matches


def _from_split(split: str, market_method: str) -> dict:
    if split == "all":
        source = MATCHES_54
    else:
        source = matches_for_batches(*BATCH_SPLITS[split])
    matches = {}
    for home, away, hg, ag, _, batch in source:
        _add_match(matches, home, away, notes=f"batch={batch}; score={hg}-{ag}", market_method=market_method)
    return matches


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--source",
        choices=["jun25", "jun26", "stryktipset", "train", "validation", "locked_test", "all"],
        default="jun25",
        help="Which slate/split to create a context template for.",
    )
    ap.add_argument(
        "--include-existing-odds",
        action="store_true",
        help="For stryktipset source, include the odds already embedded in the script.",
    )
    ap.add_argument(
        "--market-method",
        choices=["proportional", "power"],
        default="proportional",
        help="Default de-margin method to write into each match context.",
    )
    ap.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Output format. json keeps the current behavior; csv emits a fillable template for import_context_csv.py.",
    )
    ap.add_argument("--output", help="Write the selected output format to this file. Defaults to stdout.")
    args = ap.parse_args()

    if args.source == "jun25":
        matches = _from_jun25(args.market_method)
    elif args.source == "jun26":
        matches = _from_jun26(args.market_method)
    elif args.source == "stryktipset":
        matches = _from_stryktipset(args.include_existing_odds, args.market_method)
    else:
        matches = _from_split(args.source, args.market_method)

    if args.format == "json":
        payload = {
            "meta": {
                "source": args.source,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "market_method": args.market_method,
            },
            "matches": matches,
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
        else:
            print(text, end="")
    else:
        if args.output:
            with Path(args.output).open("w", newline="", encoding="utf-8") as handle:
                _write_csv(matches, handle)
        else:
            _write_csv(matches, sys.stdout)


if __name__ == "__main__":
    main()
