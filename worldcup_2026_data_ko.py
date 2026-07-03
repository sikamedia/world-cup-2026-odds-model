"""Knockout-stage results — kept SEPARATE from the 72 group-stage games.

The knockout distribution differs from the group stage (single-leg, full
intensity, no rotation, draws resolved by extra time + penalties), so it is
backtested as its own batch and never mixed into the group-stage parameter
search. This file grows one round at a time as games are played.

Row format (90-minute result):
    (home, away, hg, ag, advanced, stage)
      hg, ag    : score at the end of 90 minutes (NOT after ET/pens)
      advanced  : "H" or "A" — who actually went through (captures the
                  shootout outcome on a 90-minute draw)
      stage     : "R32" | "R16" | "QF" | "SF" | "F"

Round of 32 begins 2026-06-28 (South Africa vs Canada). No knockout game has
finished yet, so KO_RESULTS is empty — append results as they come in.
Educational/analytical use only - not betting advice.
"""
from worldcup_2026_data import ELO, HOME  # noqa: F401  (re-exported for backtest)

# (home, away, hg, ag, advanced, stage) — append as games are played.
KO_RESULTS: list[tuple[str, str, int, int, str, str]] = [
    ("South Africa", "Canada", 0, 1, "A", "R32"),  # Eustaquio 90+2', Canada through (SoFi LA)
    ("Brazil", "Japan", 2, 1, "H", "R32"),          # Casemiro 56', Martinelli 90+5'; Sano 29'. Brazil through (NRG Houston)
    ("Germany", "Paraguay", 1, 1, "A", "R32"),      # 1-1 AET (Havertz 54', Enciso 42'); Paraguay 4-3 pens (Gillette Boston)
    ("Netherlands", "Morocco", 1, 1, "A", "R32"),   # 1-1 AET (Gakpo 72', Diop 90+1'); Morocco 3-2 pens (BBVA Monterrey)
    ("Cote dIvoire", "Norway", 1, 2, "A", "R32"),   # CORRECTED 7/3: Norway won 2-1 (Nusa 39', Haaland 86'; Diallo 74'). Norway (Elo fav 1880>1820) through — NOT an upset (AT&T Arlington). Prior 6/30 ingest had the winner FLIPPED (recorded CIV 2-1). Verified ESPN/FIFA/Al Jazeera.
    ("France", "Sweden", 3, 0, "H", "R32"),         # CORRECTED 7/3: France 3-0 (Mbappe x2, Barcola), through (MetLife NJ). Prior 6/30 ingest had 3-1. Verified ESPN/FIFA.
    ("Mexico", "Ecuador", 2, 0, "H", "R32"),        # Quinones 22', Jimenez 31'; Mexico through (Azteca, host+altitude)
    ("England", "DR Congo", 2, 1, "H", "R32"),      # Cipenga 7' (COD); Kane 75',86' (both Gordon assist); Eng through (Atlanta). Saka benched.
    ("Belgium", "Senegal", 2, 2, "H", "R32"),       # 2-2 AET (Diarra + Sarr put SEN 2-0; Lukaku 86', Tielemans 89'); Tielemans 125' pen (VAR) → BEL 3-2 AET, through (Lumen Seattle)
    ("USA", "Bosnia", 2, 0, "H", "R32"),            # Balogun 45' then RED ~62'; Tillman 82' FK; USA 2-0 with 10 men, through (Levi's). Balogun suspended R16.
    ("Spain", "Austria", 3, 0, "H", "R32"),         # Spain rout; Spain through (SoFi LA). Fav advanced in 90'.
    ("Portugal", "Croatia", 2, 1, "H", "R32"),      # Portugal survive Croatia; Portugal through (BMO Toronto). Fav advanced in 90'.
    ("Switzerland", "Algeria", 2, 0, "H", "R32"),   # Switzerland 3rd straight win; Switzerland through (BC Place Vancouver). Fav advanced in 90'.
]

# Round of 32 — the 16 fixed ties, in OFFICIAL BRACKET-TREE LEAF ORDER (FIFA
# bracket, Wikipedia Match 73-104; cross-checked vs media). Knockout venues are
# neutral (no host bump). Adjacent pairs meet in the R16, then (1-2)x(3-4) in the
# QF, and so on — so predict_bracket.py reproduces the exact tree with no shuffle.
# Top half = ties 1-8, bottom half = ties 9-16. Comment shows the FIFA match no.
R32_FIXTURES = [
    ("Germany", "Paraguay"),         # M74  ┐R16-A
    ("France", "Sweden"),            # M77  ┘     ┐QF M97
    ("South Africa", "Canada"),      # M73  ┐R16-B┘
    ("Netherlands", "Morocco"),      # M75  ┘          ┐SF M101
    ("Portugal", "Croatia"),         # M83  ┐R16-E     │
    ("Spain", "Austria"),            # M84  ┘     ┐QF M98
    ("USA", "Bosnia"),               # M81  ┐R16-F┘
    ("Belgium", "Senegal"),          # M82  ┘
    ("Brazil", "Japan"),             # M76  ┐R16-C
    ("Cote dIvoire", "Norway"),      # M78  ┘     ┐QF M99
    ("Mexico", "Ecuador"),           # M79  ┐R16-D┘
    ("England", "DR Congo"),         # M80  ┘          ┐SF M102
    ("Argentina", "Cabo Verde"),     # M86  ┐R16-G     │
    ("Australia", "Egypt"),          # M88  ┘     ┐QF M100
    ("Switzerland", "Algeria"),      # M85  ┐R16-H┘
    ("Colombia", "Ghana"),           # M87  ┘
]
