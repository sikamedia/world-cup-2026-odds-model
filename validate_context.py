#!/usr/bin/env python3
"""Validate a market context JSON before using it for training or prediction."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import sys

from competition_state import match_state_summary
from match_context import context_key, de_margin_odds, load_context_file
from model_stability import PROFILE_REGISTRY, STABLE_V35, predict_match, resolve_profile
from worldcup_2026_data import BATCH_SPLITS, ELO, JUNE_25_MATCHES, MATCHES_54, matches_for_batches
from worldcup_2026_data_jun26 import JUNE_26_MATCHES


def _parse_profile(raw: str):
    try:
        return resolve_profile(raw)
    except KeyError as exc:
        available = ", ".join(sorted(PROFILE_REGISTRY))
        raise argparse.ArgumentTypeError(f"{exc}. Available profiles: {available}") from exc


def _known_slates() -> dict[str, list[tuple[str, str]]]:
    slates = {
        "train": [(home, away) for home, away, *_ in matches_for_batches(*BATCH_SPLITS["train"])],
        "validation": [(home, away) for home, away, *_ in matches_for_batches(*BATCH_SPLITS["validation"])],
        "locked_test": [(home, away) for home, away, *_ in matches_for_batches(*BATCH_SPLITS["locked_test"])],
        "all_played": [(home, away) for home, away, *_ in MATCHES_54],
        "jun25": [(home, away) for home, away, *_ in JUNE_25_MATCHES],
        "jun26": [(home, away) for home, away, *_ in JUNE_26_MATCHES],
    }
    try:
        from predict_stryktipset_8 import M

        slates["stryktipset"] = [(home, away) for home, away, *_ in M]
    except Exception:
        pass
    return slates


def _known_model_inputs() -> dict[str, dict]:
    inputs = {}
    for home, away, _, _, host_home, _ in MATCHES_54:
        inputs[context_key(home, away)] = {
            "home": home,
            "away": away,
            "host_home": host_home,
            "heat": "none",
            "mot_home": "normal",
            "mot_away": "normal",
        }
    for home, away, host_home, heat, mot_home, mot_away, _ in JUNE_25_MATCHES:
        inputs[context_key(home, away)] = {
            "home": home,
            "away": away,
            "host_home": host_home,
            "heat": heat,
            "mot_home": mot_home,
            "mot_away": mot_away,
        }
    for home, away, host_home, heat, mot_home, mot_away, _ in JUNE_26_MATCHES:
        inputs[context_key(home, away)] = {
            "home": home,
            "away": away,
            "host_home": host_home,
            "heat": heat,
            "mot_home": mot_home,
            "mot_away": mot_away,
        }
    return inputs


def _fmt_prob(values: tuple[float, float, float]) -> str:
    return f"{values[0] * 100:.1f}/{values[1] * 100:.1f}/{values[2] * 100:.1f}%"


def _add_issue(bucket: list[str], key: str, message: str) -> None:
    bucket.append(f"{key}: {message}")


def _parse_utc_timestamp(raw: str | None, field: str) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        value = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601, got {raw!r}") from exc
    if value.tzinfo is None:
        raise ValueError(f"{field} must include timezone, got {raw!r}")
    return value.astimezone(timezone.utc)


def _weather_evidence_age_hours(ctx) -> tuple[float | None, str | None]:
    try:
        kickoff = _parse_utc_timestamp(ctx.kickoff_at_utc, "kickoff_at_utc")
        checked = _parse_utc_timestamp(ctx.weather_checked_at_utc, "weather_checked_at_utc")
    except ValueError as exc:
        return None, str(exc)
    if kickoff is None or checked is None:
        return None, None
    return (kickoff - checked).total_seconds() / 3600.0, None


def _validate_weather_evidence(key: str, ctx, warnings: list[str]) -> None:
    decision = ctx.weather_decision or "none"
    evidence_type = ctx.weather_evidence_type
    weather_scale_changed = abs(ctx.weather_scale - 1.0) > 1e-9

    if weather_scale_changed and not ctx.weather_checked_at_utc:
        _add_issue(warnings, key, "weather_scale changed but weather_checked_at_utc is missing")
    if decision != "none" and not ctx.weather_source:
        _add_issue(warnings, key, f"weather_decision={decision} but weather_source is missing")

    evidence_age_hours, error = _weather_evidence_age_hours(ctx)
    if error:
        _add_issue(warnings, key, error)
        return
    if ctx.weather_checked_at_utc and not ctx.kickoff_at_utc:
        _add_issue(warnings, key, "weather_checked_at_utc present but kickoff_at_utc is missing")
    if evidence_age_hours is not None and evidence_age_hours < 0:
        _add_issue(warnings, key, f"weather_checked_at_utc is after kickoff by {-evidence_age_hours:.1f}h")

    if decision == "rain_watch" and ctx.weather_scale < 1.0:
        _add_issue(warnings, key, "rain_watch should not lower weather_scale; use rain_applied only with close evidence")
    if decision == "indoor_no_weather" and weather_scale_changed:
        _add_issue(warnings, key, "indoor_no_weather should keep weather_scale at 1.00")
    if decision == "rain_applied":
        if ctx.weather_scale >= 1.0:
            _add_issue(warnings, key, "rain_applied should use weather_scale below 1.00")
        if evidence_type not in {"hourly", "radar", "manual"}:
            _add_issue(
                warnings,
                key,
                "rain_applied requires weather_evidence_type hourly, radar, or manual",
            )
        if evidence_age_hours is None:
            _add_issue(
                warnings,
                key,
                "rain_applied requires kickoff_at_utc and weather_checked_at_utc",
            )
        elif evidence_age_hours > 3.0:
            _add_issue(
                warnings,
                key,
                f"rain_applied evidence is stale: checked {evidence_age_hours:.1f}h before kickoff (>3h)",
            )
    if decision.startswith("heat_"):
        if evidence_age_hours is None:
            _add_issue(
                warnings,
                key,
                f"{decision} requires kickoff_at_utc and weather_checked_at_utc",
            )
        elif evidence_age_hours > 6.0:
            _add_issue(
                warnings,
                key,
                f"{decision} evidence is stale: checked {evidence_age_hours:.1f}h before kickoff (>6h)",
            )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context-file", required=True, help="JSON context file to validate.")
    ap.add_argument(
        "--profile",
        type=_parse_profile,
        default=STABLE_V35,
        help="Profile used only for model-market gap diagnostics.",
    )
    ap.add_argument(
        "--gap-threshold",
        type=float,
        default=0.12,
        help="Warn when any model-vs-market probability gap exceeds this value.",
    )
    ap.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Exit non-zero when warnings are present.",
    )
    args = ap.parse_args()

    try:
        contexts = load_context_file(args.context_file)
    except Exception as exc:
        ap.error(f"failed to load context file: {exc}")

    slates = _known_slates()
    known_exact = {context_key(home, away) for matches in slates.values() for home, away in matches}
    reversed_lookup = {
        context_key(away, home): context_key(home, away)
        for matches in slates.values()
        for home, away in matches
    }
    model_inputs = _known_model_inputs()

    errors: list[str] = []
    warnings: list[str] = []
    margins: list[float] = []
    confidences: list[float] = []
    with_odds = 0
    large_gaps = 0
    source_keys = 0
    source_key_diff = 0
    competition_states = 0
    weather_evidence_rows = 0

    for key, ctx in sorted(contexts.items()):
        if ctx.source_key:
            source_keys += 1
            if ctx.source_key != key:
                source_key_diff += 1
        if ctx.competition_state is not None:
            competition_states += 1
        if (
            ctx.weather_decision != "none"
            or ctx.weather_evidence_type is not None
            or ctx.weather_checked_at_utc is not None
            or ctx.kickoff_at_utc is not None
            or ctx.weather_source is not None
        ):
            weather_evidence_rows += 1
        home, away = key.split("|", 1)
        if home not in ELO:
            _add_issue(errors, key, f"unknown home team '{home}'")
        if away not in ELO:
            _add_issue(errors, key, f"unknown away team '{away}'")

        if key not in known_exact:
            if key in reversed_lookup:
                _add_issue(errors, key, f"appears reversed; expected '{reversed_lookup[key]}'")
            elif home in ELO and away in ELO:
                _add_issue(warnings, key, "not found in known played/Jun25/Stryktipset slates")

        if ctx.market_odds is None:
            _add_issue(warnings, key, "missing market_odds; excluded from market blend training")
        else:
            with_odds += 1
            confidences.append(ctx.market_confidence)
            try:
                market_probs, margin = de_margin_odds(ctx.market_odds, method=ctx.market_method)
                margins.append(margin)
            except Exception as exc:
                _add_issue(errors, key, f"invalid odds: {exc}")
                continue

            if margin < -0.02:
                _add_issue(warnings, key, f"negative overround {margin * 100:.1f}%")
            if margin > 0.15:
                _add_issue(warnings, key, f"high overround {margin * 100:.1f}%")
            if ctx.market_confidence < 0.5:
                _add_issue(warnings, key, f"low market_confidence {ctx.market_confidence:.2f}")
            if max(market_probs) > 0.90:
                _add_issue(warnings, key, f"very concentrated market probabilities {_fmt_prob(market_probs)}")

            if key in model_inputs:
                info = model_inputs[key]
                pred = predict_match(
                    args.profile,
                    info["home"],
                    info["away"],
                    host_home=info["host_home"],
                    heat=info["heat"],
                    mot_home=info["mot_home"],
                    mot_away=info["mot_away"],
                    lineup_home=ctx.lineup_home,
                    lineup_away=ctx.lineup_away,
                    weather_scale=ctx.weather_scale,
                    market_odds=ctx.market_odds,
                    market_method=ctx.market_method,
                    competition_state=ctx.competition_state,
                )
                if pred.market_gap is not None and max(abs(value) for value in pred.market_gap) >= args.gap_threshold:
                    large_gaps += 1
                    _add_issue(
                        warnings,
                        key,
                        f"large model-market gap {_fmt_prob(tuple(abs(v) for v in pred.market_gap))}; "
                        "check team order and missing team news",
                    )

        if not 0.75 <= ctx.lineup_home <= 1.25:
            _add_issue(warnings, key, f"lineup_home scale looks extreme: {ctx.lineup_home:.2f}")
        if not 0.75 <= ctx.lineup_away <= 1.25:
            _add_issue(warnings, key, f"lineup_away scale looks extreme: {ctx.lineup_away:.2f}")
        if not 0.80 <= ctx.weather_scale <= 1.05:
            _add_issue(warnings, key, f"weather_scale looks extreme: {ctx.weather_scale:.2f}")
        _validate_weather_evidence(key, ctx, warnings)
        if ctx.competition_state is not None:
            summary = match_state_summary(ctx.competition_state)
            if "dead_rubber/high" in summary:
                _add_issue(warnings, key, f"high-rotation dead-rubber state: {summary}")

    print("=" * 88)
    print(f"Context quality report | file={args.context_file} | profile={args.profile.name}")
    print("=" * 88)
    print(f"context rows: {len(contexts)}  with market_odds: {with_odds}")
    if source_keys:
        print(f"source_key rows: {source_keys}  differing from canonical: {source_key_diff}")
    if competition_states:
        print(f"competition_state rows: {competition_states}")
    if weather_evidence_rows:
        print(f"weather_evidence rows: {weather_evidence_rows}")
    if margins:
        print(
            f"overround: avg={sum(margins) / len(margins) * 100:.1f}%  "
            f"min={min(margins) * 100:.1f}%  max={max(margins) * 100:.1f}%"
        )
    if confidences:
        print(
            f"market_confidence: avg={sum(confidences) / len(confidences):.2f}  "
            f"min={min(confidences):.2f}  max={max(confidences):.2f}"
        )
    print(f"large model-market gaps: {large_gaps}")
    print()
    print("Coverage by slate")
    for name, matches in slates.items():
        total = len(matches)
        context_hits = 0
        odds_hits = 0
        for home, away in matches:
            ctx = contexts.get(context_key(home, away))
            if ctx is not None:
                context_hits += 1
                if ctx.market_odds is not None:
                    odds_hits += 1
        print(f"  {name:<11} context {context_hits:>2}/{total:<2}  market_odds {odds_hits:>2}/{total:<2}")

    if errors:
        print("\nErrors")
        for issue in errors:
            print(f"  - {issue}")
    if warnings:
        print("\nWarnings")
        for issue in warnings:
            print(f"  - {issue}")

    if not errors and not warnings:
        print("\nNo issues found.")
    elif not errors:
        print("\nNo blocking errors found.")

    if errors or (args.fail_on_warning and warnings):
        sys.exit(1)


if __name__ == "__main__":
    main()
