#!/usr/bin/env python3
"""July 6 run: grade the 7/5 R16 games (Brazil-Norway, Mexico-England),
predict today's R16 day-3 (Portugal-Spain, USA-Belgium) on CURRENT Elo,
and refresh the bracket MC with post-7/5 Elo updates.

Elo note (this run): direct World.tsv fetch is provenance-blocked in this
session, but NONE of today's four teams (Por/Spa/USA/Bel) has played since
the 7/4 fetch, so elo_current_jul4.py IS current for them. Post-7/4 results
(Mar, Fra, Nor, Eng) are updated inside Part 3 via the World-Elo formula
(K=60, goal-diff multiplier, +100 home for Azteca) and labelled ESTIMATES.

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
    """World Football Elo delta for the winner (K=60 WC finals, G(gd))."""
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
                adv=adv["adv_reg"], k_eff=k_eff, d_eff=d_eff, P=P)


def show(tag, r):
    top = sorted(r["P"].items(), key=lambda x: -x[1])[:4]
    tops = ", ".join(f"{i}-{j} {p*100:.1f}%" for (i, j), p in top)
    print(f"\n### {tag}")
    print(f"  dElo_eff {r['d_eff']:+.0f} -> k_eff {r['k_eff']:.2f} | "
          f"lambda {r['lh']:.2f}/{r['la']:.2f}")
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
print("PART 1 — grade 7/5 (both R16 games decided in 90')")
print("=" * 68)
# Stored pre-match calls (7/5 report + evening update, CURRENT-Elo side):
#   Brazil-Norway (model B, evening): 90' 44.6/33.8/21.6, adv BRA 59.9,
#     market adv BRA 66.5, ensemble 63.2. ACTUAL: Brazil 1-2 Norway ("A").
#   Mexico-England: 90' 31.7/33.0/35.3, adv ENG 51.4, market ENG 51.9,
#     ensemble ENG 51.7, Under 51.4, BTTS 56.9. ACTUAL: Mexico 2-3 England.
rows = [
    ("Brazil-Norway", 0.599, 0.665, 0.632, 0,
     "adv side WRONG (1st regulation upset of WC; model & market agreed)"),
    ("Mexico-England", 1 - 0.514, 1 - 0.519, 1 - 0.517, 0,
     "adv side RIGHT (fav=ENG away); 90' argmax ENG hit; Tipset X missed"),
]
print(f"\n{'game':17}{'p_model':>9}{'p_mkt':>7}{'p_ens':>7}"
      f"{'Brier m/mkt/ens':>22}")
for name, pm, pk, pe, fav_adv, note in rows:
    bm, bk, be = (pm - fav_adv) ** 2, (pk - fav_adv) ** 2, (pe - fav_adv) ** 2
    print(f"{name:17}{pm*100:>8.1f}%{pk*100:>6.1f}%{pe*100:>6.1f}%"
          f"   {bm:.3f} / {bk:.3f} / {be:.3f}   {note}")
print("""
Mexico-England detail vs stored call (31.7/33.0/35.3):
  outcome A (2-3): RPS = ((0.317)^2 + (0.647-0)^2)/2 = 0.259 (coin-flip game,
  decisive result); adv Brier model 0.236 / market 0.231 / ensemble 0.233.
  BTTS-Yes 56.9% HIT; Under 51.4% marginal MISS (5 goals); scoreline 2-3 was
  deep tail (~1.5%). Pens-alert (draw 33.0%) did NOT fire — decisive in 90'.
  Team-news note: pre-match reports had Quansah OUT; he STARTED (and was sent
  off 54'). Conservative no-adjust policy was robust to the wrong report.
Dual pens-alert day verdict: both 7/5 alerts (33.8 / 33.0) resolved in 90'.
Running pens-alert tally (draw>=30% flagged KO games): 6 flagged ->
  2 went past 90' (Aus-Egy pens, Bel-Sen ET), 4 decisive. Alert = risk tier.
""")

print("=" * 68)
print("PART 2 — today (7/6) predictions, CURRENT Elo (jul4 snapshot valid)")
print("=" * 68)

# --- Portugal v Spain, AT&T Arlington (roof CLOSED, climate-controlled ->
# weather none), 15:00 ET / 14:00 local. Iberian derby, both full-intensity.
# Team news: SPA N.Williams + Pino out (standing since R32, deep squad ->
# no adj per 7/2 precedent, Discipline A: market knows). POR full XI,
# Ronaldo starts. No new absences either side -> no multipliers.
ps = ko_predict(ELO_CURRENT["Portugal"], ELO_CURRENT["Spain"])
show("Portugal v Spain — AT&T roof closed, no weather, full XIs", ps)

books = {"FanDuel": [4.10, 3.60, 1.870], "bet365": [4.00, 3.50, 1.901]}
print("\n  market 90' (proportional de-margin):  [Por / D / Spa]")
acc = [0.0, 0.0, 0.0]
for name, o in books.items():
    p, ov = demargin3(o)
    acc = [a + x for a, x in zip(acc, p)]
    print(f"    {name:10} P {p[0]*100:.1f} / D {p[1]*100:.1f} / "
          f"S {p[2]*100:.1f}  (margin {ov:.1f}%)")
mkt_ps = [x / len(books) for x in acc]
print(f"    {'AVG':10} P {mkt_ps[0]*100:.1f} / D {mkt_ps[1]*100:.1f} / "
      f"S {mkt_ps[2]*100:.1f}")
# advance: Spain -225 (1.4444) / Portugal +180 (2.80)
mkt_adv_spa = demargin2(1.4444, 2.80)
print(f"  market ADVANCE: Spain {mkt_adv_spa*100:.1f}% / "
      f"Portugal {(1-mkt_adv_spa)*100:.1f}%")
ens_por = (ps["adv"] + (1 - mkt_adv_spa)) / 2
print(f"  ENSEMBLE (model/market 50:50): Portugal {ens_por*100:.1f}% / "
      f"Spain {(1-ens_por)*100:.1f}%")

# --- USA v Belgium, Lumen Field Seattle (open-air), 20:00 ET / 17:00 local.
# Weather (FOX13 7/5 forecast): sunny, ~82F at kickoff cooling into 70s,
# DRY -> heat "none" (82F dry evening = below the mild threshold; noted).
# HOST: USA +85 (project convention, validated R32 USA & Mexico).
# Team news: Balogun red OVERTURNED by FIFA -> eligible (REMOVE the 7/2
# standing x0.90 flag). USA full strength. BEL full (KDB+Doku start,
# Trossard fit). BEL played 120' on 7/1 vs USA's 90' — 5 days ago, treated
# as recovered (no adj; market prices it).
ub = ko_predict(ELO_CURRENT["USA"], ELO_CURRENT["Belgium"], home_bump=85)
show("USA v Belgium — Lumen Seattle, host +85, 82F dry (no wx adj)", ub)
ub_neu = ko_predict(ELO_CURRENT["USA"], ELO_CURRENT["Belgium"])
print(f"  [neutral control: 90' {ub_neu['h']*100:.1f}/{ub_neu['d']*100:.1f}/"
      f"{ub_neu['a']*100:.1f}, adv USA {ub_neu['adv']*100:.1f}%]")

books2 = {"BetMGM": [2.60, 3.30, 2.60]}
print("\n  market 90' (proportional de-margin):  [USA / D / Bel]")
acc = [0.0, 0.0, 0.0]
for name, o in books2.items():
    p, ov = demargin3(o)
    acc = [a + x for a, x in zip(acc, p)]
    print(f"    {name:10} U {p[0]*100:.1f} / D {p[1]*100:.1f} / "
          f"B {p[2]*100:.1f}  (margin {ov:.1f}%)")
mkt_ub = [x / len(books2) for x in acc]
# advance: USA -120 (1.8333) / Belgium -105 (1.9524) BetMGM
mkt_adv_usa = demargin2(1.8333, 1.9524)
print(f"  market ADVANCE: USA {mkt_adv_usa*100:.1f}% / "
      f"Belgium {(1-mkt_adv_usa)*100:.1f}%")
ens_usa = (ub["adv"] + mkt_adv_usa) / 2
print(f"  ENSEMBLE (model/market 50:50): USA {ens_usa*100:.1f}% / "
      f"Belgium {(1-ens_usa)*100:.1f}%")

print()
print("=" * 68)
print("PART 3 — bracket MC from the live round (post-7/5 Elo ESTIMATES)")
print("=" * 68)
ELO_MC = dict(ELO_CURRENT)
d_mar = world_elo_update(ELO_MC["Morocco"], ELO_MC["Canada"], 3)
d_fra = world_elo_update(ELO_MC["France"], ELO_MC["Paraguay"], 1)
ELO_MC["Morocco"] += d_mar
ELO_MC["France"] += d_fra
d_nor = world_elo_update(ELO_MC["Norway"], ELO_MC["Brazil"], 1)
ELO_MC["Norway"] += d_nor
ELO_MC["Brazil"] -= d_nor
# England won 3-2 AT Azteca (Mexico +100 home in the Elo formula)
d_eng = world_elo_update(ELO_MC["England"], ELO_MC["Mexico"], 1,
                         home_bump_loser=100)
ELO_MC["England"] += d_eng
ELO_MC["Mexico"] -= d_eng
print(f"post-7/4 updates (ESTIMATED, verify vs eloratings.net next run):\n"
      f"  Morocco +{d_mar:.0f} -> {ELO_MC['Morocco']:.0f}, "
      f"France +{d_fra:.0f} -> {ELO_MC['France']:.0f}, "
      f"Norway +{d_nor:.0f} -> {ELO_MC['Norway']:.0f}, "
      f"England +{d_eng:.0f} -> {ELO_MC['England']:.0f}")

_cache = {}


def p_adv(a, b, bump_a=0.0):
    key = (a, b, bump_a)
    if key not in _cache:
        _cache[key] = ko_predict(ELO_MC[a], ELO_MC[b], home_bump=bump_a)["adv"]
    return _cache[key]


# QF97 FRA-MAR (locked) | QF98 W(PorSpa)-W(USABel) | QF99 NOR-ENG (locked) |
# QF100 W(ArgEgy)-W(SwiCol). SF101 = W97 v W98, SF102 = W99 v W100.
# USA host bump applied in their R16 game only (consistent w/ 7/5 MC method;
# QF+ venue/crowd mix uncertain -> conservative).
R16_LIVE = [("Portugal", "Spain", 0.0), ("USA", "Belgium", 85.0),
            ("Argentina", "Egypt", 0.0), ("Switzerland", "Colombia", 0.0)]
SIMS, rng = 50000, random.Random(42)
teams = ["France", "Morocco", "Norway", "England"] + \
    [t for tie in R16_LIVE for t in tie[:2]]
tally = {t: {r: 0 for r in ["QF", "SF", "Final", "Champion"]} for t in teams}
for _ in range(SIMS):
    w = {}
    for h, a, bump in R16_LIVE:
        w[(h, a)] = h if rng.random() < p_adv(h, a, bump) else a
    for t in ("France", "Morocco", "Norway", "England"):
        tally[t]["QF"] += 1
    for tie, x in w.items():
        tally[x]["QF"] += 1
    qf = [("France", "Morocco"),
          (w[("Portugal", "Spain")], w[("USA", "Belgium")]),
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
