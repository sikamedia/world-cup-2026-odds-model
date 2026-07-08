#!/usr/bin/env python3
"""PREDICTION-SIDE Elo snapshot — 2026-07-08 (QF round, 8 teams alive).

World.tsv direct fetch provenance-blocked for the THIRD consecutive
session (URL still not in the scheduled-task file — improvement #1).
Base: verified 7/7 fetch (elo_current_jul7.py). Post-7/7 games applied
via the K=60 World-Elo replica (validated 8/8 exact on 7/7):
  - Argentina 3-2 Egypt (gd 1): Arg +5.3 -> 2156, Egy -> 1742
  - Switzerland 0-0 Colombia, pens: SHOOTOUT = DRAW per eloratings.net
    convention: Swi +5.6 -> 1949, Col -> 2003
Belgium 1961 / USA 1747 still carry the 7/6 estimate (site had not yet
processed USA 1-4 Bel at the 7/7 fetch).

Governance: predictions use CURRENT ratings; backtests keep historical
snapshots in worldcup_2026_data_ko.py. Do NOT import from backtest scripts.
"""

ELO_CURRENT = {
    "Spain": 2177,        # verified 7/7, unplayed since
    "Argentina": 2156,    # ESTIMATE: 2151 (verified) + 5.3 (beat Egy 3-2)
    "France": 2143,       # verified 7/7, unplayed since
    "England": 2076,      # verified 7/7, unplayed since
    "Colombia": 2003,     # ESTIMATE: 2009 - 5.6 (pens = draw), eliminated
    "Norway": 1972,       # verified 7/7, unplayed since
    "Belgium": 1961,      # ESTIMATE: site pending USA-Bel at 7/7 fetch
    "Switzerland": 1949,  # ESTIMATE: 1943 + 5.6 (0-0 draw vs higher-rated Col)
    "Morocco": 1921,      # verified 7/7, unplayed since
    "Egypt": 1742,        # ESTIMATE: 1747 - 5.3, eliminated
    "USA": 1747,          # ESTIMATE: pending site processing, eliminated
}

FETCHED_BASE = "2026-07-07"
SOURCE = "https://www.eloratings.net/World.tsv"
ESTIMATES = ["Argentina", "Colombia", "Belgium", "Switzerland", "Egypt", "USA"]
