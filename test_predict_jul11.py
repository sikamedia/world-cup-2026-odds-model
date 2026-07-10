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


def _make_elo(tmp: Path, stem: str, fetched_at: str) -> tuple[Path, Path]:
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
    return module, source_tsv


def _weather_row(*, kickoff: str, checked: str, decision: str, scale: float) -> dict:
    snapshot = f"hourly forecast {kickoff} {decision}"
    issued = predict_jul11._parse_utc(checked)  # normalize test fixtures through runner parser
    issued_text = (
        issued.replace(minute=max(0, issued.minute - 1))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    return {
        "market_odds": [2.8, 3.2, 2.5],
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

    print("July 11 prediction runner tests passed.")


if __name__ == "__main__":
    main()
