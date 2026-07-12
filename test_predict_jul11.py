#!/usr/bin/env python3
"""End-to-end checks for July 11 finalization artifacts and bracket MC."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

import predict_jul11


ROOT = Path(__file__).resolve().parent


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
) -> tuple[Path, Path]:
    source_tsv = tmp / f"{stem}_World.tsv"
    module = tmp / f"{stem}_elo.py"
    source_tsv.write_text(_world_tsv(), encoding="utf-8")
    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "fetch_elo_current.py"),
            "--tsv",
            str(source_tsv),
            "--out",
            str(module),
            "--fetched-at-utc",
            fetched_at,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    if estimates:
        text = module.read_text(encoding="utf-8")
        module.write_text(
            text.replace("ESTIMATES = []", f"ESTIMATES = {list(estimates)!r}"),
            encoding="utf-8",
        )
    return module, source_tsv


def _weather_row(
    *,
    kickoff: str,
    checked: str,
    decision: str,
    scale: float,
    advance_odds: tuple[float, float] | None = None,
) -> dict:
    snapshot = f"hourly forecast {kickoff} {decision}"
    issued = predict_jul11._parse_utc(checked)  # normalize test fixtures through runner parser
    issued_text = (
        issued.replace(minute=max(0, issued.minute - 1))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
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
        "weather_source": "https://weather.example/hourly",
        "weather_evidence_type": "hourly",
        "weather_decision": decision,
        "weather_evidence_snapshot": snapshot,
        "weather_evidence_sha256": hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
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
        first_module, first_tsv = _make_elo(tmp, "qf99", "2026-07-11T18:00:00Z")
        second_module, second_tsv = _make_elo(tmp, "qf100", "2026-07-11T22:00:00Z")
        mc_module, mc_tsv = _make_elo(tmp, "mc", "2026-07-11T22:06:00Z")
        sf_module, sf_tsv = _make_elo(tmp, "sf101", "2026-07-14T16:00:00Z")
        sf102_module, sf102_tsv = _make_elo(tmp, "sf102", "2026-07-15T16:00:00Z")

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

        norway_artifact = tmp / "qf99.final.json"
        first = _invoke(
            _finalize_args(
                fixture="norway-england",
                module=first_module,
                source_tsv=first_tsv,
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
        assert artifact_data["payload"]["schema_version"] == 2
        assert artifact_data["payload"]["artifact_type"] == "pre_registered_match_prediction"
        assert artifact_data["payload"]["fixture"]["stage"] == "quarterfinal"

        # Semifinal fixtures use the same fail-closed finalization path and the
        # generic v2 artifact identity without changing the QF-only MC contract.
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
        france_artifact = tmp / "sf101.final.json"
        semifinal = _invoke(
            _finalize_args(
                fixture="france-spain",
                module=sf_module,
                source_tsv=sf_tsv,
                context=france_context,
                artifact=france_artifact,
            ),
            now="2026-07-14T16:05:00Z",
        )
        assert semifinal[0] == 0, semifinal[2]
        assert "France vs Spain" in semifinal[1]
        assert "REVIEW FLAG model-market gap" in semifinal[1]
        semifinal_data = json.loads(france_artifact.read_text(encoding="ascii"))
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
                context=england_context,
                artifact=england_artifact,
            ),
            now="2026-07-15T16:05:00Z",
        )
        assert second_semifinal[0] == 0, second_semifinal[2]
        second_semifinal_data = json.loads(england_artifact.read_text(encoding="ascii"))
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
                context=invalid_advance_context,
                artifact=invalid_advance_artifact,
            ),
            now="2026-07-14T16:05:00Z",
        )
        assert invalid_advance[0] != 0
        assert "official market validation failed" in invalid_advance[2]
        assert "OFFICIAL" not in invalid_advance[1]
        assert not invalid_advance_artifact.exists()

        stale_sf_module, stale_sf_tsv = _make_elo(
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
                context=france_context,
                artifact=stale_elo_artifact,
            ),
            now="2026-07-14T16:05:00Z",
        )
        assert stale_elo[0] != 0
        assert "stale" in stale_elo[2]
        assert "OFFICIAL" not in stale_elo[1]
        assert not stale_elo_artifact.exists()

        estimated_sf_module, estimated_sf_tsv = _make_elo(
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
                context=norway_context,
                artifact=norway_artifact,
            ),
            now="2026-07-11T18:06:00Z",
        )
        assert duplicate[0] != 0
        assert "will not be overwritten" in duplicate[2]
        assert "OFFICIAL advance" not in duplicate[1]

        post_kickoff_artifact = tmp / "post_kickoff.json"
        post_kickoff = _invoke(
            _finalize_args(
                fixture="norway-england",
                module=first_module,
                source_tsv=first_tsv,
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
            ),
            now="2026-07-11T22:10:00Z",
        )
        assert rejected_mc[0] != 0
        assert "artifact hash mismatch" in rejected_mc[2]
        assert "PRE-REGISTERED ARTIFACT MC" not in rejected_mc[1]

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
            ),
            now="2026-07-11T22:10:00Z",
        )
        assert future_mc[0] != 0
        assert "generated after the MC run time" in future_mc[2]
        assert "PRE-REGISTERED ARTIFACT MC" not in future_mc[1]

        # Previously published QF v1 artifacts remain valid MC inputs. The old
        # schema did not carry a stage because it was QF-specific by definition.
        legacy_qf99_data = json.loads(norway_artifact.read_text(encoding="ascii"))
        legacy_qf99_data["payload"]["schema_version"] = 1
        legacy_qf99_data["payload"]["artifact_type"] = "pre_registered_qf_prediction"
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
