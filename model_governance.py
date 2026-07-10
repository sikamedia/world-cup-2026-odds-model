#!/usr/bin/env python3
"""Governance metrics and structured-ledger readers for knockout reviews.

This module never fits or mutates production parameters.  It turns
pre-registered comparisons and small case ledgers into explicit
REVIEW/HOLD/NO_DECISION states, with one gated diagnostic ensemble grid.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from math import fsum, sqrt
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import urlparse


Z_95 = 1.959963984540054


def _check_probability(value: float, field: str) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field} must be in [0, 1], got {value!r}")
    return value


def _parse_bool(raw: str, field: str, *, optional: bool = False) -> bool | None:
    value = str(raw or "").strip().lower()
    if optional and value in {"", "na", "n/a", "pending", "none"}:
        return None
    if value in {"1", "true", "yes", "y"}:
        return True
    if value in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"{field} must be boolean, got {raw!r}")


def _optional_float(raw: str) -> float | None:
    value = str(raw or "").strip()
    return None if not value else float(value)


def _mean(values: Sequence[float]) -> float | None:
    return fsum(values) / len(values) if values else None


def _is_http_url(raw: str) -> bool:
    parsed = urlparse(raw)
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def _is_sha256(raw: str) -> bool:
    value = str(raw or "").strip()
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _is_timezone_timestamp(raw: str) -> bool:
    if not raw:
        return False
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    return value.tzinfo is not None and value.utcoffset() is not None


def _parse_timezone_timestamp(raw: str) -> datetime | None:
    if not _is_timezone_timestamp(raw):
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _is_pre_kickoff(raw: str, kickoff_raw: str) -> bool:
    observed = _parse_timezone_timestamp(raw)
    kickoff = _parse_timezone_timestamp(kickoff_raw)
    return observed is not None and kickoff is not None and observed < kickoff


def _is_available_at_registration(raw: str, registered_raw: str) -> bool:
    observed = _parse_timezone_timestamp(raw)
    registered = _parse_timezone_timestamp(registered_raw)
    return observed is not None and registered is not None and observed <= registered


def _independent_http_sources(first: str, second: str) -> bool:
    if not (_is_http_url(first) and _is_http_url(second)):
        return False
    return (urlparse(first).hostname or "").lower() != (
        urlparse(second).hostname or ""
    ).lower()


@dataclass(frozen=True)
class PairedBrierResult:
    n: int
    minimum_for_review: int
    gate_reached: bool
    mean_difference: float
    standard_error: float
    ci95_low: float
    ci95_high: float
    decision: str


def paired_brier_comparison(
    graded_probabilities: Sequence[float],
    flat1_probabilities: Sequence[float],
    outcomes: Sequence[int | float],
    *,
    minimum_for_review: int = 28,
) -> PairedBrierResult:
    """Compare paired Brier losses as graded minus flat-1.00.

    A negative difference favours graded-k.  The standard error is computed on
    the per-match paired loss differences, not by treating model scores as two
    independent samples.
    """
    if not (len(graded_probabilities) == len(flat1_probabilities) == len(outcomes)):
        raise ValueError("paired Brier inputs must have equal lengths")
    if not outcomes:
        raise ValueError("paired Brier comparison requires at least one row")

    differences: list[float] = []
    for index, (graded, flat1, outcome) in enumerate(
        zip(graded_probabilities, flat1_probabilities, outcomes), 1
    ):
        graded = _check_probability(graded, f"graded probability row {index}")
        flat1 = _check_probability(flat1, f"flat-1.00 probability row {index}")
        outcome = _check_probability(float(outcome), f"outcome row {index}")
        if outcome not in {0.0, 1.0}:
            raise ValueError(f"outcome row {index} must be binary")
        differences.append((graded - outcome) ** 2 - (flat1 - outcome) ** 2)

    n = len(differences)
    mean_difference = fsum(differences) / n
    if n > 1:
        variance = fsum((value - mean_difference) ** 2 for value in differences) / (n - 1)
        standard_error = sqrt(variance / n)
    else:
        standard_error = 0.0
    ci95_low = mean_difference - Z_95 * standard_error
    ci95_high = mean_difference + Z_95 * standard_error

    if minimum_for_review < 2:
        raise ValueError("minimum_for_review must be at least 2")
    gate_reached = n >= minimum_for_review
    if not gate_reached or ci95_low <= 0.0 <= ci95_high:
        decision = "NO_DECISION"
    elif ci95_high < 0.0:
        decision = "GRADED_BETTER"
    else:
        decision = "FLAT1_BETTER"
    return PairedBrierResult(
        n=n,
        minimum_for_review=minimum_for_review,
        gate_reached=gate_reached,
        mean_difference=mean_difference,
        standard_error=standard_error,
        ci95_low=ci95_low,
        ci95_high=ci95_high,
        decision=decision,
    )


@dataclass(frozen=True)
class FloorMetricRow:
    sequence: int
    fixture: str
    floor_active: bool
    official_rps: float
    shadow_rps: float
    official_score_log_loss: float
    shadow_score_log_loss: float
    official_adv_brier: float
    shadow_adv_brier: float

    @property
    def identifying(self) -> bool:
        values = (
            self.official_rps - self.shadow_rps,
            self.official_score_log_loss - self.shadow_score_log_loss,
            self.official_adv_brier - self.shadow_adv_brier,
        )
        return self.floor_active and any(abs(value) > 1e-12 for value in values)


@dataclass(frozen=True)
class FloorActiveSummary:
    total_rows: int
    prospective_rows: int
    historical_active_rows: int
    active_rows: int
    identifying_rows: int
    new_identifying_rows: int
    official_rps: float | None
    shadow_rps: float | None
    official_score_log_loss: float | None
    shadow_score_log_loss: float | None
    official_adv_brier: float | None
    shadow_adv_brier: float | None
    review_baseline_n: int
    minimum_for_review: int
    gate_reached: bool
    decision: str


def summarize_floor_active(
    rows: Sequence[FloorMetricRow],
    *,
    review_baseline_n: int,
    minimum_for_review: int = 28,
) -> FloorActiveSummary:
    """Summarize prospective floor evidence after the adoption baseline.

    Rows at or before ``review_baseline_n`` motivated adoption and cannot also
    decide the prospective shadow review.  The n=28 gate must be reached and at
    least one later floor-active row must change a monitored score; otherwise
    the only honest verdict is ``NO_DECISION``.
    """
    if review_baseline_n < 0:
        raise ValueError("review_baseline_n must be non-negative")
    if minimum_for_review <= review_baseline_n:
        raise ValueError("minimum_for_review must be after review_baseline_n")
    sequences = [row.sequence for row in rows]
    if any(sequence <= 0 for sequence in sequences) or len(set(sequences)) != len(sequences):
        raise ValueError("floor metric row sequences must be unique positive integers")

    prospective = [row for row in rows if row.sequence > review_baseline_n]
    historical_active = [
        row for row in rows if row.sequence <= review_baseline_n and row.floor_active
    ]
    active = [row for row in prospective if row.floor_active]
    identifying = [row for row in active if row.identifying]
    gate_reached = len(rows) >= minimum_for_review

    return FloorActiveSummary(
        total_rows=len(rows),
        prospective_rows=len(prospective),
        historical_active_rows=len(historical_active),
        active_rows=len(active),
        identifying_rows=len(identifying),
        new_identifying_rows=len(identifying),
        official_rps=_mean([row.official_rps for row in active]),
        shadow_rps=_mean([row.shadow_rps for row in active]),
        official_score_log_loss=_mean([row.official_score_log_loss for row in active]),
        shadow_score_log_loss=_mean([row.shadow_score_log_loss for row in active]),
        official_adv_brier=_mean([row.official_adv_brier for row in active]),
        shadow_adv_brier=_mean([row.shadow_adv_brier for row in active]),
        review_baseline_n=review_baseline_n,
        minimum_for_review=minimum_for_review,
        gate_reached=gate_reached,
        decision="REVIEW" if gate_reached and identifying else "NO_DECISION",
    )


@dataclass(frozen=True)
class DrawFloorMetricRow:
    sequence: int
    floor: float
    draw_boost: float
    rps: float
    score_log_loss: float
    adv_brier: float


@dataclass(frozen=True)
class DrawFloorCellSummary:
    floor: float
    draw_boost: float
    n: int
    rps: float
    score_log_loss: float
    adv_brier: float


@dataclass(frozen=True)
class DrawFloorInteractionSummary:
    total_rows: int
    fixture_rows: int
    minimum_for_review: int
    gate_reached: bool
    floor_levels: tuple[float, float]
    draw_boost_levels: tuple[float, float]
    cells: tuple[DrawFloorCellSummary, ...]
    rps_interaction: float
    score_log_loss_interaction: float
    adv_brier_interaction: float
    decision: str


def summarize_draw_floor_interaction(
    rows: Sequence[DrawFloorMetricRow],
    *,
    minimum_for_review: int = 28,
) -> DrawFloorInteractionSummary:
    """Return a complete 2x2 floor-by-draw-boost interaction summary."""
    if not rows:
        raise ValueError("draw-floor interaction requires metric rows")
    floor_levels = tuple(sorted({float(row.floor) for row in rows}))
    draw_levels = tuple(sorted({float(row.draw_boost) for row in rows}))
    if len(floor_levels) != 2 or len(draw_levels) != 2:
        raise ValueError("draw-floor interaction requires exactly two levels per factor")

    sequences = sorted({row.sequence for row in rows})
    expected_cells = {
        (sequence, floor, draw)
        for sequence in sequences
        for floor in floor_levels
        for draw in draw_levels
    }
    actual_cells = [(row.sequence, float(row.floor), float(row.draw_boost)) for row in rows]
    if any(sequence <= 0 for sequence in sequences):
        raise ValueError("draw-floor metric sequences must be positive")
    if len(set(actual_cells)) != len(actual_cells) or set(actual_cells) != expected_cells:
        raise ValueError("draw-floor metric rows must contain one complete 2x2 per fixture")

    cell_summaries: list[DrawFloorCellSummary] = []
    by_cell: dict[tuple[float, float], DrawFloorCellSummary] = {}
    for floor in floor_levels:
        for draw in draw_levels:
            cell_rows = [
                row for row in rows
                if float(row.floor) == floor and float(row.draw_boost) == draw
            ]
            cell = DrawFloorCellSummary(
                floor=floor,
                draw_boost=draw,
                n=len(cell_rows),
                rps=float(_mean([row.rps for row in cell_rows])),
                score_log_loss=float(_mean([row.score_log_loss for row in cell_rows])),
                adv_brier=float(_mean([row.adv_brier for row in cell_rows])),
            )
            cell_summaries.append(cell)
            by_cell[(floor, draw)] = cell

    low_floor, high_floor = floor_levels
    low_draw, high_draw = draw_levels

    def interaction(field: str) -> float:
        return (
            getattr(by_cell[(high_floor, high_draw)], field)
            - getattr(by_cell[(high_floor, low_draw)], field)
            - getattr(by_cell[(low_floor, high_draw)], field)
            + getattr(by_cell[(low_floor, low_draw)], field)
        )

    fixture_rows = len(sequences)
    gate_reached = fixture_rows >= minimum_for_review
    return DrawFloorInteractionSummary(
        total_rows=len(rows),
        fixture_rows=fixture_rows,
        minimum_for_review=minimum_for_review,
        gate_reached=gate_reached,
        floor_levels=(low_floor, high_floor),
        draw_boost_levels=(low_draw, high_draw),
        cells=tuple(cell_summaries),
        rps_interaction=interaction("rps"),
        score_log_loss_interaction=interaction("score_log_loss"),
        adv_brier_interaction=interaction("adv_brier"),
        decision="REVIEW_INTERACTION" if gate_reached else "NO_DECISION",
    )


@dataclass(frozen=True)
class StyleCohortRule:
    min_clean_sheets_before: int = 2
    allowed_styles: tuple[str, ...] = ("low_block", "counterattack", "low_block_counter")
    min_market_minus_model_gap: float = 0.05
    min_resolved_fixtures: int = 20


@dataclass(frozen=True)
class StyleObservation:
    observation_id: str
    date: str
    fixture_id: str
    snapshot_order: int
    stage: str
    home: str
    away: str
    cohort_side: str
    clean_sheets_before: int
    style_tag: str
    model_win90: float
    market_win90: float
    outcome_win90: bool | None
    trigger_candidate: bool
    market_source: str
    odds_checked_at_utc: str
    demargin_method: str
    style_source: str
    notes: str
    kickoff_at_utc: str = ""
    registered_at_utc: str = ""
    style_checked_at_utc: str = ""
    weaker_side: str = ""
    cohort_side_elo: float | None = None
    opponent_elo: float | None = None
    strength_source: str = ""
    strength_checked_at_utc: str = ""
    market_evidence_sha256: str = ""
    style_evidence_sha256: str = ""

    @property
    def market_minus_model_gap(self) -> float:
        return self.market_win90 - self.model_win90


@dataclass(frozen=True)
class StyleCohortSummary:
    observation_rows: int
    distinct_fixtures: int
    eligible_fixtures: int
    resolved_eligible_fixtures: int
    undercalled_wins: int
    pending_trigger_fixtures: int
    decision: str


def load_style_observations(path: str | Path) -> list[StyleObservation]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    observations: list[StyleObservation] = []
    seen_ids: set[str] = set()
    for line, row in enumerate(rows, 2):
        observation_id = row["observation_id"].strip()
        if not observation_id or observation_id in seen_ids:
            raise ValueError(f"style ledger line {line}: duplicate/empty observation_id")
        seen_ids.add(observation_id)
        observations.append(
            StyleObservation(
                observation_id=observation_id,
                date=row["date"].strip(),
                fixture_id=row["fixture_id"].strip(),
                snapshot_order=int(row["snapshot_order"]),
                stage=row["stage"].strip(),
                home=row["home"].strip(),
                away=row["away"].strip(),
                cohort_side=row["cohort_side"].strip(),
                clean_sheets_before=int(row["clean_sheets_before"]),
                style_tag=row["style_tag"].strip(),
                model_win90=_check_probability(float(row["model_win90"]), "model_win90"),
                market_win90=_check_probability(float(row["market_win90"]), "market_win90"),
                outcome_win90=_parse_bool(row["outcome_win90"], "outcome_win90", optional=True),
                trigger_candidate=bool(_parse_bool(row["trigger_candidate"], "trigger_candidate")),
                market_source=str(row.get("market_source") or "").strip(),
                odds_checked_at_utc=str(
                    row.get("odds_checked_at_utc") or ""
                ).strip(),
                demargin_method=str(row.get("demargin_method") or "").strip(),
                style_source=str(row.get("style_source") or "").strip(),
                notes=str(row.get("notes") or "").strip(),
                kickoff_at_utc=str(row.get("kickoff_at_utc") or "").strip(),
                registered_at_utc=str(row.get("registered_at_utc") or "").strip(),
                style_checked_at_utc=str(
                    row.get("style_checked_at_utc") or ""
                ).strip(),
                weaker_side=str(row.get("weaker_side") or "").strip(),
                cohort_side_elo=_optional_float(row.get("cohort_side_elo", "")),
                opponent_elo=_optional_float(row.get("opponent_elo", "")),
                strength_source=str(row.get("strength_source") or "").strip(),
                strength_checked_at_utc=str(
                    row.get("strength_checked_at_utc") or ""
                ).strip(),
                market_evidence_sha256=str(
                    row.get("market_evidence_sha256") or ""
                ).strip(),
                style_evidence_sha256=str(
                    row.get("style_evidence_sha256") or ""
                ).strip(),
            )
        )
    return observations


def style_observation_eligible(
    observation: StyleObservation,
    rule: StyleCohortRule = StyleCohortRule(),
) -> bool:
    registered_pre_kickoff = _is_pre_kickoff(
        observation.registered_at_utc, observation.kickoff_at_utc
    )
    evidence_available = all(
        _is_available_at_registration(timestamp, observation.registered_at_utc)
        for timestamp in (
            observation.odds_checked_at_utc,
            observation.style_checked_at_utc,
            observation.strength_checked_at_utc,
        )
    )
    verified_weaker_side = (
        observation.cohort_side in {observation.home, observation.away}
        and observation.weaker_side == observation.cohort_side
        and observation.cohort_side_elo is not None
        and observation.opponent_elo is not None
        and observation.cohort_side_elo < observation.opponent_elo
        and _is_http_url(observation.strength_source)
    )
    return (
        observation.clean_sheets_before >= rule.min_clean_sheets_before
        and observation.style_tag in rule.allowed_styles
        and observation.market_minus_model_gap >= rule.min_market_minus_model_gap
        and _independent_http_sources(
            observation.market_source, observation.style_source
        )
        and _is_timezone_timestamp(observation.odds_checked_at_utc)
        and _is_timezone_timestamp(observation.style_checked_at_utc)
        and _is_timezone_timestamp(observation.strength_checked_at_utc)
        and _is_sha256(observation.market_evidence_sha256)
        and _is_sha256(observation.style_evidence_sha256)
        and registered_pre_kickoff
        and evidence_available
        and verified_weaker_side
        and observation.demargin_method in {"proportional", "power"}
    )


def latest_style_observations(
    observations: Iterable[StyleObservation],
) -> dict[str, StyleObservation]:
    latest: dict[str, StyleObservation] = {}
    for observation in observations:
        previous = latest.get(observation.fixture_id)
        if previous is None or (observation.snapshot_order, observation.date) > (
            previous.snapshot_order,
            previous.date,
        ):
            latest[observation.fixture_id] = observation
    return latest


def evaluate_style_cohort(
    observations: Sequence[StyleObservation],
    rule: StyleCohortRule = StyleCohortRule(),
) -> StyleCohortSummary:
    latest = list(latest_style_observations(observations).values())
    eligible = [row for row in latest if style_observation_eligible(row, rule)]
    resolved = [row for row in eligible if row.outcome_win90 is not None]
    undercalled_wins = sum(row.outcome_win90 is True for row in resolved)
    trigger_rows = [row for row in latest if row.trigger_candidate]
    pending_triggers = sum(row.outcome_win90 is None for row in trigger_rows)
    decision = (
        "REVIEW_COHORT"
        if len(resolved) >= rule.min_resolved_fixtures
        else "MONITOR_ONLY"
    )
    return StyleCohortSummary(
        observation_rows=len(observations),
        distinct_fixtures=len(latest),
        eligible_fixtures=len(eligible),
        resolved_eligible_fixtures=len(resolved),
        undercalled_wins=undercalled_wins,
        pending_trigger_fixtures=pending_triggers,
        decision=decision,
    )


@dataclass(frozen=True)
class ShootoutRecord:
    date: str
    stage: str
    fixture_id: str
    home: str
    away: str
    elo_home: float
    elo_away: float
    shootout_winner_side: str
    elo_tilt_pick_side: str
    pen_tilt: float
    elo_tilt_probability: float
    resolution_type: str
    source: str

    @property
    def elo_tilt_hit(self) -> bool:
        return self.shootout_winner_side == self.elo_tilt_pick_side


@dataclass(frozen=True)
class ShootoutSummary:
    rows: int
    real_shootout_rows: int
    elo_tilt_hits: int
    minimum_for_review: int
    population: str
    decision: str


def load_shootout_ledger(path: str | Path) -> list[ShootoutRecord]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        raw_rows = list(csv.DictReader(handle))
    records: list[ShootoutRecord] = []
    fixtures: set[str] = set()
    for line, row in enumerate(raw_rows, 2):
        fixture_id = row["fixture_id"].strip()
        if not fixture_id or fixture_id in fixtures:
            raise ValueError(f"shootout ledger line {line}: duplicate/empty fixture_id")
        fixtures.add(fixture_id)
        winner = row["shootout_winner_side"].strip()
        pick = row["elo_tilt_pick_side"].strip()
        if winner not in {"H", "A"} or pick not in {"H", "A"}:
            raise ValueError(f"shootout ledger line {line}: sides must be H or A")
        elo_home = float(row["elo_home"])
        elo_away = float(row["elo_away"])
        expected_pick = "H" if elo_home >= elo_away else "A"
        if pick != expected_pick:
            raise ValueError(f"shootout ledger line {line}: Elo tilt must pick {expected_pick}")
        pen_tilt = _check_probability(float(row["pen_tilt"]), "pen_tilt")
        elo_expectation_home = 1.0 / (1.0 + 10.0 ** (-(elo_home - elo_away) / 400.0))
        probability_home = 0.5 + (elo_expectation_home - 0.5) * pen_tilt
        expected_probability = probability_home if pick == "H" else 1.0 - probability_home
        recorded_probability = _check_probability(
            float(row["elo_tilt_probability"]), "elo_tilt_probability"
        )
        if abs(recorded_probability - expected_probability) > 0.001:
            raise ValueError(
                f"shootout ledger line {line}: Elo tilt probability does not match ratings"
            )
        resolution_type = str(row.get("resolution_type") or "").strip()
        if resolution_type != "shootout":
            raise ValueError(
                f"shootout ledger line {line}: resolution_type must be shootout"
            )
        records.append(
            ShootoutRecord(
                date=row["date"].strip(),
                stage=row["stage"].strip(),
                fixture_id=fixture_id,
                home=row["home"].strip(),
                away=row["away"].strip(),
                elo_home=elo_home,
                elo_away=elo_away,
                shootout_winner_side=winner,
                elo_tilt_pick_side=pick,
                pen_tilt=pen_tilt,
                elo_tilt_probability=recorded_probability,
                resolution_type=resolution_type,
                source=row["source"].strip(),
            )
        )
    return records


def summarize_shootouts(
    records: Sequence[ShootoutRecord],
    *,
    minimum_for_review: int = 5,
) -> ShootoutSummary:
    if any(record.resolution_type != "shootout" for record in records):
        raise ValueError("shootout summary accepts only real shootout resolutions")
    hits = sum(record.elo_tilt_hit for record in records)
    return ShootoutSummary(
        rows=len(records),
        real_shootout_rows=len(records),
        elo_tilt_hits=hits,
        minimum_for_review=minimum_for_review,
        population="REAL_SHOOTOUTS_ONLY",
        decision="REVIEW" if len(records) >= minimum_for_review else "HOLD",
    )


@dataclass(frozen=True)
class HomeAdvantageRecord:
    date: str
    stage: str
    fixture_id: str
    home: str
    away: str
    host_side: str
    venue: str
    altitude_m: float
    home_advantage_elo: float | None
    altitude_adjustment_elo: float | None
    legacy_combined_elo: float | None
    neutral_host_adv_probability: float
    adjusted_host_adv_probability: float
    host_advanced: bool
    component_status: str
    source: str


@dataclass(frozen=True)
class HomeAdvantageSummary:
    rows: int
    separated_rows: int
    legacy_combined_rows: int
    home_only_rows: int
    altitude_identified_rows: int
    minimum_for_review: int
    true_home_fixtures_remaining: int
    archive_status: str
    review_population: str
    home_decision: str
    altitude_decision: str
    decision: str


def load_home_advantage_ledger(path: str | Path) -> list[HomeAdvantageRecord]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        raw_rows = list(csv.DictReader(handle))
    records: list[HomeAdvantageRecord] = []
    fixtures: set[str] = set()
    for line, row in enumerate(raw_rows, 2):
        fixture_id = row["fixture_id"].strip()
        if not fixture_id or fixture_id in fixtures:
            raise ValueError(f"home-advantage ledger line {line}: duplicate/empty fixture_id")
        fixtures.add(fixture_id)
        home_component = _optional_float(row["home_advantage_elo"])
        altitude_component = _optional_float(row["altitude_adjustment_elo"])
        combined = _optional_float(row["legacy_combined_elo"])
        separated = home_component is not None and altitude_component is not None
        if separated == (combined is not None):
            raise ValueError(
                f"home-advantage ledger line {line}: use separated components "
                "XOR legacy_combined_elo"
            )
        records.append(
            HomeAdvantageRecord(
                date=row["date"].strip(),
                stage=row["stage"].strip(),
                fixture_id=fixture_id,
                home=row["home"].strip(),
                away=row["away"].strip(),
                host_side=row["host_side"].strip(),
                venue=row["venue"].strip(),
                altitude_m=float(row["altitude_m"]),
                home_advantage_elo=home_component,
                altitude_adjustment_elo=altitude_component,
                legacy_combined_elo=combined,
                neutral_host_adv_probability=_check_probability(
                    float(row["neutral_host_adv_probability"]),
                    "neutral_host_adv_probability",
                ),
                adjusted_host_adv_probability=_check_probability(
                    float(row["adjusted_host_adv_probability"]),
                    "adjusted_host_adv_probability",
                ),
                host_advanced=bool(_parse_bool(row["host_advanced"], "host_advanced")),
                component_status=row["component_status"].strip(),
                source=row["source"].strip(),
            )
        )
    return records


def summarize_home_advantage(
    records: Sequence[HomeAdvantageRecord],
    *,
    minimum_for_review: int = 6,
    true_home_fixtures_remaining: int = 0,
) -> HomeAdvantageSummary:
    if true_home_fixtures_remaining < 0:
        raise ValueError("true_home_fixtures_remaining must be non-negative")
    separated = [
        row
        for row in records
        if row.home_advantage_elo is not None and row.altitude_adjustment_elo is not None
    ]
    legacy = [row for row in records if row.legacy_combined_elo is not None]
    home_only = [row for row in separated if abs(row.altitude_adjustment_elo or 0.0) < 1e-12]
    altitude_identified = [
        row for row in separated if abs(row.altitude_adjustment_elo or 0.0) >= 1e-12
    ]
    home_decision = "REVIEW" if len(home_only) >= minimum_for_review else "NO_DECISION"
    altitude_decision = (
        "REVIEW" if len(altitude_identified) >= minimum_for_review else "NO_DECISION"
    )
    return HomeAdvantageSummary(
        rows=len(records),
        separated_rows=len(separated),
        legacy_combined_rows=len(legacy),
        home_only_rows=len(home_only),
        altitude_identified_rows=len(altitude_identified),
        minimum_for_review=minimum_for_review,
        true_home_fixtures_remaining=true_home_fixtures_remaining,
        archive_status=(
            "ARCHIVED_NO_TRUE_HOMES_REMAINING"
            if true_home_fixtures_remaining == 0
            else "ACTIVE"
        ),
        review_population="HOME_ONLY_ZERO_ALTITUDE",
        home_decision=home_decision,
        altitude_decision=altitude_decision,
        decision=(
            "REVIEW"
            if home_decision == "REVIEW" or altitude_decision == "REVIEW"
            else "NO_DECISION"
        ),
    )


@dataclass(frozen=True)
class EnsembleGridPoint:
    model_weight: float
    brier: float


@dataclass(frozen=True)
class EnsembleBasisSummary:
    total_rows: int
    live_rows: int
    excluded_rows: int
    basis_counts: dict[str, int]
    minimum_for_refit: int
    current_weight: float
    current_brier: float | None
    best_weight: float | None
    best_brier: float | None
    grid: tuple[EnsembleGridPoint, ...]
    decision: str


def summarize_ensemble_basis(
    path: str | Path,
    *,
    live_basis: str = "live_current_elo",
    minimum_for_refit: int = 12,
    current_weight: float = 0.6,
) -> EnsembleBasisSummary:
    """Validate prospective live-basis rows and refit only at the n=12 gate.

    Historical ``mixed_legacy`` and counterfactual rows remain visible in the
    basis counts but never enter either the eligible n or the weight grid.
    """
    _check_probability(current_weight, "current_weight")
    if minimum_for_refit <= 0:
        raise ValueError("minimum_for_refit must be positive")
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    counts: dict[str, int] = {}
    eligible: list[tuple[float, float, float]] = []
    fixture_keys: set[tuple[str, str, str]] = set()
    for line, row in enumerate(rows, 2):
        basis = str(row.get("basis", "")).strip()
        if not basis:
            raise ValueError(f"ensemble ledger line {line}: missing basis")
        counts[basis] = counts.get(basis, 0) + 1
        if basis != live_basis:
            continue

        date = str(row.get("date", "")).strip()
        stage = str(row.get("stage", "")).strip()
        home = str(row.get("home", "")).strip()
        away = str(row.get("away", "")).strip()
        try:
            datetime.fromisoformat(date)
        except ValueError as exc:
            raise ValueError(
                f"ensemble ledger line {line}: date must be ISO-8601"
            ) from exc
        if not stage or not home or not away or home == away:
            raise ValueError(f"ensemble ledger line {line}: invalid fixture identity")
        fixture_key = (stage, home, away)
        if fixture_key in fixture_keys:
            raise ValueError(f"ensemble ledger line {line}: duplicate live fixture")
        fixture_keys.add(fixture_key)

        if str(row.get("fav_side", "")).strip() not in {"H", "A"}:
            raise ValueError(f"ensemble ledger line {line}: fav_side must be H or A")
        outcome_raw = str(row.get("advanced_fav", "")).strip()
        if outcome_raw not in {"0", "1"}:
            raise ValueError(
                f"ensemble ledger line {line}: advanced_fav must be settled as 0 or 1"
            )
        outcome = float(outcome_raw)
        p_model = _check_probability(
            float(row["p_model_currelo"]), f"ensemble line {line} p_model_currelo"
        )
        p_market = _check_probability(
            float(row["p_market"]), f"ensemble line {line} p_market"
        )
        p_recorded = _check_probability(
            float(row["p_ensemble"]), f"ensemble line {line} p_ensemble"
        )

        for field, probability in (
            ("brier_model", p_model),
            ("brier_market", p_market),
            ("brier_ensemble", p_recorded),
        ):
            recorded = float(row[field])
            expected = (probability - outcome) ** 2
            if abs(recorded - expected) > 0.0015:
                raise ValueError(
                    f"ensemble ledger line {line}: {field} does not match settled outcome"
                )
        eligible.append((p_model, p_market, outcome))

    live_rows = len(eligible)
    current_brier = _mean([
        (current_weight * p_model + (1.0 - current_weight) * p_market - outcome) ** 2
        for p_model, p_market, outcome in eligible
    ])
    grid: tuple[EnsembleGridPoint, ...] = ()
    best_weight: float | None = None
    best_brier: float | None = None
    if live_rows >= minimum_for_refit:
        grid = tuple(
            EnsembleGridPoint(
                model_weight=weight,
                brier=float(_mean([
                    (weight * p_model + (1.0 - weight) * p_market - outcome) ** 2
                    for p_model, p_market, outcome in eligible
                ])),
            )
            for weight in (index / 10.0 for index in range(11))
        )
        best = min(
            grid,
            key=lambda point: (
                point.brier,
                abs(point.model_weight - current_weight),
                point.model_weight,
            ),
        )
        best_weight = best.model_weight
        best_brier = best.brier
    return EnsembleBasisSummary(
        total_rows=len(rows),
        live_rows=live_rows,
        excluded_rows=len(rows) - live_rows,
        basis_counts=counts,
        minimum_for_refit=minimum_for_refit,
        current_weight=current_weight,
        current_brier=current_brier,
        best_weight=best_weight,
        best_brier=best_brier,
        grid=grid,
        decision="REVIEW_REFIT" if grid else "HOLD_W_0_6",
    )
