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


QF_JUL11_FIXTURES = (
    ("Norway", "England", "2026-07-11T21:00:00Z"),
    ("Argentina", "Switzerland", "2026-07-12T01:00:00Z"),
)
QF_JUL11_FIXTURE_KEYS = {
    "norway-england": context_key("Norway", "England"),
    "argentina-switzerland": context_key("Argentina", "Switzerland"),
}
SF_JUL14_15_FIXTURES = (
    ("France", "Spain", "2026-07-14T19:00:00Z"),
    ("England", "Argentina", "2026-07-15T19:00:00Z"),
)
SF_JUL14_15_FIXTURE_KEYS = {
    "france-spain": context_key("France", "Spain"),
    "england-argentina": context_key("England", "Argentina"),
}
FINALIZATION_FIXTURE_KEYS_BY_SOURCE = {
    "qf_jul11": QF_JUL11_FIXTURE_KEYS,
    "sf_jul14_15": SF_JUL14_15_FIXTURE_KEYS,
}


def _base_payload(
    notes: str = "",
    odds=None,
    market_method: str = "proportional",
    competition_state=None,
    source_key: str | None = None,
) -> dict:
    return {
        "market_odds": list(odds) if odds else None,
        "market_advance_odds": None,
        "market_method": market_method,
        "lineup_home": 1.0,
        "lineup_away": 1.0,
        "weather_scale": 1.0,
        "kickoff_at_utc": None,
        "weather_checked_at_utc": None,
        "weather_forecast_issued_at_utc": None,
        "weather_forecast_valid_at_utc": None,
        "weather_source": None,
        "weather_evidence_type": None,
        "roof_status": None,
        "weather_evidence_fixture_id": None,
        "weather_evidence_snapshot": None,
        "weather_evidence_sha256": None,
        "weather_capture_method": None,
        "weather_points_source": None,
        "weather_points_evidence_snapshot": None,
        "weather_points_evidence_sha256": None,
        "weather_forecast_generated_at_utc": None,
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
        advance_odds = payload.get("market_advance_odds") or ()
        if len(advance_odds) == 2:
            advance_odds_text = "/".join(f"{value}" for value in advance_odds)
            market_advance_home, market_advance_away = advance_odds
        else:
            advance_odds_text = ""
            market_advance_home = market_advance_away = ""
        rows.append(
            {
                "home": home,
                "away": away,
                "source_key": payload.get("source_key") or key,
                "market_odds": odds_text,
                "market_home": market_home,
                "market_draw": market_draw,
                "market_away": market_away,
                "market_advance_odds": advance_odds_text,
                "market_advance_home": market_advance_home,
                "market_advance_away": market_advance_away,
                "market_method": payload.get("market_method", "proportional"),
                "lineup_home": payload.get("lineup_home", 1.0),
                "lineup_away": payload.get("lineup_away", 1.0),
                "weather_scale": payload.get("weather_scale", 1.0),
                "kickoff_at_utc": payload.get("kickoff_at_utc") or "",
                "weather_checked_at_utc": payload.get("weather_checked_at_utc") or "",
                "weather_forecast_issued_at_utc": payload.get("weather_forecast_issued_at_utc") or "",
                "weather_forecast_valid_at_utc": payload.get("weather_forecast_valid_at_utc") or "",
                "weather_source": payload.get("weather_source") or "",
                "weather_evidence_type": payload.get("weather_evidence_type") or "",
                "roof_status": payload.get("roof_status") or "",
                "weather_evidence_fixture_id": payload.get("weather_evidence_fixture_id") or "",
                "weather_evidence_snapshot": payload.get("weather_evidence_snapshot") or "",
                "weather_evidence_sha256": payload.get("weather_evidence_sha256") or "",
                "weather_capture_method": payload.get("weather_capture_method") or "",
                "weather_points_source": payload.get("weather_points_source") or "",
                "weather_points_evidence_snapshot": (
                    payload.get("weather_points_evidence_snapshot") or ""
                ),
                "weather_points_evidence_sha256": (
                    payload.get("weather_points_evidence_sha256") or ""
                ),
                "weather_forecast_generated_at_utc": (
                    payload.get("weather_forecast_generated_at_utc") or ""
                ),
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
        "market_advance_odds",
        "market_advance_home",
        "market_advance_away",
        "market_method",
        "lineup_home",
        "lineup_away",
        "weather_scale",
        "kickoff_at_utc",
        "weather_checked_at_utc",
        "weather_forecast_issued_at_utc",
        "weather_forecast_valid_at_utc",
        "weather_source",
        "weather_evidence_type",
        "roof_status",
        "weather_evidence_fixture_id",
        "weather_evidence_snapshot",
        "weather_evidence_sha256",
        "weather_capture_method",
        "weather_points_source",
        "weather_points_evidence_snapshot",
        "weather_points_evidence_sha256",
        "weather_forecast_generated_at_utc",
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


def _from_qf_jul11(market_method: str) -> dict:
    matches = {}
    for home, away, kickoff_at_utc in QF_JUL11_FIXTURES:
        _add_match(
            matches,
            home,
            away,
            notes="QF; official weather evidence required before prediction",
            market_method=market_method,
        )
        matches[context_key(home, away)]["kickoff_at_utc"] = kickoff_at_utc
    return matches


def _from_sf_jul14_15(market_method: str) -> dict:
    matches = {}
    for home, away, kickoff_at_utc in SF_JUL14_15_FIXTURES:
        _add_match(
            matches,
            home,
            away,
            notes="SF; official roof or outdoor weather evidence required before prediction",
            market_method=market_method,
        )
        matches[context_key(home, away)]["kickoff_at_utc"] = kickoff_at_utc
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
        choices=[
            "jun25",
            "jun26",
            "qf_jul11",
            "sf_jul14_15",
            "stryktipset",
            "train",
            "validation",
            "locked_test",
            "all",
        ],
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
    ap.add_argument(
        "--fixture",
        choices=sorted(
            fixture
            for fixture_keys in FINALIZATION_FIXTURE_KEYS_BY_SOURCE.values()
            for fixture in fixture_keys
        ),
        help="For a QF/SF finalization source, emit exactly one fixture.",
    )
    ap.add_argument("--output", help="Write the selected output format to this file. Defaults to stdout.")
    args = ap.parse_args()

    if args.source == "jun25":
        matches = _from_jun25(args.market_method)
    elif args.source == "jun26":
        matches = _from_jun26(args.market_method)
    elif args.source == "qf_jul11":
        matches = _from_qf_jul11(args.market_method)
    elif args.source == "sf_jul14_15":
        matches = _from_sf_jul14_15(args.market_method)
    elif args.source == "stryktipset":
        matches = _from_stryktipset(args.include_existing_odds, args.market_method)
    else:
        matches = _from_split(args.source, args.market_method)

    if args.fixture:
        fixture_keys = FINALIZATION_FIXTURE_KEYS_BY_SOURCE.get(args.source)
        if fixture_keys is None:
            ap.error("--fixture is only valid with a QF/SF finalization source")
        if args.fixture not in fixture_keys:
            valid = ", ".join(sorted(fixture_keys))
            ap.error(f"--fixture {args.fixture!r} is not valid for {args.source}; choose: {valid}")
        key = fixture_keys[args.fixture]
        matches = {key: matches[key]}

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
