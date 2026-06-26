#!/usr/bin/env python3
"""Train the market/model blend weight without touching core model defaults."""

from __future__ import annotations

import argparse
import math

from market_blend import evaluate_market_blend, mean_and_stderr
from match_context import load_context_file
from model_stability import PROFILE_REGISTRY, STABLE_V35, resolve_profile
from worldcup_2026_data import BATCH_SPLITS, matches_for_batches


def _parse_profile(raw: str):
    try:
        return resolve_profile(raw)
    except KeyError as exc:
        available = ", ".join(sorted(PROFILE_REGISTRY))
        raise argparse.ArgumentTypeError(f"{exc}. Available profiles: {available}") from exc


def _parse_weights(raw: str) -> list[float]:
    weights = [float(part.strip()) for part in raw.split(",") if part.strip()]
    if not weights:
        raise argparse.ArgumentTypeError("at least one market weight is required")
    for weight in weights:
        if not 0.0 <= weight <= 1.0:
            raise argparse.ArgumentTypeError("market weights must be between 0 and 1")
    return weights


def _fmt_rps(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.4f}"


def _fmt_gap(gap) -> str:
    if gap is None:
        return "-"
    return f"{gap[0] * 100:.1f}/{gap[1] * 100:.1f}/{gap[2] * 100:.1f} pts"


def _weight_summary(report: dict) -> tuple[float | None, float | None]:
    rows = report.get("rows", [])
    if not rows:
        return None, None
    return mean_and_stderr([row["rps"] for row in rows])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context-file", required=True, help="JSON file with market odds.")
    ap.add_argument(
        "--profile",
        type=_parse_profile,
        default=STABLE_V35,
        help="Core model profile or alias (default: stable_v35).",
    )
    ap.add_argument(
        "--weights",
        type=_parse_weights,
        default=_parse_weights("0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1"),
        help="Comma-separated blend weights. 0=pure model, 1=pure market.",
    )
    ap.add_argument(
        "--ignore-context-adjustments",
        action="store_true",
        help="Ignore lineup/weather override fields and use market odds only.",
    )
    args = ap.parse_args()

    try:
        contexts = load_context_file(args.context_file)
    except Exception as exc:  # pragma: no cover - CLI ergonomics
        ap.error(f"failed to load context file: {exc}")

    splits = {
        "train": matches_for_batches(*BATCH_SPLITS["train"]),
        "validation": matches_for_batches(*BATCH_SPLITS["validation"]),
        "locked_test": matches_for_batches(*BATCH_SPLITS["locked_test"]),
    }
    use_adjustments = not args.ignore_context_adjustments
    validation_context_matches = sum(
        1
        for match in splits["validation"]
        if (ctx := contexts.get(f"{match[0]}|{match[1]}")) is not None and ctx.market_odds is not None
    )

    reports = {}
    for split_name, matches in splits.items():
        reports[split_name] = [
            evaluate_market_blend(args.profile, matches, contexts, weight, use_adjustments)
            for weight in args.weights
        ]

    print("=" * 96)
    print(
        f"Market blend training | profile={args.profile.name} | "
        f"context_matches={validation_context_matches}"
    )
    print("=" * 96)
    print(
        f"{'w':>5} | {'train RPS':>9} {'val RPS':>9} {'val SE':>7} {'test RPS':>9} "
        f"| {'train hit':>8} {'val hit':>8} {'test hit':>8}"
    )

    ranked = []
    for idx, weight in enumerate(args.weights):
        train_r = reports["train"][idx]
        val_r = reports["validation"][idx]
        test_r = reports["locked_test"][idx]
        val_mean, val_se = _weight_summary(val_r)
        print(
            f"{weight:5.2f} | "
            f"{_fmt_rps(train_r['rps']) if train_r['rps'] is not None else '-':>9} "
            f"{_fmt_rps(val_r['rps']) if val_r['rps'] is not None else '-':>9} "
            f"{(f'{val_se:.4f}' if val_se is not None else '-'):>7} "
            f"{_fmt_rps(test_r['rps']) if test_r['rps'] is not None else '-':>9} "
            f"| {train_r['argmax_hits']:>2}/{train_r['n']:<2} "
            f"{val_r['argmax_hits']:>2}/{val_r['n']:<2} "
            f"{test_r['argmax_hits']:>2}/{test_r['n']:<2}"
        )
        if val_mean is not None:
            ranked.append(
                (
                    val_mean,
                    val_se or 0.0,
                    test_r["rps"] if test_r["rps"] is not None else float("inf"),
                    weight,
                )
            )

    if not ranked:
        print("\nNo matches in the supplied context file intersect the selected split.")
        return

    best_val_rps, best_val_se, best_test_rps, best_weight = min(ranked)
    one_se_band = best_val_rps + best_val_se
    conservative_candidates = [item for item in ranked if item[0] <= one_se_band]
    conservative_val_rps, conservative_val_se, conservative_test_rps, conservative_weight = min(
        conservative_candidates, key=lambda item: item[3]
    )
    pure_test = reports["locked_test"][0]
    best_test = next(r for r in reports["locked_test"] if abs(r["market_weight"] - best_weight) < 1e-9)
    conservative_test = next(
        r for r in reports["locked_test"] if abs(r["market_weight"] - conservative_weight) < 1e-9
    )

    print()
    best_test_rps_text = _fmt_rps(best_test_rps if math.isfinite(best_test_rps) else None)
    conservative_test_rps_text = _fmt_rps(
        conservative_test_rps if math.isfinite(conservative_test_rps) else None
    )
    print(
        f"Best validation weight: {best_weight:.2f}  "
        f"(val RPS {_fmt_rps(best_val_rps)} ± {best_val_se:.4f}, "
        f"test RPS {best_test_rps_text})"
    )
    print(
        f"One-SE conservative weight: {conservative_weight:.2f}  "
        f"(val RPS {_fmt_rps(conservative_val_rps)} ± {conservative_val_se:.4f}, "
        f"test RPS {conservative_test_rps_text})"
    )
    print(
        f"Pure model locked-test: RPS {_fmt_rps(pure_test['rps']) if pure_test['rps'] is not None else '-'}  "
        f"hit {pure_test['argmax_hits']}/{pure_test['n']}"
    )
    print(
        f"Best blend locked-test: RPS {_fmt_rps(best_test['rps']) if best_test['rps'] is not None else '-'}  "
        f"hit {best_test['argmax_hits']}/{best_test['n']}"
    )
    if conservative_weight != best_weight:
        print(
            f"Conservative blend locked-test: RPS "
            f"{_fmt_rps(conservative_test['rps']) if conservative_test['rps'] is not None else '-'}  "
            f"hit {conservative_test['argmax_hits']}/{conservative_test['n']}"
        )
    print(
        f"Mean abs gap on best blend: {_fmt_gap(best_test['mean_abs_gap'])}"
    )
    if best_test.get("mean_market_confidence") is not None:
        print(
            f"Mean market confidence: {best_test['mean_market_confidence']:.2f}  "
            f"mean effective weight: {best_test['mean_effective_weight']:.2f}"
        )
        if conservative_weight != best_weight:
            print(
                f"Conservative mean effective weight: "
                f"{conservative_test['mean_effective_weight']:.2f}"
            )
    print("\nBest blend worst cases")
    for row in sorted(best_test["rows"], key=lambda item: item["rps"], reverse=True)[:8]:
        print(
            f"  {row['home']} v {row['away']} {row['score']:<5} "
            f"RPS {row['rps']:.4f}  method {row['market_method']}  "
            f"market_gap {_fmt_gap(row['market_gap'])}"
        )
    print("\n教育/分析用途,不构成投注技巧。")


if __name__ == "__main__":
    main()
