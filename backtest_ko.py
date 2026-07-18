#!/usr/bin/env python3
"""Knockout-stage backtest — SEPARATE batch from the 72 group-stage games.

Mirrors backtest_72.py's metrics (RPS / Tipset / draw / big-win) but runs on the
knockout profile (lower avg_goals, advancement resolver) over KO_RESULTS only.
It reuses the validated engine from skill/scripts/match_model.py — one source of
truth, no duplicated scoring code.

DISCIPLINE: do NOT tune knockout params on a handful of games. R32 is only 16
matches; treat the knockout profile (avg_goals~2.70) as a market-anchored prior
until the sample is large enough to mean something. No motivation/rotation in
the knockouts (everyone is full strength).

Run:  python3 backtest_ko.py
Educational/analytical use only - not betting advice.
"""
import math
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(__file__)
for _scripts in (os.path.join(ROOT, "skill", "scripts"), os.path.join(ROOT, "scripts")):
    if os.path.isdir(_scripts):
        sys.path.insert(0, _scripts)
        break
import match_model as mm  # noqa: E402

from worldcup_2026_data_ko import ELO, HOME, KO_RESULTS  # noqa: E402,F401
from model_governance import (  # noqa: E402
    DrawFloorMetricRow,
    FloorMetricRow,
    evaluate_style_cohort,
    load_home_advantage_ledger,
    load_shootout_ledger,
    load_style_observations,
    paired_brier_comparison,
    summarize_ensemble_basis,
    summarize_draw_floor_interaction,
    summarize_floor_active,
    summarize_home_advantage,
    summarize_shootouts,
)

KO = mm.STAGE_PROFILES["knockout"]
FLOOR_REVIEW_BASELINE_N = 24
REVIEW_GATE_N = 28
SHADOW_DRAW_BOOST = 0.07


def _ensemble_grid_lines(ensemble):
    """Format every pre-registered grid point without changing production w."""
    lines = []
    for point in ensemble.grid:
        marker = (
            " [FROZEN PRODUCTION]"
            if point.model_weight == ensemble.current_weight
            else ""
        )
        lines.append(
            f"      w={point.model_weight:.1f} Brier {point.brier:.4f}{marker}"
        )
    return tuple(lines)


def res(hg, ag):
    return 0 if hg > ag else (1 if hg == ag else 2)


def rps_hda(probs, result):
    oc = [1 if result == k else 0 for k in range(3)]
    cp = co = score = 0.0
    for k in range(2):
        cp += probs[k]
        co += oc[k]
        score += (cp - co) ** 2
    return score / 2


def graded_k_for(eh, ea):
    """LOCKED 2026-07-04: the knockout default is the ΔElo-graded ko_regress."""
    return mm.graded_ko_regress(
        eh - ea, KO["ko_regress"],
        KO.get("ko_regress_max", KO["ko_regress"]),
        KO.get("ko_elo_scale", 350.0))


def predict(home, away, floor=None, draw_boost=None):
    """Neutral-venue knockout prediction (no host bump, no motivation).
    Returns 90' probs, the score matrix, the Elo home win-expectation, and the
    advancement dict at the LOCKED graded ko_regress.
    floor: lambda floor; None = the profile value (0.30 since v3.9)."""
    eh, ea = ELO[home], ELO[away]
    if floor is None:
        floor = KO.get("lambda_floor", 0.15)
    if draw_boost is None:
        draw_boost = KO["draw_boost"]
    lh, la = mm.elo_to_lambdas(eh, ea, avg_goals=KO["avg_goals"],
                               gd_per_100=KO["gd_per_100"], floor=floor)
    style = "open" if abs(eh - ea) >= 266 else "balanced"
    P = mm.score_matrix(lh, la, opp_style=style, draw_boost=draw_boost)
    ph, pd, pa, _ov, _btts = mm.summarise(P)
    e_home = 1 / (1 + 10 ** (-(eh - ea) / 400))
    adv = mm.advancement(P, e_home, graded_k_for(eh, ea), KO["pen_tilt"])
    return ph, pd, pa, P, e_home, adv


def adv_metrics(records, k):
    """Advancement Brier, log-loss, and expected upsets at a given ko_regress k
    (k=None -> the LOCKED graded rule, computed per tie from its dElo).
    Favourite/underdog are defined by Elo (k-independent), so expected-upsets is
    comparable across k and against the fixed actual count. `records` items are
    (P, e_home, advanced, d_elo)."""
    brier = ll = exp_ups = 0.0
    for P, e_home, advanced, d_elo in records:
        k_eff = k if k is not None else mm.graded_ko_regress(
            d_elo, KO["ko_regress"],
            KO.get("ko_regress_max", KO["ko_regress"]),
            KO.get("ko_elo_scale", 350.0))
        p_home = mm.advancement(P, e_home, k_eff, KO["pen_tilt"])["adv_reg"]
        o = 1.0 if advanced == "H" else 0.0
        brier += (p_home - o) ** 2
        ll += -(o * math.log(max(p_home, 1e-12))
                + (1 - o) * math.log(max(1 - p_home, 1e-12)))
        exp_ups += (1 - p_home) if e_home >= 0.5 else p_home  # P(Elo-underdog)
    m = len(records)
    return brier / m, ll / m, exp_ups


def paired_graded_flat1(records):
    """Paired advancement Brier comparison on the exact same fixtures."""
    graded = []
    flat1 = []
    outcomes = []
    for P, e_home, advanced, d_elo in records:
        k_graded = mm.graded_ko_regress(
            d_elo, KO["ko_regress"],
            KO.get("ko_regress_max", KO["ko_regress"]),
            KO.get("ko_elo_scale", 350.0))
        graded.append(mm.advancement(P, e_home, k_graded, KO["pen_tilt"])["adv_reg"])
        flat1.append(mm.advancement(P, e_home, 1.0, KO["pen_tilt"])["adv_reg"])
        outcomes.append(1 if advanced == "H" else 0)
    return paired_brier_comparison(
        graded,
        flat1,
        outcomes,
        minimum_for_review=REVIEW_GATE_N,
    )


def build_floor_metric_rows(games=KO_RESULTS):
    """Build score/advancement metrics only once for the floor governance review."""
    official_floor = KO.get("lambda_floor", 0.15)
    shadow_floor = 0.15
    rows = []
    for sequence, (home, away, hg, ag, advanced, _stage) in enumerate(games, 1):
        eh, ea = ELO[home], ELO[away]
        goal_difference = (eh - ea) / 100.0 * KO["gd_per_100"]
        raw_lh = KO["avg_goals"] / 2.0 + goal_difference / 2.0
        raw_la = KO["avg_goals"] / 2.0 - goal_difference / 2.0
        floor_active = min(raw_lh, raw_la) < official_floor - 1e-12

        oph, opd, opa, official_P, _oe, official_adv = predict(
            home, away, floor=official_floor)
        sph, spd, spa, shadow_P, _se, shadow_adv = predict(
            home, away, floor=shadow_floor)
        result = res(hg, ag)
        outcome = 1.0 if advanced == "H" else 0.0
        rows.append(FloorMetricRow(
            sequence=sequence,
            fixture=f"{home}|{away}",
            floor_active=floor_active,
            official_rps=rps_hda((oph, opd, opa), result),
            shadow_rps=rps_hda((sph, spd, spa), result),
            official_score_log_loss=-math.log(max(official_P[(hg, ag)], 1e-12)),
            shadow_score_log_loss=-math.log(max(shadow_P[(hg, ag)], 1e-12)),
            official_adv_brier=(official_adv["adv_reg"] - outcome) ** 2,
            shadow_adv_brier=(shadow_adv["adv_reg"] - outcome) ** 2,
        ))
    return rows


def build_draw_floor_metric_rows(games=KO_RESULTS):
    """Build the pre-registered 2x2 floor-by-draw-boost score table."""
    official_floor = KO.get("lambda_floor", 0.15)
    floor_levels = (0.15, official_floor)
    draw_levels = (KO["draw_boost"], SHADOW_DRAW_BOOST)
    if len(set(floor_levels)) != 2 or len(set(draw_levels)) != 2:
        raise ValueError("draw-floor review requires two distinct factor levels")

    rows = []
    for sequence, (home, away, hg, ag, advanced, _stage) in enumerate(games, 1):
        result = res(hg, ag)
        outcome = 1.0 if advanced == "H" else 0.0
        for floor in floor_levels:
            for draw_boost in draw_levels:
                ph, pd, pa, matrix, _e_home, adv = predict(
                    home,
                    away,
                    floor=floor,
                    draw_boost=draw_boost,
                )
                rows.append(DrawFloorMetricRow(
                    sequence=sequence,
                    floor=floor,
                    draw_boost=draw_boost,
                    rps=rps_hda((ph, pd, pa), result),
                    score_log_loss=-math.log(max(matrix[(hg, ag)], 1e-12)),
                    adv_brier=(adv["adv_reg"] - outcome) ** 2,
                ))
    return rows


def structured_governance_summaries(
    root=Path(ROOT),
    *,
    trusted_anchor_resolver=None,
):
    """Load review ledgers, default-denying externally unanchored freezes."""
    style = evaluate_style_cohort(
        load_style_observations(root / "style_divergence_ledger.csv"))
    shootout = summarize_shootouts(
        load_shootout_ledger(root / "shootout_ledger.csv"))
    home = summarize_home_advantage(
        load_home_advantage_ledger(root / "home_advantage_ledger.csv"))
    ensemble = summarize_ensemble_basis(
        root / "ensemble_ledger.csv",
        trusted_anchor_resolver=trusted_anchor_resolver,
    )
    return style, shootout, home, ensemble


def main():
    games = KO_RESULTS
    n = len(games)
    print("#" * 64)
    print(f"# KNOCKOUT BACKTEST — {n} game(s)  (profile: avg_goals "
          f"{KO['avg_goals']}, ko_regress {KO['ko_regress']}, "
          f"lambda_floor {KO.get('lambda_floor', 0.15)})")
    print("#" * 64)
    if n == 0:
        print("\nNo knockout results recorded yet. Append rows to KO_RESULTS in "
              "worldcup_2026_data_ko.py as games finish, then re-run.")
        ph, pd, pa, _P, _e, adv = predict("South Africa", "Canada")
        print("\nPipeline smoke-test (South Africa vs Canada, not yet played):")
        print(f"  90' W/D/L : {ph*100:.1f}% / {pd*100:.1f}% / {pa*100:.1f}%")
        print(f"  ADVANCE   : SA raw {adv['adv_raw']*100:.1f}% / "
              f"regressed {adv['adv_reg']*100:.1f}%  |  "
              f"Canada raw {(1-adv['adv_raw'])*100:.1f}% / "
              f"regressed {(1-adv['adv_reg'])*100:.1f}%")
        return

    # 90' scoreline metrics (independent of ko_regress) + per-tie advancement.
    rps = ll90 = dps = 0.0
    dir_hit = draws_act = blow_act = act_ups = adv_hit = 0
    blow_exp = 0.0
    records = []                       # (P, e_home, advanced, d_elo)
    print(f"\n{'Tie':30}{'90':>5}   model advancement -> actual")
    for home, away, hg, ag, advanced, _stage in games:
        ph, pd, pa, P, e_home, adv = predict(home, away)
        r = res(hg, ag)
        rps += rps_hda((ph, pd, pa), r)
        ll90 += math.log(max(P[(hg, ag)], 1e-12))
        dps += pd
        dir_hit += max(range(3), key=lambda k: [ph, pd, pa][k]) == r
        draws_act += r == 1
        blow_act += abs(hg - ag) >= 3
        blow_exp += sum(p for (i, j), p in P.items() if abs(i - j) >= 3)
        records.append((P, e_home, advanced, ELO[home] - ELO[away]))
        p_home = adv["adv_reg"]
        fav_name, fav_p = (home, p_home) if p_home >= 0.5 else (away, 1 - p_home)
        act_name = home if advanced == "H" else away
        adv_hit += (p_home >= 0.5) == (advanced == "H")
        upset = (advanced == "H") != (e_home >= 0.5)   # Elo-underdog advanced
        act_ups += upset
        print(f"{(home[:13] + ' v ' + away[:13]):30}{f'{hg}-{ag}':>5}   "
              f"adv {fav_name[:12]} {fav_p*100:2.0f}% -> {act_name[:12]}"
              f"  {'UPSET' if upset else 'ok'}")

    print(f"\n90' scoreline: RPS {rps/n:.4f} | logL {ll90:.2f} "
          f"(avg {ll90/n:.3f}) | dir {dir_hit}/{n} | draws {draws_act}/{n} "
          f"| blowout>=3 {blow_act} (model exp {blow_exp:.1f})")

    bg, lg, eg = adv_metrics(records, None)   # LOCKED graded default
    print(f"\nADVANCEMENT (LOCKED graded k {KO['ko_regress']}->"
          f"{KO.get('ko_regress_max', KO['ko_regress'])}"
          f"/{KO.get('ko_elo_scale', 350.0):.0f}):  called-right {adv_hit}/{n}"
          f"  |  Brier {bg:.4f}  |  log-loss {lg:.4f}")
    print(f"  upsets: actual {act_ups}  vs  model-expected {eg:.2f}")

    paired = paired_graded_flat1(records)
    print("  paired graded-flat1 Brier: "
          f"delta {paired.mean_difference:+.4f} | SE {paired.standard_error:.4f} "
          f"| 95% CI [{paired.ci95_low:+.4f}, {paired.ci95_high:+.4f}] "
          f"| gate {paired.n}/{paired.minimum_for_review} => {paired.decision}")

    floor_review = summarize_floor_active(
        build_floor_metric_rows(games),
        review_baseline_n=FLOOR_REVIEW_BASELINE_N,
        minimum_for_review=REVIEW_GATE_N,
    )
    print(f"\nFLOOR-ACTIVE REVIEW (official {KO.get('lambda_floor', 0.15):.2f} "
          f"vs shadow 0.15; baseline n={FLOOR_REVIEW_BASELINE_N}):")
    print(f"  prospective rows {floor_review.prospective_rows} | "
          f"prospective active {floor_review.active_rows} | "
          f"historical active excluded {floor_review.historical_active_rows} | "
          f"identifying {floor_review.identifying_rows} | "
          f"gate {floor_review.total_rows}/{floor_review.minimum_for_review}")
    if floor_review.active_rows:
        print(f"  active-only RPS official/shadow "
              f"{floor_review.official_rps:.4f}/{floor_review.shadow_rps:.4f} | "
              f"score logLoss {floor_review.official_score_log_loss:.3f}/"
              f"{floor_review.shadow_score_log_loss:.3f} | adv Brier "
              f"{floor_review.official_adv_brier:.4f}/"
              f"{floor_review.shadow_adv_brier:.4f}")
    if not floor_review.gate_reached:
        floor_reason = "n=28 review gate not reached"
    elif not floor_review.identifying_rows:
        floor_reason = "no post-adoption floor-active fixture added identifying power"
    else:
        floor_reason = "post-adoption floor-active evidence is ready for review"
    print(f"  => {floor_review.decision}: {floor_reason}.")

    draw_floor = summarize_draw_floor_interaction(
        build_draw_floor_metric_rows(games),
        minimum_for_review=REVIEW_GATE_N,
    )
    print(f"\nDRAW_BOOST x FLOOR 2x2 (gate "
          f"{draw_floor.fixture_rows}/{draw_floor.minimum_for_review}):")
    print(f"  {'floor':>6}{'draw':>7}{'RPS':>9}{'scoreLL':>10}{'advBrier':>11}")
    for cell in draw_floor.cells:
        print(f"  {cell.floor:>6.2f}{cell.draw_boost:>7.2f}"
              f"{cell.rps:>9.4f}{cell.score_log_loss:>10.4f}"
              f"{cell.adv_brier:>11.4f}")
    print(f"  factorial interaction: RPS {draw_floor.rps_interaction:+.5f} | "
          f"scoreLL {draw_floor.score_log_loss_interaction:+.5f} | "
          f"advBrier {draw_floor.adv_brier_interaction:+.5f} "
          f"=> {draw_floor.decision}")

    ks = [0.60, 0.70, 0.85, 1.00]
    print(f"\nk-sensitivity (advancement; n={n} — MONITORING ONLY, the graded "
          f"default above is locked):")
    print(f"  {'k':>5}{'Brier':>9}{'logLoss':>9}{'expUps':>9}   (actual ups {act_ups})")
    briers = {}
    for k in ks:
        b, log_loss, e = adv_metrics(records, k)
        briers[k] = b
        print(f"  {k:>5.2f}{b:>9.4f}{log_loss:>9.4f}{e:>9.2f}")
    best_k = min(briers, key=briers.get)
    e70 = adv_metrics(records, 0.70)[2]

    print("\nVERDICT:")
    tone = "MORE" if act_ups > e70 else ("LESS" if act_ups < e70 else "as")
    print(f"  reality was {tone} upset-heavy than the regressed model "
          f"(actual {act_ups} vs {e70:.2f} expected at k=0.70).")
    print(f"  best-Brier k among {ks} = {best_k}  (n={n}, high variance).")
    print("  => MONITORING ONLY: graded-k, lambda floor, draw boost, and w=0.6 "
          "remain frozen through the tournament; review output cannot refit "
          "production parameters.")

    style, shootout, home, ensemble = structured_governance_summaries()
    print("\nSTRUCTURED GOVERNANCE LEDGERS:")
    print(f"  style cohort: observations {style.observation_rows}, distinct fixtures "
          f"{style.distinct_fixtures}, eligible {style.eligible_fixtures}, "
          f"pending triggers {style.pending_trigger_fixtures} => {style.decision}")
    print(f"  real shootouts: Elo tilt {shootout.elo_tilt_hits}/"
          f"{shootout.real_shootout_rows} "
          f"(review at n>={shootout.minimum_for_review}) => {shootout.decision}")
    print(f"  home/altitude: home-only {home.home_only_rows}, "
          f"separated {home.separated_rows}, "
          f"legacy-combined {home.legacy_combined_rows}, altitude-identified "
          f"{home.altitude_identified_rows} => home {home.home_decision} / "
          f"altitude {home.altitude_decision} | {home.archive_status}")
    print(f"  ensemble basis: live_current_elo {ensemble.live_rows}/"
          f"{ensemble.total_rows} (refit at n>={ensemble.minimum_for_refit}) "
          f"=> {ensemble.decision} | {ensemble.basis_counts}")
    if ensemble.best_weight is None:
        print(f"    current w={ensemble.current_weight:.1f} Brier "
              f"{ensemble.current_brier:.4f}; grid not run before eligible n=12")
    else:
        print(f"    current w={ensemble.current_weight:.1f} Brier "
              f"{ensemble.current_brier:.4f} vs best w={ensemble.best_weight:.1f} "
              f"Brier {ensemble.best_brier:.4f}")
        print("    diagnostic model-weight grid (review only; production remains frozen):")
        for line in _ensemble_grid_lines(ensemble):
            print(line)
    print("\nEducational/analytical use only; not betting advice.")


if __name__ == "__main__":
    main()
