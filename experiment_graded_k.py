#!/usr/bin/env python3
"""Experiment: ΔElo-GRADED knockout regression vs a flat ko_regress.

MOTIVATION (n=13, R32 nearly complete): the flat ko_regress=0.70 has been
over-regressing knockout favourites. best-Brier k drifted 0.70 -> 0.85 -> 1.00
across three runs, and every LARGE-ΔElo favourite advanced in regulation; the
only 3 upsets were 2 penalty-shootout deaths (Ger, Ned, both 1-1 at 90') and 1
near-coin-flip (CIV over Norway, ΔElo -60). That is exactly the shape a graded
regression predicts: huge favourites barely need regressing, coin-flips need it
most.

GRADED RULE:
    k_eff = k_min + (k_max - k_min) * min(1, |ΔElo| / SCALE)
  |ΔElo| >= SCALE  -> k_eff = k_max (~1.0, trust the 90' win split, no regress)
  |ΔElo| = 0       -> k_eff = k_min (regress the coin-flip hardest toward 0.5)

This keeps the single-leg variance cushion exactly where the data says upsets
live (even ties), and removes it where the data says they don't (blowout-gap
favourites). Educational/analytical use only - not betting advice.
"""
import math
import os
import sys

ROOT = os.path.dirname(__file__)
for _scripts in (os.path.join(ROOT, "skill", "scripts"), os.path.join(ROOT, "scripts")):
    if os.path.isdir(_scripts):
        sys.path.insert(0, _scripts)
        break
import match_model as mm  # noqa: E402
from worldcup_2026_data_ko import ELO, KO_RESULTS  # noqa: E402

KO = mm.STAGE_PROFILES["knockout"]


def graded_k(d_elo, k_min, k_max, scale):
    return k_min + (k_max - k_min) * min(1.0, abs(d_elo) / scale)


def adv_home(P, e_home, k):
    return mm.advancement(P, e_home, k, KO["pen_tilt"])["adv_reg"]


def build_records():
    recs = []
    for home, away, hg, ag, advanced, _stage in KO_RESULTS:
        eh, ea = ELO[home], ELO[away]
        lh, la = mm.elo_to_lambdas(eh, ea, avg_goals=KO["avg_goals"],
                                   gd_per_100=KO["gd_per_100"])
        style = "open" if abs(eh - ea) >= 266 else "balanced"
        P = mm.score_matrix(lh, la, opp_style=style, draw_boost=KO["draw_boost"])
        e_home = 1 / (1 + 10 ** (-(eh - ea) / 400))
        recs.append(dict(home=home, away=away, d=eh - ea, P=P, e=e_home,
                         o=1.0 if advanced == "H" else 0.0))
    return recs


def score_flat(recs, k):
    b = ll = 0.0
    for r in recs:
        p = adv_home(r["P"], r["e"], k)
        b += (p - r["o"]) ** 2
        ll += -(r["o"] * math.log(max(p, 1e-12))
                + (1 - r["o"]) * math.log(max(1 - p, 1e-12)))
    n = len(recs)
    return b / n, ll / n


def score_graded(recs, k_min, k_max, scale):
    b = ll = 0.0
    for r in recs:
        k = graded_k(r["d"], k_min, k_max, scale)
        p = adv_home(r["P"], r["e"], k)
        b += (p - r["o"]) ** 2
        ll += -(r["o"] * math.log(max(p, 1e-12))
                + (1 - r["o"]) * math.log(max(1 - p, 1e-12)))
    n = len(recs)
    return b / n, ll / n


def main():
    recs = build_records()
    n = len(recs)
    print("#" * 68)
    print(f"# GRADED-k EXPERIMENT — knockout advancement, n={n}")
    print("#" * 68)

    print("\nFLAT ko_regress (baseline sweep):")
    print(f"  {'k':>6}{'Brier':>10}{'logLoss':>10}")
    for k in (0.60, 0.70, 0.85, 1.00):
        b, l = score_flat(recs, k)
        star = "  <- current default" if abs(k - 0.70) < 1e-9 else ""
        print(f"  {k:>6.2f}{b:>10.4f}{l:>10.4f}{star}")

    print("\nGRADED ko_regress  k_eff = k_min + (k_max-k_min)*min(1,|dElo|/scale):")
    print(f"  {'k_min':>6}{'k_max':>6}{'scale':>7}{'Brier':>10}{'logLoss':>10}")
    configs = [
        (0.70, 1.00, 300),
        (0.65, 1.00, 300),
        (0.60, 1.00, 300),
        (0.70, 1.00, 350),
        (0.65, 1.00, 350),
        (0.60, 1.00, 400),
    ]
    best = None
    for kmin, kmax, sc in configs:
        b, l = score_graded(recs, kmin, kmax, sc)
        print(f"  {kmin:>6.2f}{kmax:>6.2f}{sc:>7d}{b:>10.4f}{l:>10.4f}")
        if best is None or b < best[0]:
            best = (b, l, kmin, kmax, sc)

    print(f"\nBEST graded on n={n}: k_min {best[2]} k_max {best[3]} scale {best[4]}"
          f"  Brier {best[0]:.4f}  logLoss {best[1]:.4f}")

    # per-game k_eff for the best graded config (sanity: huge favs ~1.0, coin-flips low)
    _, _, kmin, kmax, sc = best
    print(f"\nPer-tie k_eff (best graded: {kmin}->{kmax} over |dElo|/{sc}):")
    print(f"  {'Tie':30}{'dElo':>6}{'k_eff':>7}{'advH_flat70':>12}{'advH_grad':>11}")
    for r in recs:
        k = graded_k(r["d"], kmin, kmax, sc)
        p70 = adv_home(r["P"], r["e"], 0.70)
        pg = adv_home(r["P"], r["e"], k)
        tie = f"{r['home'][:12]} v {r['away'][:12]}"
        print(f"  {tie:30}{r['d']:>6d}{k:>7.2f}{p70*100:>11.1f}%{pg*100:>10.1f}%")

    print("\nEducational/analytical use only; not betting advice.")


if __name__ == "__main__":
    main()
