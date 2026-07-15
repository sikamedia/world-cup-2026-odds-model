#!/usr/bin/env python3
"""End-to-end checks for July 11 finalization artifacts and bracket MC."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile

import fetch_elo_current
from elo_snapshot import load_elo_capture_receipt, parse_world_tsv_bytes
import predict_jul11


SCHEMA4_WEATHER_FIELDS = (
    "capture_method",
    "points_source",
    "points_evidence_snapshot",
    "points_evidence_sha256",
    "forecast_generated_at_utc",
)
SCHEMA4_CONTEXT_FIELDS = tuple(
    f"weather_{field}" for field in SCHEMA4_WEATHER_FIELDS
)


def _world_tsv() -> str:
    rows = [
        ("ES", 2177),
        ("AR", 2156),
        ("FR", 2143),
        ("EN", 2076),
        ("BR", 2050),
        ("PT", 2040),
        ("CO", 2003),
        ("NL", 1995),
        ("MX", 1980),
        ("CH", 1949),
        ("NO", 1972),
        ("BE", 1961),
        ("DE", 1950),
        ("JP", 1930),
        ("MA", 1921),
        ("HR", 1910),
    ]
    return "".join(
        f"{rank}\t{rank}\t{code}\t{rating}\n"
        for rank, (code, rating) in enumerate(rows, start=1)
    )


def _make_elo(
    tmp: Path,
    stem: str,
    fetched_at: str,
    *,
    estimates: tuple[str, ...] = (),
) -> tuple[Path, Path, Path]:
    source_tsv = tmp / f"{stem}_World.tsv"
    receipt = tmp / f"{stem}_receipt.json"
    module = tmp / f"{stem}_elo.py"
    source_bytes = _world_tsv().encode("utf-8")
    source_tsv.write_bytes(source_bytes)
    receipt.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "artifact_type": "elo_http_capture_receipt",
                "capture_method": "direct_http_response_body",
                "requested_url": "https://www.eloratings.net/World.tsv",
                "final_url": "https://www.eloratings.net/World.tsv",
                "http_status": 200,
                "response_completed_at_utc": fetched_at,
                "evidence_file": source_tsv.name,
                "body_byte_count": len(source_bytes),
                "body_sha256": hashlib.sha256(source_bytes).hexdigest(),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="ascii",
    )
    fixture_now = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    capture_receipt = load_elo_capture_receipt(
        receipt,
        source_tsv=source_tsv,
        source_bytes=source_bytes,
        now_utc=fixture_now,
    )
    with redirect_stdout(io.StringIO()):
        fetch_elo_current.emit_module(
            parse_world_tsv_bytes(source_bytes, source_tsv),
            module,
            source_bytes=source_bytes,
            fetched_at_utc=capture_receipt.response_completed_at_utc,
            capture_receipt=capture_receipt,
        )
    if estimates:
        text = module.read_text(encoding="utf-8")
        module.write_text(
            text.replace("ESTIMATES = []", f"ESTIMATES = {list(estimates)!r}"),
            encoding="utf-8",
        )
    return module, source_tsv, receipt


def _weather_row(
    *,
    kickoff: str,
    checked: str,
    decision: str,
    scale: float,
    advance_odds: tuple[float, float] | None = None,
) -> dict:
    issued = predict_jul11._parse_utc(checked)  # normalize test fixtures through runner parser
    issued_text = (
        issued.replace(minute=max(0, issued.minute - 1))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    generated_text = issued.isoformat(timespec="seconds").replace("+00:00", "Z")
    period_start = predict_jul11._parse_utc(kickoff)
    period_end = period_start + timedelta(hours=1)
    period_end_text = period_end.isoformat(timespec="seconds").replace("+00:00", "Z")
    points_source = "https://api.weather.gov/points/25.7617,-80.1918"
    hourly_source = "https://api.weather.gov/gridpoints/MFL/110,50/forecast/hourly"
    points_snapshot = json.dumps(
        {"id": points_source, "properties": {"forecastHourly": hourly_source}},
        separators=(",", ":"),
    )
    snapshot = json.dumps(
        {
            "properties": {
                "updateTime": issued_text,
                "generatedAt": generated_text,
                "periods": [
                    {
                        "startTime": kickoff,
                        "endTime": period_end_text,
                    }
                ],
            }
        },
        separators=(",", ":"),
    )
    return {
        "market_odds": [2.8, 3.2, 2.5],
        "market_advance_odds": list(advance_odds) if advance_odds else None,
        "market_method": "proportional",
        "weather_scale": scale,
        "kickoff_at_utc": kickoff,
        "weather_checked_at_utc": checked,
        "weather_forecast_issued_at_utc": issued_text,
        "weather_forecast_valid_at_utc": kickoff,
        "weather_forecast_generated_at_utc": generated_text,
        "weather_source": hourly_source,
        "weather_evidence_type": "hourly",
        "weather_decision": decision,
        "weather_evidence_snapshot": snapshot,
        "weather_evidence_sha256": hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
        "weather_capture_method": "direct_http_response_body",
        "weather_points_source": points_source,
        "weather_points_evidence_snapshot": points_snapshot,
        "weather_points_evidence_sha256": hashlib.sha256(
            points_snapshot.encode("utf-8")
        ).hexdigest(),
        "source_key": "synthetic-market-source",
    }


def _roof_row(
    *,
    kickoff: str,
    checked: str,
    fixture_id: str,
    advance_odds: tuple[float, float] | None = None,
) -> dict:
    snapshot = f"Official matchday notice for {fixture_id}: roof will remain closed"
    return {
        "market_odds": [2.8, 3.2, 2.5],
        "market_advance_odds": list(advance_odds) if advance_odds else None,
        "market_method": "proportional",
        "weather_scale": 1.0,
        "kickoff_at_utc": kickoff,
        "weather_checked_at_utc": checked,
        "weather_source": "https://stadium.example.org/matchday/roof-status",
        "weather_evidence_type": "official_roof",
        "roof_status": "closed",
        "weather_evidence_fixture_id": fixture_id,
        "weather_decision": "indoor_no_weather",
        "weather_evidence_snapshot": snapshot,
        "weather_evidence_sha256": hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
        "weather_capture_method": "workspace_web_fetch",
        "source_key": "synthetic-market-source",
    }


def _write_context(path: Path, key: str, row: dict) -> None:
    path.write_text(json.dumps({"matches": {key: row}}), encoding="utf-8")


def _invoke(argv: list[str], *, now: str) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = 0
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            predict_jul11.main(argv, now_utc=predict_jul11._parse_utc(now))
    except SystemExit as exc:
        code = int(exc.code or 0)
    return code, stdout.getvalue(), stderr.getvalue()


def _finalize_args(
    *,
    fixture: str,
    module: Path,
    source_tsv: Path,
    receipt: Path,
    context: Path,
    artifact: Path,
) -> list[str]:
    return [
        "finalize",
        "--fixture",
        fixture,
        "--elo-module",
        str(module),
        "--elo-source-tsv",
        str(source_tsv),
        "--elo-receipt",
        str(receipt),
        "--context-file",
        str(context),
        "--artifact-out",
        str(artifact),
    ]


def _mc_args(
    *,
    artifacts: tuple[Path, Path],
    module: Path,
    source_tsv: Path,
    receipt: Path,
) -> list[str]:
    return [
        "mc",
        "--artifacts",
        str(artifacts[0]),
        str(artifacts[1]),
        "--elo-module",
        str(module),
        "--elo-source-tsv",
        str(source_tsv),
        "--elo-receipt",
        str(receipt),
        "--qf98-winner",
        "Spain",
        "--sims",
        "20",
        "--seed",
        "7",
    ]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        first_module, first_tsv, first_receipt = _make_elo(
            tmp, "qf99", "2026-07-11T18:00:00Z"
        )
        second_module, second_tsv, second_receipt = _make_elo(
            tmp, "qf100", "2026-07-11T22:00:00Z"
        )
        mc_module, mc_tsv, mc_receipt = _make_elo(
            tmp, "mc", "2026-07-11T22:06:00Z"
        )
        sf_module, sf_tsv, sf_receipt = _make_elo(
            tmp, "sf101", "2026-07-14T16:00:00Z"
        )
        sf102_module, sf102_tsv, sf102_receipt = _make_elo(
            tmp, "sf102", "2026-07-15T16:00:00Z"
        )

        norway_context = tmp / "norway_context.json"
        _write_context(
            norway_context,
            "Norway|England",
            _weather_row(
                kickoff="2026-07-11T21:00:00Z",
                checked="2026-07-11T18:05:00Z",
                decision="heat_mild",
                scale=0.95,
            ),
        )
        argentina_context = tmp / "argentina_context.json"
        _write_context(
            argentina_context,
            "Argentina|Switzerland",
            _weather_row(
                kickoff="2026-07-12T01:00:00Z",
                checked="2026-07-11T22:05:00Z",
                decision="none",
                scale=1.0,
            ),
        )

        # Both official commands require a direct-capture receipt at the CLI
        # boundary, before any output artifact can be created.
        missing_receipt_artifact = tmp / "missing_receipt.final.json"
        missing_receipt_args = _finalize_args(
            fixture="norway-england",
            module=first_module,
            source_tsv=first_tsv,
            receipt=first_receipt,
            context=norway_context,
            artifact=missing_receipt_artifact,
        )
        receipt_index = missing_receipt_args.index("--elo-receipt")
        del missing_receipt_args[receipt_index : receipt_index + 2]
        missing_receipt = _invoke(
            missing_receipt_args,
            now="2026-07-11T18:05:00Z",
        )
        assert missing_receipt[0] != 0
        assert "--elo-receipt" in missing_receipt[2]
        assert "OFFICIAL" not in missing_receipt[1]
        assert not missing_receipt_artifact.exists()

        mismatched_receipt = tmp / "mismatched_receipt.json"
        mismatched_data = json.loads(first_receipt.read_text(encoding="ascii"))
        mismatched_data["body_sha256"] = "0" * 64
        mismatched_receipt.write_text(
            json.dumps(mismatched_data, sort_keys=True) + "\n",
            encoding="ascii",
        )
        mismatched_receipt_artifact = tmp / "mismatched_receipt.final.json"
        mismatch = _invoke(
            _finalize_args(
                fixture="norway-england",
                module=first_module,
                source_tsv=first_tsv,
                receipt=mismatched_receipt,
                context=norway_context,
                artifact=mismatched_receipt_artifact,
            ),
            now="2026-07-11T18:05:00Z",
        )
        assert mismatch[0] != 0
        assert "receipt" in mismatch[2].lower()
        assert "OFFICIAL" not in mismatch[1]
        assert not mismatched_receipt_artifact.exists()

        norway_artifact = tmp / "qf99.final.json"
        first = _invoke(
            _finalize_args(
                fixture="norway-england",
                module=first_module,
                source_tsv=first_tsv,
                receipt=first_receipt,
                context=norway_context,
                artifact=norway_artifact,
            ),
            now="2026-07-11T18:05:00Z",
        )
        assert first[0] == 0, first[2]
        assert "OFFICIAL PRE-KICKOFF FINALIZATION" in first[1]
        assert "Norway vs England" in first[1]
        assert "Argentina vs Switzerland" not in first[1]
        assert "OFFICIAL w=0.6 model/0.4 market" in first[1]
        assert norway_artifact.is_file()
        assert not (norway_artifact.stat().st_mode & stat.S_IWUSR)

        argentina_artifact = tmp / "qf100.final.json"
        second = _invoke(
            _finalize_args(
                fixture="argentina-switzerland",
                module=second_module,
                source_tsv=second_tsv,
                receipt=second_receipt,
                context=argentina_context,
                artifact=argentina_artifact,
            ),
            now="2026-07-11T22:05:00Z",
        )
        assert second[0] == 0, second[2]
        assert "Argentina vs Switzerland" in second[1]
        assert "Norway vs England" not in second[1]
        assert argentina_artifact.is_file()

        artifact_data = json.loads(norway_artifact.read_text(encoding="ascii"))
        assert artifact_data["payload_sha256"] == predict_jul11._payload_sha256(
            artifact_data["payload"]
        )
        assert artifact_data["payload"]["official"]["model_weight"] == 0.6
        assert artifact_data["payload"]["elo_provenance"]["estimates"] == []
        assert artifact_data["payload"]["schema_version"] == 3
        assert artifact_data["payload"]["artifact_type"] == "pre_registered_match_prediction"
        assert artifact_data["payload"]["fixture"]["stage"] == "quarterfinal"
        elo_provenance = artifact_data["payload"]["elo_provenance"]
        assert elo_provenance["provenance_contract"] == "direct_http_v1"
        assert elo_provenance["capture_method"] == "direct_http_response_body"
        assert elo_provenance["receipt_sha256"] == hashlib.sha256(
            first_receipt.read_bytes()
        ).hexdigest()
        assert elo_provenance["retained_receipt_name"] == first_receipt.name
        assert elo_provenance["body_byte_count"] == len(first_tsv.read_bytes())
        weather_provenance = artifact_data["payload"]["context"]["weather"]
        for schema4_field in SCHEMA4_WEATHER_FIELDS:
            assert schema4_field not in weather_provenance

        missing_mc_receipt_args = _mc_args(
            artifacts=(norway_artifact, argentina_artifact),
            module=mc_module,
            source_tsv=mc_tsv,
            receipt=mc_receipt,
        )
        receipt_index = missing_mc_receipt_args.index("--elo-receipt")
        del missing_mc_receipt_args[receipt_index : receipt_index + 2]
        missing_mc_receipt = _invoke(
            missing_mc_receipt_args,
            now="2026-07-11T22:10:00Z",
        )
        assert missing_mc_receipt[0] != 0
        assert "--elo-receipt" in missing_mc_receipt[2]
        assert "PRE-REGISTERED ARTIFACT MC" not in missing_mc_receipt[1]

        # Semifinal fixtures keep the schema-3 contract through SF102. Schema 4
        # activates only for the third-place match and final.
        france_context = tmp / "france_context.json"
        france_row = _roof_row(
            kickoff="2026-07-14T19:00:00Z",
            checked="2026-07-14T16:05:00Z",
            fixture_id="2026-SF101-France-Spain",
            advance_odds=(1.8, 2.2),
        )
        _write_context(
            france_context,
            "France|Spain",
            france_row,
        )
        hard_stale_module, hard_stale_tsv, hard_stale_receipt = _make_elo(
            tmp,
            "sf101_hard_stale",
            "2026-07-14T15:34:59Z",
        )
        hard_stale_artifact = tmp / "sf_hard_stale_elo.final.json"
        hard_stale_args = _finalize_args(
            fixture="france-spain",
            module=hard_stale_module,
            source_tsv=hard_stale_tsv,
            receipt=hard_stale_receipt,
            context=france_context,
            artifact=hard_stale_artifact,
        )
        hard_stale_args.extend(("--max-elo-age-hours", "24"))
        hard_stale = _invoke(
            hard_stale_args,
            now="2026-07-14T16:05:00Z",
        )
        assert hard_stale[0] != 0
        assert "stale" in hard_stale[2]
        assert "OFFICIAL" not in hard_stale[1]
        assert not hard_stale_artifact.exists()

        france_artifact = tmp / "sf101.final.json"
        semifinal = _invoke(
            _finalize_args(
                fixture="france-spain",
                module=sf_module,
                source_tsv=sf_tsv,
                receipt=sf_receipt,
                context=france_context,
                artifact=france_artifact,
            ),
            now="2026-07-14T16:05:00Z",
        )
        assert semifinal[0] == 0, semifinal[2]
        assert "France vs Spain" in semifinal[1]
        assert "REVIEW FLAG model-market gap" in semifinal[1]
        semifinal_data = json.loads(france_artifact.read_text(encoding="ascii"))
        assert semifinal_data["payload"]["schema_version"] == 3
        assert semifinal_data["payload"]["fixture"]["fixture_id"] == "2026-SF101-France-Spain"
        assert semifinal_data["payload"]["fixture"]["stage"] == "semifinal"
        assert semifinal_data["payload"]["market"]["odds_advance"] == [1.8, 2.2]
        assert semifinal_data["payload"]["market"]["advance_method"] == "direct_two_way"
        assert semifinal_data["payload"]["market"]["advance_home"] == 0.55
        assert semifinal_data["payload"]["market"]["draw_resolution_home"] is None
        assert semifinal_data["payload"]["context"]["weather"]["roof_status"] == "closed"
        assert (
            semifinal_data["payload"]["context"]["weather"]["evidence_fixture_id"]
            == "2026-SF101-France-Spain"
        )
        semifinal_market = semifinal_data["payload"]["market"]
        assert semifinal_market["review_threshold"] == 0.04
        assert semifinal_market["review_required"] is True
        assert abs(
            semifinal_market["model_gap_advance_home"]
            - (
                semifinal_data["payload"]["model"]["advance_home"]
                - semifinal_market["advance_home"]
            )
        ) < 1e-12
        expected_official_advance = (
            0.6 * semifinal_data["payload"]["model"]["advance_home"] + 0.4 * 0.55
        )
        assert abs(
            semifinal_data["payload"]["official"]["advance_home"]
            - expected_official_advance
        ) < 1e-12

        england_context = tmp / "england_context.json"
        _write_context(
            england_context,
            "England|Argentina",
            _weather_row(
                kickoff="2026-07-15T19:00:00Z",
                checked="2026-07-15T16:05:00Z",
                decision="none",
                scale=1.0,
            ),
        )
        england_artifact = tmp / "sf102.final.json"
        second_semifinal = _invoke(
            _finalize_args(
                fixture="england-argentina",
                module=sf102_module,
                source_tsv=sf102_tsv,
                receipt=sf102_receipt,
                context=england_context,
                artifact=england_artifact,
            ),
            now="2026-07-15T16:05:00Z",
        )
        assert second_semifinal[0] == 0, second_semifinal[2]
        second_semifinal_data = json.loads(england_artifact.read_text(encoding="ascii"))
        assert second_semifinal_data["payload"]["schema_version"] == 3
        assert second_semifinal_data["payload"]["fixture"] == {
            "away": "Argentina",
            "fixture_id": "2026-SF102-England-Argentina",
            "home": "England",
            "kickoff_at_utc": "2026-07-15T19:00:00Z",
            "slug": "england-argentina",
            "stage": "semifinal",
        }
        assert second_semifinal_data["payload"]["market"]["odds_advance"] == []
        assert second_semifinal_data["payload"]["market"]["advance_margin"] is None
        assert second_semifinal_data["payload"]["market"]["advance_method"] == "derived_from_90"
        fallback_market = second_semifinal_data["payload"]["market"]
        expected_market_advance = (
            fallback_market["wdl_90"]["home"]
            + fallback_market["wdl_90"]["draw"]
            * fallback_market["draw_resolution_home"]
        )
        assert abs(fallback_market["advance_home"] - expected_market_advance) < 1e-12
        expected_fallback_official = (
            0.6 * second_semifinal_data["payload"]["model"]["advance_home"]
            + 0.4 * expected_market_advance
        )
        assert abs(
            second_semifinal_data["payload"]["official"]["advance_home"]
            - expected_fallback_official
        ) < 1e-12

        # Schema 4 is staged for the remaining post-semifinal fixtures. A
        # synthetic final exercises the same emitter/reader without registering
        # teams before the real SF102 result is known.
        synthetic_final = predict_jul11.Fixture(
            slug="schema4-final-test",
            fixture_id="2026-FINAL-Schema4-Test",
            stage="final",
            home="Norway",
            away="England",
            kickoff_at_utc="2026-07-11T21:00:00Z",
        )
        synthetic_third_place = predict_jul11.Fixture(
            slug="schema4-third-place-test",
            fixture_id="2026-3P-Schema4-Test",
            stage="third_place",
            home="Norway",
            away="England",
            kickoff_at_utc="2026-07-11T21:00:00Z",
        )
        assert predict_jul11._artifact_schema_version(synthetic_third_place) == 4
        predict_jul11.FIXTURES[synthetic_final.slug] = synthetic_final
        try:
            schema4_final_artifact = tmp / "schema4_final.json"
            schema4_final = _invoke(
                _finalize_args(
                    fixture=synthetic_final.slug,
                    module=first_module,
                    source_tsv=first_tsv,
                    receipt=first_receipt,
                    context=norway_context,
                    artifact=schema4_final_artifact,
                ),
                now="2026-07-11T18:05:00Z",
            )
            assert schema4_final[0] == 0, schema4_final[2]
            schema4_final_data = json.loads(
                schema4_final_artifact.read_text(encoding="ascii")
            )
            assert schema4_final_data["payload"]["schema_version"] == 4
            schema4_weather = schema4_final_data["payload"]["context"]["weather"]
            assert schema4_weather["capture_method"] == "direct_http_response_body"
            assert schema4_weather["points_source"].startswith(
                "https://api.weather.gov/points/"
            )
            assert schema4_weather["forecast_generated_at_utc"] == (
                "2026-07-11T18:05:00Z"
            )
            loaded_final, _probability, _digest = predict_jul11._load_artifact(
                schema4_final_artifact,
                now=predict_jul11._parse_utc("2026-07-11T18:10:00Z"),
            )
            assert loaded_final == synthetic_final

            for missing_key in (
                "decision",
                "capture_method",
                "source",
                "evidence_snapshot",
                "evidence_sha256",
            ):
                missing_weather_data = json.loads(
                    schema4_final_artifact.read_text(encoding="ascii")
                )
                del missing_weather_data["payload"]["context"]["weather"][missing_key]
                missing_weather_data["payload_sha256"] = predict_jul11._payload_sha256(
                    missing_weather_data["payload"]
                )
                missing_weather = tmp / f"missing_weather_{missing_key}.json"
                missing_weather.write_text(
                    json.dumps(missing_weather_data),
                    encoding="ascii",
                )
                try:
                    predict_jul11._load_artifact(
                        missing_weather,
                        now=predict_jul11._parse_utc("2026-07-11T18:10:00Z"),
                    )
                except predict_jul11.ArtifactError as exc:
                    assert "missing required schema-4 weather provenance keys" in str(exc)
                else:
                    raise AssertionError(
                        f"schema-4 artifact accepted without weather key {missing_key}"
                    )

            # A valid schema-4 envelope cannot be relabelled as a QF/SF
            # artifact; those stages remain on schema 3 through SF102.
            wrong_stage_data = json.loads(
                schema4_final_artifact.read_text(encoding="ascii")
            )
            wrong_stage_data["payload"]["fixture"] = artifact_data["payload"][
                "fixture"
            ]
            wrong_stage_data["payload_sha256"] = predict_jul11._payload_sha256(
                wrong_stage_data["payload"]
            )
            wrong_stage = tmp / "schema4_qf_not_permitted.json"
            wrong_stage.write_text(json.dumps(wrong_stage_data), encoding="ascii")
            try:
                predict_jul11._load_artifact(
                    wrong_stage,
                    now=predict_jul11._parse_utc("2026-07-11T18:10:00Z"),
                )
            except predict_jul11.ArtifactError as exc:
                assert "expected schema 3" in str(exc)
            else:
                raise AssertionError("schema-4 artifact was accepted for a QF fixture")

            legacy_weather_row = _weather_row(
                kickoff=synthetic_final.kickoff_at_utc,
                checked="2026-07-11T18:05:00Z",
                decision="heat_mild",
                scale=0.95,
            )
            for field in SCHEMA4_CONTEXT_FIELDS:
                legacy_weather_row.pop(field, None)
            legacy_final_context = tmp / "legacy_final_context.json"
            _write_context(
                legacy_final_context,
                "Norway|England",
                legacy_weather_row,
            )
            legacy_schema3_output = tmp / "legacy_schema3_qf.json"
            accepted_legacy_weather = _invoke(
                _finalize_args(
                    fixture="norway-england",
                    module=first_module,
                    source_tsv=first_tsv,
                    receipt=first_receipt,
                    context=legacy_final_context,
                    artifact=legacy_schema3_output,
                ),
                now="2026-07-11T18:05:00Z",
            )
            assert accepted_legacy_weather[0] == 0, accepted_legacy_weather[2]
            assert json.loads(legacy_schema3_output.read_text(encoding="ascii"))[
                "payload"
            ]["schema_version"] == 3

            invalid_schema4_output = tmp / "invalid_schema4_final.json"
            rejected_legacy_weather = _invoke(
                _finalize_args(
                    fixture=synthetic_final.slug,
                    module=first_module,
                    source_tsv=first_tsv,
                    receipt=first_receipt,
                    context=legacy_final_context,
                    artifact=invalid_schema4_output,
                ),
                now="2026-07-11T18:05:00Z",
            )
            assert rejected_legacy_weather[0] != 0
            assert "weather_capture_method" in rejected_legacy_weather[2]
            assert not invalid_schema4_output.exists()
        finally:
            predict_jul11.FIXTURES.pop(synthetic_final.slug, None)

        # SF-specific fail-closed cases must publish neither an artifact nor
        # official probabilities.
        missing_market_context = tmp / "sf_missing_market.json"
        missing_market_row = dict(france_row)
        missing_market_row["market_odds"] = None
        _write_context(missing_market_context, "France|Spain", missing_market_row)
        missing_market_artifact = tmp / "sf_missing_market.final.json"
        missing_market = _invoke(
            _finalize_args(
                fixture="france-spain",
                module=sf_module,
                source_tsv=sf_tsv,
                receipt=sf_receipt,
                context=missing_market_context,
                artifact=missing_market_artifact,
            ),
            now="2026-07-14T16:05:00Z",
        )
        assert missing_market[0] != 0
        assert "requires market_odds" in missing_market[2]
        assert "OFFICIAL" not in missing_market[1]
        assert not missing_market_artifact.exists()

        invalid_roof_context = tmp / "sf_invalid_roof.json"
        invalid_roof_row = dict(france_row)
        invalid_roof_row["roof_status"] = "open"
        _write_context(invalid_roof_context, "France|Spain", invalid_roof_row)
        invalid_roof_artifact = tmp / "sf_invalid_roof.final.json"
        invalid_roof = _invoke(
            _finalize_args(
                fixture="france-spain",
                module=sf_module,
                source_tsv=sf_tsv,
                receipt=sf_receipt,
                context=invalid_roof_context,
                artifact=invalid_roof_artifact,
            ),
            now="2026-07-14T16:05:00Z",
        )
        assert invalid_roof[0] != 0
        assert "requires roof_status=closed" in invalid_roof[2]
        assert "OFFICIAL" not in invalid_roof[1]
        assert not invalid_roof_artifact.exists()

        wrong_roof_context = tmp / "sf_wrong_roof_fixture.json"
        wrong_roof_row = dict(france_row)
        wrong_roof_row["weather_evidence_fixture_id"] = "2026-SF102-England-Argentina"
        _write_context(wrong_roof_context, "France|Spain", wrong_roof_row)
        wrong_roof_artifact = tmp / "sf_wrong_roof_fixture.final.json"
        wrong_roof = _invoke(
            _finalize_args(
                fixture="france-spain",
                module=sf_module,
                source_tsv=sf_tsv,
                receipt=sf_receipt,
                context=wrong_roof_context,
                artifact=wrong_roof_artifact,
            ),
            now="2026-07-14T16:05:00Z",
        )
        assert wrong_roof[0] != 0
        assert "does not match the selected fixture" in wrong_roof[2]
        assert "OFFICIAL" not in wrong_roof[1]
        assert not wrong_roof_artifact.exists()

        invalid_advance_context = tmp / "sf_invalid_advance.json"
        invalid_advance_row = dict(france_row)
        invalid_advance_row["market_advance_odds"] = [1.0, 2.2]
        _write_context(invalid_advance_context, "France|Spain", invalid_advance_row)
        invalid_advance_artifact = tmp / "sf_invalid_advance.final.json"
        invalid_advance = _invoke(
            _finalize_args(
                fixture="france-spain",
                module=sf_module,
                source_tsv=sf_tsv,
                receipt=sf_receipt,
                context=invalid_advance_context,
                artifact=invalid_advance_artifact,
            ),
            now="2026-07-14T16:05:00Z",
        )
        assert invalid_advance[0] != 0
        assert "official market validation failed" in invalid_advance[2]
        assert "OFFICIAL" not in invalid_advance[1]
        assert not invalid_advance_artifact.exists()

        stale_sf_module, stale_sf_tsv, stale_sf_receipt = _make_elo(
            tmp,
            "sf101_stale",
            "2026-07-13T12:00:00Z",
        )
        stale_elo_artifact = tmp / "sf_stale_elo.final.json"
        stale_elo = _invoke(
            _finalize_args(
                fixture="france-spain",
                module=stale_sf_module,
                source_tsv=stale_sf_tsv,
                receipt=stale_sf_receipt,
                context=france_context,
                artifact=stale_elo_artifact,
            ),
            now="2026-07-14T16:05:00Z",
        )
        assert stale_elo[0] != 0
        assert "stale" in stale_elo[2]
        assert "OFFICIAL" not in stale_elo[1]
        assert not stale_elo_artifact.exists()

        estimated_sf_module, estimated_sf_tsv, estimated_sf_receipt = _make_elo(
            tmp,
            "sf101_estimated",
            "2026-07-14T16:00:00Z",
            estimates=("Spain",),
        )
        estimated_elo_artifact = tmp / "sf_estimated_elo.final.json"
        estimated_elo = _invoke(
            _finalize_args(
                fixture="france-spain",
                module=estimated_sf_module,
                source_tsv=estimated_sf_tsv,
                receipt=estimated_sf_receipt,
                context=france_context,
                artifact=estimated_elo_artifact,
            ),
            now="2026-07-14T16:05:00Z",
        )
        assert estimated_elo[0] != 0
        assert "estimated Elo" in estimated_elo[2]
        assert "OFFICIAL" not in estimated_elo[1]
        assert not estimated_elo_artifact.exists()

        sf_in_qf_mc = _invoke(
            _mc_args(
                artifacts=(france_artifact, argentina_artifact),
                module=mc_module,
                source_tsv=mc_tsv,
                receipt=mc_receipt,
            ),
            now="2026-07-14T16:06:00Z",
        )
        assert sf_in_qf_mc[0] != 0
        assert "exactly one artifact per July 11 QF is required" in sf_in_qf_mc[2]
        assert "PRE-REGISTERED ARTIFACT MC" not in sf_in_qf_mc[1]

        # Final artifacts are create-only: a second run publishes no probability.
        duplicate = _invoke(
            _finalize_args(
                fixture="norway-england",
                module=first_module,
                source_tsv=first_tsv,
                receipt=first_receipt,
                context=norway_context,
                artifact=norway_artifact,
            ),
            now="2026-07-11T18:06:00Z",
        )
        assert duplicate[0] != 0
        assert "will not be overwritten" in duplicate[2]
        assert "OFFICIAL advance" not in duplicate[1]

        kickoff_module, kickoff_tsv, kickoff_receipt = _make_elo(
            tmp,
            "qf99_kickoff",
            "2026-07-11T20:59:00Z",
        )
        post_kickoff_artifact = tmp / "post_kickoff.json"
        post_kickoff = _invoke(
            _finalize_args(
                fixture="norway-england",
                module=kickoff_module,
                source_tsv=kickoff_tsv,
                receipt=kickoff_receipt,
                context=norway_context,
                artifact=post_kickoff_artifact,
            ),
            now="2026-07-11T21:00:00Z",
        )
        assert post_kickoff[0] != 0
        assert "finalization is closed at kickoff" in post_kickoff[2]
        assert not post_kickoff_artifact.exists()

        stale_context = tmp / "stale_context.json"
        _write_context(
            stale_context,
            "Norway|England",
            _weather_row(
                kickoff="2026-07-11T21:00:00Z",
                checked="2026-07-11T14:00:00Z",
                decision="heat_mild",
                scale=0.95,
            ),
        )
        stale_artifact = tmp / "stale.json"
        stale = _invoke(
            _finalize_args(
                fixture="norway-england",
                module=first_module,
                source_tsv=first_tsv,
                receipt=first_receipt,
                context=stale_context,
                artifact=stale_artifact,
            ),
            now="2026-07-11T18:05:00Z",
        )
        assert stale[0] != 0
        assert "evidence is stale" in stale[2]
        assert not stale_artifact.exists()

        future_context = tmp / "future_context.json"
        _write_context(
            future_context,
            "Norway|England",
            _weather_row(
                kickoff="2026-07-11T21:00:00Z",
                checked="2026-07-11T18:06:00Z",
                decision="heat_mild",
                scale=0.95,
            ),
        )
        future = _invoke(
            _finalize_args(
                fixture="norway-england",
                module=first_module,
                source_tsv=first_tsv,
                receipt=first_receipt,
                context=future_context,
                artifact=tmp / "future.json",
            ),
            now="2026-07-11T18:05:00Z",
        )
        assert future[0] != 0
        assert "later than run time" in future[2]

        # Changing a sealed value without updating the canonical hash is rejected.
        tampered_data = json.loads(norway_artifact.read_text(encoding="ascii"))
        tampered_data["payload"]["official"]["advance_home"] = 0.0
        tampered = tmp / "tampered.json"
        tampered.write_text(json.dumps(tampered_data), encoding="ascii")
        rejected_mc = _invoke(
            _mc_args(
                artifacts=(tampered, argentina_artifact),
                module=mc_module,
                source_tsv=mc_tsv,
                receipt=mc_receipt,
            ),
            now="2026-07-11T22:10:00Z",
        )
        assert rejected_mc[0] != 0
        assert "artifact hash mismatch" in rejected_mc[2]
        assert "PRE-REGISTERED ARTIFACT MC" not in rejected_mc[1]

        # Re-sealing cannot make an advancement probability that violates the
        # frozen 0.6/0.4 blend valid.
        inconsistent_data = json.loads(norway_artifact.read_text(encoding="ascii"))
        inconsistent_data["payload"]["official"]["advance_home"] = 0.0
        inconsistent_data["payload_sha256"] = predict_jul11._payload_sha256(
            inconsistent_data["payload"]
        )
        inconsistent = tmp / "inconsistent_blend.json"
        inconsistent.write_text(json.dumps(inconsistent_data), encoding="ascii")
        rejected_blend = _invoke(
            _mc_args(
                artifacts=(inconsistent, argentina_artifact),
                module=mc_module,
                source_tsv=mc_tsv,
                receipt=mc_receipt,
            ),
            now="2026-07-11T22:10:00Z",
        )
        assert rejected_blend[0] != 0
        assert "does not match frozen w=0.6 ensemble" in rejected_blend[2]

        future_artifact_data = json.loads(argentina_artifact.read_text(encoding="ascii"))
        future_artifact_data["payload"]["generated_at_utc"] = "2026-07-11T22:11:00Z"
        future_artifact_data["payload_sha256"] = predict_jul11._payload_sha256(
            future_artifact_data["payload"]
        )
        future_artifact = tmp / "future_generated_artifact.json"
        future_artifact.write_text(json.dumps(future_artifact_data), encoding="ascii")
        future_mc = _invoke(
            _mc_args(
                artifacts=(norway_artifact, future_artifact),
                module=mc_module,
                source_tsv=mc_tsv,
                receipt=mc_receipt,
            ),
            now="2026-07-11T22:10:00Z",
        )
        assert future_mc[0] != 0
        assert "generated after the MC run time" in future_mc[2]
        assert "PRE-REGISTERED ARTIFACT MC" not in future_mc[1]

        invalid_schema_data = json.loads(norway_artifact.read_text(encoding="ascii"))
        invalid_schema_data["payload"]["schema_version"] = True
        invalid_schema_data["payload_sha256"] = predict_jul11._payload_sha256(
            invalid_schema_data["payload"]
        )
        invalid_schema = tmp / "invalid_schema_type.json"
        invalid_schema.write_text(json.dumps(invalid_schema_data), encoding="ascii")
        invalid_schema_mc = _invoke(
            _mc_args(
                artifacts=(invalid_schema, argentina_artifact),
                module=mc_module,
                source_tsv=mc_tsv,
                receipt=mc_receipt,
            ),
            now="2026-07-11T22:10:00Z",
        )
        assert invalid_schema_mc[0] != 0
        assert "invalid schema_version type" in invalid_schema_mc[2]

        # Previously published v3 artifacts remain readable and retain their
        # direct-Elo provenance requirement; schema 4 weather fields are not
        # applied retroactively.
        legacy_v3_data = json.loads(norway_artifact.read_text(encoding="ascii"))
        legacy_v3_data["payload"]["schema_version"] = 3
        for field in SCHEMA4_WEATHER_FIELDS:
            legacy_v3_data["payload"]["context"]["weather"].pop(field, None)
        legacy_v3_data["payload_sha256"] = predict_jul11._payload_sha256(
            legacy_v3_data["payload"]
        )
        legacy_v3 = tmp / "legacy_v3_qf99.json"
        legacy_v3.write_text(json.dumps(legacy_v3_data), encoding="ascii")
        legacy_v3_mc = _invoke(
            _mc_args(
                artifacts=(legacy_v3, argentina_artifact),
                module=mc_module,
                source_tsv=mc_tsv,
                receipt=mc_receipt,
            ),
            now="2026-07-11T22:10:00Z",
        )
        assert legacy_v3_mc[0] == 0, legacy_v3_mc[2]

        invalid_v3_data = json.loads(legacy_v3.read_text(encoding="ascii"))
        del invalid_v3_data["payload"]["elo_provenance"]["receipt_sha256"]
        invalid_v3_data["payload_sha256"] = predict_jul11._payload_sha256(
            invalid_v3_data["payload"]
        )
        invalid_v3 = tmp / "invalid_v3_qf99.json"
        invalid_v3.write_text(json.dumps(invalid_v3_data), encoding="ascii")
        invalid_v3_mc = _invoke(
            _mc_args(
                artifacts=(invalid_v3, argentina_artifact),
                module=mc_module,
                source_tsv=mc_tsv,
                receipt=mc_receipt,
            ),
            now="2026-07-11T22:10:00Z",
        )
        assert invalid_v3_mc[0] != 0
        assert "invalid Elo receipt SHA-256" in invalid_v3_mc[2]

        # Previously published generic v2 artifacts remain valid MC inputs; the
        # direct-capture fields are required only on v3+ artifacts.
        direct_provenance_fields = (
            "provenance_contract",
            "capture_method",
            "receipt_sha256",
            "retained_receipt_name",
            "body_byte_count",
        )
        legacy_v2_data = json.loads(norway_artifact.read_text(encoding="ascii"))
        legacy_v2_data["payload"]["schema_version"] = 2
        for field in direct_provenance_fields:
            legacy_v2_data["payload"]["elo_provenance"].pop(field)
        legacy_v2_data["payload_sha256"] = predict_jul11._payload_sha256(
            legacy_v2_data["payload"]
        )
        legacy_v2 = tmp / "legacy_v2_qf99.json"
        legacy_v2.write_text(json.dumps(legacy_v2_data), encoding="ascii")
        legacy_v2_mc = _invoke(
            _mc_args(
                artifacts=(legacy_v2, argentina_artifact),
                module=mc_module,
                source_tsv=mc_tsv,
                receipt=mc_receipt,
            ),
            now="2026-07-11T22:10:00Z",
        )
        assert legacy_v2_mc[0] == 0, legacy_v2_mc[2]
        assert "PRE-REGISTERED ARTIFACT MC" in legacy_v2_mc[1]

        # Previously published QF v1 artifacts remain valid too. The old schema
        # did not carry a stage because it was QF-specific by definition.
        legacy_qf99_data = json.loads(norway_artifact.read_text(encoding="ascii"))
        legacy_qf99_data["payload"]["schema_version"] = 1
        legacy_qf99_data["payload"]["artifact_type"] = "pre_registered_qf_prediction"
        for field in direct_provenance_fields:
            legacy_qf99_data["payload"]["elo_provenance"].pop(field)
        del legacy_qf99_data["payload"]["fixture"]["stage"]
        del legacy_qf99_data["payload"]["market"]["odds_advance"]
        del legacy_qf99_data["payload"]["market"]["advance_margin"]
        legacy_qf99_data["payload"]["market"]["advance_method"] = (
            "wdl_90_plus_model_elo_draw_resolution"
        )
        legacy_qf99_data["payload_sha256"] = predict_jul11._payload_sha256(
            legacy_qf99_data["payload"]
        )
        legacy_qf99 = tmp / "legacy_qf99.json"
        legacy_qf99.write_text(json.dumps(legacy_qf99_data), encoding="ascii")
        legacy_mc = _invoke(
            _mc_args(
                artifacts=(legacy_qf99, argentina_artifact),
                module=mc_module,
                source_tsv=mc_tsv,
                receipt=mc_receipt,
            ),
            now="2026-07-11T22:10:00Z",
        )
        assert legacy_mc[0] == 0, legacy_mc[2]
        assert "PRE-REGISTERED ARTIFACT MC" in legacy_mc[1]

        # Valid sealed artifacts with forced QF values prove MC consumes stored
        # advancement probabilities rather than recalculating those fixtures.
        forced_paths = []
        for source, name in (
            (norway_artifact, "forced_qf99.json"),
            (argentina_artifact, "forced_qf100.json"),
        ):
            data = json.loads(source.read_text(encoding="ascii"))
            data["payload"]["model"]["advance_home"] = 1.0
            data["payload"]["market"]["advance_home"] = 1.0
            data["payload"]["official"]["advance_home"] = 1.0
            data["payload_sha256"] = predict_jul11._payload_sha256(data["payload"])
            forced = tmp / name
            forced.write_text(json.dumps(data), encoding="ascii")
            forced_paths.append(forced)
        mc = _invoke(
            _mc_args(
                artifacts=(forced_paths[0], forced_paths[1]),
                module=mc_module,
                source_tsv=mc_tsv,
                receipt=mc_receipt,
            ),
            now="2026-07-11T22:10:00Z",
        )
        assert mc[0] == 0, mc[2]
        assert "PRE-REGISTERED ARTIFACT MC" in mc[1]
        assert "not recalculated or republished" in mc[1]
        assert "Live match state is not incorporated" in mc[1]
        norway_line = next(line for line in mc[1].splitlines() if line.startswith("Norway"))
        argentina_line = next(line for line in mc[1].splitlines() if line.startswith("Argentina"))
        assert norway_line.rstrip().endswith("100.0%"), norway_line
        assert argentina_line.rstrip().endswith("100.0%"), argentina_line
        assert "OFFICIAL advance" not in mc[1]

        # Restore write bits so TemporaryDirectory cleanup is portable.
        os.chmod(norway_artifact, 0o600)
        os.chmod(argentina_artifact, 0o600)
        os.chmod(france_artifact, 0o600)
        os.chmod(england_artifact, 0o600)

    print("July 11 prediction runner tests passed.")


if __name__ == "__main__":
    main()
