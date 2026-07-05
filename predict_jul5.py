#!/usr/bin/env python3
"""July 5 run: R16 day-2 predictions (Brazil-Norway, Mexico-England) +
Elo-staleness counterfactual grading of the 7/4 games + updated bracket MC.

PREDICTION SIDE uses CURRENT Elo (elo_current_jul4.py, fetched 7/4 —
none of today's four teams has played since, so the snapshot is current),
per the 7/4 governance split. Backtests keep the stored historical dict.

Educational/analytical use only - not betting advice.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "skill", "scripts"))
import match_model as mm  # noqa: E402

from elo_current_jul4 import ELO_CURRENT  # noqa: E402
from worldcup_2026_data_ko import ELO as ELO_SNAPSHOT  # noqa: E402

KO = mm.STAGE_PROFILES["knockout"]


def world_elo_update(r_win, r_lose, gd, K=60):
    """World Football Elo: K=60 (WC finals), goal-diff multiplier."""
    g = 1.0 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8)
    we = 1 / (1 + 10 ** (-(r_win - r_lose) / 400))
    return K * g * (1 - we)


def ko_predict(eh, ea, home_bump=0.0, heat=None, rain=False,
               inj_home=1.0, inj_away=1.0):
    """Knockout tie: 90' probs + advancement at LOCKED graded k."""
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


print("=" * 68)
print("PART 1 — 7/4 counterfactual: stale vs current Elo (staleness grading)")
print("=" * 68)
for home, away, adv_actual in [("Canada", "Morocco", 0.0),
                               ("Paraguay", "France", 0.0)]:
    # adv_actual = 1.0 if HOME advanced else 0.0 (both away sides advanced)
    stale = ko_predict(ELO_SNAPSHOT[home], ELO_SNAPSHOT[away])
    cur = ko_predict(ELO_CURRENT[home], ELO_CURRENT[away])
    b_stale = (stale["adv"] - adv_actual) ** 2
    b_cur = (cur["adv"] - adv_actual) ** 2
    print(f"\n{home} v {away}  (actual: away advanced)")
    print(f"  stale Elo {ELO_SNAPSHOT[home]}/{ELO_SNAPSHOT[away]}: "
          f"adv_home {stale['adv']*100:.1f}%  Brier {b_stale:.4f}")
    print(f"  curr  Elo {ELO_CURRENT[home]}/{ELO_CURRENT[away]}: "
          f"adv_home {cur['adv']*100:.1f}%  Brier {b_cur:.4f}"
          f"   ({'BETTER' if b_cur < b_stale else 'worse'})")

print()
print("=" * 68)
print("PART 2 — today (7/5) predictions, CURRENT Elo")
print("=" * 68)

# --- Brazil v Norway, MetLife (neutral), 16:00 ET.
# Weather: 86F humid -> heat mild; 60% storms from ~kickoff -> rain scenario.
# Injuries: BRA no Paqueta (starter CM, thigh) x0.97; Raphinha already out all
# tournament (in Elo). NOR no Ryerson (starter wingback) x0.97 -> offsetting.
bn = ko_predict(ELO_CURRENT["Brazil"], ELO_CURRENT["Norway"],
                heat="mild", inj_home=0.97, inj_away=0.97)
show("Brazil v Norway — baseline (heat mild, Paqueta/Ryerson out)", bn)
bn_rain = ko_predict(ELO_CURRENT["Brazil"], ELO_CURRENT["Norway"],
                     heat="mild", rain=True, inj_home=0.97, inj_away=0.97)
show("Brazil v Norway — RAIN variant (60% storms at kickoff)", bn_rain)

# Market: FanDuel -125/+260/+360; bet365 -112/+240/+320; DK -110/+260/+310.
books = {"FanDuel": [1.80, 3.60, 4.60], "bet365": [1.893, 3.40, 4.20],
         "DraftKings": [1.909, 3.60, 4.10]}
print("\n  market 90' (proportional de-margin):")
acc = [0.0, 0.0, 0.0]
for name, o in books.items():
    p, ov = demargin3(o)
    acc = [a + x for a, x in zip(acc, p)]
    print(f"    {name:10} H {p[0]*100:.1f} / D {p[1]*100:.1f} / "
          f"A {p[2]*100:.1f}  (margin {ov:.1f}%)")
mkt_bn = [x / len(books) for x in acc]
print(f"    {'AVG':10} H {mkt_bn[0]*100:.1f} / D {mkt_bn[1]*100:.1f} / "
      f"A {mkt_bn[2]*100:.1f}")
# advance: FanDuel -270/+210 -> 69.3/30.7; DK -215/+170 -> 64.8/35.2;
# Kalshi 67c/36c -> 65.0/35.0
adv_books = [(0.7297, 0.3226), (0.6825, 0.3704), (0.67, 0.36)]
mkt_adv_bra = sum(a / (a + b) for a, b in adv_books) / len(adv_books)
print(f"  market ADVANCE: Brazil {mkt_adv_bra*100:.1f}% / "
      f"Norway {(1-mkt_adv_bra)*100:.1f}%")
ens_bra = (bn["adv"] + mkt_adv_bra) / 2
print(f"  ENSEMBLE (model/market 50:50): Brazil {ens_bra*100:.1f}% / "
      f"Norway {(1-ens_bra)*100:.1f}%")

# --- Mexico v England, Azteca (HOST + 2200m altitude: +90 per project
# convention, validated on Mexico-Ecuador R32 and USA R32). 18:00 local.
# Weather: ~19C evening, rainy-season storm risk (conditional, not applied).
# Injuries: ENG Quansah/James out = backup defenders, first XI intact -> no adj.
me = ko_predict(ELO_CURRENT["Mexico"], ELO_CURRENT["England"], home_bump=90)
show("Mexico v England — Azteca host+altitude +90 (baseline)", me)
me_neu = ko_predict(ELO_CURRENT["Mexico"], ELO_CURRENT["England"])
print(f"  [neutral control: 90' {me_neu['h']*100:.1f}/{me_neu['d']*100:.1f}/"
      f"{me_neu['a']*100:.1f}, adv MEX {me_neu['adv']*100:.1f}%]")

books2 = {"bet365": [3.00, 3.10, 2.50], "book2": [3.20, 3.10, 2.43],
          "Kalshi": [1 / .32, 1 / .30, 1 / .40]}
print("\n  market 90' (proportional de-margin):")
acc = [0.0, 0.0, 0.0]
for name, o in books2.items():
    p, ov = demargin3(o)
    acc = [a + x for a, x in zip(acc, p)]
    print(f"    {name:10} H {p[0]*100:.1f} / D {p[1]*100:.1f} / "
          f"A {p[2]*100:.1f}  (margin {ov:.1f}%)")
mkt_me = [x / len(books2) for x in acc]
print(f"    {'AVG':10} H {mkt_me[0]*100:.1f} / D {mkt_me[1]*100:.1f} / "
      f"A {mkt_me[2]*100:.1f}")
# advance: ENG -108 / MEX +108 (near pick'em)
p_eng = (108 / 208) / (108 / 208 + 100 / 208)
mkt_adv_mex = 1 - p_eng
print(f"  market ADVANCE: Mexico {mkt_adv_mex*100:.1f}% / "
      f"England {p_eng*100:.1f}%")
ens_mex = (me["adv"] + mkt_adv_mex) / 2
print(f"  ENSEMBLE (model/market 50:50): Mexico {ens_mex*100:.1f}% / "
      f"England {(1-ens_mex)*100:.1f}%")

print()
print("=" * 68)
print("PART 3 — bracket MC from the live round (current Elo, post-7/4 upd)")
print("=" * 68)
ELO_MC = dict(ELO_CURRENT)
d_mar = world_elo_update(ELO_MC["Morocco"], ELO_MC["Canada"], 3)
d_fra = world_elo_update(ELO_MC["France"], ELO_MC["Paraguay"], 1)
ELO_MC["Morocco"] += d_mar
ELO_MC["France"] += d_fra
print(f"post-7/4 updates: Morocco +{d_mar:.0f} -> {ELO_MC['Morocco']:.0f}, "
      f"France +{d_fra:.0f} -> {ELO_MC['France']:.0f}")

_cache = {}


def p_adv(a, b, bump_a=0.0):
    key = (a, b, bump_a)
    if key not in _cache:
        _cache[key] = ko_predict(ELO_MC[a], ELO_MC[b], home_bump=bump_a)["adv"]
    return _cache[key]


R16_LIVE = [("Brazil", "Norway", 0.0), ("Mexico", "England", 90.0),
            ("Portugal", "Spain", 0.0), ("USA", "Belgium", 0.0),
            ("Argentina", "Egypt", 0.0), ("Switzerland", "Colombia", 0.0)]
SIMS, rng = 50000, random.Random(42)
teams = ["France", "Morocco"] + [t for tie in R16_LIVE for t in tie[:2]]
tally = {t: {r: 0 for r in ["QF", "SF", "Final", "Champion"]} for t in teams}
for _ in range(SIMS):
    # R16 live ties
    w = {}
    for h, a, bump in R16_LIVE:
        w[(h, a)] = h if rng.random() < p_adv(h, a, bump) else a
    for t in ("France", "Morocco"):
        tally[t]["QF"] += 1
    for tie, x in w.items():
        tally[x]["QF"] += 1
    # official tree: QF97 FRA-MAR | QF98 W(PorSpa)-W(USABel) |
    #                QF99 W(BraNor)-W(MexEng) | QF100 W(ArgEgy)-W(SwiCol)
    qf = [("France", "Morocco"),
          (w[("Portugal", "Spain")], w[("USA", "Belgium")]),
          (w[("Brazil", "Norway")], w[("Mexico", "England")]),
          (w[("Argentina", "Egypt")], w[("Switzerland", "Colombia")])]
    sf_in = []
    for h, a in qf:
        x = h if rng.random() < p_adv(h, a) else a
        tally[x]["SF"] += 1
        sf_in.append(x)
    # SF101 = W97 v W98, SF102 = W99 v W100
    fin = []
    for h, a in [(sf_in[0], sf_in[1]), (sf_in[2], sf_in[3])]:
        x = h if rng.random() < p_adv(h, a) else a
        tally[x]["Final"] += 1
        fin.append(x)
    c = fin[0] if rng.random() < p_adv(fin[0], fin[1]) else fin[1]
    tally[c]["Champion"] += 1

print(f"\n{'Team':13}{'Champ':>7}{'Final':>7}{'SF':>7}{'QF':>7}   ({SIMS} sims)")
for t in sorted(teams, key=lambda x: -tally[x]["Champion"]):
    x = tally[t]
    print(f"{t:13}{x['Champion']/SIMS*100:6.1f}%{x['Final']/SIMS*100:6.1f}%"
          f"{x['SF']/SIMS*100:6.1f}%{x['QF']/SIMS*100:6.1f}%")
print("\nEducational/analytical use only; not betting advice.")
