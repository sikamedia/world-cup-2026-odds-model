#!/usr/bin/env python3
"""Predict the 6 June-26 2026 WC matchday-3 finales.

This version uses the shared profile engine plus structured competition_state
instead of manual MOT scaling. The default slate comes from
worldcup_2026_data_jun27.py; a context file can override market odds, lineup
scales, weather, or the competition state itself.
"""

from __future__ import annotations

import argparse

from competition_state import competition_state_payload, match_adjustments, match_state_from_motivation, match_state_summary
from market_blend import blend_probs, effective_market_weight
from match_context import context_key, load_context_file
from model_stability import CANDIDATE_V36, PROFILE_REGISTRY, STABLE_V35, predict_match, resolve_profile
from worldcup_2026_data_jun27 import JUNE_27_COMPETITION_STATE, JUNE_27_MATCHES


def _parse_profile(raw: str):
    try:
        return resolve_profile(raw)
    except KeyError as exc:
        available = ", ".join(sorted(PROFILE_REGISTRY))
        raise argparse.ArgumentTypeError(f"{exc}. Available profiles: {available}") from exc


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _fmt_gap(values: tuple[float, float, float]) -> str:
    return f"{values[0] * 100:+.1f}/{values[1] * 100:+.1f}/{values[2] * 100:+.1f} pts"


def _fmt_triplet(values: tuple[float, float, float]) -> str:
    return f"{values[0] * 100:.1f}% / {values[1] * 100:.1f}% / {values[2] * 100:.1f}%"


def _default_competition_state(home: str, away: str, mot_home: str, mot_away: str):
    key = context_key(home, away)
    return JUNE_27_COMPETITION_STATE.get(key) or competition_state_payload(
        match_state_from_motivation(mot_home, mot_away)
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--profile",
        type=_parse_profile,
        default=CANDIDATE_V36,
        help="Model profile or alias (default: candidate_v36 = recommended v3.7A).",
    )
    ap.add_argument(
        "--context-file",
        help="Optional JSON file with per-match market odds and lineup overrides.",
    )
    ap.add_argument(
        "--market-weight",
        type=float,
        default=None,
        help="Optional blend weight for market probabilities when context odds exist (0..1).",
    )
    args = ap.parse_args()

    profile = args.profile
    try:
        contexts = load_context_file(args.context_file) if args.context_file else {}
    except Exception as exc:  # pragma: no cover - CLI ergonomics
        ap.error(f"failed to load context file: {exc}")
    if args.market_weight is not None and not 0.0 <= args.market_weight <= 1.0:
        ap.error("--market-weight must be between 0 and 1")

    print("=" * 78)
    print(f"2026 WORLD CUP - June 27 predictions ({profile.name})")
    print(f"  {profile.notes}")
    print("=" * 78)

    for home, away, host_home, heat, mot_home, mot_away, ctx in JUNE_27_MATCHES:
        ctx_override = contexts.get(context_key(home, away))
        weather_scale = ctx_override.weather_scale if ctx_override else 1.0
        lineup_home = ctx_override.lineup_home if ctx_override else 1.0
        lineup_away = ctx_override.lineup_away if ctx_override else 1.0
        market_odds = ctx_override.market_odds if ctx_override else None
        market_method = ctx_override.market_method if ctx_override else "proportional"
        market_confidence = ctx_override.market_confidence if ctx_override else 1.0
        competition_state = (
            ctx_override.competition_state
            if ctx_override and ctx_override.competition_state is not None
            else _default_competition_state(home, away, mot_home, mot_away)
        )
        state_adj = match_adjustments(competition_state)
        pred = predict_match(
            profile,
            home,
            away,
            host_home=host_home,
            heat=heat,
            weather_scale=weather_scale,
            lineup_home=lineup_home,
            lineup_away=lineup_away,
            market_odds=market_odds,
            market_method=market_method,
            competition_state=competition_state,
        )
        adj = []
        if heat != "none":
            adj.append(f"heat={heat}")
        if weather_scale != 1.0:
            adj.append(f"weather_scale={weather_scale:.2f}")
        if state_adj["mot_home"] != "normal":
            adj.append(f"{home}={state_adj['mot_home']}")
        if state_adj["mot_away"] != "normal":
            adj.append(f"{away}={state_adj['mot_away']}")
        if state_adj["lineup_home"] != 1.0:
            adj.append(f"{home}_state_lineup={state_adj['lineup_home']:.2f}")
        if state_adj["lineup_away"] != 1.0:
            adj.append(f"{away}_state_lineup={state_adj['lineup_away']:.2f}")
        if lineup_home != 1.0:
            adj.append(f"{home}_lineup={lineup_home:.2f}")
        if lineup_away != 1.0:
            adj.append(f"{away}_lineup={lineup_away:.2f}")
        if market_confidence != 1.0:
            adj.append(f"market_conf={market_confidence:.2f}")

        print(f"\n{'-' * 78}")
        print(f"{home} (home{'+HA' if host_home else ''}) vs {away}")
        print(f"  ctx: {ctx}")
        if ctx_override and ctx_override.notes:
            print(f"  ext: {ctx_override.notes}")
        print(f"  state: {match_state_summary(competition_state)}")
        print(f"  adj: {', '.join(adj) if adj else 'none'}")
        print(
            f"  lambdas: {home} {pred.lambda_home:.2f}  {away} {pred.lambda_away:.2f}  "
            f"(total {pred.lambda_home + pred.lambda_away:.2f})"
        )
        print(
            f"  1X2 :  {home} {_fmt_pct(pred.home_prob)}   "
            f"Draw {_fmt_pct(pred.draw_prob)}   {away} {_fmt_pct(pred.away_prob)}"
        )
        print(
            f"  fair odds : {1 / pred.home_prob:.2f} / {1 / pred.draw_prob:.2f} / "
            f"{1 / pred.away_prob:.2f}   | +5% margin: "
            f"{1 / (pred.home_prob * 1.05):.2f} / {1 / (pred.draw_prob * 1.05):.2f} / "
            f"{1 / (pred.away_prob * 1.05):.2f}"
        )
        print(
            f"  O/U 2.5 : Over {_fmt_pct(pred.over_prob)}  "
            f"Under {_fmt_pct(1 - pred.over_prob)}   BTTS {_fmt_pct(pred.btts_prob)}"
        )
        print(
            "  top scorelines: "
            + "  ".join(
                f"{i}-{j} {p * 100:.1f}%"
                for (i, j), p in pred.top_scorelines[:3]
            )
        )
        if pred.market_prob is not None and pred.market_gap is not None:
            print(
                f"  market ({pred.market_method}): "
                f"{_fmt_pct(pred.market_prob[0])} / {_fmt_pct(pred.market_prob[1])} / "
                f"{_fmt_pct(pred.market_prob[2])}"
            )
            print(f"  gap:    {_fmt_gap(pred.market_gap)}")
            if args.market_weight is not None:
                eff_weight = effective_market_weight(args.market_weight, market_confidence)
                blended = blend_probs(
                    (pred.home_prob, pred.draw_prob, pred.away_prob),
                    pred.market_prob,
                    eff_weight,
                )
                blend_pick = "1" if blended[0] > blended[2] else "2"
                if blended[1] >= 0.26 and max(blended[0], blended[2]) < profile.draw_gate:
                    blend_pick = "X"
                print(
                    f"  blend w={args.market_weight:.2f}"
                    + (f" eff={eff_weight:.2f}" if eff_weight != args.market_weight else "")
                    + f": {_fmt_triplet(blended)}  "
                    f"lean {blend_pick}"
                )
        print(f"  style: {pred.style_note}")
        print(f"  model lean: {pred.pick}")

    print("\nEducational/analytical use only; not betting advice. / 教育/分析用途,不构成投注建议。")


if __name__ == "__main__":
    main()
