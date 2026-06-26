#!/usr/bin/env python3
"""Train / validate the odds-model profiles without coupling train and test.

This is the guardrail layer:
  - fixed chronological split
  - candidate grid around the current stable core
  - bootstrap stability check
  - explicit train / validation / locked-test reporting
  - miss labeling to separate model error from likely information gaps

It does not overwrite defaults by itself. It prints the recommendation and the
reason, so the user can promote a candidate manually.
"""

from __future__ import annotations

import argparse

from model_stability import (
    CANDIDATE_V36,
    LEGACY_V34,
    STABLE_V35,
    bootstrap_selection_rates,
    candidate_grid,
    evaluate_profile,
    predict_match,
    profile_distance,
)
from match_context import context_key, load_context_file
from worldcup_2026_data import BATCH_SPLITS, matches_for_batches


def format_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def score_tuple(metrics: dict, anchor) -> tuple:
    return (
        metrics["rps"],
        -metrics["log_likelihood"],
        abs(metrics["draw_model"] - metrics["draw_actual"]),
        abs(metrics["blowout_expected"] - metrics["blowout_actual"]),
        profile_distance(metrics["profile"], anchor),
    )


def rank_profiles(profiles, validation, anchor):
    rows = []
    for profile in profiles:
        metrics = evaluate_profile(profile, validation)
        rows.append((score_tuple(metrics, anchor), profile, metrics))
    return sorted(rows, key=lambda x: x[0])


def print_metrics(label: str, metrics: dict):
    print(
        f"{label:<22} "
        f"argmax {metrics['wdl_argmax']:>2}/{metrics['n']:<2}  "
        f"tipset {metrics['tipset']:>2}/{metrics['n']:<2}  "
        f"RPS {metrics['rps']:.4f}  "
        f"logL {metrics['log_likelihood']:.2f}  "
        f"draw {format_pct(metrics['draw_model'])}/{format_pct(metrics['draw_actual'])}  "
        f"blow {metrics['blowout_expected']:.1f}/{metrics['blowout_actual']}"
    )


def market_diagnostics(profile, matches, contexts):
    total = 0
    sum_abs = [0.0, 0.0, 0.0]
    max_abs = [0.0, 0.0, 0.0]
    for home, away, _, _, host_home, *_ in matches:
        ctx = contexts.get(context_key(home, away))
        if not ctx or ctx.market_odds is None:
            continue
        pred = predict_match(
            profile,
            home,
            away,
            host_home=host_home,
            lineup_home=ctx.lineup_home,
            lineup_away=ctx.lineup_away,
            weather_scale=ctx.weather_scale,
            market_odds=ctx.market_odds,
            market_method=ctx.market_method,
            competition_state=ctx.competition_state,
        )
        if pred.market_gap is None:
            continue
        total += 1
        for idx, value in enumerate(pred.market_gap):
            abs_value = abs(value)
            sum_abs[idx] += abs_value
            max_abs[idx] = max(max_abs[idx], abs_value)
    if not total:
        return None
    return {
        "n": total,
        "mean_abs": tuple(value / total for value in sum_abs),
        "max_abs": tuple(max_abs),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--profile-set",
        choices=["core", "full"],
        default="core",
        help="core = stable + candidate; full = add the legacy v3.4 profile",
    )
    ap.add_argument(
        "--context-file",
        help="Optional JSON file with market odds and lineup overrides for diagnostics.",
    )
    args = ap.parse_args()
    try:
        contexts = load_context_file(args.context_file) if args.context_file else {}
    except Exception as exc:  # pragma: no cover - CLI ergonomics
        ap.error(f"failed to load context file: {exc}")

    split = {
        "train": matches_for_batches(*BATCH_SPLITS["train"]),
        "validation": matches_for_batches(*BATCH_SPLITS["validation"]),
        "locked_test": matches_for_batches(*BATCH_SPLITS["locked_test"]),
    }

    profiles = [STABLE_V35, CANDIDATE_V36]
    if args.profile_set == "full":
        profiles.append(LEGACY_V34)
    profiles.extend(candidate_grid())

    # De-duplicate on parameter tuple so the grid doesn't create noisy copies.
    unique = {}
    for p in profiles:
        key = (p.avg_goals, p.gd_per_100, p.draw_boost, p.draw_gate, p.open_delo)
        unique.setdefault(key, p)
    profiles = list(unique.values())

    train_metrics = {p.name: evaluate_profile(p, split["train"]) for p in profiles}
    val_metrics = {p.name: evaluate_profile(p, split["validation"]) for p in profiles}
    test_metrics = {p.name: evaluate_profile(p, split["locked_test"]) for p in profiles}
    boot_rates = bootstrap_selection_rates(profiles, split["train"], n_boot=args.bootstrap, seed=args.seed)

    anchor = STABLE_V35
    ranked = rank_profiles(profiles, split["validation"], anchor)
    best_score, best_profile, best_val = ranked[0]
    stable_val = val_metrics[anchor.name]
    stable_test = test_metrics[anchor.name]
    best_test = test_metrics[best_profile.name]
    best_boot = boot_rates.get(best_profile.name, 0.0)

    print("=" * 88)
    print("Stable-vs-candidate training report (split: train 40 / validation 8 / locked test 6)")
    print("=" * 88)
    print(
        f"train={len(split['train'])}  validation={len(split['validation'])}  "
        f"locked_test={len(split['locked_test'])}"
    )
    print(f"anchor={anchor.name}  candidate_pool={len(profiles)}  bootstrap={args.bootstrap}")
    print()
    print("Top validation profiles")
    for idx, (_, profile, metrics) in enumerate(ranked[:8], 1):
        print(
            f"{idx:>2}. {profile.name:<22} "
            f"RPS {metrics['rps']:.4f}  "
            f"logL {metrics['log_likelihood']:.2f}  "
            f"draw {format_pct(metrics['draw_model'])}  "
            f"brier {metrics['ou_brier']:.4f}  "
            f"boot {boot_rates.get(profile.name, 0.0) * 100:5.1f}%"
        )
    print()
    print_metrics("anchor / validation", stable_val)
    print_metrics("best / validation", best_val)
    print_metrics("anchor / locked", stable_test)
    print_metrics("best / locked", best_test)
    print()
    print("Bootstrap stability")
    for profile, rate in sorted(boot_rates.items(), key=lambda kv: kv[1], reverse=True)[:8]:
        print(f"  {profile:<22} {rate * 100:5.1f}%")
    print()

    if contexts:
        anchor_market_val = market_diagnostics(anchor, split["validation"], contexts)
        best_market_val = market_diagnostics(best_profile, split["validation"], contexts)
        anchor_market_test = market_diagnostics(anchor, split["locked_test"], contexts)
        best_market_test = market_diagnostics(best_profile, split["locked_test"], contexts)
        print("Market diagnostics")
        if anchor_market_val:
            mean_abs = anchor_market_val["mean_abs"]
            print(
                f"  anchor / validation  n={anchor_market_val['n']}  "
                f"mean_abs_gap {mean_abs[0]*100:.1f}/{mean_abs[1]*100:.1f}/{mean_abs[2]*100:.1f} pts"
            )
        if best_market_val:
            mean_abs = best_market_val["mean_abs"]
            print(
                f"  best   / validation  n={best_market_val['n']}  "
                f"mean_abs_gap {mean_abs[0]*100:.1f}/{mean_abs[1]*100:.1f}/{mean_abs[2]*100:.1f} pts"
            )
        if anchor_market_test:
            mean_abs = anchor_market_test["mean_abs"]
            print(
                f"  anchor / locked      n={anchor_market_test['n']}  "
                f"mean_abs_gap {mean_abs[0]*100:.1f}/{mean_abs[1]*100:.1f}/{mean_abs[2]*100:.1f} pts"
            )
        if best_market_test:
            mean_abs = best_market_test["mean_abs"]
            print(
                f"  best   / locked      n={best_market_test['n']}  "
                f"mean_abs_gap {mean_abs[0]*100:.1f}/{mean_abs[1]*100:.1f}/{mean_abs[2]*100:.1f} pts"
            )
        if not any((anchor_market_val, best_market_val, anchor_market_test, best_market_test)):
            print("  no market odds found in the supplied context file")
        print()

    if best_profile.name != anchor.name and best_val["rps"] <= stable_val["rps"] - 0.001:
        if best_boot >= 0.30 and best_test["rps"] <= stable_test["rps"] + 0.0005:
            recommendation = best_profile
            reason = "validation gain + bootstrap stability + no locked-test regression"
        else:
            recommendation = anchor
            reason = "candidate did not clear the stability gate"
    else:
        recommendation = anchor
        reason = "anchor already matches the stability target"

    print("Miss diagnostics (validation)")
    for miss in best_val.get("misses", [])[:12]:
        print(
            f"  {miss['home']} v {miss['away']} {miss['score']:<5} "
            f"batch={miss['batch']} label={miss['label']:<30} "
            f"{miss['home_prob']*100:4.0f}/{miss['draw_prob']*100:3.0f}/{miss['away_prob']*100:3.0f}"
        )
    print()
    print(f"Recommendation: {recommendation.name}  ({reason})")
    print("Do not promote candidate unless the locked-test split stays clean on the next run.")


if __name__ == "__main__":
    main()
