#!/usr/bin/env python3
"""Regression checks for prediction-side Elo provenance and fail-closed use."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

from elo_snapshot import EloSnapshotError, OFFICIAL_ELO_SOURCE, load_elo_snapshot


ROOT = Path(__file__).resolve().parent
NOW = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
VALID_HASH = "a" * 64


def _snapshot_text(
    *,
    fetched_at: datetime = NOW - timedelta(hours=1),
    source: str = OFFICIAL_ELO_SOURCE,
    source_sha256: str = VALID_HASH,
    estimates: tuple[str, ...] = (),
    include_switzerland: bool = True,
    argentina_rating: int = 2156,
    switzerland_rating: int = 1949,
) -> str:
    ratings = {f'"Argentina": {argentina_rating}'}
    if include_switzerland:
        ratings.add(f'"Switzerland": {switzerland_rating}')
    return "\n".join(
        [
            f"ELO_CURRENT = {{{', '.join(sorted(ratings))}}}",
            f"FETCHED_AT_UTC = {fetched_at.isoformat()!r}",
            f"SOURCE = {source!r}",
            f"SOURCE_SHA256 = {source_sha256!r}",
            f"ESTIMATES = {list(estimates)!r}",
            "",
        ]
    )


def _expect_error(path: Path, message: str, **kwargs) -> None:
    try:
        load_elo_snapshot(path, now_utc=NOW, **kwargs)
    except EloSnapshotError as exc:
        assert message in str(exc), str(exc)
    else:
        raise AssertionError(f"expected EloSnapshotError containing {message!r}")


def _world_tsv() -> str:
    """Minimal real-format fixture accepted by the production parser."""

    codes = [
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
        for rank, (code, rating) in enumerate(codes, start=1)
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        fresh = tmp / "fresh.py"
        fresh.write_text(_snapshot_text(), encoding="utf-8")
        loaded = load_elo_snapshot(
            fresh,
            required_teams=["Argentina", "Switzerland"],
            max_age_hours=24,
            now_utc=NOW,
        )
        assert loaded.ratings["Argentina"] == 2156
        assert loaded.fetched_at_utc == NOW - timedelta(hours=1)

        stale = tmp / "stale.py"
        stale.write_text(
            _snapshot_text(fetched_at=NOW - timedelta(hours=24, seconds=1)),
            encoding="utf-8",
        )
        _expect_error(stale, "stale", required_teams=["Argentina"])

        missing = tmp / "missing.py"
        missing.write_text(_snapshot_text(include_switzerland=False), encoding="utf-8")
        _expect_error(missing, "missing current Elo", required_teams=["Switzerland"])

        estimated = tmp / "estimated.py"
        estimated.write_text(
            _snapshot_text(estimates=("Switzerland",)), encoding="utf-8"
        )
        _expect_error(estimated, "estimated Elo", required_teams=["Switzerland"])

        wrong_source = tmp / "wrong_source.py"
        wrong_source.write_text(
            _snapshot_text(source="https://example.com/World.tsv"), encoding="utf-8"
        )
        _expect_error(wrong_source, "SOURCE must be exactly")

        invalid_hash = tmp / "invalid_hash.py"
        invalid_hash.write_text(_snapshot_text(source_sha256="not-a-hash"), encoding="utf-8")
        _expect_error(invalid_hash, "SOURCE_SHA256")
        _expect_error(
            fresh,
            "SHA-256 mismatch",
            expected_source_sha256="b" * 64,
        )

        naive_time = tmp / "naive_time.py"
        naive_time.write_text(
            _snapshot_text(fetched_at=datetime(2026, 7, 10, 11, 0)),
            encoding="utf-8",
        )
        _expect_error(naive_time, "timezone offset")

        future_time = tmp / "future.py"
        future_time.write_text(
            _snapshot_text(fetched_at=NOW + timedelta(minutes=1)),
            encoding="utf-8",
        )
        _expect_error(future_time, "in the future", required_teams=["Argentina"])

        tsv = tmp / "World.tsv"
        tsv.write_text(_world_tsv(), encoding="utf-8")
        tsv_sha256 = hashlib.sha256(tsv.read_bytes()).hexdigest()
        generated = tmp / "elo_current_latest.py"

        unstamped_output = tmp / "unstamped.py"
        unstamped_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "fetch_elo_current.py"),
                "--tsv",
                str(tsv),
                "--out",
                str(unstamped_output),
            ],
            cwd=tmp,
            capture_output=True,
            text=True,
            check=False,
        )
        assert unstamped_proc.returncode != 0
        assert "--fetched-at-utc" in unstamped_proc.stderr
        assert not unstamped_output.exists()

        generated_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "fetch_elo_current.py"),
                "--tsv",
                str(tsv),
                "--out",
                str(generated),
                "--required-team",
                "Argentina",
                "--required-team",
                "Switzerland",
                "--fetched-at-utc",
                "2026-07-10T11:00:00Z",
            ],
            cwd=tmp,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generated_proc.returncode == 0, generated_proc.stderr
        emitted = runpy.run_path(str(generated))
        assert emitted["FETCHED_AT_UTC"] == "2026-07-10T11:00:00Z"
        assert emitted["SOURCE"] == OFFICIAL_ELO_SOURCE
        assert emitted["SOURCE_SHA256"] == tsv_sha256
        assert emitted["ESTIMATES"] == []
        assert emitted["FETCHED"] == "2026-07-10"
        assert emitted["FETCHED_BASE"] == "2026-07-10"
        load_elo_snapshot(
            generated,
            required_teams=["Argentina", "Switzerland"],
            now_utc=NOW,
            expected_source_sha256=tsv_sha256,
            source_tsv=tsv,
        )

        changed_tsv = tmp / "changed_World.tsv"
        changed_tsv.write_text(
            _world_tsv().replace("\tAR\t2156\n", "\tAR\t2155\n"),
            encoding="utf-8",
        )
        _expect_error(
            generated,
            "SHA-256 mismatch",
            required_teams=["Argentina"],
            source_tsv=changed_tsv,
        )

        handwritten = tmp / "handwritten.py"
        handwritten.write_text(
            _snapshot_text(source_sha256=tsv_sha256, argentina_rating=999),
            encoding="utf-8",
        )
        _expect_error(
            handwritten,
            "current Elo mismatch for Argentina",
            required_teams=["Argentina", "Switzerland"],
            source_tsv=tsv,
        )

        unparseable_tsv = tmp / "unparseable_World.tsv"
        unparseable_tsv.write_text("not an official World.tsv\n", encoding="utf-8")
        unparseable_module = tmp / "unparseable_source.py"
        unparseable_module.write_text(
            _snapshot_text(
                source_sha256=hashlib.sha256(unparseable_tsv.read_bytes()).hexdigest()
            ),
            encoding="utf-8",
        )
        _expect_error(
            unparseable_module,
            "cannot parse World.tsv",
            required_teams=["Argentina"],
            source_tsv=unparseable_tsv,
        )

        rejected_output = tmp / "must_not_exist.py"
        missing_team_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "fetch_elo_current.py"),
                "--tsv",
                str(tsv),
                "--out",
                str(rejected_output),
                "--required-team",
                "Scotland",
                "--fetched-at-utc",
                "2026-07-10T11:00:00Z",
            ],
            cwd=tmp,
            capture_output=True,
            text=True,
            check=False,
        )
        assert missing_team_proc.returncode != 0
        assert "Scotland" in missing_team_proc.stderr
        assert not rejected_output.exists()

        if not (ROOT / "generate_paper_signals.py").is_file():
            print("Elo provenance parser/helper tests passed (paper integration not bundled).")
            return

        context = tmp / "context.json"
        weather_snapshot = "synthetic kickoff-hour forecast"
        runtime_now = datetime.now(timezone.utc).replace(microsecond=0)
        kickoff_at = runtime_now + timedelta(hours=2)
        checked_at = runtime_now - timedelta(minutes=1)
        issued_at = runtime_now - timedelta(minutes=2)
        context.write_text(
            json.dumps(
                {
                    "matches": {
                        "Argentina|Switzerland": {
                            "market_odds": [1.8, 3.5, 4.5],
                            "market_method": "proportional",
                            "weather_scale": 1.0,
                            "kickoff_at_utc": kickoff_at.isoformat(),
                            "weather_checked_at_utc": checked_at.isoformat(),
                            "weather_forecast_issued_at_utc": issued_at.isoformat(),
                            "weather_forecast_valid_at_utc": kickoff_at.isoformat(),
                            "weather_source": "https://weather.example/hourly",
                            "weather_evidence_type": "hourly",
                            "weather_decision": "none",
                            "weather_evidence_snapshot": weather_snapshot,
                            "weather_evidence_sha256": hashlib.sha256(
                                weather_snapshot.encode("utf-8")
                            ).hexdigest(),
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        runtime_tsv = tmp / "runtime_World.tsv"
        runtime_tsv.write_text(_world_tsv(), encoding="utf-8")
        runtime_sha256 = hashlib.sha256(runtime_tsv.read_bytes()).hexdigest()
        estimated_runtime = tmp / "estimated_runtime.py"
        estimated_runtime.write_text(
            _snapshot_text(
                fetched_at=datetime.now(timezone.utc),
                source_sha256=runtime_sha256,
                estimates=("Switzerland",),
            ),
            encoding="utf-8",
        )
        signals = tmp / "signals.csv"
        signal_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "generate_paper_signals.py"),
                "--context-file",
                str(context),
                "--output-csv",
                str(signals),
                "--date",
                "2026-07-10",
                "--stage",
                "QF",
                "--elo-module",
                str(estimated_runtime),
                "--elo-source-tsv",
                str(runtime_tsv),
                "--max-odds-age-minutes",
                "0",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert signal_proc.returncode != 0
        assert "estimated Elo" in signal_proc.stderr
        assert not signals.exists()

        fresh_runtime = tmp / "fresh_runtime.py"
        fresh_runtime.write_text(
            _snapshot_text(
                fetched_at=datetime.now(timezone.utc),
                source_sha256=runtime_sha256,
            ),
            encoding="utf-8",
        )
        success_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "generate_paper_signals.py"),
                "--context-file",
                str(context),
                "--output-csv",
                str(signals),
                "--date",
                "2026-07-10",
                "--stage",
                "QF",
                "--elo-module",
                str(fresh_runtime),
                "--elo-source-tsv",
                str(runtime_tsv),
                "--max-odds-age-minutes",
                "0",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert success_proc.returncode == 0, success_proc.stderr
        assert signals.exists()

        # Current-Elo official paths may not apply a fixture CSV's legacy heat
        # override on top of an auditable context decision, even when that
        # decision is the neutral scale=1.00 case.
        legacy_fixture = tmp / "legacy_heat_fixture.csv"
        legacy_fixture.write_text(
            "home,away,heat\nArgentina,Switzerland,severe\n",
            encoding="utf-8",
        )
        legacy_signals = tmp / "legacy_heat_signals.csv"
        legacy_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "generate_paper_signals.py"),
                "--context-file",
                str(context),
                "--fixture-csv",
                str(legacy_fixture),
                "--output-csv",
                str(legacy_signals),
                "--date",
                "2026-07-10",
                "--stage",
                "QF",
                "--elo-module",
                str(fresh_runtime),
                "--elo-source-tsv",
                str(runtime_tsv),
                "--max-odds-age-minutes",
                "0",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert legacy_proc.returncode != 0
        assert "legacy heat=severe conflicts" in legacy_proc.stderr
        assert not legacy_signals.exists()

    print("Elo provenance tests passed.")


if __name__ == "__main__":
    main()
