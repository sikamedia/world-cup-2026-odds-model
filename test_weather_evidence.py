#!/usr/bin/env python3
"""Regression checks for weather-evidence context governance."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from match_context import MatchContext, validate_weather_context
from model_stability import STABLE_V35, predict_match


ROOT = Path(__file__).resolve().parent


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def _digest(snapshot: str) -> str:
    return hashlib.sha256(snapshot.encode("utf-8")).hexdigest()


def _outdoor_payload(
    *,
    decision: str = "none",
    scale: float = 1.0,
    checked: str = "2026-07-11T19:00:00Z",
    issued: str = "2026-07-11T18:30:00Z",
    valid: str = "2026-07-11T21:00:00Z",
    evidence_type: str = "point_forecast",
    source: str = "https://api.weather.gov/gridpoints/MFL/110,50/forecast/hourly",
    snapshot: str = '{"validTime":"2026-07-11T21:00:00Z","temperature":88}',
) -> dict[str, object]:
    return {
        "market_odds": [2.4, 3.2, 2.9],
        "weather_scale": scale,
        "kickoff_at_utc": "2026-07-11T21:00:00Z",
        "weather_checked_at_utc": checked,
        "weather_forecast_issued_at_utc": issued,
        "weather_forecast_valid_at_utc": valid,
        "weather_source": source,
        "weather_evidence_type": evidence_type,
        "weather_evidence_snapshot": snapshot,
        "weather_evidence_sha256": _digest(snapshot),
        "weather_decision": decision,
    }


def _nws_payload(
    *,
    decision: str = "none",
    scale: float = 1.0,
    kickoff: str = "2026-07-11T21:00:00Z",
    checked: str = "2026-07-11T19:00:00Z",
    issued: str = "2026-07-11T18:30:00Z",
    generated: str = "2026-07-11T18:45:00Z",
    period_start: str = "2026-07-11T21:00:00Z",
    period_end: str = "2026-07-11T22:00:00Z",
    capture_method: str = "direct_http_response_body",
) -> dict[str, object]:
    points_source = "https://api.weather.gov/points/25.7617,-80.1918"
    hourly_source = "https://api.weather.gov/gridpoints/MFL/110,50/forecast/hourly"
    points_snapshot = json.dumps(
        {"id": points_source, "properties": {"forecastHourly": hourly_source}},
        separators=(",", ":"),
    )
    hourly_snapshot = json.dumps(
        {
            "properties": {
                "updateTime": issued,
                "generatedAt": generated,
                "periods": [
                    {
                        "startTime": period_start,
                        "endTime": period_end,
                        "temperature": 88,
                    }
                ],
            }
        },
        separators=(",", ":"),
    )
    return {
        "market_odds": [2.4, 3.2, 2.9],
        "weather_scale": scale,
        "kickoff_at_utc": kickoff,
        "weather_checked_at_utc": checked,
        "weather_forecast_issued_at_utc": issued,
        "weather_forecast_valid_at_utc": period_start,
        "weather_forecast_generated_at_utc": generated,
        "weather_source": hourly_source,
        "weather_evidence_type": "hourly",
        "weather_evidence_snapshot": hourly_snapshot,
        "weather_evidence_sha256": _digest(hourly_snapshot),
        "weather_capture_method": capture_method,
        "weather_points_source": points_source,
        "weather_points_evidence_snapshot": points_snapshot,
        "weather_points_evidence_sha256": _digest(points_snapshot),
        "weather_decision": decision,
    }


def _write_context(path: Path, key: str, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps({"matches": {key: payload}}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _validate(path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return _run(
        [sys.executable, "validate_context.py", "--context-file", str(path), *extra],
        check=False,
    )


def _assert_invalid(path: Path, expected: str, *extra: str) -> None:
    proc = _validate(path, *extra)
    output = proc.stdout + proc.stderr
    assert proc.returncode != 0, output
    assert expected in output, output


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # CSV import preserves all provenance fields. Rain at exactly T-3h is valid.
        valid_csv = tmp / "weather_evidence_valid.csv"
        valid_json = tmp / "weather_evidence_valid.json"
        rain_payload = _nws_payload(
            decision="rain_applied",
            scale=0.95,
            checked="2026-07-11T18:00:00Z",
            issued="2026-07-11T17:30:00Z",
            generated="2026-07-11T17:45:00Z",
        )
        rain_row = {
            "home": "Norway",
            "away": "England",
            "market_home": "2.40",
            "market_draw": "3.20",
            "market_away": "2.90",
            **{key: value for key, value in rain_payload.items() if key != "market_odds"},
        }
        with valid_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rain_row))
            writer.writeheader()
            writer.writerow(rain_row)
        _run(
            [
                sys.executable,
                "import_context_csv.py",
                "--input",
                str(valid_csv),
                "--output",
                str(valid_json),
            ]
        )
        imported = json.loads(valid_json.read_text(encoding="utf-8"))["matches"]["Norway|England"]
        for field in (
            "weather_forecast_issued_at_utc",
            "weather_forecast_valid_at_utc",
            "weather_forecast_generated_at_utc",
            "weather_evidence_snapshot",
            "weather_evidence_sha256",
            "weather_capture_method",
            "weather_points_source",
            "weather_points_evidence_snapshot",
            "weather_points_evidence_sha256",
        ):
            assert imported[field] == rain_row[field]
        valid_check = _validate(
            valid_json,
            "--require-structured-weather",
            "--now-utc",
            "2026-07-11T18:00:00Z",
        )
        assert valid_check.returncode == 0, valid_check.stdout + valid_check.stderr
        valid_pipeline_json = tmp / "weather_evidence_pipeline.json"
        valid_pipeline = _run(
            [
                sys.executable,
                "run_context_pipeline.py",
                "--input-csv",
                str(valid_csv),
                "--output-json",
                str(valid_pipeline_json),
                "--require-weather-evidence",
                "--require-structured-weather",
                "--now-utc",
                "2026-07-11T18:00:00Z",
                "--context-only",
            ],
            check=False,
        )
        assert valid_pipeline.returncode == 0, valid_pipeline.stdout + valid_pipeline.stderr
        assert "Context validation complete:" in valid_pipeline.stdout
        assert "Selected prediction profile:" not in valid_pipeline.stdout

        future_cli_payload = _nws_payload(checked="2026-07-11T19:01:00Z")
        future_cli_path = tmp / "weather_evidence_future_cli.json"
        _write_context(future_cli_path, "Norway|England", future_cli_payload)
        _assert_invalid(
            future_cli_path,
            "weather_checked_at_utc is later than run time",
            "--require-structured-weather",
            "--now-utc",
            "2026-07-11T19:00:00Z",
        )

        future_pipeline_json = tmp / "weather_evidence_future_pipeline.json"
        future_pipeline = _run(
            [
                sys.executable,
                "run_context_pipeline.py",
                "--input-csv",
                str(valid_csv),
                "--output-json",
                str(future_pipeline_json),
                "--require-structured-weather",
                "--now-utc",
                "2026-07-11T17:59:00Z",
                "--context-only",
            ],
            check=False,
        )
        assert future_pipeline.returncode != 0, (
            future_pipeline.stdout + future_pipeline.stderr
        )
        assert "weather_checked_at_utc is later than run time" in future_pipeline.stdout

        # Schema-4 structured NWS evidence accepts both declared capture paths.
        for capture_method in ("direct_http_response_body", "workspace_web_fetch"):
            payload = _nws_payload(capture_method=capture_method)
            context = MatchContext(
                **{key: value for key, value in payload.items() if key != "market_odds"}
            )
            assert validate_weather_context(
                context,
                require_evidence=True,
                require_structured_weather=True,
            ) == []

        invalid_method_payload = _nws_payload(capture_method="browser_summary")
        invalid_method_context = MatchContext(
            **{
                key: value
                for key, value in invalid_method_payload.items()
                if key != "market_odds"
            }
        )
        assert any(
            "weather_capture_method must be one of" in issue
            for issue in validate_weather_context(
                invalid_method_context,
                require_evidence=True,
                require_structured_weather=True,
            )
        )

        mismatched_url_payload = _nws_payload()
        mismatched_url_payload["weather_source"] = (
            "https://api.weather.gov/gridpoints/FFC/1,1/forecast/hourly"
        )
        mismatched_url_context = MatchContext(
            **{
                key: value
                for key, value in mismatched_url_payload.items()
                if key != "market_odds"
            }
        )
        assert any(
            "must exactly match points properties.forecastHourly" in issue
            for issue in validate_weather_context(
                mismatched_url_context,
                require_evidence=True,
                require_structured_weather=True,
            )
        )

        atlanta_points_payload = _nws_payload()
        atlanta_points_payload["weather_points_source"] = (
            "https://api.weather.gov/points/33.755,-84.39"
        )
        atlanta_points_context = MatchContext(
            **{
                key: value
                for key, value in atlanta_points_payload.items()
                if key != "market_odds"
            }
        )
        assert any(
            "weather_points_source must exactly match weather points JSON id" in issue
            for issue in validate_weather_context(
                atlanta_points_context,
                require_evidence=True,
                require_structured_weather=True,
            )
        )

        properties_id_payload = _nws_payload()
        points_json = json.loads(
            properties_id_payload["weather_points_evidence_snapshot"]
        )
        points_json["properties"]["@id"] = properties_id_payload[
            "weather_points_source"
        ]
        points_json.pop("id")
        points_snapshot = json.dumps(points_json, separators=(",", ":"))
        properties_id_payload["weather_points_evidence_snapshot"] = points_snapshot
        properties_id_payload["weather_points_evidence_sha256"] = _digest(
            points_snapshot
        )
        properties_id_context = MatchContext(
            **{
                key: value
                for key, value in properties_id_payload.items()
                if key != "market_odds"
            }
        )
        assert validate_weather_context(
            properties_id_context,
            require_evidence=True,
            require_structured_weather=True,
        ) == []

        conflicting_ids_payload = _nws_payload()
        points_json = json.loads(
            conflicting_ids_payload["weather_points_evidence_snapshot"]
        )
        points_json["properties"]["@id"] = (
            "https://api.weather.gov/points/33.755,-84.39"
        )
        points_snapshot = json.dumps(points_json, separators=(",", ":"))
        conflicting_ids_payload["weather_points_evidence_snapshot"] = points_snapshot
        conflicting_ids_payload["weather_points_evidence_sha256"] = _digest(
            points_snapshot
        )
        conflicting_ids_context = MatchContext(
            **{
                key: value
                for key, value in conflicting_ids_payload.items()
                if key != "market_odds"
            }
        )
        assert any(
            "weather points JSON id and properties.@id must match" in issue
            for issue in validate_weather_context(
                conflicting_ids_context,
                require_evidence=True,
                require_structured_weather=True,
            )
        )

        bad_points_hash_payload = _nws_payload()
        bad_points_hash_payload["weather_points_evidence_sha256"] = "0" * 64
        bad_points_hash_context = MatchContext(
            **{
                key: value
                for key, value in bad_points_hash_payload.items()
                if key != "market_odds"
            }
        )
        assert any(
            "weather_points_evidence_sha256 does not match" in issue
            for issue in validate_weather_context(
                bad_points_hash_context,
                require_evidence=True,
                require_structured_weather=True,
            )
        )

        stale_update_payload = _nws_payload(
            issued="2026-07-09T18:00:00Z",
            generated="2026-07-11T18:45:00Z",
        )
        stale_update_context = MatchContext(
            **{
                key: value
                for key, value in stale_update_payload.items()
                if key != "market_odds"
            }
        )
        assert any(
            "weather forecast issue is stale" in issue
            for issue in validate_weather_context(
                stale_update_context,
                require_evidence=True,
                require_structured_weather=True,
            )
        )

        stale_json_forged_issue_payload = _nws_payload(
            issued="2026-07-09T18:00:00Z",
            generated="2026-07-11T18:45:00Z",
        )
        stale_json_forged_issue_payload["weather_forecast_issued_at_utc"] = (
            "2026-07-11T18:30:00Z"
        )
        stale_json_forged_issue_context = MatchContext(
            **{
                key: value
                for key, value in stale_json_forged_issue_payload.items()
                if key != "market_odds"
            }
        )
        stale_json_forged_issues = validate_weather_context(
            stale_json_forged_issue_context,
            require_evidence=True,
            require_structured_weather=True,
        )
        assert any(
            "must match weather hourly properties.updateTime" in issue
            for issue in stale_json_forged_issues
        )
        assert any(
            "weather forecast issue is stale" in issue
            for issue in stale_json_forged_issues
        )

        forged_time_payload = _nws_payload()
        forged_time_payload["weather_forecast_issued_at_utc"] = "2026-07-11T18:31:00Z"
        forged_time_context = MatchContext(
            **{
                key: value
                for key, value in forged_time_payload.items()
                if key != "market_odds"
            }
        )
        assert any(
            "must match weather hourly properties.updateTime" in issue
            for issue in validate_weather_context(
                forged_time_context,
                require_evidence=True,
                require_structured_weather=True,
            )
        )

        forged_generated_payload = _nws_payload()
        forged_generated_payload["weather_forecast_generated_at_utc"] = (
            "2026-07-11T18:46:00Z"
        )
        forged_generated_context = MatchContext(
            **{
                key: value
                for key, value in forged_generated_payload.items()
                if key != "market_odds"
            }
        )
        assert any(
            "must match weather hourly properties.generatedAt" in issue
            for issue in validate_weather_context(
                forged_generated_context,
                require_evidence=True,
                require_structured_weather=True,
            )
        )

        forged_valid_payload = _nws_payload()
        forged_valid_payload["weather_forecast_valid_at_utc"] = "2026-07-11T21:01:00Z"
        forged_valid_context = MatchContext(
            **{
                key: value
                for key, value in forged_valid_payload.items()
                if key != "market_odds"
            }
        )
        assert any(
            "must match the kickoff period startTime" in issue
            for issue in validate_weather_context(
                forged_valid_context,
                require_evidence=True,
                require_structured_weather=True,
            )
        )

        missing_kickoff_period_payload = _nws_payload(
            period_start="2026-07-11T20:00:00Z",
            period_end="2026-07-11T21:00:00Z",
        )
        missing_kickoff_period_context = MatchContext(
            **{
                key: value
                for key, value in missing_kickoff_period_payload.items()
                if key != "market_odds"
            }
        )
        assert any(
            "exactly one period covering kickoff" in issue
            for issue in validate_weather_context(
                missing_kickoff_period_context,
                require_evidence=True,
                require_structured_weather=True,
            )
        )

        # Heat at exactly T-6h passes, including equivalent non-UTC offsets.
        heat_payload = _outdoor_payload(
            decision="heat_mild",
            scale=0.95,
            checked="2026-07-11T11:00:00-04:00",
            issued="2026-07-11T10:30:00-04:00",
            valid="2026-07-11T17:30:00-04:00",
        )
        heat_context = MatchContext(**{key: value for key, value in heat_payload.items() if key != "market_odds"})
        assert validate_weather_context(heat_context, require_evidence=True) == []
        for decision, scale in (("heat_moderate", 0.92), ("heat_severe", 0.90)):
            payload = _outdoor_payload(decision=decision, scale=scale)
            context = MatchContext(**{key: value for key, value in payload.items() if key != "market_odds"})
            assert validate_weather_context(context, require_evidence=True) == []

        no_adjustment = _outdoor_payload()
        no_adjustment_context = MatchContext(
            **{key: value for key, value in no_adjustment.items() if key != "market_odds"}
        )
        assert validate_weather_context(no_adjustment_context, require_evidence=True) == []
        manual_no_adjustment = MatchContext(
            **{**no_adjustment_context.__dict__, "weather_evidence_type": "manual"}
        )
        assert any(
            "weather_decision=none requires weather_evidence_type" in issue
            for issue in validate_weather_context(manual_no_adjustment, require_evidence=True)
        )

        stale_heat = dict(heat_payload)
        stale_heat["weather_checked_at_utc"] = "2026-07-11T10:54:00-04:00"
        stale_heat_path = tmp / "stale_heat.json"
        _write_context(stale_heat_path, "Norway|England", stale_heat)
        _assert_invalid(stale_heat_path, "heat_mild evidence is stale")

        after_kickoff = _outdoor_payload(checked="2026-07-11T21:01:00Z")
        after_kickoff_path = tmp / "after_kickoff.json"
        _write_context(after_kickoff_path, "Norway|England", after_kickoff)
        _assert_invalid(after_kickoff_path, "weather_checked_at_utc is after kickoff")

        for future_minute in (1, 5):
            future_checked = _outdoor_payload(
                checked=f"2026-07-11T19:{future_minute:02d}:00Z",
                issued="2026-07-11T18:30:00Z",
            )
            future_checked_context = MatchContext(
                **{key: value for key, value in future_checked.items() if key != "market_odds"}
            )
            future_issues = validate_weather_context(
                future_checked_context,
                require_evidence=True,
                now_utc=datetime(2026, 7, 11, 19, 0, tzinfo=timezone.utc),
            )
            assert any("later than run time" in issue for issue in future_issues)
        kickoff_issues = validate_weather_context(
            no_adjustment_context,
            require_evidence=True,
            now_utc=datetime(2026, 7, 11, 21, 0, tzinfo=timezone.utc),
        )
        assert any("at or after kickoff" in issue for issue in kickoff_issues)

        stale_forecast = _outdoor_payload(valid="2026-07-11T20:59:00Z")
        stale_forecast_path = tmp / "stale_forecast.json"
        _write_context(stale_forecast_path, "Norway|England", stale_forecast)
        _assert_invalid(stale_forecast_path, "must cover the kickoff hour")

        stale_issue = _outdoor_payload(issued="2026-07-09T18:00:00Z")
        stale_issue_path = tmp / "stale_issue.json"
        _write_context(stale_issue_path, "Norway|England", stale_issue)
        _assert_invalid(stale_issue_path, "weather forecast issue is stale")

        # Sources must be URLs and snapshots must be present with a matching hash.
        missing_audit = _outdoor_payload(source="NWS radar")
        missing_audit.pop("weather_evidence_sha256")
        missing_audit_path = tmp / "missing_audit.json"
        _write_context(missing_audit_path, "Norway|England", missing_audit)
        missing_audit_check = _validate(missing_audit_path)
        missing_output = missing_audit_check.stdout + missing_audit_check.stderr
        assert missing_audit_check.returncode != 0
        assert "weather_source must be an http(s) URL" in missing_output
        assert "weather evidence requires weather_evidence_sha256" in missing_output

        bad_hash = _outdoor_payload()
        bad_hash["weather_evidence_sha256"] = "0" * 64
        bad_hash_path = tmp / "bad_hash.json"
        _write_context(bad_hash_path, "Norway|England", bad_hash)
        _assert_invalid(bad_hash_path, "does not match weather_evidence_snapshot")

        # Roof evidence is official and auditable, but is not a weather forecast.
        roof_snapshot = "Official: roof will remain closed for the match"
        roof = MatchContext(
            kickoff_at_utc="2026-07-11T21:00:00Z",
            weather_checked_at_utc="2026-07-11T12:00:00-07:00",
            weather_source="https://stadium.example.org/matchday/roof-status",
            weather_evidence_type="official_roof",
            roof_status="closed",
            weather_evidence_fixture_id="2026-QF99-Norway-England",
            weather_evidence_snapshot=roof_snapshot,
            weather_evidence_sha256=_digest(roof_snapshot),
            weather_decision="indoor_no_weather",
            weather_capture_method="workspace_web_fetch",
        )
        assert validate_weather_context(
            roof,
            require_evidence=True,
            expected_fixture_id="2026-QF99-Norway-England",
            require_structured_weather=True,
        ) == []
        roof_with_forecast_metadata = MatchContext(
            **{
                **roof.__dict__,
                "weather_forecast_issued_at_utc": "2026-07-11T18:30:00Z",
                "weather_forecast_valid_at_utc": "2026-07-11T21:00:00Z",
                "weather_forecast_generated_at_utc": "2026-07-11T18:45:00Z",
            }
        )
        assert validate_weather_context(
            roof_with_forecast_metadata,
            require_evidence=True,
            expected_fixture_id="2026-QF99-Norway-England",
            require_structured_weather=True,
        ) == []
        nws_points_roof_fields = {
            "weather_points_source": "https://api.weather.gov/points/25.7617,-80.1918",
            "weather_points_evidence_snapshot": "{}",
            "weather_points_evidence_sha256": _digest("{}"),
        }
        for field, value in nws_points_roof_fields.items():
            mixed_roof = MatchContext(**{**roof.__dict__, field: value})
            assert f"official_roof evidence cannot include {field}" in (
                validate_weather_context(
                    mixed_roof,
                    require_evidence=True,
                    expected_fixture_id="2026-QF99-Norway-England",
                    require_structured_weather=True,
                )
            )
        invalid_roof = MatchContext(
            **{
                **roof.__dict__,
                "weather_evidence_type": "point_forecast",
            }
        )
        assert "indoor_no_weather requires weather_evidence_type=official_roof" in validate_weather_context(
            invalid_roof,
            require_evidence=True,
        )
        open_roof = MatchContext(**{**roof.__dict__, "roof_status": "open"})
        assert "indoor_no_weather requires roof_status=closed" in validate_weather_context(
            open_roof,
            require_evidence=True,
        )
        wrong_fixture_roof = MatchContext(
            **{
                **roof.__dict__,
                "weather_evidence_fixture_id": "2026-SF101-France-Spain",
            }
        )
        assert any(
            "does not match the selected fixture" in issue
            for issue in validate_weather_context(
                wrong_fixture_roof,
                require_evidence=True,
                expected_fixture_id="2026-QF99-Norway-England",
            )
        )
        stale_roof = MatchContext(
            **{
                **roof.__dict__,
                "weather_checked_at_utc": "2026-07-11T14:00:00Z",
            }
        )
        assert any(
            "indoor_no_weather evidence is stale" in issue
            for issue in validate_weather_context(stale_roof, require_evidence=True)
        )

        # rain_watch is a scale=1 decision; all fixed decision mappings are enforced.
        rain_watch = _outdoor_payload(decision="rain_watch", scale=1.0)
        rain_watch_context = MatchContext(**{key: value for key, value in rain_watch.items() if key != "market_odds"})
        assert validate_weather_context(rain_watch_context, require_evidence=True) == []
        wrong_scale = MatchContext(**{**rain_watch_context.__dict__, "weather_scale": 0.95})
        assert any("requires weather_scale=1.00" in issue for issue in validate_weather_context(wrong_scale))
        non_finite_scale = MatchContext(**{**rain_watch_context.__dict__, "weather_scale": float("nan")})
        assert "weather_scale must be finite" in validate_weather_context(non_finite_scale)

        stale_rain = dict(rain_row)
        stale_rain["weather_checked_at_utc"] = "2026-07-11T17:59:00Z"
        stale_rain_path = tmp / "stale_rain.csv"
        with stale_rain_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(stale_rain))
            writer.writeheader()
            writer.writerow(stale_rain)
        stale_rain_json = tmp / "stale_rain.json"
        _run(
            [sys.executable, "import_context_csv.py", "--input", str(stale_rain_path), "--output", str(stale_rain_json)]
        )
        _assert_invalid(stale_rain_json, "rain_applied evidence is stale")

        # CLI validation and model execution both block double weather scaling.
        legacy_conflict = _outdoor_payload(decision="heat_mild", scale=0.95)
        legacy_conflict_path = tmp / "legacy_conflict.json"
        _write_context(legacy_conflict_path, "Curacao|Cote dIvoire", legacy_conflict)
        _assert_invalid(legacy_conflict_path, "legacy heat=mild conflicts")
        try:
            predict_match(
                STABLE_V35,
                "Norway",
                "England",
                heat="mild",
                weather_scale=0.95,
            )
        except ValueError as exc:
            assert "cannot be combined" in str(exc)
        else:
            raise AssertionError("predict_match accepted legacy heat plus weather_scale")

        # qf_jul11 templates contain fixed kickoffs and intentionally fail the official gate until filled.
        template_csv = tmp / "weather_evidence_template.csv"
        _run(
            [
                sys.executable,
                "create_context_template.py",
                "--source",
                "qf_jul11",
                "--format",
                "csv",
                "--output",
                str(template_csv),
            ]
        )
        with template_csv.open(newline="", encoding="utf-8") as handle:
            template_rows = {f"{row['home']}|{row['away']}": row for row in csv.DictReader(handle)}
        assert template_rows["Norway|England"]["kickoff_at_utc"] == "2026-07-11T21:00:00Z"
        assert template_rows["Argentina|Switzerland"]["kickoff_at_utc"] == "2026-07-12T01:00:00Z"
        for field in (
            "weather_forecast_issued_at_utc",
            "weather_forecast_valid_at_utc",
            "weather_forecast_generated_at_utc",
            "weather_evidence_snapshot",
            "weather_evidence_sha256",
            "weather_capture_method",
            "weather_points_source",
            "weather_points_evidence_snapshot",
            "weather_points_evidence_sha256",
        ):
            assert field in template_rows["Norway|England"]
            assert template_rows["Norway|England"][field] == ""

        single_template_csv = tmp / "weather_evidence_single_template.csv"
        _run(
            [
                sys.executable,
                "create_context_template.py",
                "--source",
                "qf_jul11",
                "--fixture",
                "norway-england",
                "--format",
                "csv",
                "--output",
                str(single_template_csv),
            ]
        )
        with single_template_csv.open(newline="", encoding="utf-8") as handle:
            single_rows = list(csv.DictReader(handle))
        assert len(single_rows) == 1
        assert single_rows[0]["home"] == "Norway"
        assert single_rows[0]["away"] == "England"

        sf_template_csv = tmp / "weather_evidence_sf_template.csv"
        _run(
            [
                sys.executable,
                "create_context_template.py",
                "--source",
                "sf_jul14_15",
                "--format",
                "csv",
                "--output",
                str(sf_template_csv),
            ]
        )
        with sf_template_csv.open(newline="", encoding="utf-8") as handle:
            sf_rows = {f"{row['home']}|{row['away']}": row for row in csv.DictReader(handle)}
        assert sf_rows["France|Spain"]["kickoff_at_utc"] == "2026-07-14T19:00:00Z"
        assert sf_rows["England|Argentina"]["kickoff_at_utc"] == "2026-07-15T19:00:00Z"
        assert sf_rows["France|Spain"]["market_advance_odds"] == ""
        assert sf_rows["France|Spain"]["market_advance_home"] == ""
        assert sf_rows["France|Spain"]["market_advance_away"] == ""
        assert sf_rows["France|Spain"]["roof_status"] == ""
        assert sf_rows["France|Spain"]["weather_evidence_fixture_id"] == ""

        sf_single_csv = tmp / "weather_evidence_sf_single.csv"
        _run(
            [
                sys.executable,
                "create_context_template.py",
                "--source",
                "sf_jul14_15",
                "--fixture",
                "france-spain",
                "--format",
                "csv",
                "--output",
                str(sf_single_csv),
            ]
        )
        with sf_single_csv.open(newline="", encoding="utf-8") as handle:
            sf_single_rows = list(csv.DictReader(handle))
        assert len(sf_single_rows) == 1
        assert sf_single_rows[0]["home"] == "France"
        assert sf_single_rows[0]["away"] == "Spain"

        wrong_sf_fixture = _run(
            [
                sys.executable,
                "create_context_template.py",
                "--source",
                "sf_jul14_15",
                "--fixture",
                "norway-england",
                "--format",
                "csv",
            ],
            check=False,
        )
        assert wrong_sf_fixture.returncode != 0
        assert "is not valid for sf_jul14_15" in wrong_sf_fixture.stderr

        pipeline_output = tmp / "qf_blank.json"
        pipeline = _run(
            [
                sys.executable,
                "run_context_pipeline.py",
                "--fixture-source",
                "qf_jul11",
                "--output-json",
                str(pipeline_output),
                "--now-utc",
                "2026-07-11T18:00:00Z",
            ],
            check=False,
        )
        assert pipeline.returncode != 0, pipeline.stdout + pipeline.stderr
        assert "weather evidence requires weather_checked_at_utc" in pipeline.stdout
        assert "Predict June" not in pipeline.stdout

        sf_pipeline_output = tmp / "sf_blank.json"
        sf_pipeline = _run(
            [
                sys.executable,
                "run_context_pipeline.py",
                "--fixture-source",
                "sf_jul14_15",
                "--fixture",
                "england-argentina",
                "--output-json",
                str(sf_pipeline_output),
                "--now-utc",
                "2026-07-15T16:05:00Z",
            ],
            check=False,
        )
        assert sf_pipeline.returncode != 0, sf_pipeline.stdout + sf_pipeline.stderr
        assert "weather evidence requires weather_checked_at_utc" in sf_pipeline.stdout
        assert "France|Spain" not in sf_pipeline.stdout
        assert "Predict June" not in sf_pipeline.stdout

        # A noncompliant override is blocking in the default pipeline, without --fail-on-warning.
        invalid_pipeline_csv = tmp / "invalid_pipeline.csv"
        with invalid_pipeline_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["home", "away", "weather_scale"])
            writer.writeheader()
            writer.writerow({"home": "Norway", "away": "England", "weather_scale": "0.95"})
        invalid_pipeline = _run(
            [
                sys.executable,
                "run_context_pipeline.py",
                "--input-csv",
                str(invalid_pipeline_csv),
                "--context-only",
            ],
            check=False,
        )
        assert invalid_pipeline.returncode != 0, invalid_pipeline.stdout + invalid_pipeline.stderr
        assert "Errors" in invalid_pipeline.stdout

    print("WEATHER_EVIDENCE_REGRESSION PASS")


if __name__ == "__main__":
    main()
