#!/usr/bin/env python3
"""Regression checks for competition-state context integration."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from competition_state import competition_state_payload, match_state_from_motivation
from match_context import context_key, load_context_file
from model_stability import STABLE_V35, predict_match


ROOT = Path(__file__).resolve().parent


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.stdout + "\n" + proc.stderr)


def main() -> None:
    tmp = Path(tempfile.gettempdir())
    template_json = tmp / "competition_state_template.json"
    template_csv = tmp / "competition_state_template.csv"
    jun26_template_json = tmp / "competition_state_jun26_template.json"
    jun26_template_csv = tmp / "competition_state_jun26_template.csv"
    jun26_imported_json = tmp / "competition_state_jun26_imported.json"
    imported_json = tmp / "competition_state_imported.json"

    _run(
        [
            sys.executable,
            "create_context_template.py",
            "--source",
            "jun25",
            "--format",
            "json",
            "--output",
            str(template_json),
        ]
    )
    data = json.loads(template_json.read_text(encoding="utf-8"))
    usa_state = data["matches"]["USA|Turkiye"]["competition_state"]
    assert usa_state is not None
    assert usa_state["home"]["mathematical_state"] == "qualified"
    assert usa_state["home"]["rotation_risk"] == "medium"
    assert usa_state["away"]["mathematical_state"] == "eliminated"
    assert usa_state["away"]["rotation_risk"] == "high"

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
    with template_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert "competition_state" in rows[0]
    assert rows[0]["competition_state"].startswith("{")

    _run(
        [
            sys.executable,
            "import_context_csv.py",
            "--input",
            str(template_csv),
            "--output",
            str(imported_json),
        ]
    )
    contexts = load_context_file(imported_json)
    ctx = contexts[context_key("United States", "Turkey")]
    assert ctx.competition_state is not None
    assert ctx.competition_state.home.mathematical_state == "qualified"
    assert ctx.competition_state.away.mathematical_state == "eliminated"

    neutral = predict_match(STABLE_V35, "USA", "Turkiye", host_home=1)
    stateful = predict_match(
        STABLE_V35,
        "USA",
        "Turkiye",
        host_home=1,
        competition_state=ctx.competition_state,
    )
    assert stateful.lambda_home < neutral.lambda_home
    assert stateful.lambda_away < neutral.lambda_away
    assert abs(stateful.lineup_home - 0.97) < 1e-9
    assert abs(stateful.lineup_away - 0.94) < 1e-9

    mustwin_state = competition_state_payload(match_state_from_motivation("normal", "mustwin"))
    mustwin = predict_match(
        STABLE_V35,
        "Paraguay",
        "Australia",
        competition_state=mustwin_state,
    )
    baseline = predict_match(STABLE_V35, "Paraguay", "Australia")
    assert mustwin.lambda_away > baseline.lambda_away
    assert abs(mustwin.lineup_away - 1.0) < 1e-9

    _run([sys.executable, "validate_context.py", "--context-file", str(imported_json)])

    _run(
        [
            sys.executable,
            "create_context_template.py",
            "--source",
            "jun26",
            "--format",
            "json",
            "--output",
            str(jun26_template_json),
        ]
    )
    jun26_data = json.loads(jun26_template_json.read_text(encoding="utf-8"))
    spain_state = jun26_data["matches"]["Spain|Saudi Arabia"]["competition_state"]
    assert spain_state is not None
    assert spain_state["home"]["mathematical_state"] == "qualified"
    assert spain_state["home"]["stake_state"] == "advance"
    assert spain_state["home"]["rotation_risk"] == "medium"
    assert spain_state["away"]["stake_state"] == "mustwin"
    _run([sys.executable, "validate_context.py", "--context-file", str(jun26_template_json)])
    pred_proc = subprocess.run(
        [
            sys.executable,
            "predict_jun26.py",
            "--context-file",
            str(jun26_template_json),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if pred_proc.returncode != 0:
        raise SystemExit(pred_proc.stdout + "\n" + pred_proc.stderr)
    assert "2026 WORLD CUP - June 26 predictions" in pred_proc.stdout
    assert "state: home=alive/mustwin/low" in pred_proc.stdout
    assert "Uruguay" in pred_proc.stdout and "Spain" in pred_proc.stdout

    _run(
        [
            sys.executable,
            "create_context_template.py",
            "--source",
            "jun26",
            "--format",
            "csv",
            "--output",
            str(jun26_template_csv),
        ]
    )
    _run(
        [
            sys.executable,
            "import_context_csv.py",
            "--input",
            str(jun26_template_csv),
            "--output",
            str(jun26_imported_json),
        ]
    )
    jun26_contexts = load_context_file(jun26_imported_json)
    assert jun26_contexts[context_key("Spain", "Saudi Arabia")].competition_state is not None
    print("COMPETITION_STATE_CONTEXT_REGRESSION PASS")


if __name__ == "__main__":
    main()
