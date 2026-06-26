#!/usr/bin/env python3
"""Evaluate model-vs-market blending on matches with supplied market odds.

This script is diagnostic only. It never promotes a model profile or mutates
defaults; it reports whether market information helps on the supplied split.
"""

from __future__ import annotations

import argparse

from market_blend import evaluate_market_blend, mean_and_stderr
from match_context import load_context_file
from model_stability import PROFILE_REGISTRY, STABLE_V35, resolve_profile
from worldcup_2026_data import BATCH_SPLITS, MATCHES_54, matches_for_batches


SPLIT_BATCHES = {
    "train": BATCH_SPLITS["train"],
    "validation": BATCH_SPLITS["validation"],
    "locked_test": BATCH_SPLITS["locked_test"],
    "all": tuple(sorted({m[5] for m in MATCHES_54})),
}


def _parse_profile(raw: str):
    try:
        return resolve_profile(raw)
    except KeyError as exc:
        available = ", ".join(sorted(PROFILE_REGISTRY))
        raise argparse.ArgumentTypeError(f"{exc}. Available profiles: {available}") from exc


def _parse_weights(raw: str) -> list[float]:
    weights = [float(part.strip()) for part in raw.split(",") if part.strip()]
    for weight in weights:
        if not 0.0 <= weight <= 1.0:
            raise argparse.ArgumentTypeError("weights must be in [0, 1]")
    return weights


def _pct_triplet(values: tuple[float, float, float]) -> str:
    return f"{values[0] * 100:5.1f}/{values[1] * 100:4.1f}/{values[2] * 100:4.1f}%"


def _weight_summary(report: dict) -> tuple[float | None, float | None]:
    rows = report.get("rows", [])
    if not rows:
        return None, None
    return mean_and_stderr([row["rps"] for row in rows])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context-file", required=True, help="JSON context file with market_odds.")
    ap.add_argument(
        "--profile",
        type=_parse_profile,
        default=STABLE_V35,
        help="Model profile or alias (default: stable_v35).",
    )
    ap.add_argument(
        "--split",
        choices=sorted(SPLIT_BATCHES),
        default="validation",
        help="Which chronological split to evaluate.",
    )
    ap.add_argument(
        "--weights",
        type=_parse_weights,
        default=_parse_weights("0,0.25,0.5,0.75,1"),
        help="Comma-separated market weights. 0=pure model, 1=pure market.",
    )
    ap.add_argument(
        "--ignore-context-adjustments",
        action="store_true",
        help="Use only market_odds from context, ignoring lineup/weather overrides.",
    )
    args = ap.parse_args()

    try:
        contexts = load_context_file(args.context_file)
    except Exception as exc:  # pragma: no cover - CLI ergonomics
        ap.error(f"failed to load context file: {exc}")

    matches = matches_for_batches(*SPLIT_BATCHES[args.split])
    use_adjustments = not args.ignore_context_adjustments
    context_matches = sum(
        1
        for match in matches
        if (ctx := contexts.get(f"{match[0]}|{match[1]}")) is not None and ctx.market_odds is not None
    )
    reports = [
        evaluate_market_blend(args.profile, matches, contexts, weight, use_adjustments)
        for weight in args.weights
    ]

    print("=" * 88)
    print(
        f"Market blend evaluation | profile={args.profile.name} | split={args.split} | "
        f"context_matches={context_matches}/{len(matches)}"
    )
    print("=" * 88)
    print(f"{'market_w':>8} {'n':>3} {'argmax':>8} {'RPS':>8} {'logLoss':>9} {'mean_abs_gap H/X/A':>24}")
    ranked = []
    for report in reports:
        if not report["n"]:
            print(f"{report['market_weight']:8.2f} {0:>3} {'-':>8} {'-':>8} {'-':>9} {'-':>24}")
            continue
        mean_gap = report["mean_abs_gap"]
        print(
            f"{report['market_weight']:8.2f} {report['n']:>3} "
            f"{report['argmax_hits']:>2}/{report['n']:<3} "
            f"{report['rps']:>8.4f} {report['log_loss']:>9.4f} "
            f"{mean_gap[0] * 100:6.1f}/{mean_gap[1] * 100:4.1f}/{mean_gap[2] * 100:4.1f} pts"
        )
        val_mean, val_se = _weight_summary(report)
        ranked.append((report["rps"], report["log_loss"], report["market_weight"], val_mean, val_se, report))

    if not ranked:
        print("\nNo evaluable matches. Add exact-orientation market odds such as 'France|Iraq'.")
        return

    _, _, best_weight, best_val_mean, best_val_se, best_report = min(ranked)
    one_se_band = (best_val_mean if best_val_mean is not None else best_report["rps"]) + (best_val_se or 0.0)
    conservative_candidates = [item for item in ranked if item[3] is not None and item[3] <= one_se_band]
    _, _, conservative_weight, conservative_val_mean, conservative_val_se, conservative_report = min(
        conservative_candidates, key=lambda item: item[2]
    )
    print()
    print(f"Best by RPS: market_weight={best_weight:.2f}")
    if conservative_val_mean is not None:
        print(
            f"One-SE conservative weight: market_weight={conservative_weight:.2f}  "
            f"(val RPS {conservative_val_mean:.4f} ± {conservative_val_se or 0.0:.4f})"
        )
    if best_report.get("mean_market_confidence") is not None:
        print(
            f"Mean market confidence: {best_report['mean_market_confidence']:.2f}  "
            f"mean effective weight: {best_report['mean_effective_weight']:.2f}"
        )
    print("Worst rows under the best blend")
    for row in sorted(best_report["rows"], key=lambda item: item["rps"], reverse=True)[:8]:
        model = _pct_triplet(row["model_probs"])
        market = _pct_triplet(row["market_probs"])
        blend = _pct_triplet(row["blend_probs"])
        print(
            f"  {row['home']} v {row['away']} {row['score']:<5} "
            f"RPS {row['rps']:.4f}  model {model}  market({row['market_method']}) {market}  blend {blend}"
        )
    if conservative_weight != best_weight:
        print("\nWorst rows under the conservative blend")
        for row in sorted(conservative_report["rows"], key=lambda item: item["rps"], reverse=True)[:8]:
            model = _pct_triplet(row["model_probs"])
            market = _pct_triplet(row["market_probs"])
            blend = _pct_triplet(row["blend_probs"])
            print(
                f"  {row['home']} v {row['away']} {row['score']:<5} "
                f"RPS {row['rps']:.4f}  model {model}  market({row['market_method']}) {market}  blend {blend}"
            )

    print("\n教育/分析用途,不构成投注建议。")


if __name__ == "__main__":
    main()
