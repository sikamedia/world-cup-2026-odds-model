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
      stage     : "R32" | "R16" | "QF" | "SF" | "3P" | "F"

Every row is VALIDATED at import (validate_ko_results below) — a row whose
`advanced` contradicts the 90' score, an unknown team, a duplicate, or an R32
pairing that doesn't match the official fixtures fails fast. Lesson from the
6/30 ingest that recorded Cote d'Ivoire-Norway with the winner flipped. NOTE:
the validator only catches internal inconsistency; a wrongly transcribed but
self-consistent score still requires the double-source check (ESPN/FIFA) at
ingest time.
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
    ("Argentina", "Cabo Verde", 1, 1, "H", "R32"),  # 90' 1-1 (Messi 29'; Duarte 59'). ET: L.Martinez 93', Lopes Cabral 104' (2-2), Borges OG -> ARG 3-2 AET, through. Near-historic upset avoided (Hard Rock Miami). Verified ESPN/Sky/CBS 7/4.
    ("Australia", "Egypt", 1, 1, "A", "R32"),       # 90' 1-1 (Ashour 13'; Hany OG 55'). 1-1 AET -> Egypt 4-2 pens (Salah panenka; Souttar+Harrington missed). Egypt first-ever KO win (AT&T Arlington). Verified Sky/Opta/SBS 7/4.
    ("Colombia", "Ghana", 1, 0, "H", "R32"),        # Arias 14'; Colombia through in 90' (Arrowhead KC). Fav advanced. Verified ESPN/Yahoo 7/4.
    ("Canada", "Morocco", 0, 3, "A", "R16"),        # Ounahi x2 + Rahimi 90'+; Morocco rout, through to QF (NRG Houston). Market (MAR 68.8% adv) right, stale-Elo model coin-flip (CAN 50.5%) wrong — Elo-staleness evidence #2. Verified ESPN/NBC/Outlook 7/4.
    ("Brazil", "Norway", 1, 2, "A", "R16"),         # Haaland late double (~88',90+'), Neymar 90+' pen consolation; Guimaraes 1H pen SAVED by Nyland. Norway first-ever QF. FIRST regulation upset of the tournament (both model 44.6/33.8/21.6 and market 52.4/25.7/21.9 had Brazil). Verified NBC/Outlook/VAVEL 7/5.
    ("Paraguay", "France", 0, 1, "A", "R16"),       # Mbappe 70' pen (VAR, Gomez knee on Doue); 100F heat Philadelphia, feisty/bruising. France through to QF vs Morocco (Gillette 7/9). Model fav side right (FRA adv 85.6%, market 92.6%). Verified ESPN/Opta/FIFA/Sky/AlJazeera 7/5.
    ("Mexico", "England", 2, 3, "A", "R16"),        # Bellingham 2 in <2min late 1H; Quinones pre-HT; Quansah RED 54' (VAR) — England played ~40' with 10; Kane 60' pen 3-1, Jimenez 69' pen 3-2. Mexico's first-ever home WC loss. Model/market both ~ENG 51-52% adv — coin-flip called right. Verified FOX boxscore/NBC/CBS/englandfootball.com 7/6.
    ("Portugal", "Spain", 0, 1, "A", "R16"),        # Merino 90+1' (Ferran Torres assist, both subs); Ronaldo's last WC game. Spain through to QF (AT&T Arlington, roof closed). Model adv SPA 67.2 / market 66.0 — fav advanced in 90'. Verified ESPN/FIFA/CBS/AlJazeera 7/7.
    ("USA", "Belgium", 1, 4, "A", "R16"),           # De Ketelaere 9',32'; Tillman FK 31'; Vanaken 2H; Lukaku 90+'. Belgium rout at Lumen Seattle. Model BEL 52.9 adv RIGHT, market USA 51.6 WRONG (fan-money lean); pens-alert (32.9) didn't fire. Verified FIFA/ESPN/NPR/ussoccer 7/7.
    ("Argentina", "Egypt", 3, 2, "H", "R16"),      # Egypt led 2-0 (Yasser Ibrahim 15', Zico 67'); Romero 79', Messi 83', Enzo Fernandez 90+2' — ARG comeback in 90' (Mercedes-Benz Atlanta, roof closed). Salah started. Verified ESPN/FIFA/NBC/NPR/olympics.com 7/8.
    ("Switzerland", "Colombia", 0, 0, "H", "R16"),  # 0-0 after 120'; Switzerland 4-3 pens (Vargas winning kick) — first Swiss QF since 1954 (BC Place Vancouver). Pens-alert (32.4) FIRED and HIT; Elo pen tilt had COL 51.7. Verified ESPN/FIFA/FOX/CBS 7/8.
    ("France", "Morocco", 2, 0, "H", "QF"),         # Mbappe 60' (20th career WC goal; missed 1H pen), Dembele 66'; shots 21-4, SOT 8-1 France. France to SF (Gillette Foxborough). Pre-reg 2-0 was model TOP scoreline (14.4%). Verified FIFA/ESPN/FOX/NBC/CNN 7/10.
    ("Spain", "Belgium", 2, 1, "H", "QF"),          # Fabian Ruiz 30' (rebound), De Ketelaere 40' (header), Merino 88' (sub 86', Lammens spill off Cubarsi shot — 3rd career super-sub rescue). Tielemans injured in WARM-UP (out); Courtois injured 2H (Lammens on). Spain to SF vs France. Low-block trigger NOT fired (Belgium lost). Verified ESPN/CNN/Yahoo/FOX 7/11.
    ("Norway", "England", 1, 1, "A", "QF"),         # 90' 1-1 (Schjelderup 36'; Bellingham 45+2'). ET: Bellingham 93' -> ENG 2-1 AET, through to SF vs ARG (Hard Rock Miami, heat idx ~107 forecast). Pens-prep alert (31.3%) half-fired: 90' draw YES, decided in ET not pens. Verified FIFA/ESPN/englandfootball/NPR/FOX 7/12.
    ("Argentina", "Switzerland", 1, 1, "H", "QF"),  # 90' 1-1 (Mac Allister 10' hdr off Messi corner; Ndoye 67'); Embolo RED 72' (2nd yellow, simulation VAR). ET: Alvarez 112' golazo, L.Martinez 121' -> ARG 3-1 AET (Arrowhead KC). Low-block divergence case #4 resolved MODEL-side (SUI 90' win 10.1 vs mkt 16.0 — didn't happen); 4/4. Verified ESPN/Yahoo/NPR/WaPo/CBS 7/12.
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

_VALID_STAGES = {"R32", "R16", "QF", "SF", "3P", "F"}


def validate_ko_results(rows, elo, r32_fixtures=None):
    """Fail fast on internally inconsistent knockout rows.

    Guards (per row): known teams, valid stage, non-negative integer 90'
    score, `advanced` consistent with the score (a side that lost on goals
    cannot be the one that advanced; only a 90' draw may go either way via
    ET/pens), no duplicate tie per stage, and R32 rows must match an official
    fixture in the recorded home/away order.
    """
    seen = set()
    for i, row in enumerate(rows):
        assert len(row) == 6, f"KO row {i}: expected 6 fields, got {row!r}"
        home, away, hg, ag, advanced, stage = row
        tag = f"KO row {i} ({home} v {away})"
        assert home != away, f"{tag}: home == away"
        assert home in elo, f"{tag}: unknown team {home!r} (not in ELO)"
        assert away in elo, f"{tag}: unknown team {away!r} (not in ELO)"
        assert isinstance(hg, int) and isinstance(ag, int) and hg >= 0 <= ag, \
            f"{tag}: bad 90' score {hg!r}-{ag!r}"
        assert advanced in ("H", "A"), \
            f"{tag}: advanced must be 'H' or 'A', got {advanced!r}"
        assert stage in _VALID_STAGES, f"{tag}: bad stage {stage!r}"
        if hg > ag:
            assert advanced == "H", \
                f"{tag}: 90' score {hg}-{ag} but advanced={advanced!r} (winner flipped?)"
        elif ag > hg:
            assert advanced == "A", \
                f"{tag}: 90' score {hg}-{ag} but advanced={advanced!r} (winner flipped?)"
        key = (frozenset((home, away)), stage)
        assert key not in seen, f"{tag}: duplicate result for stage {stage}"
        seen.add(key)
        if r32_fixtures is not None and stage == "R32":
            assert (home, away) in r32_fixtures, \
                f"{tag}: not an official R32 fixture (home/away order swapped?)"


validate_ko_results(KO_RESULTS, ELO, R32_FIXTURES)

if __name__ == "__main__":
    print(f"KO data OK: {len(KO_RESULTS)} result(s) validated "
          f"({len(R32_FIXTURES)} R32 fixtures)")
