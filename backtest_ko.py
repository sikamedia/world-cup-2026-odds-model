#!/usr/bin/env python3
"""Knockout-stage backtest — SEPARATE batch from the 72 group-stage games.

Mirrors backtest_72.py's metrics (RPS / Tipset / draw / big-win) but runs on the
knockout profile (lower avg_goals, advancement resolver) over KO_RESULTS only.
It reuses the validated engine from skill/scripts/match_model.py — one source of
truth, no duplicated scoring code.

DISCIPLINE: do NOT tune knockout params on a handful of games. R32 is only 16
matches; treat the knockout profile (avg_goals~2.70) as a market-anchored prior
until the sample is large enough to mean something. No motivation/rotation in
the knockouts (everyone is full strength).

Run:  python3 backtest_ko.py
Educational/analytical use only - not betting advice.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "skill", "scripts"))
import match_model as mm  # noqa: E402

from worldcup_2026_data_ko import ELO, HOME, KO_RESULTS  # noqa: E402,F401

KO = mm.STAGE_PROFILES["knockout"]


def res(hg, ag):
    return 0 if hg > ag else (1 if hg == ag else 2)


def rps_hda(probs, result):
    oc = [1 if result == k else 0 for k in range(3)]
    cp = co = score = 0.0
    for k in range(2):
        cp += probs[k]
        co += oc[k]
        score += (cp - co) ** 2
    return score / 2


def predict(home, away):
    """Neutral-venue knockout prediction (no host bump, no motivation)."""
    eh, ea = ELO[home], ELO[away]
    lh, la = mm.elo_to_lambdas(eh, ea, avg_goals=KO["avg_goals"],
                               gd_per_100=KO["gd_per_100"])
    style = "open" if abs(eh - ea) >= 266 else "balanced"
    P = mm.score_matrix(lh, la, opp_style=style, draw_boost=KO["draw_boost"])
    ph, pd, pa, _ov, _btts = mm.summarise(P)
    e_home = 1 / (1 + 10 ** (-(eh - ea) / 400))
    adv = mm.advancement(P, e_home, KO["ko_regress"], KO["pen_tilt"])
    return ph, pd, pa, P, adv


def main():
    games = KO_RESULTS
    n = len(games)
    print("#" * 64)
    print(f"# KNOCKOUT BACKTEST — {n} game(s)  (profile: avg_goals "
          f"{KO['avg_goals']}, ko_regress {KO['ko_regress']})")
    print("#" * 64)
    if n == 0:
        print("\nNo knockout results recorded yet. Append rows to KO_RESULTS in "
              "worldcup_2026_data_ko.py as games finish, then re-run.")
        # Smoke-test the pipeline on today's R32 fixture so the harness is known
        # to work before any results exist.
        ph, pd, pa, _P, adv = predict("South Africa", "Canada")
        print("\nPipeline smoke-test (South Africa vs Canada, not yet played):")
        print(f"  90' W/D/L : {ph*100:.1f}% / {pd*100:.1f}% / {pa*100:.1f}%")
        # adv_* is the HOME (South Africa) advancement; away is the complement.
        print(f"  ADVANCE   : SA raw {adv['adv_raw']*100:.1f}% / "
              f"regressed {adv['adv_reg']*100:.1f}%  |  "
              f"Canada raw {(1-adv['adv_raw'])*100:.1f}% / "
              f"regressed {(1-adv['adv_reg'])*100:.1f}%")
        return

    rps = ll = dps = 0.0
    dir_hit = rule_hit = adv_hit = draws_act = blow_act = 0
    blow_exp = 0.0
    print(f"\n{'Match':30}{'Score':>6}{'  H/D/A model%':>16}{'adv':>6}{'arg':>5}")
    for home, away, hg, ag, advanced, stage in games:
        ph, pd, pa, P, adv = predict(home, away)
        r = res(hg, ag)
        arg3 = max(range(3), key=lambda k: [ph, pd, pa][k])
        tip = 1 if (pd >= 0.26 and max(ph, pa) < 0.42) else (0 if ph > pa else 2)
        rps += rps_hda((ph, pd, pa), r)
        ll += math.log(max(P[(hg, ag)], 1e-12))
        dps += pd
        dir_hit += arg3 == r
        rule_hit += tip == r
        draws_act += r == 1
        blow_act += abs(hg - ag) >= 3
        blow_exp += sum(p for (i, j), p in P.items() if abs(i - j) >= 3)
        model_adv = "H" if adv["adv_reg"] >= 0.5 else "A"
        adv_hit += model_adv == advanced
        print(f"{home + ' v ' + away:30}{f'{hg}-{ag}':>6}"
              f"{ph*100:5.0f}/{pd*100:3.0f}/{pa*100:3.0f}"
              f"{advanced:>6}{['H','D','A'][arg3]:>5}")

    print(f"\nRPS {rps/n:.4f} | scoreline logL {ll:.2f} (avg {ll/n:.3f})")
    print(f"90' argmax dir {dir_hit}/{n} | Tipset {rule_hit}/{n}")
    print(f"Advancement called right: {adv_hit}/{n} "
          f"(model favourite actually went through)")
    print(f"Draws(90') actual {draws_act}/{n} | model avg draw {dps/n*100:.1f}%")
    print(f"Blowout>=3 actual {blow_act} | model exp {blow_exp:.1f}")
    print("\nEducational/analytical use only; not betting advice.")


if __name__ == "__main__":
    main()
