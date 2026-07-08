#!/usr/bin/env python3
"""Knockout bracket Monte Carlo from the FIXED Round-of-32 ties.

Starts from the 16 known R32 matchups (no group simulation, no random
qualification) and plays out the single-elimination bracket, resolving every
tie with the validated knockout advancement (90' Poisson+DC -> ET/penalties,
match_model.advancement). Reports R16 / QF / SF / Final / Champion probabilities.

R32_FIXTURES is in OFFICIAL bracket-tree leaf order (FIFA Match 73-104), so
pairing winners in list order — (tie1,tie2) -> R16, (tie3,tie4) -> R16, ... —
reproduces the exact tree: top half = ties 1-8, bottom half = ties 9-16. No
shuffle. (Spain & Portugal meet in R16; Argentina & Brazil are in the same
bottom half and can only meet from the SF.)

Run:  python3 predict_bracket.py [--sims N]
Educational/analytical use only - not betting advice.
"""
import argparse
import os
import random
import sys

ROOT = os.path.dirname(__file__)
for _scripts in (os.path.join(ROOT, "skill", "scripts"), os.path.join(ROOT, "scripts")):
    if os.path.isdir(_scripts):
        sys.path.insert(0, _scripts)
        break
import match_model as mm  # noqa: E402

from worldcup_2026_data_ko import ELO, R32_FIXTURES  # noqa: E402

KO = mm.STAGE_PROFILES["knockout"]
_cache: dict[tuple[str, str], float] = {}


def p_advance(a, b):
    """P(team a beats team b in a knockout tie), with caching (symmetric)."""
    if (a, b) in _cache:
        return _cache[(a, b)]
    ea, eb = ELO[a], ELO[b]
    lh, la = mm.elo_to_lambdas(ea, eb, avg_goals=KO["avg_goals"],
                               gd_per_100=KO["gd_per_100"],
                               floor=KO.get("lambda_floor", 0.15))
    style = "open" if abs(ea - eb) >= 266 else "balanced"
    P = mm.score_matrix(lh, la, opp_style=style, draw_boost=KO["draw_boost"])
    e_home = 1 / (1 + 10 ** (-(ea - eb) / 400))
    # LOCKED 2026-07-04: ΔElo-graded ko_regress (was flat KO["ko_regress"]).
    k_eff = mm.graded_ko_regress(ea - eb, KO["ko_regress"],
                                 KO.get("ko_regress_max", KO["ko_regress"]),
                                 KO.get("ko_elo_scale", 350.0))
    pa = mm.advancement(P, e_home, k_eff, KO["pen_tilt"])["adv_reg"]
    _cache[(a, b)] = pa
    _cache[(b, a)] = 1 - pa
    return pa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=50000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    teams = [t for tie in R32_FIXTURES for t in tie]  # 32 in bracket order
    rounds = ["R16", "QF", "SF", "Final", "Champion"]
    tally = {t: {r: 0 for r in rounds} for t in teams}

    for _ in range(args.sims):
        cur = teams[:]
        for r in rounds:
            nxt = []
            for i in range(0, len(cur), 2):
                a, b = cur[i], cur[i + 1]
                w = a if rng.random() < p_advance(a, b) else b
                tally[w][r] += 1
                nxt.append(w)
            cur = nxt

    N = args.sims
    order = sorted(teams, key=lambda t: -tally[t]["Champion"])
    print(f"KNOCKOUT BRACKET from fixed R32 ({N} sims, knockout profile)")
    print("Official FIFA bracket tree (Match 73-104) — exact pairings, no shuffle.")
    print(f"\n{'Team':16}{'Champ':>7}{'Final':>7}{'SF':>6}{'QF':>6}{'R16':>6}")
    for t in order:
        x = tally[t]
        print(f"{t:16}{x['Champion']/N*100:6.1f}%{x['Final']/N*100:6.1f}%"
              f"{x['SF']/N*100:5.1f}%{x['QF']/N*100:5.1f}%{x['R16']/N*100:5.1f}%")
    print("\nEducational/analytical use only; not betting advice.")


if __name__ == "__main__":
    main()
