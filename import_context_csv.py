#!/usr/bin/env python3
"""Import market context rows from CSV into the shared JSON schema.

Optionally merge into an existing JSON context file without overwriting
non-empty fields that the CSV does not provide.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import subprocess

from competition_state import coerce_match_state, competition_state_payload
from match_context import coerce_context_payload, context_key, context_payload


def _first_non_empty(row: dict[str, str], keys: list[str]) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is not None:
            value = value.strip()
            if value:
                return value
    return None


def _parse_market_method(raw: str | None) -> str | None:
    if raw is None:
        return None
    method = raw.strip().lower().replace("-", "_")
    if method in {"prop", "proportional"}:
        return "proportional"
    if method in {"power", "power_method"}:
        return "power"
    raise ValueError("market_method must be proportional or power")


def _parse_odds(row: dict[str, str]) -> list[float] | None:
    raw = _first_non_empty(row, ["market_odds", "odds", "closing_odds"])
    if raw is not None:
        parts = [part.strip() for part in raw.replace("|", "/").split("/") if part.strip()]
        if len(parts) != 3:
            raise ValueError("market_odds must contain 3 values")
        return [float(part) for part in parts]

    home = _first_non_empty(row, ["market_home", "odds_home", "home_odds"])
    draw = _first_non_empty(row, ["market_draw", "odds_draw", "draw_odds"])
    away = _first_non_empty(row, ["market_away", "odds_away", "away_odds"])
    if home is None and draw is None and away is None:
        return None
    if home is None or draw is None or away is None:
        raise ValueError("all three odds columns are required when using split odds fields")
    return [float(home), float(draw), float(away)]


def _parse_advance_odds(row: dict[str, str]) -> list[float] | None:
    raw = _first_non_empty(row, ["market_advance_odds", "advance_odds"])
    if raw is not None:
        parts = [part.strip() for part in raw.replace("|", "/").split("/") if part.strip()]
        if len(parts) != 2:
            raise ValueError("market_advance_odds must contain 2 values")
        return [float(part) for part in parts]

    home = _first_non_empty(
        row,
        ["market_advance_home", "advance_home_odds", "odds_advance_home"],
    )
    away = _first_non_empty(
        row,
        ["market_advance_away", "advance_away_odds", "odds_advance_away"],
    )
    if home is None and away is None:
        return None
    if home is None or away is None:
        raise ValueError("both advancement odds columns are required when using split fields")
    return [float(home), float(away)]


def _parse_key(row: dict[str, str], source_label: str) -> tuple[str, str]:
    raw_key = _first_non_empty(row, ["match", "fixture", "key", "context_key"])
    if raw_key is not None:
        if "|" in raw_key:
            home, away = raw_key.split("|", 1)
            return context_key(home.strip(), away.strip()), raw_key.strip()
        if " vs " in raw_key:
            home, away = raw_key.split(" vs ", 1)
            return context_key(home.strip(), away.strip()), raw_key.strip()
        if " - " in raw_key:
            home, away = raw_key.split(" - ", 1)
            return context_key(home.strip(), away.strip()), raw_key.strip()
        raise ValueError(f"{source_label}: unable to parse match key {raw_key!r}")

    home_raw = _first_non_empty(row, ["home", "team1", "side1"])
    away_raw = _first_non_empty(row, ["away", "team2", "side2"])
    if home_raw and away_raw:
        return context_key(home_raw, away_raw), f"{home_raw.strip()}|{away_raw.strip()}"
    raise ValueError(f"{source_label}: missing home/away columns")


def _parse_optional_float(row: dict[str, str], keys: list[str], field: str) -> float | None:
    raw = _first_non_empty(row, keys)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{field} must be numeric: {raw!r}") from exc


def _parse_weather_evidence_type(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip().lower().replace("-", "_")
    allowed = {"point_forecast", "hourly", "radar", "official_roof", "manual"}
    if value not in allowed:
        raise ValueError(f"weather_evidence_type must be one of: {', '.join(sorted(allowed))}")
    return value


def _parse_weather_decision(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip().lower().replace("-", "_")
    allowed = {
        "none",
        "heat_mild",
        "heat_moderate",
        "heat_severe",
        "rain_watch",
        "rain_applied",
        "indoor_no_weather",
    }
    if value not in allowed:
        raise ValueError(f"weather_decision must be one of: {', '.join(sorted(allowed))}")
    return value


def _parse_roof_status(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip().lower().replace("-", "_")
    if value not in {"closed", "open"}:
        raise ValueError("roof_status must be closed or open")
    return value


def _parse_weather_capture_method(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip().lower().replace("-", "_")
    allowed = {"direct_http_response_body", "workspace_web_fetch"}
    if value not in allowed:
        raise ValueError(
            f"weather_capture_method must be one of: {', '.join(sorted(allowed))}"
        )
    return value


def _parse_competition_state(row: dict[str, str]) -> dict | None:
    raw = _first_non_empty(row, ["competition_state"])
    if raw is None:
        return None
    return competition_state_payload(coerce_match_state(raw))


def _parse_row(row: dict[str, str], source_label: str) -> tuple[str, dict, str]:
    key, source_key = _parse_key(row, source_label)
    payload: dict[str, object] = {}
    odds = _parse_odds(row)
    if odds is not None:
        payload["market_odds"] = odds
    advance_odds = _parse_advance_odds(row)
    if advance_odds is not None:
        payload["market_advance_odds"] = advance_odds
    market_method = _parse_market_method(_first_non_empty(row, ["market_method", "demargin"]))
    if market_method is not None:
        payload["market_method"] = market_method
    lineup_home = _parse_optional_float(row, ["lineup_home"], "lineup_home")
    if lineup_home is not None:
        payload["lineup_home"] = lineup_home
    lineup_away = _parse_optional_float(row, ["lineup_away"], "lineup_away")
    if lineup_away is not None:
        payload["lineup_away"] = lineup_away
    weather_scale = _parse_optional_float(row, ["weather_scale"], "weather_scale")
    if weather_scale is not None:
        payload["weather_scale"] = weather_scale
    kickoff_at_utc = _first_non_empty(row, ["kickoff_at_utc", "kickoff_utc"])
    if kickoff_at_utc is not None:
        payload["kickoff_at_utc"] = kickoff_at_utc
    weather_checked_at_utc = _first_non_empty(row, ["weather_checked_at_utc", "weather_checked_utc"])
    if weather_checked_at_utc is not None:
        payload["weather_checked_at_utc"] = weather_checked_at_utc
    weather_forecast_issued_at_utc = _first_non_empty(
        row,
        ["weather_forecast_issued_at_utc", "weather_forecast_issued_utc"],
    )
    if weather_forecast_issued_at_utc is not None:
        payload["weather_forecast_issued_at_utc"] = weather_forecast_issued_at_utc
    weather_forecast_valid_at_utc = _first_non_empty(
        row,
        ["weather_forecast_valid_at_utc", "weather_forecast_valid_utc"],
    )
    if weather_forecast_valid_at_utc is not None:
        payload["weather_forecast_valid_at_utc"] = weather_forecast_valid_at_utc
    weather_source = _first_non_empty(row, ["weather_source", "weather_url"])
    if weather_source is not None:
        payload["weather_source"] = weather_source
    weather_evidence_type = _parse_weather_evidence_type(_first_non_empty(row, ["weather_evidence_type"]))
    if weather_evidence_type is not None:
        payload["weather_evidence_type"] = weather_evidence_type
    roof_status = _parse_roof_status(_first_non_empty(row, ["roof_status"]))
    if roof_status is not None:
        payload["roof_status"] = roof_status
    weather_evidence_fixture_id = _first_non_empty(
        row,
        ["weather_evidence_fixture_id", "roof_evidence_fixture_id"],
    )
    if weather_evidence_fixture_id is not None:
        payload["weather_evidence_fixture_id"] = weather_evidence_fixture_id
    weather_evidence_snapshot = row.get("weather_evidence_snapshot")
    if weather_evidence_snapshot is not None and weather_evidence_snapshot.strip():
        payload["weather_evidence_snapshot"] = weather_evidence_snapshot
    weather_evidence_sha256 = _first_non_empty(row, ["weather_evidence_sha256"])
    if weather_evidence_sha256 is not None:
        payload["weather_evidence_sha256"] = weather_evidence_sha256
    weather_capture_method = _parse_weather_capture_method(
        _first_non_empty(row, ["weather_capture_method"])
    )
    if weather_capture_method is not None:
        payload["weather_capture_method"] = weather_capture_method
    weather_points_source = _first_non_empty(row, ["weather_points_source"])
    if weather_points_source is not None:
        payload["weather_points_source"] = weather_points_source
    weather_points_evidence_snapshot = row.get("weather_points_evidence_snapshot")
    if (
        weather_points_evidence_snapshot is not None
        and weather_points_evidence_snapshot.strip()
    ):
        payload["weather_points_evidence_snapshot"] = weather_points_evidence_snapshot
    weather_points_evidence_sha256 = _first_non_empty(
        row,
        ["weather_points_evidence_sha256"],
    )
    if weather_points_evidence_sha256 is not None:
        payload["weather_points_evidence_sha256"] = weather_points_evidence_sha256
    weather_forecast_generated_at_utc = _first_non_empty(
        row,
        ["weather_forecast_generated_at_utc", "weather_forecast_generated_utc"],
    )
    if weather_forecast_generated_at_utc is not None:
        payload["weather_forecast_generated_at_utc"] = weather_forecast_generated_at_utc
    weather_decision = _parse_weather_decision(_first_non_empty(row, ["weather_decision"]))
    if weather_decision is not None:
        payload["weather_decision"] = weather_decision
    market_confidence = _parse_optional_float(row, ["market_confidence", "confidence"], "market_confidence")
    if market_confidence is not None:
        payload["market_confidence"] = market_confidence
    competition_state = _parse_competition_state(row)
    if competition_state is not None:
        payload["competition_state"] = competition_state
    explicit_source_key = _first_non_empty(row, ["source_key"])
    if explicit_source_key is not None:
        payload["source_key"] = explicit_source_key
    notes = _first_non_empty(row, ["notes", "comment", "remark"])
    if notes is not None:
        payload["notes"] = notes
    return key, payload, source_key


def _load_existing_contexts(path: Path) -> tuple[dict, dict[str, dict]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    meta: dict = {}
    if isinstance(raw, dict) and "matches" in raw and isinstance(raw["matches"], dict):
        raw_meta = raw.get("meta")
        if isinstance(raw_meta, dict):
            meta = raw_meta
        raw = raw["matches"]
    if not isinstance(raw, dict):
        raise ValueError("base JSON must be a JSON object or {matches: {...}}")

    contexts: dict[str, dict] = {}
    for raw_key, payload in raw.items():
        key, _ = _parse_key({"match": str(raw_key)}, f"base file {path.name}")
        contexts[key] = context_payload(coerce_context_payload(payload))
    return meta, contexts


def _merge_payload(base: dict, update: dict) -> dict:
    merged = dict(base)
    for key, value in update.items():
        if value is not None:
            merged[key] = value
    return merged


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="CSV file with market context rows.")
    ap.add_argument(
        "--base-json",
        help="Optional existing JSON context file to merge into. Existing non-empty fields are preserved unless the CSV provides a value.",
    )
    ap.add_argument("--output", help="Write JSON to this file. Defaults to stdout.")
    ap.add_argument(
        "--source-label",
        help="Label stored in meta.source; defaults to the input filename.",
    )
    ap.add_argument(
        "--validate",
        action="store_true",
        help="Run validate_context.py on the generated JSON after writing it.",
    )
    ap.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Pass --fail-on-warning to the validator when --validate is set.",
    )
    args = ap.parse_args()

    input_path = Path(args.input)
    source_label = args.source_label or input_path.name
    with input_path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    base_meta: dict = {}
    base_contexts: dict[str, dict] = {}
    if args.base_json:
        try:
            base_meta, base_contexts = _load_existing_contexts(Path(args.base_json))
        except Exception as exc:
            raise SystemExit(f"failed to load base JSON: {exc}") from exc

    matches: dict[str, dict] = {}
    duplicates: list[str] = []
    for idx, row in enumerate(rows, 2):
        try:
            key, payload, default_source_key = _parse_row(row, f"row {idx}")
        except Exception as exc:
            raise SystemExit(str(exc)) from exc
        if key in matches:
            duplicates.append(key)
        if key in base_contexts:
            merged = _merge_payload(base_contexts[key], payload)
        else:
            merged = dict(payload)
            if "source_key" not in merged:
                merged["source_key"] = default_source_key
        matches[key] = context_payload(coerce_context_payload(merged))

    payload = {
        "meta": {
            "source": source_label,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "input_file": str(input_path),
            "format": "csv-import",
        },
        "matches": matches,
    }
    if args.base_json:
        payload["meta"]["merged_from"] = str(Path(args.base_json))
        if base_meta:
            payload["meta"]["base_meta"] = base_meta
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        output_path = Path(args.output)
    else:
        print(text, end="")
        output_path = None

    if duplicates:
        print(f"Warning: duplicate match keys overwritten: {', '.join(sorted(set(duplicates)))}", file=sys.stderr)

    if args.validate:
        if output_path is None:
            raise SystemExit("--validate requires --output")
        cmd = [sys.executable, "validate_context.py", "--context-file", str(output_path)]
        if args.fail_on_warning:
            cmd.append("--fail-on-warning")
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
