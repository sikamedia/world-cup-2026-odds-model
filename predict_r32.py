#!/usr/bin/env python3
"""Round of 32 advancement table — who reaches the Round of 16.

Uses the validated knockout profile (match_model.py --stage knockout): 90' from
Poisson+Dixon-Coles, then the draw mass resolved by ET/penalties. This needs
ONLY the 16 fixed matchups (no bracket tree), so the advancement numbers here
are exact. Champion / deep-run odds need the R16+ bracket order (see
tournament_mc.py) and are NOT produced here.

Neutral venues (no host bump), full intensity (no motivation/rotation).
Run:  python3 predict_r32.py
Educational/analytical use only - not betting advice.
"""
import os
import sys

ROOT = os.path.dirname(__file__)
for _scripts in (os.path.join(ROOT, "skill", "scripts"), os.path.join(ROOT, "scripts")):
    if os.path.isdir(_scripts):
        sys.path.insert(0, _scripts)
        break
import match_model as mm  # noqa: E402

from worldcup_2026_data_ko import ELO, R32_FIXTURES  # noqa: E402

KO = mm.STAGE_PROFILES["knockout"]


def tie(home, away):
    eh, ea = ELO[home], ELO[away]
    lh, la = mm.elo_to_lambdas(eh, ea, avg_goals=KO["avg_goals"],
                               gd_per_100=KO["gd_per_100"],
                               floor=KO.get("lambda_floor", 0.15))
    style = "open" if abs(eh - ea) >= 266 else "balanced"
    P = mm.score_matrix(lh, la, opp_style=style, draw_boost=KO["draw_boost"])
    ph, pd, pa, _ov, _btts = mm.summarise(P)
    e_home = 1 / (1 + 10 ** (-(eh - ea) / 400))
    k_eff = mm.graded_ko_regress(eh - ea, KO["ko_regress"],
                                 KO.get("ko_regress_max", KO["ko_regress"]),
                                 KO.get("ko_elo_scale", 350.0))
    adv = mm.advancement(P, e_home, k_eff, KO["pen_tilt"])
    return ph, pd, pa, adv, k_eff


def main():
    print("ROUND OF 32 — advancement to R16 (knockout profile, "
          f"avg_goals {KO['avg_goals']}, graded-k)")
    print(f"\n{'Tie':34}{'90 H/D/A %':>16}{'k_eff':>8}{'  ADVANCE (graded)':>26}")
    print("-" * 86)
    for home, away in R32_FIXTURES:
        ph, pd, pa, adv, k_eff = tie(home, away)
        ah, aa = adv["adv_reg"], 1 - adv["adv_reg"]
        fav, fav_p = (home, ah) if ah >= aa else (away, aa)
        print(f"{home + ' v ' + away:34}"
              f"{ph*100:5.0f}/{pd*100:3.0f}/{pa*100:3.0f}"
              f"{k_eff:8.2f}    "
              f"{home[:12]:>12} {ah*100:4.1f}%  |  {away[:12]:>12} {aa*100:4.1f}%")
    print("\nADVANCE = P(through to R16) incl. ET/penalties; home+away = 100%.")
    print("Educational/analytical use only; not betting advice.")


if __name__ == "__main__":
    main()
