#!/usr/bin/env python3
"""Knockout bracket Monte Carlo from the KNOWN Round-of-16 field (R32 done).

All 16 R32 ties are decided (7/3), so the R16 pairings are fixed by the FIFA
bracket tree (Match 89-104). This conditions on the actual qualifiers instead
of simulating the R32 (predict_bracket.py). Ties resolve with the LOCKED
2026-07-04 graded ko_regress advancement (see match_model.STAGE_PROFILES).

R16 list order below reproduces the official tree with adjacent pairing:
  QF M97=(A,B)  M98=(E,F)  M99=(C,D)  M100=(G,H)
  SF M101=(W97,W98)   M102=(W99,W100)

Run:  python3 predict_r16_bracket.py [--sims N]
Educational/analytical use only - not betting advice.
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "skill", "scripts"))
import match_model as mm  # noqa: E402

from worldcup_2026_data_ko import ELO  # noqa: E402

KO = mm.STAGE_PROFILES["knockout"]
_cache: dict[tuple[str, str], float] = {}

# Actual R16 field (winners of M73-M88), in bracket-tree leaf order A..H.
R16_FIXTURES = [
    ("Paraguay", "France"),        # M89  R16-A ┐QF M97
    ("Canada", "Morocco"),         # M90  R16-B ┘        ┐SF M101
    ("Portugal", "Spain"),         # R16-E ┐QF M98       │
    ("USA", "Belgium"),            # R16-F ┘
    ("Brazil", "Norway"),          # R16-C ┐QF M99
    ("Mexico", "England"),         # R16-D ┘        ┐SF M102
    ("Argentina", "Egypt"),        # R16-G ┐QF M100 │
    ("Switzerland", "Colombia"),   # R16-H ┘
]


def p_advance(a, b):
    """P(team a beats team b in a knockout tie), cached, graded ko_regress."""
    if (a, b) in _cache:
        return _cache[(a, b)]
    ea, eb = ELO[a], ELO[b]
    lh, la = mm.elo_to_lambdas(ea, eb, avg_goals=KO["avg_goals"],
                               gd_per_100=KO["gd_per_100"])
    style = "open" if abs(ea - eb) >= 266 else "balanced"
    P = mm.score_matrix(lh, la, opp_style=style, draw_boost=KO["draw_boost"])
    e_home = 1 / (1 + 10 ** (-(ea - eb) / 400))
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

    teams = [t for tie in R16_FIXTURES for t in tie]  # 16 in bracket order
    rounds = ["QF", "SF", "Final", "Champion"]
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
    print(f"BRACKET from KNOWN R16 field ({N} sims, LOCKED graded ko_regress)")
    print("QF=(A,B)(E,F)(C,D)(G,H); SF=(97,98)(99,100) — official FIFA tree.")
    print(f"\n{'Team':16}{'Champ':>7}{'Final':>7}{'SF':>6}{'QF':>6}")
    for t in order:
        x = tally[t]
        print(f"{t:16}{x['Champion']/N*100:6.1f}%{x['Final']/N*100:6.1f}%"
              f"{x['SF']/N*100:5.1f}%{x['QF']/N*100:5.1f}%")
    print("\nEducational/analytical use only; not betting advice.")


if __name__ == "__main__":
    main()
