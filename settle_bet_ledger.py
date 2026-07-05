#!/usr/bin/env python3
"""Settle paper-trading ledger rows from confirmed results."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from bet_ledger import normalize_selection, read_ledger, settle_row, write_ledger
from match_context import context_key


def _first_non_empty(row: dict[str, str], keys: tuple[str, ...], default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _actual_selection(row: dict[str, str], market_type: str) -> str:
    explicit = _first_non_empty(
        row,
        ("result", "actual", "actual_selection", "advanced", "actual_advanced", "winner"),
    )
    if explicit:
        token = explicit.strip().upper()
        if token in {"WIN", "LOSS"}:
            raise ValueError("results CSV must contain the actual H/X/A outcome, not win/loss")
        actual = normalize_selection(token)
        if market_type == "advance" and actual == "X":
            raise ValueError("advance result must be H or A, not X")
        return actual

    if market_type == "advance":
        raise ValueError("advance result rows require explicit result/advanced H or A")

    home_goals = _first_non_empty(row, ("home_goals", "hg", "score_home"))
    away_goals = _first_non_empty(row, ("away_goals", "ag", "score_away"))
    if home_goals and away_goals:
        hg, ag = int(float(home_goals)), int(float(away_goals))
        return "H" if hg > ag else ("X" if hg == ag else "A")
    raise ValueError("result rows require result/actual_selection or home_goals+away_goals")


def _closing_odds(row: dict[str, str]) -> float | None:
    raw = _first_non_empty(row, ("closing_odds_decimal", "close_odds", "closing_odds"))
    return float(raw) if raw else None


def _result_key(row: dict[str, str]) -> tuple[str, str, str]:
    market_type = _first_non_empty(row, ("market_type",), "h2h_90") or "h2h_90"
    home = _first_non_empty(row, ("home", "team1", "side1"))
    away = _first_non_empty(row, ("away", "team2", "side2"))
    if not home or not away:
        raw = _first_non_empty(row, ("match", "fixture", "key", "context_key"))
        if "|" not in raw:
            raise ValueError(f"cannot parse result row fixture: {row!r}")
        home, away = raw.split("|", 1)
    canonical = context_key(home, away)
    return canonical, market_type, _first_non_empty(row, ("selection",), "")


def _load_results(path: str | Path) -> dict[tuple[str, str, str], tuple[str, float | None]]:
    results: dict[tuple[str, str, str], tuple[str, float | None]] = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            fixture_key, market_type, selection = _result_key(row)
            actual = _actual_selection(row, market_type)
            close = _closing_odds(row)
            keys = [(fixture_key, market_type, selection)] if selection else [(fixture_key, market_type, "")]
            for key in keys:
                results[key] = (actual, close)
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger-csv", required=True, help="Input paper ledger CSV.")
    ap.add_argument("--results-csv", required=True, help="Confirmed result CSV.")
    ap.add_argument(
        "--output-csv",
        help="Where to write settled ledger. Defaults to overwriting --ledger-csv.",
    )
    args = ap.parse_args()

    rows = read_ledger(args.ledger_csv)
    results = _load_results(args.results_csv)

    settled = 0
    missing = 0
    updated = []
    for row in rows:
        fixture_key = context_key(row["home"], row["away"])
        exact_key = (fixture_key, row["market_type"], row["selection"])
        fallback_key = (fixture_key, row["market_type"], "")
        result = results.get(exact_key) or results.get(fallback_key)
        if result is None:
            if row["status"] == "paper_bet":
                missing += 1
            updated.append(row)
            continue
        actual, close = result
        new_row = settle_row(row, actual, closing_odds_decimal=close)
        if new_row["status"] == "settled" and row["status"] == "paper_bet":
            settled += 1
        updated.append(new_row)

    output = args.output_csv or args.ledger_csv
    write_ledger(output, updated)
    print(f"Settlement complete | settled={settled} | missing_open_paper_bets={missing} | output={output}")
    print("PAPER-ONLY calibration audit. Educational/analytical use only; not "
          "betting advice. / 教育/分析用途，不构成投注建议。")


if __name__ == "__main__":
    main()
