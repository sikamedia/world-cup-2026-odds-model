#!/usr/bin/env python3
"""End-to-end regression for the context pipeline CLI."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    tmp = Path(tempfile.gettempdir())
    input_csv = tmp / "context_pipeline_input.csv"
    base_json = tmp / "context_pipeline_base.json"
    output_json = tmp / "context_pipeline_output.json"
    weather_points_source = "https://api.weather.gov/points/38.9072,-77.0369"
    weather_source = "https://api.weather.gov/gridpoints/LWX/97,71/forecast/hourly"
    weather_points_snapshot = json.dumps(
        {
            "id": weather_points_source,
            "properties": {"forecastHourly": weather_source},
        },
        separators=(",", ":"),
    )
    weather_points_sha256 = hashlib.sha256(
        weather_points_snapshot.encode("utf-8")
    ).hexdigest()
    weather_snapshot = json.dumps(
        {
            "properties": {
                "updateTime": "2026-06-26T16:00:00Z",
                "generatedAt": "2026-06-26T16:30:00Z",
                "periods": [
                    {
                        "startTime": "2026-06-26T20:00:00Z",
                        "endTime": "2026-06-26T21:00:00Z",
                    }
                ],
            }
        },
        separators=(",", ":"),
    )
    weather_sha256 = hashlib.sha256(weather_snapshot.encode("utf-8")).hexdigest()

    input_csv.write_text(
        "\n".join(
            [
                "home,away,market_home,market_draw,market_away,market_advance_odds,market_confidence",
                "United States,Turkey,1.65,3.60,5.50,1.75/2.15,0.8",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    base_json.write_text(
        json.dumps(
            {
                "meta": {
                    "source": "pipeline-base",
                    "generated_at_utc": "2026-06-26T00:00:00+00:00",
                },
                "matches": {
                    "USA|Turkiye": {
                        "market_odds": [1.70, 3.55, 5.10],
                        "market_advance_odds": [1.80, 2.10],
                        "market_method": "power",
                        "lineup_home": 0.92,
                        "lineup_away": 1.08,
                        "weather_scale": 0.95,
                        "kickoff_at_utc": "2026-06-26T20:00:00Z",
                        "weather_checked_at_utc": "2026-06-26T17:00:00Z",
                        "weather_forecast_issued_at_utc": "2026-06-26T16:00:00Z",
                        "weather_forecast_valid_at_utc": "2026-06-26T20:00:00Z",
                        "weather_forecast_generated_at_utc": "2026-06-26T16:30:00Z",
                        "weather_source": weather_source,
                        "weather_evidence_type": "hourly",
                        "weather_decision": "heat_mild",
                        "weather_evidence_snapshot": weather_snapshot,
                        "weather_evidence_sha256": weather_sha256,
                        "weather_capture_method": "workspace_web_fetch",
                        "weather_points_source": weather_points_source,
                        "weather_points_evidence_snapshot": weather_points_snapshot,
                        "weather_points_evidence_sha256": weather_points_sha256,
                        "market_confidence": 0.7,
                        "source_key": "manual base key",
                        "notes": "base notes",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "run_context_pipeline.py",
            "--input-csv",
            str(input_csv),
            "--base-json",
            str(base_json),
            "--output-json",
            str(output_json),
        ],
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        check=False,
    )

    if proc.returncode != 0:
        raise SystemExit(proc.stdout + "\n" + proc.stderr)

    out = proc.stdout
    assert "Selected prediction profile:" in out
    assert "Pipeline complete:" in out
    assert output_json.exists()

    data = json.loads(output_json.read_text(encoding="utf-8"))
    merged = data["matches"]["USA|Turkiye"]
    assert merged["market_odds"] == [1.65, 3.60, 5.50]
    assert merged["market_advance_odds"] == [1.75, 2.15]
    assert merged["market_method"] == "power"
    assert merged["lineup_home"] == 0.92
    assert merged["lineup_away"] == 1.08
    assert merged["weather_scale"] == 0.95
    assert merged["weather_capture_method"] == "workspace_web_fetch"
    assert merged["weather_points_source"] == weather_points_source
    assert merged["weather_points_evidence_snapshot"] == weather_points_snapshot
    assert merged["weather_points_evidence_sha256"] == weather_points_sha256
    assert merged["weather_forecast_generated_at_utc"] == "2026-06-26T16:30:00Z"
    assert merged["market_confidence"] == 0.8
    assert merged["source_key"] == "manual base key"
    assert merged["notes"] == "base notes"

    print("CONTEXT_PIPELINE_REGRESSION PASS")


if __name__ == "__main__":
    main()
