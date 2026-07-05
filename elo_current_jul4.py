#!/usr/bin/env python3
"""PREDICTION-SIDE Elo snapshot — eloratings.net fetched 2026-07-04 (World.tsv).

Governance (7/4 report improvement #2a): predictions use CURRENT ratings;
backtests keep the historical snapshot in `worldcup_2026_data_ko.py` so past
model calls are scored against what the model knew at the time. Do NOT import
this file from backtest scripts.

Drift vs the stored dict ranges -106 (Canada, overrated) to +114 (Egypt,
underrated). Both 7/3-7/4 market-vs-model blowups are explained by opposite-
direction drift: Canada-Morocco stored dElo -10 vs current +122 (the 19-pt
advancement gap), Australia-Egypt stored +92 vs current +58. Paraguay-France
drifts in the SAME direction for both teams (dElo 333 -> 311, negligible).
"""

ELO_CURRENT = {  # the 16 R16 teams
    "Canada": 1764, "Brazil": 2031, "Paraguay": 1823, "Morocco": 1886,
    "Norway": 1934, "France": 2134, "Mexico": 1943, "England": 2046,
    "Belgium": 1910, "USA": 1798, "Spain": 2159, "Portugal": 2013,
    "Switzerland": 1943, "Argentina": 2148, "Egypt": 1742, "Colombia": 2004,
}

FETCHED = "2026-07-04"
SOURCE = "https://www.eloratings.net/World.tsv"
