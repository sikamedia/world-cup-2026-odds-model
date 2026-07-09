#!/usr/bin/env python3
"""Regression checks for weather-evidence context governance."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def main() -> None:
    tmp = Path(tempfile.gettempdir())

    valid_csv = tmp / "weather_evidence_valid.csv"
    valid_json = tmp / "weather_evidence_valid.json"
    valid_csv.write_text(
        "\n".join(
            [
                "home,away,market_home,market_draw,market_away,weather_scale,kickoff_at_utc,weather_checked_at_utc,weather_source,weather_evidence_type,weather_decision",
                "USA,Paraguay,1.80,3.50,4.80,0.95,2026-07-09T20:00:00+00:00,2026-07-09T18:00:00+00:00,NWS radar,radar,rain_applied",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
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
    valid = json.loads(valid_json.read_text(encoding="utf-8"))
    row = valid["matches"]["USA|Paraguay"]
    assert row["weather_scale"] == 0.95
    assert row["kickoff_at_utc"] == "2026-07-09T20:00:00+00:00"
    assert row["weather_checked_at_utc"] == "2026-07-09T18:00:00+00:00"
    assert row["weather_source"] == "NWS radar"
    assert row["weather_evidence_type"] == "radar"
    assert row["weather_decision"] == "rain_applied"
    valid_check = _run([sys.executable, "validate_context.py", "--context-file", str(valid_json)], check=False)
    assert valid_check.returncode == 0, valid_check.stdout + valid_check.stderr
    assert "rain_applied evidence is stale" not in valid_check.stdout
    assert "rain_applied requires" not in valid_check.stdout

    stale_csv = tmp / "weather_evidence_stale.csv"
    stale_json = tmp / "weather_evidence_stale.json"
    stale_csv.write_text(
        "\n".join(
            [
                "home,away,market_home,market_draw,market_away,weather_scale,kickoff_at_utc,weather_checked_at_utc,weather_source,weather_evidence_type,weather_decision",
                "Australia,Turkiye,2.30,3.20,3.10,0.95,2026-07-09T20:00:00+00:00,2026-07-09T12:00:00+00:00,NWS point forecast,point_forecast,rain_applied",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _run(
        [
            sys.executable,
            "import_context_csv.py",
            "--input",
            str(stale_csv),
            "--output",
            str(stale_json),
        ]
    )
    stale_check = _run(
        [
            sys.executable,
            "validate_context.py",
            "--context-file",
            str(stale_json),
            "--fail-on-warning",
        ],
        check=False,
    )
    assert stale_check.returncode != 0
    assert "rain_applied requires weather_evidence_type hourly, radar, or manual" in stale_check.stdout
    assert "rain_applied evidence is stale" in stale_check.stdout

    template_csv = tmp / "weather_evidence_template.csv"
    _run(
        [
            sys.executable,
            "create_context_template.py",
            "--source",
            "jun25",
            "--format",
            "csv",
            "--output",
            str(template_csv),
        ]
    )
    header = template_csv.read_text(encoding="utf-8").splitlines()[0]
    for field in (
        "kickoff_at_utc",
        "weather_checked_at_utc",
        "weather_source",
        "weather_evidence_type",
        "weather_decision",
    ):
        assert field in header

    print("WEATHER_EVIDENCE_REGRESSION PASS")


if __name__ == "__main__":
    main()
