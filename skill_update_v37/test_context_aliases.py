#!/usr/bin/env python3
"""Regression checks for team alias resolution and context import."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from match_context import context_key, load_context_file


def main() -> None:
    assert context_key("United States", "Turkey") == "USA|Turkiye"
    assert context_key("Côte d'Ivoire", "Curaçao") == "Cote dIvoire|Curacao"

    tmp = Path(tempfile.gettempdir())
    csv_path = tmp / "context_alias_regression.csv"
    json_path = tmp / "context_alias_regression.json"
    base_json = tmp / "context_alias_base.json"
    manual_json = tmp / "context_alias_manual.json"

    csv_path.write_text(
        "\n".join(
            [
                "home,away,market_home,market_draw,market_away,market_method,market_confidence,notes",
                "United States,Turkey,1.65,3.60,5.50,power,0.8,alias csv",
                "Curacao,Cote d'Ivoire,1.30,4.80,9.00,proportional,1.0,accent csv",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        [sys.executable, "import_context_csv.py", "--input", str(csv_path), "--output", str(json_path), "--source-label", "alias-regression"],
        check=True,
    )
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "USA|Turkiye" in data["matches"]
    assert "Curacao|Cote dIvoire" in data["matches"]
    assert data["matches"]["USA|Turkiye"]["market_method"] == "power"
    assert data["matches"]["USA|Turkiye"]["source_key"] == "United States|Turkey"
    assert data["matches"]["Curacao|Cote dIvoire"]["source_key"] == "Curacao|Cote d'Ivoire"

    base_json.write_text(
        json.dumps(
            {
                "meta": {
                    "source": "base-context",
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
    merged_csv = tmp / "context_alias_merge.csv"
    merged_json = tmp / "context_alias_merge.json"
    merged_csv.write_text(
        "\n".join(
            [
                "home,away,market_home,market_draw,market_away,market_confidence",
                "United States,Turkey,1.65,3.60,5.50,0.8",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            "import_context_csv.py",
            "--input",
            str(merged_csv),
            "--base-json",
            str(base_json),
            "--output",
            str(merged_json),
        ],
        check=True,
    )
    merged = json.loads(merged_json.read_text(encoding="utf-8"))
    merged_row = merged["matches"]["USA|Turkiye"]
    assert merged_row["market_odds"] == [1.65, 3.60, 5.50]
    assert merged_row["market_method"] == "power"
    assert merged_row["lineup_home"] == 0.92
    assert merged_row["lineup_away"] == 1.08
    assert merged_row["weather_scale"] == 0.95
    assert merged_row["market_confidence"] == 0.8
    assert merged_row["source_key"] == "manual base key"
    assert merged_row["notes"] == "base notes"

    template_csv = tmp / "context_template.csv"
    subprocess.run(
        [
            sys.executable,
            "create_context_template.py",
            "--source",
            "jun25",
            "--format",
            "csv",
            "--output",
            str(template_csv),
        ],
        check=True,
    )
    template_header = template_csv.read_text(encoding="utf-8").splitlines()[0]
    assert "source_key" in template_header
    assert "market_home" in template_header

    manual_json.write_text(
        json.dumps(
            {
                "matches": {
                    "United States|Turkey": {
                        "market_odds": [1.65, 3.60, 5.50],
                        "market_method": "power",
                        "source_key": "United States|Turkey",
                    },
                    "Côte d'Ivoire|Curaçao": {
                        "market_odds": [1.30, 4.80, 9.00],
                        "source_key": "Côte d'Ivoire|Curaçao",
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    contexts = load_context_file(manual_json)
    assert "USA|Turkiye" in contexts
    assert "Cote dIvoire|Curacao" in contexts
    assert contexts["USA|Turkiye"].market_method == "power"
    assert contexts["USA|Turkiye"].source_key == "United States|Turkey"

    subprocess.run([sys.executable, "validate_context.py", "--context-file", str(json_path)], check=True)
    print("ALIAS_CONTEXT_REGRESSION PASS")


if __name__ == "__main__":
    main()
