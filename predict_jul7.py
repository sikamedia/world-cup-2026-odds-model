#!/usr/bin/env python3
"""July 7 run: grade the 7/6 R16 games (Portugal-Spain, USA-Belgium),
predict the final R16 day (Argentina-Egypt, Switzerland-Colombia) on
CURRENT Elo, and refresh the bracket MC with post-7/6 Elo updates.

Elo note (this run): direct World.tsv fetch is provenance-blocked again
(URL still not in the task file — improvement #1 stands). NONE of today's
four teams (Arg/Egy/Swi/Col) has played since the 7/4 fetch, so
elo_current_jul4.py IS current for them. Post-7/4 results (Mar, Fra, Nor,
Eng, Spa, Bel) are updated via the World-Elo formula (K=60) and labelled
ESTIMATES pending verification.

Educational/analytical use only - not betting advice.
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "skill", "scripts"))
import match_model as mm  # noqa: E402

from elo_current_jul4 import ELO_CURRENT  # noqa: E402

KO = mm.STAGE_PROFILES["knockout"]


def world_elo_update(r_win, r_lose, gd, K=60, home_bump_winner=0.0,
                     home_bump_loser=0.0):
    g = 1.0 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8)
    we = 1 / (1 + 10 ** (-((r_win + home_bump_winner) -
                           (r_lose + home_bump_loser)) / 400))
    return K * g * (1 - we)


def ko_predict(eh, ea, home_bump=0.0, heat=None, rain=False,
               inj_home=1.0, inj_away=1.0):
    lh, la = mm.elo_to_lambdas(eh, ea, home_bump=home_bump,
                               avg_goals=KO["avg_goals"],
                               gd_per_100=KO["gd_per_100"])
    scale = {"mild": 0.95, "moderate": 0.90, "severe": 0.85}.get(heat, 1.0)
    if rain:
        scale *= 0.95
    lh, la = lh * scale * inj_home, la * scale * inj_away
    d_eff = (eh + home_bump) - ea
    style = "open" if abs(d_eff) >= 266 else "balanced"
    P = mm.score_matrix(lh, la, opp_style=style, draw_boost=KO["draw_boost"])
    h, d, a, ov, btts = mm.summarise(P)
    e_home = 1 / (1 + 10 ** (-d_eff / 400))
    k_eff = mm.graded_ko_regress(d_eff, KO["ko_regress"],
                                 KO["ko_regress_max"], KO["ko_elo_scale"])
    adv = mm.advancement(P, e_home, k_eff, KO["pen_tilt"])
    return dict(lh=lh, la=la, h=h, d=d, a=a, ov=ov, btts=btts,
                adv=adv["adv_reg"], k_eff=k_eff, d_eff=d_eff, P=P,
                style=style)


def show(tag, r):
    top = sorted(r["P"].items(), key=lambda x: -x[1])[:4]
    tops = ", ".join(f"{i}-{j} {p*100:.1f}%" for (i, j), p in top)
    print(f"\n### {tag}")
    print(f"  dElo_eff {r['d_eff']:+.0f} -> k_eff {r['k_eff']:.2f} | "
          f"lambda {r['lh']:.2f}/{r['la']:.2f} | opp-style {r['style']}")
    print(f"  90': H {r['h']*100:.1f} / D {r['d']*100:.1f} / A {r['a']*100:.1f}"
          f"  | O2.5 {r['ov']*100:.1f} | BTTS {r['btts']*100:.1f}")
    print(f"  fair odds {1/r['h']:.2f} / {1/r['d']:.2f} / {1/r['a']:.2f}"
          f"  | +5% {1/(r['h']*1.05):.2f} / {1/(r['d']*1.05):.2f} / "
          f"{1/(r['a']*1.05):.2f}")
    print(f"  ADVANCE home {r['adv']*100:.1f}% / away {(1-r['adv'])*100:.1f}%")
    print(f"  top scores: {tops}")


def demargin3(o):
    inv = [1 / x for x in o]
    s = sum(inv)
    return [x / s for x in inv], (s - 1) * 100


def demargin2(oa, ob):
    ia, ib = 1 / oa, 1 / ob
    return ia / (ia + ib)


print("=" * 68)
print("PART 1 — grade 7/6 (both R16 games decided in 90')")
print("=" * 68)
# Stored pre-match calls (7/6 report, CURRENT-Elo side):
#   Portugal-Spain: 90' 15.8/29.7/54.6, adv SPA 67.2, market SPA 66.0,
#     ensemble 66.6. ACTUAL: Portugal 0-1 Spain (Merino 90+1'). "A" in 90'.
#   USA-Belgium: 90' 29.8/32.9/37.2, adv BEL 52.9, market USA 51.6 (i.e.
#     BEL 48.4), ensemble BEL 50.7. ACTUAL: USA 1-4 Belgium. "A" in 90'.
rows = [
    ("Portugal-Spain", 0.672, 0.660, 0.666, 1,
     "adv RIGHT all three; argmax SPA hit; Tipset 2 hit; 0-1 was rank-2 score"),
    ("USA-Belgium", 0.529, 0.484, 0.507, 1,
     "MODEL side (BEL) RIGHT, MARKET side (USA) WRONG; ens barely right"),
]
print(f"\n{'game':17}{'p_model':>9}{'p_mkt':>7}{'p_ens':>7}"
      f"{'Brier m/mkt/ens':>22}")
for name, pm, pk, pe, fav_adv, note in rows:
    bm, bk, be = (pm - fav_adv) ** 2, (pk - fav_adv) ** 2, (pe - fav_adv) ** 2
    print(f"{name:17}{pm*100:>8.1f}%{pk*100:>6.1f}%{pe*100:>6.1f}%"
          f"   {bm:.3f} / {bk:.3f} / {be:.3f}   {note}")

print("""
Portugal-Spain detail vs stored call (15.8/29.7/54.6):
  outcome A (0-1): RPS = ((0.158)^2 + (0.455)^2)/2 = 0.116. Under 2.5 HIT
  (51.6%), BTTS-Yes 51.0% marginal MISS, scoreline 0-1 was model rank-2
  (10.8%). No pens-alert (29.7% < 30) and none needed — but only just:
  90' winner arrived at 90+1'. Draw was 2nd-most-likely single outcome
  at the whistle-edge; the alert line is doing its risk-tier job.
USA-Belgium detail vs stored call (29.8/32.9/37.2):
  outcome A (1-4): RPS = ((0.298)^2 + (0.627)^2)/2 = 0.241. O2.5 HIT
  (48.5% -> 5 goals, marginal), BTTS-Yes 56.7% HIT, scoreline 1-4 deep
  tail. Pens-alert (32.9%) did NOT fire — 3rd alert day in a row, all
  decisive in 90'. Running tally (KO draw>=30% flagged): 7 flagged ->
  2 went past 90' (28.6% vs implied ~32% — consistent, small n).
  HOST-BUMP CASE FILE (+85 Lumen): neutral control had USA adv 37.0,
  bumped call 47.1, market 51.6, reality a 1-4 rout. The bump moved us
  TOWARD the market's error, not past it — model still beat market by
  4.4 Brier pts. Fan-money hypothesis (b) from 7/6 gains a point:
  proportional de-margin of a sentiment-soaked home line overstated USA.
  Archive with Azteca +90 case; aggregate at n>=6 host games.
""")

print("=" * 68)
print("PART 2 — today (7/7) predictions, CURRENT Elo (jul4 snapshot valid)")
print("=" * 68)

# --- Argentina v Egypt, Mercedes-Benz Atlanta (roof CLOSED, full AC ->
# weather none; outside 88F/38% rain irrelevant), 12:00 ET.
# Team news: ARG no significant concerns (Sports Mole/Goal). EGY: Salah
# STARTS (hamstring managed since MD3, played 120' R32 — official status
# available, per only-official-rulings rule NO multiplier); Abdelmonem
# (CB, ankle) touch-and-go = NOT confirmed out -> no adjustment;
# Fatouh/El Fotouh out (depth, not core); Lasheen back from suspension.
# Rest symmetric: BOTH played 120' AET on 7/3 (4 days) -> no fatigue diff.
# NOTE: dElo 406 -> lambda floor engages (the pre-registered 0.15->0.30
# test case flagged in the 7/6 report). Engine as-is; review at n=24.
ae = ko_predict(ELO_CURRENT["Argentina"], ELO_CURRENT["Egypt"])
show("Argentina v Egypt — MBS Atlanta roof closed/AC, full XIs", ae)

books = {"FanDuel": [1.3448, 4.70, 10.00]}
print("\n  market 90' (proportional de-margin):  [Arg / D / Egy]")
acc = [0.0, 0.0, 0.0]
for name, o in books.items():
    p, ov = demargin3(o)
    acc = [a + x for a, x in zip(acc, p)]
    print(f"    {name:10} A {p[0]*100:.1f} / D {p[1]*100:.1f} / "
          f"E {p[2]*100:.1f}  (margin {ov:.1f}%)")
kal = [0.72, 0.20, 0.10]
ks = sum(kal)
kal = [x / ks for x in kal]
print(f"    {'Kalshi':10} A {kal[0]*100:.1f} / D {kal[1]*100:.1f} / "
      f"E {kal[2]*100:.1f}  (normalised)")
mkt_ae = [(a / len(books) + k) / 2 for a, k in zip(acc, kal)]
print(f"    {'AVG':10} A {mkt_ae[0]*100:.1f} / D {mkt_ae[1]*100:.1f} / "
      f"E {mkt_ae[2]*100:.1f}")
# advance: Argentina -750 (1.1333) / Egypt +510 (6.10)
mkt_adv_arg = demargin2(1.1333, 6.10)
print(f"  market ADVANCE: Argentina {mkt_adv_arg*100:.1f}% / "
      f"Egypt {(1-mkt_adv_arg)*100:.1f}%")
ens_arg = (ae["adv"] + mkt_adv_arg) / 2
print(f"  ENSEMBLE (model/market 50:50): Argentina {ens_arg*100:.1f}% / "
      f"Egypt {(1-ens_arg)*100:.1f}%")

# --- Switzerland v Colombia, BC Place Vancouver (retractable roof; even
# open: 68F / 4% rain / 9mph -> NO weather adjustment), 16:00 ET / 13:00 PT.
# Team news: SUI fully fit, settled squad (Yakin, no inj/susp). COL
# unbeaten, 1 goal conceded all tournament; no new absences reported.
# Rest: SUI last played 7/3 (90'), COL 7/3 (90') — symmetric.
sc = ko_predict(ELO_CURRENT["Switzerland"], ELO_CURRENT["Colombia"])
show("Switzerland v Colombia — BC Place, 68F mild, full XIs", sc)

books2 = {"FanDuel": [3.50, 3.10, 2.25], "best-line": [3.75, 3.25, 2.375]}
print("\n  market 90' (proportional de-margin):  [Sui / D / Col]")
acc = [0.0, 0.0, 0.0]
for name, o in books2.items():
    p, ov = demargin3(o)
    acc = [a + x for a, x in zip(acc, p)]
    print(f"    {name:10} S {p[0]*100:.1f} / D {p[1]*100:.1f} / "
          f"C {p[2]*100:.1f}  (margin {ov:.1f}%)")
mkt_sc = [x / len(books2) for x in acc]
print(f"    {'AVG':10} S {mkt_sc[0]*100:.1f} / D {mkt_sc[1]*100:.1f} / "
      f"C {mkt_sc[2]*100:.1f}")
# No two-way advance market found this session (stated assumption):
# derive market-implied advance = P(win90) + P(draw) * pen-split, using
# the model's Elo-tilted pen split for consistency.
e_sui = 1 / (1 + 10 ** (-(ELO_CURRENT["Switzerland"] -
                          ELO_CURRENT["Colombia"]) / 400))
pen_sui = 0.5 + KO["pen_tilt"] * (e_sui - 0.5)
mkt_adv_sui = mkt_sc[0] + mkt_sc[1] * pen_sui
print(f"  market ADVANCE (derived, pen-split {pen_sui*100:.1f}% SUI): "
      f"Sui {mkt_adv_sui*100:.1f}% / Col {(1-mkt_adv_sui)*100:.1f}%")
ens_sui = (sc["adv"] + mkt_adv_sui) / 2
print(f"  ENSEMBLE (model/market 50:50): Switzerland {ens_sui*100:.1f}% / "
      f"Colombia {(1-ens_sui)*100:.1f}%")

print()
print("=" * 68)
print("PART 3 — bracket MC from the live round (post-7/6 Elo ESTIMATES)")
print("=" * 68)
ELO_MC = dict(ELO_CURRENT)
d_mar = world_elo_update(ELO_MC["Morocco"], ELO_MC["Canada"], 3)
d_fra = world_elo_update(ELO_MC["France"], ELO_MC["Paraguay"], 1)
ELO_MC["Morocco"] += d_mar
ELO_MC["France"] += d_fra
d_nor = world_elo_update(ELO_MC["Norway"], ELO_MC["Brazil"], 1)
ELO_MC["Norway"] += d_nor
ELO_MC["Brazil"] -= d_nor
d_eng = world_elo_update(ELO_MC["England"], ELO_MC["Mexico"], 1,
                         home_bump_loser=100)
ELO_MC["England"] += d_eng
ELO_MC["Mexico"] -= d_eng
# NEW 7/6 results:
d_spa = world_elo_update(ELO_MC["Spain"], ELO_MC["Portugal"], 1)
ELO_MC["Spain"] += d_spa
ELO_MC["Portugal"] -= d_spa
d_bel = world_elo_update(ELO_MC["Belgium"], ELO_MC["USA"], 3,
                         home_bump_loser=100)
ELO_MC["Belgium"] += d_bel
ELO_MC["USA"] -= d_bel
print(f"post-7/4 updates (ESTIMATED, verify vs eloratings.net when "
      f"unblocked):\n"
      f"  Morocco +{d_mar:.0f} -> {ELO_MC['Morocco']:.0f}, "
      f"France +{d_fra:.0f} -> {ELO_MC['France']:.0f}, "
      f"Norway +{d_nor:.0f} -> {ELO_MC['Norway']:.0f}, "
      f"England +{d_eng:.0f} -> {ELO_MC['England']:.0f},\n"
      f"  Spain +{d_spa:.0f} -> {ELO_MC['Spain']:.0f}, "
      f"Belgium +{d_bel:.0f} -> {ELO_MC['Belgium']:.0f}")

_cache = {}


def p_adv(a, b, bump_a=0.0):
    key = (a, b, bump_a)
    if key not in _cache:
        _cache[key] = ko_predict(ELO_MC[a], ELO_MC[b], home_bump=bump_a)["adv"]
    return _cache[key]


# QF97 FRA-MAR | QF98 SPA-BEL (locked 7/6) | QF99 NOR-ENG |
# QF100 W(ArgEgy)-W(SuiCol). SF101 = W97 v W98, SF102 = W99 v W100.
R16_LIVE = [("Argentina", "Egypt", 0.0), ("Switzerland", "Colombia", 0.0)]
SIMS, rng = 50000, random.Random(42)
teams = ["France", "Morocco", "Norway", "England", "Spain", "Belgium"] + \
    [t for tie in R16_LIVE for t in tie[:2]]
tally = {t: {r: 0 for r in ["QF", "SF", "Final", "Champion"]} for t in teams}
for _ in range(SIMS):
    w = {}
    for h, a, bump in R16_LIVE:
        w[(h, a)] = h if rng.random() < p_adv(h, a, bump) else a
    for t in ("France", "Morocco", "Norway", "England", "Spain", "Belgium"):
        tally[t]["QF"] += 1
    for tie, x in w.items():
        tally[x]["QF"] += 1
    qf = [("France", "Morocco"),
          ("Spain", "Belgium"),
          ("Norway", "England"),
          (w[("Argentina", "Egypt")], w[("Switzerland", "Colombia")])]
    sf_in = []
    for h, a in qf:
        x = h if rng.random() < p_adv(h, a) else a
        tally[x]["SF"] += 1
        sf_in.append(x)
    fin = []
    for h, a in [(sf_in[0], sf_in[1]), (sf_in[2], sf_in[3])]:
        x = h if rng.random() < p_adv(h, a) else a
        tally[x]["Final"] += 1
        fin.append(x)
    c = fin[0] if rng.random() < p_adv(fin[0], fin[1]) else fin[1]
    tally[c]["Champion"] += 1

print(f"\n{'Team':13}{'Champ':>7}{'Final':>7}{'SF':>7}{'QF':>7}   ({SIMS} sims)")
for t in sorted(teams, key=lambda x: -tally[x]["Champion"]):
    r = tally[t]
    print(f"{t:13}{r['Champion']/SIMS*100:>6.1f}%"
          f"{r['Final']/SIMS*100:>6.1f}%{r['SF']/SIMS*100:>6.1f}%"
          f"{r['QF']/SIMS*100:>6.1f}%")

print("\nEducational/analytical use only; not betting advice. / "
      "教育/分析用途，不构成投注建议。")
