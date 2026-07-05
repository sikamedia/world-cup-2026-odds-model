#!/usr/bin/env python3
"""Regression checks for the paper-trading ledger workflow."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from bet_ledger import append_ledger_rows, build_ledger_row, read_ledger, risk_status, write_ledger
from elo_current_jul4 import ELO_CURRENT
from model_stability import KNOCKOUT_LOCKED, predict_match


ROOT = Path(__file__).resolve().parent


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.stdout + "\n" + proc.stderr)
    return proc


def _odds_from_probs(probs: tuple[float, float, float], margin: float = 0.04) -> list[float]:
    return [1.0 / (p * (1.0 + margin)) for p in probs]


def _market_probs_with_edge(
    home: str,
    away: str,
    edge: float = 0.06,
) -> tuple[list[float], str]:
    pred = predict_match(KNOCKOUT_LOCKED, home, away, elo_override=ELO_CURRENT)
    model_probs = [pred.home_prob, pred.draw_prob, pred.away_prob]
    idx = max(range(3), key=lambda i: model_probs[i])
    market_probs = list(model_probs)
    market_probs[idx] -= edge
    for other in range(3):
        if other != idx:
            market_probs[other] += edge / 2.0
    assert min(market_probs) > 0.0
    return _odds_from_probs(tuple(market_probs)), ("H", "X", "A")[idx]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    try:
        predict_match(KNOCKOUT_LOCKED, "France", "Morocco", elo_override={})
    except KeyError:
        pass
    else:
        raise AssertionError("empty elo_override must not fall back to stale snapshot ELO")

    status, reason = risk_status(
        market_type="h2h_90",
        edge_raw=0.08,
        edge_net=0.06,
        market_margin=0.10,
        max_abs_gap=0.08,
    )
    assert status == "no_bet"
    assert "market margin" in reason

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        context_json = tmp / "context.json"
        signals_csv = tmp / "signals.csv"
        ledger_csv = tmp / "ledger.csv"
        settled_csv = tmp / "settled.csv"
        results_csv = tmp / "results.csv"

        france_odds, expected_selection = _market_probs_with_edge("France", "Morocco")
        mexico_pred = predict_match(KNOCKOUT_LOCKED, "Mexico", "England", elo_override=ELO_CURRENT)
        mexico_probs = (mexico_pred.home_prob, mexico_pred.draw_prob, mexico_pred.away_prob)
        payload = {
            "meta": {
                "source": "test",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            "matches": {
                "France|Morocco": {
                    "market_odds": france_odds,
                    "market_method": "proportional",
                    "market_confidence": 1.0,
                    "notes": "synthetic edge row",
                },
                "Mexico|England": {
                    "market_odds": _odds_from_probs(mexico_probs),
                    "market_method": "proportional",
                    "market_confidence": 1.0,
                    "notes": "synthetic no-edge row",
                },
            },
        }
        context_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        _run(
            [
                sys.executable,
                "generate_paper_signals.py",
                "--context-file",
                str(context_json),
                "--output-csv",
                str(signals_csv),
                "--append-ledger",
                str(ledger_csv),
                "--date",
                "2026-07-05",
                "--stage",
                "R16",
                "--max-odds-age-minutes",
                "60",
            ]
        )

        rows = _read_csv(signals_csv)
        assert len(rows) == 2
        paper_rows = [row for row in rows if row["status"] == "paper_bet"]
        assert len(paper_rows) == 1
        paper = paper_rows[0]
        assert paper["selection"] == expected_selection
        assert 0.0 < float(paper["stake_units"]) <= 0.5
        assert float(paper["edge_net"]) >= 0.03

        appended, skipped = append_ledger_rows(ledger_csv, rows)
        assert appended == 0
        assert skipped == len(rows)

        upgrade_csv = tmp / "upgrade.csv"
        old_row = dict(paper)
        old_row["status"] = "no_bet"
        old_row["stake_units"] = "0.00"
        old_row["notes"] = "stale earlier run"
        write_ledger(upgrade_csv, [old_row])
        written, skipped_upgrade = append_ledger_rows(upgrade_csv, [paper])
        upgraded = read_ledger(upgrade_csv)
        assert written == 1
        assert skipped_upgrade == 0
        assert upgraded[0]["status"] == "paper_bet"

        results_csv.write_text(
            "\n".join(
                [
                    "home,away,market_type,result,closing_odds_decimal",
                    f"{paper['home']},{paper['away']},{paper['market_type']},{paper['selection']},{float(paper['odds_decimal']) - 0.10}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        _run(
            [
                sys.executable,
                "settle_bet_ledger.py",
                "--ledger-csv",
                str(ledger_csv),
                "--results-csv",
                str(results_csv),
                "--output-csv",
                str(settled_csv),
            ]
        )
        settled = read_ledger(settled_csv)
        settled_paper = [row for row in settled if row["status"] == "settled"]
        assert len(settled_paper) == 1
        assert settled_paper[0]["result"] == "win"
        assert float(settled_paper[0]["roi"]) > 0.0
        assert float(settled_paper[0]["clv"]) > 0.0

        _run([sys.executable, "evaluate_bet_ledger.py", "--ledger-csv", str(settled_csv)])

        # The shared writer should accept already-normalized settled rows.
        copy_csv = tmp / "copy.csv"
        write_ledger(copy_csv, settled)
        assert len(read_ledger(copy_csv)) == len(settled)

        advance_ledger = tmp / "advance.csv"
        advance_results = tmp / "advance_results.csv"
        advance_row = build_ledger_row(
            date="2026-07-05",
            stage="R16",
            market_type="advance",
            home="France",
            away="Morocco",
            selection="H",
            bookmaker="manual",
            odds_decimal=1.80,
            p_model=0.60,
            p_market=0.55,
            edge_raw=0.05,
            edge_net=0.03,
            stake_units=0.30,
            status="paper_bet",
        )
        write_ledger(advance_ledger, [advance_row])
        advance_results.write_text(
            "\n".join(
                [
                    "home,away,market_type,home_goals,away_goals",
                    "France,Morocco,advance,1,1",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [
                sys.executable,
                "settle_bet_ledger.py",
                "--ledger-csv",
                str(advance_ledger),
                "--results-csv",
                str(advance_results),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode != 0
        assert "advance result rows require explicit" in (proc.stdout + proc.stderr)


if __name__ == "__main__":
    main()
