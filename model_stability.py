"""Profile registry and stability helpers for the World Cup odds model."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from random import Random
import math
from typing import Sequence

import match_model_v35 as mm

from competition_state import match_adjustments
from match_context import de_margin_odds, market_gap
from worldcup_2026_data import ELO, HOME, split_matches

HEAT_SCALE = {"none": 1.0, "mild": 0.95, "moderate": 0.90, "severe": 0.85}
MOT_SCALE = {"normal": 1.0, "through": 0.88, "eliminated": 0.90, "mustwin": 1.06}


@dataclass(frozen=True)
class ModelProfile:
    name: str
    avg_goals: float
    gd_per_100: float
    draw_boost: float
    draw_gate: float = 0.42
    open_delo: float = 300.0
    dispersion: float = 5.0
    notes: str = ""


@dataclass(frozen=True)
class Prediction:
    profile: str
    home: str
    away: str
    home_prob: float
    draw_prob: float
    away_prob: float
    over_prob: float
    btts_prob: float
    pick: str
    style: str
    style_note: str
    lambda_home: float
    lambda_away: float
    matrix: dict
    top_scorelines: tuple
    total_goals: dict
    win_margin: dict
    market_odds: tuple[float, float, float] | None = None
    market_method: str = "proportional"
    market_prob: tuple[float, float, float] | None = None
    market_gap: tuple[float, float, float] | None = None
    market_margin: float | None = None
    lineup_home: float = 1.0
    lineup_away: float = 1.0
    weather_scale: float = 1.0


STABLE_V35 = ModelProfile(
    name="stable_v35",
    avg_goals=2.85,
    gd_per_100=0.60,
    draw_boost=0.08,
    notes="Frozen core: 48-game stable profile.",
)

CANDIDATE_V36 = ModelProfile(
    name="candidate_v36",
    avg_goals=2.90,
    gd_per_100=0.65,
    draw_boost=0.06,
    notes="Experimental candidate from the 54-game run.",
)

LEGACY_V34 = ModelProfile(
    name="legacy_v34",
    avg_goals=2.85,
    gd_per_100=0.55,
    draw_boost=0.07,
    notes="Older 44-game profile kept for comparison.",
)

PROFILE_REGISTRY = {p.name: p for p in (STABLE_V35, CANDIDATE_V36, LEGACY_V34)}
PROFILE_ALIASES = {
    "stable": STABLE_V35.name,
    "core": STABLE_V35.name,
    "v35": STABLE_V35.name,
    "production": STABLE_V35.name,
    "candidate": CANDIDATE_V36.name,
    "experimental": CANDIDATE_V36.name,
    "v36": CANDIDATE_V36.name,
    "legacy": LEGACY_V34.name,
    "v34": LEGACY_V34.name,
}


def resolve_profile(name: str) -> ModelProfile:
    key = PROFILE_ALIASES.get(name.lower(), name.lower())
    if key not in PROFILE_REGISTRY:
        raise KeyError(f"unknown profile '{name}'")
    return PROFILE_REGISTRY[key]


def _tail_style(elo_gap: float, open_delo: float) -> tuple[str, str]:
    if abs(elo_gap) >= open_delo:
        return "open", f"auto-open (|ΔElo|={abs(elo_gap):.0f} ≥ {open_delo:.0f})"
    return "balanced", f"auto-balanced (|ΔElo|={abs(elo_gap):.0f} < {open_delo:.0f})"


def _res_code(hg: int, ag: int) -> int:
    return 0 if hg > ag else (1 if hg == ag else 2)


def _rps(probs: tuple[float, float, float], result: int) -> float:
    actual = [1 if result == k else 0 for k in range(3)]
    cp = co = score = 0.0
    for k in range(2):
        cp += probs[k]
        co += actual[k]
        score += (cp - co) ** 2
    return score / 2


def predict_match(
    profile: ModelProfile,
    home: str,
    away: str,
    host_home: int = 0,
    heat: str = "none",
    weather_scale: float = 1.0,
    mot_home: str = "normal",
    mot_away: str = "normal",
    lineup_home: float = 1.0,
    lineup_away: float = 1.0,
    market_odds: tuple[float, float, float] | None = None,
    market_method: str = "proportional",
    competition_state=None,
) -> Prediction:
    eh = ELO[home] + (HOME if host_home else 0)
    ea = ELO[away]
    lh, la = mm.elo_to_lambdas(eh, ea, avg_goals=profile.avg_goals, gd_per_100=profile.gd_per_100)
    state_lineup_home = 1.0
    state_lineup_away = 1.0
    if competition_state is not None:
        state_adj = match_adjustments(competition_state)
        mot_home = state_adj["mot_home"]
        mot_away = state_adj["mot_away"]
        state_lineup_home = state_adj["lineup_home"]
        state_lineup_away = state_adj["lineup_away"]
    scale = HEAT_SCALE.get(heat, 1.0) * weather_scale * MOT_SCALE[mot_home] * MOT_SCALE[mot_away]
    final_lineup_home = state_lineup_home * lineup_home
    final_lineup_away = state_lineup_away * lineup_away
    lh *= scale * final_lineup_home
    la *= scale * final_lineup_away
    style, style_note = _tail_style(eh - ea, profile.open_delo)
    matrix = mm.score_matrix(
        lh,
        la,
        opp_style=style,
        draw_boost=profile.draw_boost,
        disp=profile.dispersion,
    )
    home_prob, draw_prob, away_prob, over_prob, btts_prob = mm.summarise(matrix)
    pick = "X" if (draw_prob >= 0.26 and max(home_prob, away_prob) < profile.draw_gate) else (
        "1" if home_prob > away_prob else "2"
    )
    top_scorelines = tuple(sorted(matrix.items(), key=lambda x: -x[1])[:8])
    total_goals = {}
    win_margin = {}
    for (i, j), p in matrix.items():
        total_goals[i + j] = total_goals.get(i + j, 0.0) + p
        win_margin[abs(i - j)] = win_margin.get(abs(i - j), 0.0) + p
    market_prob = market_margin = market_gap_probs = None
    if market_odds is not None:
        market_prob, market_margin = de_margin_odds(market_odds, method=market_method)
        market_gap_probs = market_gap((home_prob, draw_prob, away_prob), market_prob)
    return Prediction(
        profile=profile.name,
        home=home,
        away=away,
        home_prob=home_prob,
        draw_prob=draw_prob,
        away_prob=away_prob,
        over_prob=over_prob,
        btts_prob=btts_prob,
        pick=pick,
        style=style,
        style_note=style_note,
        lambda_home=lh,
        lambda_away=la,
        matrix=matrix,
        top_scorelines=top_scorelines,
        total_goals=total_goals,
        win_margin=win_margin,
        market_odds=market_odds,
        market_method=market_method,
        market_prob=market_prob,
        market_gap=market_gap_probs,
        market_margin=market_margin,
        lineup_home=final_lineup_home,
        lineup_away=final_lineup_away,
        weather_scale=weather_scale,
    )


def classify_miss(pred: Prediction, actual: tuple[int, int], batch: int) -> str:
    hg, ag = actual
    result = _res_code(hg, ag)
    predicted = 1 if pred.pick == "X" else (0 if pred.home_prob > pred.away_prob else 2)
    favorite = max(pred.home_prob, pred.draw_prob, pred.away_prob)
    goal_diff = abs(hg - ag)
    if goal_diff >= 3:
        return "tail_variance"
    if predicted == result:
        return "covered"
    if batch == 3 and favorite >= 0.55:
        return "rotation_or_motivation"
    if result == 1 and favorite >= 0.60:
        return "favored_draw_information_gap"
    if favorite >= 0.60:
        return "favored_upset_information_gap"
    return "routine_noise"


def evaluate_profile(profile: ModelProfile, matches: Sequence[tuple]) -> dict:
    n = len(matches)
    wdl_argmax = tipset = 0
    rps_sum = log_likelihood = 0.0
    draw_model = draw_actual = 0.0
    blowout_expected = 0.0
    blowout_actual = 0
    ou_brier = 0.0
    ou_actual = 0
    misses = []

    for home, away, hg, ag, host_home, batch in matches:
        pred = predict_match(profile, home, away, host_home)
        result = _res_code(hg, ag)
        argmax = 0 if pred.home_prob > pred.away_prob else 2
        tipset_pick = 1 if pred.pick == "X" else argmax
        wdl_argmax += argmax == result
        tipset += tipset_pick == result
        rps_sum += _rps((pred.home_prob, pred.draw_prob, pred.away_prob), result)
        log_likelihood += math.log(max(pred.matrix[(hg, ag)], 1e-12))
        draw_model += pred.draw_prob
        draw_actual += 1 if result == 1 else 0
        blowout_expected += sum(p for (i, j), p in pred.matrix.items() if abs(i - j) >= 3)
        blowout_actual += 1 if abs(hg - ag) >= 3 else 0
        actual_over = 1 if (hg + ag) >= 3 else 0
        ou_actual += actual_over
        ou_brier += (pred.over_prob - actual_over) ** 2
        if argmax != result:
            misses.append(
                {
                    "home": home,
                    "away": away,
                    "score": f"{hg}-{ag}",
                    "batch": batch,
                    "label": classify_miss(pred, (hg, ag), batch),
                    "home_prob": pred.home_prob,
                    "draw_prob": pred.draw_prob,
                    "away_prob": pred.away_prob,
                }
            )

    return {
        "profile": profile,
        "n": n,
        "wdl_argmax": wdl_argmax,
        "tipset": tipset,
        "rps": rps_sum / n,
        "log_likelihood": log_likelihood,
        "draw_model": draw_model / n,
        "draw_actual": draw_actual / n,
        "blowout_expected": blowout_expected,
        "blowout_actual": blowout_actual,
        "ou_brier": ou_brier / n,
        "ou_actual": ou_actual,
        "misses": misses,
    }


def bootstrap_selection_rates(
    profiles: Sequence[ModelProfile],
    matches: Sequence[tuple],
    n_boot: int = 200,
    seed: int = 42,
) -> dict[str, float]:
    if not profiles:
        return {}
    rng = Random(seed)
    wins = {p.name: 0 for p in profiles}
    indices = list(range(len(matches)))
    if not indices:
        return {p.name: 0.0 for p in profiles}

    for _ in range(n_boot):
        sample = [matches[rng.choice(indices)] for _ in indices]
        scored = []
        for profile in profiles:
            metrics = evaluate_profile(profile, sample)
            scored.append((metrics["rps"], -metrics["log_likelihood"], profile.name))
        winner = min(scored)[2]
        wins[winner] += 1
    return {name: count / n_boot for name, count in wins.items()}


def profile_distance(a: ModelProfile, b: ModelProfile) -> float:
    return (
        abs(a.avg_goals - b.avg_goals) / 0.05
        + abs(a.gd_per_100 - b.gd_per_100) / 0.05
        + abs(a.draw_boost - b.draw_boost) / 0.01
    )


def candidate_grid() -> list[ModelProfile]:
    return [
        ModelProfile(
            name=f"grid_gd{gd:.2f}_avg{avg:.2f}_db{db:.2f}",
            avg_goals=avg,
            gd_per_100=gd,
            draw_boost=db,
            notes="Grid-search candidate",
        )
        for gd, avg, db in product([0.55, 0.60, 0.65], [2.85, 2.90], [0.06, 0.07, 0.08])
    ]


def split_report() -> dict[str, dict]:
    split = split_matches()
    return {name: evaluate_profile(STABLE_V35, games) for name, games in split.items()}
