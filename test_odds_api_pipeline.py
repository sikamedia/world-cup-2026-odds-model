#!/usr/bin/env python3
"""Regression checks for Odds API enrichment and pipeline integration."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from match_context import load_context_file


ROOT = Path(__file__).resolve().parent


def _outcome(name: str, price: float) -> dict[str, object]:
    return {"name": name, "price": price}


def _bookmaker(key: str, outcomes: list[dict[str, object]], *, title: str | None = None, market_key: str = "h2h") -> dict[str, object]:
    return {
        "key": key,
        "title": title or key,
        "markets": [{"key": market_key, "outcomes": outcomes}],
    }


def _event(
    home_team: str,
    away_team: str,
    outcomes: list[dict[str, object]],
    *,
    event_id: str,
    commence_time: str,
    bookmakers: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "id": event_id,
        "commence_time": commence_time,
        "home_team": home_team,
        "away_team": away_team,
        "bookmakers": bookmakers or [_bookmaker("pinnacle", outcomes)],
    }


def _run(cmd: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.stdout + "\n" + proc.stderr)
    return proc


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return {f"{row['home']}|{row['away']}": row for row in rows}


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Standalone enrichment + import regression.
        fixture_csv = tmp / "odds_fixture.csv"
        fixture_json = tmp / "odds_fixture.json"
        enriched_csv = tmp / "odds_enriched.csv"
        imported_json = tmp / "odds_imported.json"

        fixture_csv.write_text(
            "\n".join(
                [
                    "home,away,market_method,market_confidence,notes",
                    "United States,Turkey,proportional,1.0,manual row",
                    "Curaçao,Côte d'Ivoire,proportional,1.0,alias row",
                    "France,Argentina,proportional,1.0,missing row",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        _write_json(
            fixture_json,
            [
                _event(
                    "Turkey",
                    "United States",
                    [_outcome("Turkey", 5.00), _outcome("Draw", 3.60), _outcome("United States", 1.70)],
                    event_id="evt-usa-tur",
                    commence_time="2026-06-01T00:00:00Z",
                    bookmakers=[
                        _bookmaker("somebook", [], market_key="spreads"),
                        _bookmaker(
                            "altfair",
                            [_outcome("Turkey", 5.00), _outcome("Draw", 3.60), _outcome("United States", 1.70)],
                            title="Alt Fair",
                        ),
                    ],
                ),
                _event(
                    "Curaçao",
                    "Côte d'Ivoire",
                    [_outcome("Curaçao", 2.90), _outcome("Draw", 3.20), _outcome("Côte d'Ivoire", 2.45)],
                    event_id="evt-cur-iv",
                    commence_time="2026-06-01T01:00:00Z",
                    bookmakers=[
                        _bookmaker(
                            "pinnacle",
                            [_outcome("Curaçao", 2.90), _outcome("Draw", 3.20), _outcome("Côte d'Ivoire", 2.45)],
                            title="Pinnacle",
                        ),
                    ],
                ),
            ],
        )

        _run(
            [
                sys.executable,
                "fetch_the_odds_api.py",
                "--fixture-csv",
                str(fixture_csv),
                "--fixture-json",
                str(fixture_json),
                "--output-csv",
                str(enriched_csv),
            ]
        )

        enriched = _read_csv(enriched_csv)
        assert enriched["United States|Turkey"]["odds_source_status"] == "matched"
        assert enriched["United States|Turkey"]["odds_bookmaker"] == "altfair"
        assert float(enriched["United States|Turkey"]["market_confidence"]) == 0.75
        assert enriched["United States|Turkey"]["market_odds"] == "1.7/3.6/5.0"
        assert enriched["Curaçao|Côte d'Ivoire"]["odds_bookmaker"] == "pinnacle"
        assert enriched["Curaçao|Côte d'Ivoire"]["market_odds"] == "2.9/3.2/2.45"
        assert enriched["France|Argentina"]["odds_source_status"] == "missing"
        assert enriched["France|Argentina"]["market_odds"] == ""

        _run(
            [
                sys.executable,
                "import_context_csv.py",
                "--input",
                str(enriched_csv),
                "--output",
                str(imported_json),
            ]
        )
        contexts = load_context_file(imported_json)
        assert contexts["USA|Turkiye"].market_odds == (1.7, 3.6, 5.0)
        assert contexts["Curacao|Cote dIvoire"].market_odds == (2.9, 3.2, 2.45)
        assert contexts["France|Argentina"].market_odds is None

        # End-to-end pipeline regression.
        pipeline_json = tmp / "pipeline_odds.json"
        pipeline_output = tmp / "pipeline_output.json"
        pipeline_events = [
            _event(
                "Turkey",
                "United States",
                [_outcome("Turkey", 5.20), _outcome("Draw", 3.55), _outcome("United States", 1.66)],
                event_id="evt-p1",
                commence_time="2026-06-25T00:00:00Z",
            ),
            _event(
                "Paraguay",
                "Australia",
                [_outcome("Paraguay", 2.36), _outcome("Draw", 3.22), _outcome("Australia", 2.90)],
                event_id="evt-p2",
                commence_time="2026-06-25T01:00:00Z",
            ),
            _event(
                "Curaçao",
                "Côte d'Ivoire",
                [_outcome("Curaçao", 3.05), _outcome("Draw", 3.12), _outcome("Côte d'Ivoire", 2.25)],
                event_id="evt-p3",
                commence_time="2026-06-25T02:00:00Z",
            ),
            _event(
                "Germany",
                "Ecuador",
                [_outcome("Germany", 1.95), _outcome("Draw", 3.45), _outcome("Ecuador", 3.80)],
                event_id="evt-p4",
                commence_time="2026-06-25T03:00:00Z",
            ),
            _event(
                "Japan",
                "Sweden",
                [_outcome("Japan", 2.12), _outcome("Draw", 3.30), _outcome("Sweden", 3.25)],
                event_id="evt-p5",
                commence_time="2026-06-25T04:00:00Z",
            ),
            _event(
                "Netherlands",
                "Tunisia",
                [_outcome("Netherlands", 1.58), _outcome("Draw", 4.00), _outcome("Tunisia", 5.40)],
                event_id="evt-p6",
                commence_time="2026-06-25T05:00:00Z",
            ),
        ]
        _write_json(pipeline_json, pipeline_events)

        proc = subprocess.run(
            [
                sys.executable,
                "run_context_pipeline.py",
                "--fixture-source",
                "jun25",
                "--market-source",
                "odds-api",
                "--odds-api-fixture-json",
                str(pipeline_json),
                "--output-json",
                str(pipeline_output),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise SystemExit(proc.stdout + "\n" + proc.stderr)

        assert "Odds API enrichment complete" in proc.stdout
        assert "Selected prediction profile:" in proc.stdout
        assert "Pipeline complete:" in proc.stdout
        assert pipeline_output.exists()

        data = json.loads(pipeline_output.read_text(encoding="utf-8"))
        assert data["meta"]["source"] == "odds-api:jun25"
        assert len(data["matches"]) == 6
        assert all(payload["market_odds"] is not None for payload in data["matches"].values())
        assert data["matches"]["USA|Turkiye"]["market_odds"] == [1.66, 3.55, 5.20]
        assert data["matches"]["Curacao|Cote dIvoire"]["market_odds"] == [3.05, 3.12, 2.25]

        print("ODDS_API_PIPELINE_REGRESSION PASS")


if __name__ == "__main__":
    main()
