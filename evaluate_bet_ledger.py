#!/usr/bin/env python3
"""Evaluate settled paper-trading ledger performance."""

from __future__ import annotations

import argparse
import math
from collections import defaultdict

from bet_ledger import parse_float, read_ledger


def _log_loss(p: float, actual: int) -> float:
    p = min(max(p, 1e-12), 1 - 1e-12)
    return -math.log(p if actual else 1.0 - p)


def _summary(rows: list[dict[str, str]]) -> dict[str, float | int | None]:
    settled = [row for row in rows if row["status"] == "settled"]
    if not settled:
        return {
            "n": 0,
            "wins": 0,
            "stake": 0.0,
            "roi_units": 0.0,
            "roi_pct": None,
            "avg_edge_net": None,
            "avg_clv": None,
            "brier_model": None,
            "brier_market": None,
            "logloss_model": None,
            "logloss_market": None,
        }

    stake = sum(parse_float(row["stake_units"]) for row in settled)
    roi_units = sum(parse_float(row["roi"]) for row in settled)
    wins = sum(1 for row in settled if row["result"] == "win")
    actuals = [1 if row["result"] == "win" else 0 for row in settled]
    p_model = [parse_float(row["p_model"]) for row in settled]
    p_market = [parse_float(row["p_market"]) for row in settled]
    clv_values = [parse_float(row["clv"]) for row in settled if row["clv"].strip()]

    return {
        "n": len(settled),
        "wins": wins,
        "stake": stake,
        "roi_units": roi_units,
        "roi_pct": roi_units / stake if stake > 0 else None,
        "avg_edge_net": sum(parse_float(row["edge_net"]) for row in settled) / len(settled),
        "avg_clv": sum(clv_values) / len(clv_values) if clv_values else None,
        "brier_model": sum((p - a) ** 2 for p, a in zip(p_model, actuals)) / len(settled),
        "brier_market": sum((p - a) ** 2 for p, a in zip(p_market, actuals)) / len(settled),
        "logloss_model": sum(_log_loss(p, a) for p, a in zip(p_model, actuals)) / len(settled),
        "logloss_market": sum(_log_loss(p, a) for p, a in zip(p_market, actuals)) / len(settled),
    }


def _fmt_pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.1f}%"


def _fmt_float(value: float | None, digits: int = 4) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def _print_summary(label: str, summary: dict[str, float | int | None]) -> None:
    print(f"\n{label}")
    print("-" * len(label))
    print(f"settled bets : {summary['n']}")
    print(f"wins         : {summary['wins']}/{summary['n']}")
    print(f"stake units  : {_fmt_float(summary['stake'], 2)}")
    print(f"ROI units    : {_fmt_float(summary['roi_units'], 2)}")
    print(f"ROI %        : {_fmt_pct(summary['roi_pct'])}")
    print(f"avg edge_net : {_fmt_pct(summary['avg_edge_net'])}")
    print(f"avg CLV      : {_fmt_float(summary['avg_clv'], 4)}")
    print(f"Brier model  : {_fmt_float(summary['brier_model'])}")
    print(f"Brier market : {_fmt_float(summary['brier_market'])}")
    print(f"logL model   : {_fmt_float(summary['logloss_model'])}")
    print(f"logL market  : {_fmt_float(summary['logloss_market'])}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger-csv", required=True, help="Settled paper ledger CSV.")
    args = ap.parse_args()

    rows = read_ledger(args.ledger_csv)
    _print_summary("ALL SETTLED PAPER BETS", _summary(rows))

    by_market: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_market[row["market_type"]].append(row)
    for market_type in sorted(by_market):
        _print_summary(f"MARKET: {market_type}", _summary(by_market[market_type]))

    open_paper = sum(1 for row in rows if row["status"] == "paper_bet")
    watchlist = sum(1 for row in rows if row["status"] == "watchlist")
    no_bet = sum(1 for row in rows if row["status"] == "no_bet")
    print(f"\nOpen rows: paper_bet={open_paper} watchlist={watchlist} no_bet={no_bet}")
    print("Paper-trading only; not betting advice.")


if __name__ == "__main__":
    main()
