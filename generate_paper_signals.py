#!/usr/bin/env python3
"""Generate conservative paper-trading signals from model and market context.

The script writes ledger-shaped rows and can optionally append them to a paper
ledger. It never places real bets.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

from bet_ledger import (
    DEFAULT_RISK_POLICY,
    RiskPolicy,
    append_ledger_rows,
    build_ledger_row,
    edge_values,
    risk_status,
    suggested_stake_units,
    write_ledger,
)
from competition_state import match_adjustments
from external_ratings import audit_fixture_ratings, load_external_ratings_csv
from match_context import context_key, de_margin_odds, load_context_file
from model_stability import GROUP_V37A, KNOCKOUT_LOCKED, PROFILE_REGISTRY, predict_match, resolve_profile
from team_aliases import resolve_team_name

try:
    from elo_current_jul8 import ELO_CURRENT, FETCHED_BASE as ELO_CURRENT_FETCHED
except Exception:  # pragma: no cover - optional prediction-side snapshot
    ELO_CURRENT = None
    ELO_CURRENT_FETCHED = "unavailable"


SELECTIONS = ("H", "X", "A")


def _parse_profile(raw: str):
    try:
        return resolve_profile(raw)
    except KeyError as exc:
        available = ", ".join(sorted(PROFILE_REGISTRY))
        raise argparse.ArgumentTypeError(f"{exc}. Available profiles: {available}") from exc


def _profile_for_stage(stage: str):
    token = stage.strip().lower().replace("-", "_").replace(" ", "_")
    if token in {"r32", "r16", "qf", "sf", "3p", "f", "final", "knockout"}:
        return KNOCKOUT_LOCKED
    return GROUP_V37A


def _parse_float(raw: str | None, default: float = 0.0) -> float:
    if raw is None or str(raw).strip() == "":
        return default
    return float(raw)


def _parse_int(raw: str | None, default: int = 0) -> int:
    if raw is None or str(raw).strip() == "":
        return default
    return int(float(raw))


def _context_payload(path: Path) -> tuple[dict, dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "matches" in raw and isinstance(raw["matches"], dict):
        return raw.get("meta") if isinstance(raw.get("meta"), dict) else {}, raw["matches"]
    if isinstance(raw, dict):
        return {}, raw
    raise ValueError("context file must be a JSON object or {matches: {...}}")


def _fixture_rows_from_context(context_matches: dict) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw_key in context_matches:
        if "|" not in str(raw_key):
            continue
        home, away = str(raw_key).split("|", 1)
        rows.append({"home": home, "away": away})
    return rows


def _load_fixture_rows(path: str | None, context_matches: dict) -> list[dict[str, str]]:
    if path:
        with Path(path).open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    return _fixture_rows_from_context(context_matches)


def _first_non_empty(row: dict[str, str], keys: tuple[str, ...], default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _bookmaker(row: dict[str, str], fallback: str | None) -> str:
    return _first_non_empty(
        row,
        ("odds_bookmaker", "bookmaker", "odds_bookmaker_title", "source_key"),
        fallback or "context",
    )


def _is_group_stage(stage: str) -> bool:
    token = stage.strip().lower().replace("-", "_").replace(" ", "_")
    return token in {"group", "groups", "group_stage", "gs"}


def _elo_for_fixture(
    *,
    home: str,
    away: str,
    elo_source: str,
) -> tuple[dict[str, float] | None, str]:
    if elo_source == "snapshot":
        return None, "snapshot"
    if ELO_CURRENT is None:
        return None, "current Elo snapshot unavailable"
    missing = [team for team in (home, away) if team not in ELO_CURRENT]
    if missing:
        return None, f"missing current Elo for {', '.join(missing)}"
    return ELO_CURRENT, f"current Elo fetched {ELO_CURRENT_FETCHED}"


def _competition_block_reason(stage: str, ctx, require_group_state: bool) -> str:
    if not _is_group_stage(stage):
        return ""
    if require_group_state and ctx.competition_state is None:
        return "group-stage signal requires explicit competition_state"
    if ctx.competition_state is None:
        return ""
    adjustments = match_adjustments(ctx.competition_state)
    for side_name in ("home", "away"):
        side = adjustments.get(side_name)
        if side is None:
            continue
        if side.rotation_risk == "high":
            return f"{side_name} rotation risk is high"
        if side.stake_state == "dead_rubber":
            return f"{side_name} is in a dead-rubber state"
    return ""


def _odds_age_block_reason(meta: dict, max_minutes: int) -> str:
    if max_minutes <= 0:
        return ""
    raw = meta.get("generated_at_utc") or meta.get("fetched_at_utc")
    if not raw:
        return ""
    text = str(raw).replace("Z", "+00:00")
    try:
        generated = datetime.fromisoformat(text)
    except ValueError:
        return "cannot parse context generated_at_utc"
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    age_minutes = (datetime.now(timezone.utc) - generated.astimezone(timezone.utc)).total_seconds() / 60.0
    if age_minutes > max_minutes:
        return f"odds snapshot age {age_minutes:.0f}m > {max_minutes}m"
    return ""


def _best_signal(
    *,
    profile,
    fixture: dict[str, str],
    ctx,
    date: str,
    stage: str,
    market_type: str,
    bookmaker: str,
    policy: RiskPolicy,
    block_reasons: list[str],
    elo_source: str,
    external_ratings: dict | None,
    external_rank_gap_threshold: int,
    external_rating_gap_threshold: float,
) -> dict[str, str] | None:
    if ctx.market_odds is None:
        return None

    home = resolve_team_name(_first_non_empty(fixture, ("home", "team1", "side1")))
    away = resolve_team_name(_first_non_empty(fixture, ("away", "team2", "side2")))
    elo_override, elo_note = _elo_for_fixture(home=home, away=away, elo_source=elo_source)
    if elo_source == "current" and elo_override is None:
        block_reasons = [*block_reasons, elo_note]
        return build_ledger_row(
            date=date,
            stage=stage,
            market_type=market_type,
            home=home,
            away=away,
            selection="H",
            bookmaker=bookmaker,
            odds_decimal=ctx.market_odds[0],
            p_model=0.0,
            p_market=0.0,
            edge_raw=0.0,
            edge_net=0.0,
            stake_units=0.0,
            status="no_bet",
            notes="; ".join(block_reasons),
        )
    host_home = _parse_int(_first_non_empty(fixture, ("host_home", "home_field"), "0"))
    heat = _first_non_empty(fixture, ("heat",), "none")

    pred = predict_match(
        profile,
        home,
        away,
        host_home=host_home,
        heat=heat,
        weather_scale=ctx.weather_scale,
        lineup_home=ctx.lineup_home,
        lineup_away=ctx.lineup_away,
        market_odds=ctx.market_odds,
        market_method=ctx.market_method,
        competition_state=ctx.competition_state,
        elo_override=elo_override,
    )
    model_probs = (pred.home_prob, pred.draw_prob, pred.away_prob)
    market_probs, market_margin = de_margin_odds(ctx.market_odds, method=ctx.market_method)
    max_abs_gap = max(abs(model - market) for model, market in zip(model_probs, market_probs))

    candidates = []
    for idx, selection in enumerate(SELECTIONS):
        edge_raw, edge_net = edge_values(
            model_probs[idx],
            market_probs[idx],
            uncertainty_discount=policy.uncertainty_discount,
        )
        candidates.append((edge_net, edge_raw, selection, idx))
    edge_net, edge_raw, selection, idx = max(candidates, key=lambda item: item[0])

    blocked = bool(block_reasons)
    status, status_note = risk_status(
        market_type=market_type,
        edge_raw=edge_raw,
        edge_net=edge_net,
        market_margin=market_margin,
        max_abs_gap=max_abs_gap,
        blocked=blocked,
        blocked_reason="; ".join(block_reasons),
        policy=policy,
    )
    stake = suggested_stake_units(
        edge_net,
        min_edge_net=policy.min_edge_net,
        max_stake_units=policy.max_stake_units,
    ) if status == "paper_bet" else 0.0
    audit_note = ""
    if external_ratings is not None:
        audit = audit_fixture_ratings(
            home,
            away,
            model_probs=model_probs,
            market_probs=market_probs,
            ratings=external_ratings,
            rank_gap_threshold=external_rank_gap_threshold,
            rating_gap_threshold=external_rating_gap_threshold,
        )
        audit_note = audit.reason
        if status == "paper_bet" and audit.manual_review:
            original_stake = stake
            status = "watchlist"
            stake = 0.0
            audit_note += (
                f"; paper_bet downgraded to watchlist; "
                f"confidence_penalty={audit.confidence_penalty:.2f}; "
                f"would_be_stake={original_stake:.2f}u"
            )
    notes = "; ".join(part for part in [status_note, elo_note, audit_note, ctx.notes] if part)

    return build_ledger_row(
        date=date,
        stage=stage,
        market_type=market_type,
        home=home,
        away=away,
        selection=selection,
        bookmaker=bookmaker,
        odds_decimal=ctx.market_odds[idx],
        p_model=model_probs[idx],
        p_market=market_probs[idx],
        edge_raw=edge_raw,
        edge_net=edge_net,
        stake_units=stake,
        status=status,
        notes=notes,
    )


def _apply_daily_limit(rows: list[dict[str, str]], limit_units: float) -> None:
    approved: set[str] = set()
    used = 0.0
    candidates = sorted(
        [row for row in rows if row["status"] == "paper_bet"],
        key=lambda row: float(row["edge_net"]),
        reverse=True,
    )
    for row in candidates:
        stake = float(row["stake_units"])
        if used + stake <= limit_units + 1e-12:
            approved.add(row["signal_id"])
            used += stake

    for row in rows:
        if row["status"] == "paper_bet" and row["signal_id"] not in approved:
            row["status"] = "watchlist"
            row["stake_units"] = "0.00"
            suffix = f"daily risk limit {limit_units:.2f}u reached"
            row["notes"] = f"{row['notes']}; {suffix}" if row["notes"] else suffix


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context-file", required=True, help="JSON context with market_odds rows.")
    ap.add_argument("--fixture-csv", help="Optional fixture/enriched CSV; defaults to context keys.")
    ap.add_argument("--output-csv", required=True, help="Write paper signals to this CSV.")
    ap.add_argument("--append-ledger", help="Append unique rows to this ledger CSV.")
    ap.add_argument("--date", required=True, help="Signal date, e.g. 2026-07-05.")
    ap.add_argument("--stage", required=True, help="Stage label, e.g. group, R16, QF.")
    ap.add_argument("--market-type", choices=["h2h_90"], default="h2h_90")
    ap.add_argument(
        "--profile",
        type=_parse_profile,
        help="Override model profile. Defaults to group_v37a for group stages and knockout_locked for KO stages.",
    )
    ap.add_argument(
        "--elo-source",
        choices=["current", "snapshot"],
        default="current",
        help="Prediction-side Elo source. Default current uses elo_current_jul8.py; snapshot uses backtest Elo.",
    )
    ap.add_argument(
        "--external-ratings-csv",
        help="Optional second-opinion ratings CSV (for example Opta). Used only for audit/downgrade flags; does not change p_model.",
    )
    ap.add_argument(
        "--external-rank-gap-threshold",
        type=int,
        default=8,
        help="Minimum external rank gap before rating audit can trigger manual review.",
    )
    ap.add_argument(
        "--external-rating-gap-threshold",
        type=float,
        default=2.0,
        help="Minimum external rating gap before rating audit can trigger manual review.",
    )
    ap.add_argument("--uncertainty-discount", type=float, default=DEFAULT_RISK_POLICY.uncertainty_discount)
    ap.add_argument("--min-edge-net", type=float, default=DEFAULT_RISK_POLICY.min_edge_net)
    ap.add_argument("--max-stake-units", type=float, default=DEFAULT_RISK_POLICY.max_stake_units)
    ap.add_argument("--daily-risk-limit-units", type=float, default=DEFAULT_RISK_POLICY.daily_risk_limit_units)
    ap.add_argument("--max-market-margin", type=float, default=DEFAULT_RISK_POLICY.max_market_margin)
    ap.add_argument("--max-model-market-gap", type=float, default=DEFAULT_RISK_POLICY.max_model_market_gap)
    ap.add_argument(
        "--max-odds-age-minutes",
        type=int,
        default=10,
        help="If context meta has generated_at_utc/fetched_at_utc, block stale snapshots. 0 disables.",
    )
    ap.add_argument(
        "--require-group-state",
        action="store_true",
        help="For group-stage slates, no-bet fixtures without explicit competition_state.",
    )
    args = ap.parse_args()

    profile = args.profile or _profile_for_stage(args.stage)
    policy = RiskPolicy(
        uncertainty_discount=args.uncertainty_discount,
        min_edge_net=args.min_edge_net,
        max_stake_units=args.max_stake_units,
        daily_risk_limit_units=args.daily_risk_limit_units,
        max_market_margin=args.max_market_margin,
        max_model_market_gap=args.max_model_market_gap,
    )
    context_path = Path(args.context_file)
    meta, context_matches = _context_payload(context_path)
    contexts = load_context_file(context_path)
    fixtures = _load_fixture_rows(args.fixture_csv, context_matches)
    external_ratings = (
        load_external_ratings_csv(args.external_ratings_csv)
        if args.external_ratings_csv
        else None
    )

    rows: list[dict[str, str]] = []
    skipped_missing_odds = 0
    age_reason = _odds_age_block_reason(meta, args.max_odds_age_minutes)
    for fixture in fixtures:
        home_raw = _first_non_empty(fixture, ("home", "team1", "side1"))
        away_raw = _first_non_empty(fixture, ("away", "team2", "side2"))
        if not home_raw or not away_raw:
            continue
        key = context_key(home_raw, away_raw)
        ctx = contexts.get(key)
        if ctx is None or ctx.market_odds is None:
            skipped_missing_odds += 1
            continue
        block_reasons = [reason for reason in [age_reason, _competition_block_reason(
            args.stage,
            ctx,
            args.require_group_state,
        )] if reason]
        row = _best_signal(
            profile=profile,
            fixture=fixture,
            ctx=ctx,
            date=args.date,
            stage=args.stage,
            market_type=args.market_type,
            bookmaker=_bookmaker(fixture, ctx.source_key),
            policy=policy,
            block_reasons=block_reasons,
            elo_source=args.elo_source,
            external_ratings=external_ratings,
            external_rank_gap_threshold=args.external_rank_gap_threshold,
            external_rating_gap_threshold=args.external_rating_gap_threshold,
        )
        if row is not None:
            rows.append(row)

    _apply_daily_limit(rows, policy.daily_risk_limit_units)
    write_ledger(args.output_csv, rows)

    appended = skipped = 0
    if args.append_ledger:
        appended, skipped = append_ledger_rows(args.append_ledger, rows)

    counts = {status: sum(1 for row in rows if row["status"] == status) for status in ("paper_bet", "watchlist", "no_bet")}
    print(
        "Paper signals complete | "
        f"rows={len(rows)} | paper_bet={counts['paper_bet']} | "
        f"watchlist={counts['watchlist']} | no_bet={counts['no_bet']} | "
        f"missing_odds={skipped_missing_odds} | output={args.output_csv}"
    )
    if args.append_ledger:
        print(f"Ledger write | written={appended} | duplicate_skipped={skipped} | ledger={args.append_ledger}")
    print("PAPER-ONLY calibration audit — signals are hypothetical, never a "
          "recommendation to bet. Educational/analytical use only; not betting "
          "advice. / 教育/分析用途，不构成投注建议。")


if __name__ == "__main__":
    main()
