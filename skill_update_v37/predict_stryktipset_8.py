#!/usr/bin/env python3
"""Stryktipset 8-match slate.

Profile-driven engine. Default: stable_v35. Use --profile candidate_v36 to
run the latest experimental candidate without rewriting the script.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import match_model_v35 as mm

from market_blend import blend_probs
from match_context import de_margin_odds, market_gap
from model_stability import PROFILE_REGISTRY, STABLE_V35, resolve_profile
from worldcup_2026_data import ELO


M = [
    (
        "Switzerland",
        "Canada",
        2,
        85,
        0.92,
        0.92,
        1.00,
        (2.50, 3.05, 3.40),
        "Vancouver (Canada real home, indoor); both on 4 pts, draw may suit both",
    ),
    (
        "Bosnia",
        "Qatar",
        0,
        0,
        0.94,
        0.94,
        1.00,
        (1.34, 5.80, 8.50),
        "Seattle neutral; bottom two, one side will go out",
    ),
    (
        "Morocco",
        "Haiti",
        0,
        0,
        1.00,
        0.90,
        1.00,
        (1.15, 8.50, 23.00),
        "Atlanta indoor AC; Morocco chase group top, Haiti already out",
    ),
    (
        "Scotland",
        "Brazil",
        0,
        0,
        0.93,
        0.93,
        0.92,
        (11.00, 6.00, 1.29),
        "Miami humid heat (total goals down); both need something, Brazil edge",
    ),
    (
        "Czechia",
        "Mexico",
        2,
        85,
        1.06,
        0.88,
        1.00,
        (4.00, 4.00, 1.92),
        "Azteca (Mexico real home + altitude); Mexico already through, Czechia must win",
    ),
    (
        "South Africa",
        "Korea",
        0,
        0,
        1.00,
        1.00,
        0.95,
        (6.40, 3.90, 1.61),
        "Monterrey heat (light downshift); Korea need a point, South Africa must win",
    ),
    (
        "Japan",
        "Sweden",
        0,
        0,
        1.00,
        1.00,
        1.00,
        (1.91, 3.50, 4.50),
        "Neutral; Japan 4 pts, Sweden 3 pts, both full pace",
    ),
    (
        "Tunisia",
        "Netherlands",
        0,
        0,
        0.90,
        1.00,
        1.00,
        None,
        "Neutral (market missing); Netherlands chase top, Tunisia already out",
    ),
]


def _parse_profile(raw: str):
    try:
        return resolve_profile(raw)
    except KeyError as exc:
        available = ", ".join(sorted(PROFILE_REGISTRY))
        raise argparse.ArgumentTypeError(f"{exc}. Available profiles: {available}") from exc


def model_match(t1, t2, home_side, bump, m1, m2, wx, profile):
    e1 = ELO[t1] + (bump if home_side == 1 else 0)
    e2 = ELO[t2] + (bump if home_side == 2 else 0)
    lh, la = mm.elo_to_lambdas(
        e1,
        e2,
        avg_goals=profile.avg_goals,
        gd_per_100=profile.gd_per_100,
    )
    lh *= m1 * wx
    la *= m2 * wx
    style = "open" if abs(e1 - e2) >= profile.open_delo else "balanced"
    P = mm.score_matrix(
        lh,
        la,
        opp_style=style,
        draw_boost=profile.draw_boost,
        disp=profile.dispersion,
    )
    h, d, a, ov, _ = mm.summarise(P)
    top = sorted(P.items(), key=lambda x: -x[1])[:3]
    return h, d, a, ov, lh, la, top


def _fmt_triplet(values: tuple[float, float, float]) -> str:
    return f"{values[0] * 100:.1f}/{values[1] * 100:.1f}/{values[2] * 100:.1f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--profile",
        type=_parse_profile,
        default=STABLE_V35,
        help="Model profile or alias (default: stable_v35).",
    )
    ap.add_argument(
        "--market-weight",
        type=float,
        default=None,
        help="Optional blend weight for market probabilities where odds exist (0..1).",
    )
    ap.add_argument(
        "--market-method",
        choices=["proportional", "power"],
        default="proportional",
        help="De-margin method for embedded odds.",
    )
    args = ap.parse_args()
    profile = args.profile
    if args.market_weight is not None and not 0.0 <= args.market_weight <= 1.0:
        ap.error("--market-weight must be between 0 and 1")

    print(f"{'#':<2}{'Match':28}{'model 1/X/2':>20}{'  pick':>7}{'conf':>6}   market(de-marg) 1/X/2")
    print("-" * 100)
    print(f"Profile: {profile.name} | {profile.notes}")
    rows = []
    for i, (t1, t2, hs, bump, m1, m2, wx, odds, note) in enumerate(M, 1):
        h, d, a, ov, lh, la, top = model_match(t1, t2, hs, bump, m1, m2, wx, profile)
        if d >= 0.26 and max(h, a) < profile.draw_gate:
            pick = "X"
        else:
            pick = "1" if h > a else "2"
        conf = max(h, d, a)
        if odds:
            mk, overround = de_margin_odds(odds, method=args.market_method)
            gap = market_gap((h, d, a), mk)
            blended = blend_probs((h, d, a), mk, args.market_weight) if args.market_weight is not None else None
            mkt = f"{mk[0] * 100:4.0f}/{mk[1] * 100:3.0f}/{mk[2] * 100:3.0f}%"
        else:
            gap = None
            blended = None
            mkt = "   (no odds)"
        print(
            f"{i:<2}{t1[:11] + '-' + t2[:11]:28}{h * 100:5.1f}/{d * 100:4.1f}/{a * 100:4.1f}%"
            f"{pick:>7}{conf * 100:5.0f}%   {mkt}"
        )
        rows.append((i, t1, t2, h, d, a, ov, pick, conf, lh, la, top, odds, note, gap, overround if odds else None, blended))

    print("\n--- per-match detail (top scorelines, O/U2.5, notes) ---")
    for (i, t1, t2, h, d, a, ov, pick, conf, lh, la, top, odds, note, gap, overround, blended) in rows:
        cs = " ".join(f"{x[0][0]}-{x[0][1]}:{x[1] * 100:.0f}%" for x in top)
        print(f"\n{i}. {t1} - {t2}   [λ {lh:.2f}-{la:.2f}]")
        print(
            f"   1X2: 1 {h * 100:.1f}%  X {d * 100:.1f}%  2 {a * 100:.1f}%  | "
            f"pick {pick} (conf {conf * 100:.0f}%)  | O2.5 {ov * 100:.0f}%"
        )
        print(f"   top CS: {cs}")
        if gap is not None:
            print(
                f"   market gap: {gap[0] * 100:+.1f}/{gap[1] * 100:+.1f}/{gap[2] * 100:+.1f} pts"
                f" | {args.market_method} overround {overround * 100:.1f}%"
            )
        if blended is not None:
            print(f"   blend w={args.market_weight:.2f}: {_fmt_triplet(blended)}")
        print(f"   note: {note}")
    print("\n教育/分析用途,不构成投注建议。")


if __name__ == "__main__":
    main()
