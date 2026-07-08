#!/usr/bin/env python3
"""July 8 run (REST DAY — QFs start 7/9): grade the 7/7 R16 finale
(Argentina-Egypt official vs shadow lambda-floor, Switzerland-Colombia),
run the PRE-REGISTERED n=24 four-pack review, predict the QF slate
(France-Morocco 7/9 in full; other three QFs previewed), refresh the MC.

Elo note: World.tsv provenance-blocked AGAIN (3rd session; URL still not
in the task file). Fra/Mor/Spa/Nor/Eng verified 7/7 and unplayed since;
Arg/Swi/Egy/Col updated via the K=60 World-Elo replica (shootout counted
as a DRAW per eloratings.net convention) and labelled ESTIMATES.

Educational/analytical use only - not betting advice.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "skill", "scripts"))
import match_model as mm  # noqa: E402

KO = mm.STAGE_PROFILES["knockout"]


def lambdas_floor(eh, ea, floor):
    """Replicate elo_to_lambdas with a configurable lambda floor."""
    d = eh - ea
    gd = d / 100.0 * KO["gd_per_100"]
    base = KO["avg_goals"] / 2.0
    return max(floor, base + gd / 2), max(floor, base - gd / 2)


def ko_from_lambdas(lh, la, d_eff):
    style = "open" if abs(d_eff) >= 266 else "balanced"
    P = mm.score_matrix(lh, la, opp_style=style, draw_boost=KO["draw_boost"])
    h, d, a, ov, btts = mm.summarise(P)
    e_home = 1 / (1 + 10 ** (-d_eff / 400))
    k_eff = mm.graded_ko_regress(d_eff, KO["ko_regress"],
                                 KO["ko_regress_max"], KO["ko_elo_scale"])
    adv = mm.advancement(P, e_home, k_eff, KO["pen_tilt"])
    return dict(P=P, h=h, d=d, a=a, ov=ov, btts=btts,
                adv=adv["adv_reg"], k_eff=k_eff, style=style)


def rps3(ph, pd, pa, outcome):  # outcome: 0=H,1=D,2=A
    cum = [ph, ph + pd, 1.0]
    obs = [1.0 if outcome <= i else 0.0 for i in range(3)]
    return sum((c - o) ** 2 for c, o in zip(cum[:2], obs[:2])) / 2


print("=" * 68)
print("PART 1 — grade 7/7  (lambda-floor NATURAL EXPERIMENT: Arg-Egy)")
print("=" * 68)

# --- Argentina 3-2 Egypt (90'), ARG advanced. Egypt led 2-0 until 79'.
# Official call (floor 0.15, jul4-snapshot Elo 2148/1742):
#   90' 79.1/19.4/1.5, adv ARG 90.4, O2.5 46.1, BTTS 13.1
# Shadow call (floor 0.30, same inputs):
#   90' 76.0/20.7/3.3, adv ARG 88.1, BTTS 24.1
# Market adv ARG 84.3, ensemble 87.3.
EH, EA = 2148, 1742
d_eff = EH - EA
for tag, floor in (("OFFICIAL floor 0.15", 0.15), ("SHADOW  floor 0.30", 0.30)):
    lh, la = lambdas_floor(EH, EA, floor)
    r = ko_from_lambdas(lh, la, d_eff)
    p32 = r["P"].get((3, 2), 0.0)
    pegy2 = sum(p for (i, j), p in r["P"].items() if j >= 2)
    rps = rps3(r["h"], r["d"], r["a"], 0)
    print(f"\n  {tag}: lambda {lh:.2f}/{la:.2f}")
    print(f"    90' {r['h']*100:.1f}/{r['d']*100:.1f}/{r['a']*100:.1f}"
          f"  RPS(outcome H) {rps:.4f} | adv ARG {r['adv']*100:.1f}"
          f" Brier {(r['adv']-1)**2:.4f}")
    print(f"    channels vs reality (3-2, BTTS yes, 5 goals):"
          f"  P(3-2) {p32*100:.2f}%  logL {math.log(max(p32,1e-12)):.2f}"
          f" | P(Egy>=2) {pegy2*100:.1f}%"
          f" | BTTS-yes {r['btts']*100:.1f} (log {math.log(r['btts']):.2f})"
          f" | O2.5 {r['ov']*100:.1f}")
print(f"""
  market adv Brier (0.843): {(0.843-1)**2:.4f} | ensemble (0.873): {(0.873-1)**2:.4f}
  READ: official floor-0.15 wins the ADVANCEMENT channel (Arg did go
  through) — but Egypt led 2-0 and scored 2 REAL goals against a lambda
  pinned at 0.15 (expected 0.15 goals). Every goals-facing channel says
  the pinned distribution was wrong; see verdict in Part 2b.""")

# --- Switzerland 0-0 Colombia (120'), SUI 4-3 pens. Model had COL.
print("\n  Switzerland 0-0 Colombia (pens 4-3 SUI) — stored call "
      "25.4/32.4/42.1, adv COL 56.8:")
rps = rps3(0.254, 0.324, 0.421, 1)
print(f"    90' RPS(outcome D) {rps:.4f}; 0-0 was model rank-3 (9.0%); "
      f"U2.5 HIT (51.5); BTTS-yes 55.9 MISS (0-0 -> BTTS-no)")
print(f"    adv Brier: model (0.568) {0.568**2:.4f} | market (0.582) "
      f"{0.582**2:.4f} | ens (0.575) {0.575**2:.4f}  — ALL wrong side; "
      f"model least wrong")
print("    PENS-ALERT (32.4 >= 30) FIRED and HIT — 4th alert day, first "
      "hit since 6/28: tally 8 flagged -> 3 past 90' (37.5% vs implied "
      "~32%, consistent). Pen tilt had COL 51.7 — near-coin-flip, "
      "Swiss won it (miss, within design).")

print()
print("=" * 68)
print("PART 2 — PRE-REGISTERED n=24 REVIEW (four-pack)")
print("=" * 68)

# (a) ko_regress: numbers from backtest_ko.py n=24 run today.
print("""
(a) ko_regress graded (locked) vs flat-1.00  [backtest_ko.py, n=24]
      graded  Brier 0.1752   flat-1.00 0.1736   gap 0.0016 (was 0.0033 @n=22)
      Swi-Col upset PAID the graded buffer back: graded had COL 60.4 vs
      flat-1.00 COL 63.2 -> graded loses less on the wrong side. Exactly
      the Bra-Nor-class defence pre-registered on 7/3.
      DECISION (per pre-registration): KEEP graded lock. flat-1.00's edge
      halved on one upset; n=24 still too small to refit (script verdict
      agrees: HOLD). Re-review at n=28 (QFs complete).""")

# (b) lambda floor: verdict from Part 1 numbers (printed above).
lh15, la15 = lambdas_floor(EH, EA, 0.15)
lh30, la30 = lambdas_floor(EH, EA, 0.30)
r15 = ko_from_lambdas(lh15, la15, d_eff)
r30 = ko_from_lambdas(lh30, la30, d_eff)
print(f"""(b) lambda floor 0.15 vs 0.30 — graded on Arg 3-2 Egy:
      advancement: 0.15 wins by {((r30['adv']-1)**2-(r15['adv']-1)**2):.4f} Brier (tiny)
      goals channels: 0.30 wins BIG — P(3-2) {r30['P'].get((3,2),0)*100:.2f}% vs {r15['P'].get((3,2),0)*100:.2f}%,
      P(Egy>=2) {sum(p for (i,j),p in r30['P'].items() if j>=2)*100:.1f}% vs {sum(p for (i,j),p in r15['P'].items() if j>=2)*100:.1f}%, BTTS log {math.log(r30['btts']):.2f} vs {math.log(r15['btts']):.2f}
      DECISION: ADOPT floor 0.30 for the KO profile (affects only
      |dElo|-extreme ties where the floor engages). One game, but the
      failure mode is structural: a floor of 0.15 goals/90 makes ANY
      2-goal underdog day a ~1% event, and the market (Egy 90' 9.6%,
      BTTS ~market-implied 20s) always knew better. Advancement cost ~0.005.
      Goes into v3.9 bundle; shadow-log floor-0.15 for 2 more rounds.""")

# (c) ensemble w-fit on ledger n=8.
rows = [  # (p_model, p_market, fav_advanced)
    (0.642, 0.688, 1), (0.827, 0.889, 1), (0.599, 0.665, 0),
    (0.514, 0.519, 1), (0.672, 0.660, 1), (0.529, 0.484, 1),
    (0.904, 0.843, 1), (0.568, 0.582, 0),
]
best = min(((sum((w/100*pm+(1-w/100)*pk-y)**2 for pm, pk, y in rows)/len(rows), w/100)
            for w in range(0, 101, 5)))
bm = sum((pm-y)**2 for pm, pk, y in rows)/len(rows)
bk = sum((pk-y)**2 for pm, pk, y in rows)/len(rows)
be = sum((0.5*pm+0.5*pk-y)**2 for pm, pk, y in rows)/len(rows)
print(f"(c) ensemble ledger n=8: model {bm:.4f} < ens50 {be:.4f} < market {bk:.4f}")
print(f"      best w (grid .05): w_model = {best[1]:.2f} -> Brier {best[0]:.4f}")
print("      DECISION: n=8 too small for a hard switch; move official "
      "ensemble to w=0.6 model / 0.4 market (conservative step toward "
      "the fitted optimum), re-fit at n=12.")

# (d) KO draw_boost 0.06 check: expected vs actual 90' draws over n=24.
import worldcup_2026_data_ko as ko  # noqa: E402
exp_draws, act_draws = 0.0, 0
for home, away, hg, ag, advanced, stage in ko.KO_RESULTS:
    eh, ea = ko.ELO[home], ko.ELO[away]
    if home in ("USA", "Mexico", "Canada") or away in ("USA", "Mexico", "Canada"):
        pass  # backtest applies host bumps internally; replicate simply:
    bump = 85 if home in ("USA",) else (90 if home == "Mexico" else 0)
    lh, la = lambdas_floor(eh + bump, ea, 0.15)
    r = ko_from_lambdas(lh, la, eh + bump - ea)
    exp_draws += r["d"]
    act_draws += 1 if hg == ag else 0
print(f"(d) KO draw_boost 0.06: expected 90' draws {exp_draws:.1f} vs "
      f"actual {act_draws} over n=24 ({exp_draws/24*100:.1f}% vs "
      f"{act_draws/24*100:.1f}%)")
print("      DECISION: gap is small and the floor-0.30 adoption (b) will "
      "shave expected draws in extreme ties; keep 0.06, re-check at n=28.")

print()
print("=" * 68)
print("PART 3 — Elo updates (K=60 replica; shootout = DRAW per site rule)")
print("=" * 68)
# Arg 2151 beat Egy 1747 by 1 (90' 3-2): g=1.0
we = 1 / (1 + 10 ** (-(2151 - 1747) / 400))
d_arg = 60 * 1.0 * (1 - we)
# Swi 1943 drew Col 2009 (0-0, pens don't count): draw
we_s = 1 / (1 + 10 ** (-(1943 - 2009) / 400))
d_swi = 60 * 1.0 * (0.5 - we_s)
print(f"  Argentina +{d_arg:.1f} -> {2151+d_arg:.0f} | Egypt -> "
      f"{1747-d_arg:.0f} | Switzerland +{d_swi:.1f} -> {1943+d_swi:.0f} | "
      f"Colombia -> {2009-d_swi:.0f}   (ALL ESTIMATES pending World.tsv)")

ELO_QF = {"France": 2143, "Morocco": 1921, "Spain": 2177,
          "Belgium": 1961,  # est (site hadn't processed USA-Bel 7/7)
          "Norway": 1972, "England": 2076,
          "Argentina": round(2151 + d_arg), "Switzerland": round(1943 + d_swi)}

print()
print("=" * 68)
print("PART 4 — QF predictions (floor 0.30 NOW OFFICIAL per (b); "
      "floor-0.15 shadow-logged)")
print("=" * 68)


def qf_predict(eh, ea, floor=0.30, heat=None):
    lh, la = lambdas_floor(eh, ea, floor)
    scale = {"mild": 0.95, "moderate": 0.90, "severe": 0.85}.get(heat, 1.0)
    lh, la = lh * scale, la * scale
    return ko_from_lambdas(lh, la, eh - ea), lh, la


def show(tag, r, lh, la):
    top = sorted(r["P"].items(), key=lambda x: -x[1])[:4]
    tops = ", ".join(f"{i}-{j} {p*100:.1f}%" for (i, j), p in top)
    print(f"\n### {tag}")
    print(f"  lambda {lh:.2f}/{la:.2f} (k_eff {r['k_eff']:.2f}, "
          f"opp-style {r['style']})")
    print(f"  90': {r['h']*100:.1f} / {r['d']*100:.1f} / {r['a']*100:.1f}"
          f" | O2.5 {r['ov']*100:.1f} | BTTS {r['btts']*100:.1f}")
    print(f"  fair {1/r['h']:.2f}/{1/r['d']:.2f}/{1/r['a']:.2f} | +5% "
          f"{1/(r['h']*1.05):.2f}/{1/(r['d']*1.05):.2f}/{1/(r['a']*1.05):.2f}")
    print(f"  ADVANCE {r['adv']*100:.1f}% / {(1-r['adv'])*100:.1f}%")
    print(f"  top: {tops}")
    if r["d"] >= 0.30:
        print("  *** PENS-ALERT: 90' draw >= 30% ***")


# QF97 France-Morocco, Gillette Foxborough 7/9 16:00 ET, open-air,
# NWS 7/6 cycle: mostly sunny ~87F, SW 5-9 -> heat MILD (0.95).
fm, lh, la = qf_predict(ELO_QF["France"], ELO_QF["Morocco"], heat="mild")
show("QF97 France v Morocco — Gillette 7/9, 87F sunny -> heat mild", fm, lh, la)
# market: FanDuel -180/+290/+550, DK -170/+285/+500; advance -410/+310
for name, o in (("FanDuel", [1.5556, 3.90, 6.50]),
                ("DraftKings", [1.5882, 3.85, 6.00])):
    inv = [1 / x for x in o]
    s = sum(inv)
    p = [x / s for x in inv]
    print(f"  mkt {name}: F {p[0]*100:.1f} / D {p[1]*100:.1f} / "
          f"M {p[2]*100:.1f} (margin {(s-1)*100:.1f}%)")
adv_mkt = (1/1.2439) / ((1/1.2439) + (1/4.10))  # -410 = 1.2439, +310 = 4.10
print(f"  mkt ADVANCE: France {adv_mkt*100:.1f}% / Morocco "
      f"{(1-adv_mkt)*100:.1f}%")
w = 0.6
ens = w * fm["adv"] + (1 - w) * adv_mkt
print(f"  ENSEMBLE (w=0.6 model, per review (c)): France {ens*100:.1f}% / "
      f"Morocco {(1-ens)*100:.1f}%")

# Previews (weather = day-of check pending; no adjustment yet):
for tag, a, b in (("QF98 Spain v Belgium — SoFi LA 7/10 (indoor-roof venue)",
                   "Spain", "Belgium"),
                  ("QF99 Norway v England — Miami 7/11 17:00 ET (heat check pending)",
                   "Norway", "England"),
                  ("QF100 Argentina v Switzerland — Kansas City 7/11 21:00 ET (evening)",
                   "Argentina", "Switzerland")):
    r, lh, la = qf_predict(ELO_QF[a], ELO_QF[b])
    show(tag, r, lh, la)

print()
print("=" * 68)
print("PART 5 — bracket MC, QFs locked (50k sims; floor 0.30 official)")
print("=" * 68)
_cache = {}


def p_adv(a, b):
    key = (a, b)
    if key not in _cache:
        _cache[key] = qf_predict(ELO_QF[a], ELO_QF[b])[0]["adv"]
    return _cache[key]


SIMS, rng = 50000, random.Random(42)
teams = list(ELO_QF)
tally = {t: {r: 0 for r in ["SF", "Final", "Champion"]} for t in teams}
QF = [("France", "Morocco"), ("Spain", "Belgium"),
      ("Norway", "England"), ("Argentina", "Switzerland")]
for _ in range(SIMS):
    sf_in = []
    for h, a in QF:
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
print(f"\n{'Team':13}{'Champ':>7}{'Final':>7}{'SF':>7}   ({SIMS} sims)")
for t in sorted(teams, key=lambda x: -tally[x]["Champion"]):
    r = tally[t]
    print(f"{t:13}{r['Champion']/SIMS*100:>6.1f}%"
          f"{r['Final']/SIMS*100:>6.1f}%{r['SF']/SIMS*100:>6.1f}%")

print("\nEducational/analytical use only; not betting advice. / "
      "教育/分析用途，不构成投注建议。")
