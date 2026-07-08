#!/usr/bin/env python3
"""PREDICTION-SIDE Elo snapshot — eloratings.net World.tsv fetched 2026-07-07
(user posted the URL in-session, lifting the provenance block).

VERIFICATION RESULT: all 8 post-match estimates from predict_jul6/jul7 runs
matched the live table EXACTLY (Spa 2177, Fra 2143, Eng 2076, Nor 1972,
Mar 1921, Por 1995, Mex 1913, Bra 1993) — the K=60 World-Elo replica is
confirmed. Site had processed games through Por-Spa (7/6 afternoon) but NOT
YET USA-Belgium (Bel still 1910, USA 1798 = pre-match); keep the estimated
post-match values for those two until the next fetch.

Minor drift vs jul4 snapshot for teams that did NOT play (site-side
retro-adjustments): Arg 2148->2151, Col 2004->2009, Egy 1742->1747.

Governance: predictions use CURRENT ratings; backtests keep historical
snapshots in worldcup_2026_data_ko.py. Do NOT import from backtest scripts.
"""

ELO_CURRENT = {  # verified live 2026-07-07 unless noted
    "Spain": 2177, "Argentina": 2151, "France": 2143, "England": 2076,
    "Colombia": 2009, "Portugal": 1995, "Brazil": 1993, "Norway": 1972,
    "Switzerland": 1943, "Morocco": 1921, "Mexico": 1913,
    "Belgium": 1961,  # ESTIMATE: site not yet processed USA 1-4 Bel (showed 1910)
    "USA": 1747,      # ESTIMATE: same game pending (site showed 1798)
    "Egypt": 1747, "Canada": 1729, "Paraguay": 1814,
}

FETCHED = "2026-07-07"
SOURCE = "https://www.eloratings.net/World.tsv"
PENDING_SITE_PROCESSING = ["Belgium", "USA"]
