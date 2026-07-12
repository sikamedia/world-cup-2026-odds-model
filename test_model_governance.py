#!/usr/bin/env python3
"""Regression checks for the structured knockout-model governance layer."""

from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import backtest_ko as bt
from model_governance import (
    FloorMetricRow,
    evaluate_style_cohort,
    latest_style_observations,
    load_home_advantage_ledger,
    load_shootout_ledger,
    load_style_observations,
    paired_brier_comparison,
    style_observation_eligible,
    summarize_draw_floor_interaction,
    summarize_ensemble_basis,
    summarize_floor_active,
    summarize_home_advantage,
    summarize_shootouts,
)


ROOT = Path(__file__).resolve().parent


def _approx(actual: float, expected: float, tolerance: float = 1e-12) -> None:
    assert abs(actual - expected) <= tolerance, (actual, expected)


def _raises_value_error(callable_) -> None:
    try:
        callable_()
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def _write_ensemble(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "date", "stage", "home", "away", "fav_side", "p_model_currelo",
        "p_market", "p_ensemble", "advanced_fav", "brier_model",
        "brier_market", "brier_ensemble", "basis", "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _ensemble_row(index: int, *, basis: str = "live_current_elo") -> dict[str, str]:
    return {
        "date": f"2026-08-{index + 1:02d}",
        "stage": "TEST",
        "home": f"Home {index}",
        "away": f"Away {index}",
        "fav_side": "H",
        "p_model_currelo": "0.800",
        "p_market": "0.600",
        "p_ensemble": "0.700",
        "advanced_fav": "1",
        "brier_model": "0.040",
        "brier_market": "0.160",
        "brier_ensemble": "0.090",
        "basis": basis,
        "notes": "synthetic governance boundary",
    }


def main() -> None:
    # Paired uncertainty is computed from per-match loss deltas.  This fixture
    # has deltas -0.05 and -0.09: mean -0.07 and paired SE 0.02.
    gated_simple = paired_brier_comparison([0.8, 0.4], [0.7, 0.5], [1, 0])
    assert not gated_simple.gate_reached
    assert gated_simple.decision == "NO_DECISION"
    simple = paired_brier_comparison(
        [0.8, 0.4], [0.7, 0.5], [1, 0], minimum_for_review=2
    )
    assert simple.n == 2
    _approx(simple.mean_difference, -0.07)
    _approx(simple.standard_error, 0.02)
    assert simple.ci95_high < 0.0
    assert simple.decision == "GRADED_BETTER"

    records = []
    for home, away, _hg, _ag, advanced, _stage in bt.KO_RESULTS:
        _ph, _pd, _pa, matrix, e_home, _adv = bt.predict(home, away)
        records.append((matrix, e_home, advanced, bt.ELO[home] - bt.ELO[away]))
    paired = bt.paired_graded_flat1(records)
    graded_brier = bt.adv_metrics(records, None)[0]
    flat1_brier = bt.adv_metrics(records, 1.0)[0]
    assert paired.n == len(bt.KO_RESULTS)
    assert paired.n >= 24
    assert paired.minimum_for_review == 28
    # Gate is a function of n: the pre-registered review fires at n>=28
    # (reached 2026-07-12 when the two July 11 QFs were graded; CI still
    # crossed zero, so the frozen graded-k default stands).
    assert paired.gate_reached == (paired.n >= paired.minimum_for_review)
    _approx(paired.mean_difference, graded_brier - flat1_brier)
    assert paired.standard_error > 0.0
    assert paired.ci95_low < 0.0 < paired.ci95_high
    assert paired.decision == "NO_DECISION"

    floor_rows = bt.build_floor_metric_rows()
    floor_review = summarize_floor_active(
        floor_rows,
        review_baseline_n=bt.FLOOR_REVIEW_BASELINE_N,
    )
    assert floor_review.prospective_rows == len(bt.KO_RESULTS) - 24
    assert floor_review.historical_active_rows == 5
    assert floor_review.active_rows == 0
    assert floor_review.identifying_rows == 0
    assert floor_review.new_identifying_rows == 0
    assert floor_review.decision == "NO_DECISION"
    assert floor_review.official_score_log_loss is None
    # Same n-driven gate as the paired review: reached at n>=28 (2026-07-12),
    # but with zero prospective floor-active rows it stays NO_DECISION.
    assert floor_review.gate_reached == (len(bt.KO_RESULTS) >= 28)

    # The gate and prospective floor activation are both necessary.  Historical
    # floor-active rows cannot be reused after adoption at sequence 24.
    # Synthetic scenarios below reconstruct the n=25 state they were written
    # against (sequences 26-28 are synthetic slots), so they stay valid as real
    # graded rows accumulate past the gate.
    floor_rows = [row for row in floor_rows if row.sequence <= 25]
    inert = FloorMetricRow(
        sequence=26,
        fixture="NoFloor|Fixture",
        floor_active=False,
        official_rps=0.1,
        shadow_rps=0.1,
        official_score_log_loss=1.0,
        shadow_score_log_loss=1.0,
        official_adv_brier=0.1,
        shadow_adv_brier=0.1,
    )
    assert summarize_floor_active(
        [*floor_rows, inert], review_baseline_n=24
    ).decision == "NO_DECISION"
    new_active = replace(
        next(row for row in floor_rows if row.floor_active),
        sequence=28,
        fixture="New|FloorActive",
    )
    inert_27 = replace(inert, sequence=27, fixture="NoFloor|Fixture27")
    below_gate = summarize_floor_active(
        [*floor_rows, new_active], review_baseline_n=24
    )
    assert below_gate.new_identifying_rows == 1
    assert below_gate.decision == "NO_DECISION"
    active_review = summarize_floor_active(
        [*floor_rows, inert, inert_27, new_active], review_baseline_n=24
    )
    assert active_review.new_identifying_rows == 1
    assert active_review.gate_reached
    assert active_review.decision == "REVIEW"
    no_active_at_gate = summarize_floor_active(
        [
            *floor_rows,
            inert,
            inert_27,
            replace(inert, sequence=28, fixture="NoFloor|Fixture28"),
        ],
        review_baseline_n=24,
    )
    assert no_active_at_gate.gate_reached
    assert no_active_at_gate.decision == "NO_DECISION"

    draw_floor_rows = bt.build_draw_floor_metric_rows()
    draw_floor = summarize_draw_floor_interaction(draw_floor_rows)
    assert draw_floor.fixture_rows == len(bt.KO_RESULTS)
    assert len(draw_floor.cells) == 4
    assert all(cell.n == len(bt.KO_RESULTS) for cell in draw_floor.cells)
    # n-driven gate: reached at n>=28 (2026-07-12). At the gate the summary
    # flags REVIEW_INTERACTION by construction; the measured interaction
    # (~+0.00003 RPS) is fixture-level noise, so frozen params stand.
    assert draw_floor.gate_reached == (len(bt.KO_RESULTS) >= 28)
    assert draw_floor.decision == (
        "REVIEW_INTERACTION" if draw_floor.gate_reached else "NO_DECISION"
    )
    first_fixture_cells = [row for row in draw_floor_rows if row.sequence == 1]
    extended_cells = [*draw_floor_rows]
    _base = max(row.sequence for row in draw_floor_rows)
    for sequence in (_base + 1, _base + 2, _base + 3):
        extended_cells.extend(replace(row, sequence=sequence) for row in first_fixture_cells)
    gated_interaction = summarize_draw_floor_interaction(extended_cells)
    assert gated_interaction.gate_reached
    assert gated_interaction.decision == "REVIEW_INTERACTION"
    _raises_value_error(
        lambda: summarize_draw_floor_interaction(draw_floor_rows[:-1])
    )

    style_rows = load_style_observations(ROOT / "style_divergence_ledger.csv")
    style_latest = latest_style_observations(style_rows)
    assert len(style_rows) == 3
    assert len(style_latest) == 2
    assert style_latest["2026-QF97-France-Morocco"].observation_id == "fra_mar_final"
    assert not style_observation_eligible(style_latest["2026-QF97-France-Morocco"])
    assert not style_observation_eligible(style_latest["2026-QF98-Spain-Belgium"])
    style_summary = evaluate_style_cohort(style_rows)
    assert style_summary.eligible_fixtures == 0
    assert style_summary.pending_trigger_fixtures == 1
    assert style_summary.decision == "MONITOR_ONLY"

    trigger_win = [
        replace(row, outcome_win90=True) if row.trigger_candidate else row
        for row in style_rows
    ]
    assert evaluate_style_cohort(trigger_win).decision == "MONITOR_ONLY"
    trigger_loss = [
        replace(row, outcome_win90=False) if row.trigger_candidate else row
        for row in style_rows
    ]
    assert evaluate_style_cohort(trigger_loss).decision == "MONITOR_ONLY"

    prospective = []
    template = replace(
        style_latest["2026-QF97-France-Morocco"],
        clean_sheets_before=2,
        market_source="https://market.example/fixture",
        odds_checked_at_utc="2026-07-10T17:00:00Z",
        demargin_method="proportional",
        style_source="https://analysis.example/fixture",
        style_checked_at_utc="2026-07-10T16:00:00Z",
        strength_source="https://www.eloratings.net/World.tsv",
        strength_checked_at_utc="2026-07-10T17:30:00Z",
        registered_at_utc="2026-07-10T18:00:00Z",
        kickoff_at_utc="2026-07-10T20:00:00Z",
        weaker_side="Morocco",
        cohort_side_elo=1800.0,
        opponent_elo=1950.0,
        market_evidence_sha256="a" * 64,
        style_evidence_sha256="b" * 64,
    )
    assert style_observation_eligible(template)
    assert not style_observation_eligible(
        replace(template, registered_at_utc="2026-07-10T20:00:00Z")
    )
    assert not style_observation_eligible(
        replace(template, odds_checked_at_utc="2026-07-10T20:00:00Z")
    )
    assert not style_observation_eligible(
        replace(template, style_checked_at_utc="2026-07-10T20:00:00Z")
    )
    assert not style_observation_eligible(
        replace(template, weaker_side="France")
    )
    assert not style_observation_eligible(
        replace(template, cohort_side_elo=2000.0)
    )
    assert not style_observation_eligible(
        replace(template, style_source="https://market.example/style")
    )
    assert not style_observation_eligible(
        replace(template, market_evidence_sha256="not-a-sha256")
    )
    for index in range(20):
        prospective.append(
            replace(
                template,
                observation_id=f"prospective-{index}",
                fixture_id=f"prospective-fixture-{index}",
                outcome_win90=bool(index % 2),
                trigger_candidate=False,
            )
        )
    reviewed = evaluate_style_cohort(prospective)
    assert reviewed.resolved_eligible_fixtures == 20
    assert reviewed.decision == "REVIEW_COHORT"

    shootouts = load_shootout_ledger(ROOT / "shootout_ledger.csv")
    shootout_summary = summarize_shootouts(shootouts)
    assert shootout_summary.rows == 4
    assert shootout_summary.real_shootout_rows == 4
    assert shootout_summary.population == "REAL_SHOOTOUTS_ONLY"
    assert shootout_summary.elo_tilt_hits == 0
    assert shootout_summary.minimum_for_review == 5
    assert shootout_summary.decision == "HOLD"
    assert all(record.pen_tilt == 0.20 for record in shootouts)
    assert all(record.elo_tilt_probability > 0.5 for record in shootouts)
    assert all(record.resolution_type == "shootout" for record in shootouts)
    assert {(record.home, record.away) for record in shootouts} == {
        ("Germany", "Paraguay"),
        ("Netherlands", "Morocco"),
        ("Australia", "Egypt"),
        ("Switzerland", "Colombia"),
    }
    ko_lookup = {
        (home, away, stage): (home_goals, away_goals, advanced)
        for home, away, home_goals, away_goals, advanced, stage in bt.KO_RESULTS
    }
    for record in shootouts:
        home_goals, away_goals, advanced = ko_lookup[
            (record.home, record.away, record.stage)
        ]
        assert home_goals == away_goals
        assert advanced == record.shootout_winner_side
    fifth_shootout = replace(
        shootouts[0],
        date="2026-07-11",
        fixture_id="synthetic-fifth-real-shootout",
    )
    five_summary = summarize_shootouts([*shootouts, fifth_shootout])
    assert five_summary.real_shootout_rows == 5
    assert five_summary.decision == "REVIEW"
    _raises_value_error(
        lambda: summarize_shootouts([
            *shootouts,
            replace(fifth_shootout, resolution_type="extra_time"),
        ])
    )
    with TemporaryDirectory() as temp_dir:
        invalid_shootout = Path(temp_dir) / "shootout.csv"
        ledger_text = (ROOT / "shootout_ledger.csv").read_text(encoding="utf-8")
        invalid_shootout.write_text(
            ledger_text.replace(",shootout,", ",extra_time,", 1),
            encoding="utf-8",
        )
        _raises_value_error(lambda: load_shootout_ledger(invalid_shootout))

    home_rows = load_home_advantage_ledger(ROOT / "home_advantage_ledger.csv")
    home_summary = summarize_home_advantage(home_rows)
    assert home_summary.rows == 2
    assert home_summary.separated_rows == 1
    assert home_summary.home_only_rows == 1
    assert home_summary.altitude_identified_rows == 0
    assert home_summary.legacy_combined_rows == 1
    assert home_summary.home_decision == "NO_DECISION"
    assert home_summary.altitude_decision == "NO_DECISION"
    assert home_summary.decision == "NO_DECISION"
    assert home_summary.review_population == "HOME_ONLY_ZERO_ALTITUDE"
    assert home_summary.true_home_fixtures_remaining == 0
    assert home_summary.archive_status == "ARCHIVED_NO_TRUE_HOMES_REMAINING"
    azteca = next(row for row in home_rows if row.venue == "Estadio Azteca")
    assert azteca.legacy_combined_elo == 90.0
    assert azteca.home_advantage_elo is None
    assert azteca.altitude_adjustment_elo is None
    for record in home_rows:
        _home_goals, _away_goals, advanced = ko_lookup[
            (record.home, record.away, record.stage)
        ]
        assert (advanced == record.host_side) is record.host_advanced
    separated_template = next(row for row in home_rows if row.home_advantage_elo)
    altitude_only = [
        replace(
            separated_template,
            fixture_id=f"synthetic-altitude-{index}",
            altitude_adjustment_elo=20.0,
        )
        for index in range(6)
    ]
    altitude_summary = summarize_home_advantage(altitude_only)
    assert altitude_summary.separated_rows == 6
    assert altitude_summary.home_only_rows == 0
    assert altitude_summary.home_decision == "NO_DECISION"
    assert altitude_summary.altitude_decision == "REVIEW"
    home_only = [
        replace(
            separated_template,
            fixture_id=f"synthetic-home-{index}",
        )
        for index in range(6)
    ]
    assert summarize_home_advantage(home_only).home_decision == "REVIEW"

    ensemble = summarize_ensemble_basis(ROOT / "ensemble_ledger.csv")
    assert ensemble.live_rows >= 6
    assert ensemble.basis_counts["mixed_legacy"] == 1
    assert ensemble.basis_counts["current_elo_counterfactual"] == 1
    assert ensemble.total_rows == ensemble.live_rows + 2
    assert ensemble.minimum_for_refit == 12
    assert ensemble.decision == "HOLD_W_0_6"
    assert ensemble.current_weight == 0.6
    assert ensemble.current_brier is not None
    assert ensemble.best_weight is None
    assert ensemble.grid == ()

    with TemporaryDirectory() as temp_dir:
        ledger = Path(temp_dir) / "ensemble.csv"
        rows = [_ensemble_row(index) for index in range(12)]
        rows.append(_ensemble_row(12, basis="mixed_legacy"))
        _write_ensemble(ledger, rows[:11])
        eleven = summarize_ensemble_basis(ledger)
        assert eleven.live_rows == 11
        assert eleven.grid == ()
        assert eleven.decision == "HOLD_W_0_6"

        _write_ensemble(ledger, rows)
        twelve = summarize_ensemble_basis(ledger)
        assert twelve.live_rows == 12
        assert twelve.excluded_rows == 1
        assert len(twelve.grid) == 11
        assert twelve.best_weight == 1.0
        _approx(twelve.best_brier, 0.04)
        assert twelve.current_brier > twelve.best_brier
        assert twelve.decision == "REVIEW_REFIT"

        duplicate_row = dict(rows[0])
        duplicate_row["date"] = "2026-09-01"
        duplicate = [*rows[:12], duplicate_row]
        _write_ensemble(ledger, duplicate)
        _raises_value_error(lambda: summarize_ensemble_basis(ledger))
        pending = [dict(row) for row in rows[:12]]
        pending[-1]["advanced_fav"] = "pending"
        _write_ensemble(ledger, pending)
        _raises_value_error(lambda: summarize_ensemble_basis(ledger))

    print("MODEL_GOVERNANCE_REGRESSION PASS")


if __name__ == "__main__":
    main()
