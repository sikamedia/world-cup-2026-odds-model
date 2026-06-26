#!/usr/bin/env python3
"""End-to-end regression for the context pipeline CLI."""

from __future__ import annotations

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

    input_csv.write_text(
        "\n".join(
            [
                "home,away,market_home,market_draw,market_away,market_confidence",
                "United States,Turkey,1.65,3.60,5.50,0.8",
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
                        "market_method": "power",
                        "lineup_home": 0.92,
                        "lineup_away": 1.08,
                        "weather_scale": 0.95,
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
    assert merged["market_method"] == "power"
    assert merged["lineup_home"] == 0.92
    assert merged["lineup_away"] == 1.08
    assert merged["weather_scale"] == 0.95
    assert merged["market_confidence"] == 0.8
    assert merged["source_key"] == "manual base key"
    assert merged["notes"] == "base notes"

    print("CONTEXT_PIPELINE_REGRESSION PASS")


if __name__ == "__main__":
    main()
