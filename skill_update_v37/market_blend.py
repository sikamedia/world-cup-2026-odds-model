"""Market/model blend evaluation helpers.

The market layer is deliberately separate from the profile registry. A market
blend can be evaluated and reported without changing core model defaults.
"""

from __future__ import annotations

import math
from typing import Sequence

from match_context import MatchContext, context_key
from model_stability import ModelProfile, predict_match


def normalize_probs(values: Sequence[float]) -> tuple[float, float, float]:
    if len(values) != 3:
        raise ValueError("expected 3 probabilities")
    total = sum(values)
    if total <= 0:
        raise ValueError("probability sum must be positive")
    return tuple(float(v) / total for v in values)


def effective_market_weight(base_weight: float, market_confidence: float = 1.0) -> float:
    if not 0.0 <= base_weight <= 1.0:
        raise ValueError("market_weight must be in [0, 1]")
    if not 0.0 <= market_confidence <= 1.0:
        raise ValueError("market_confidence must be in [0, 1]")
    return base_weight * market_confidence


def blend_probs(
    model_probs: tuple[float, float, float],
    market_probs: tuple[float, float, float],
    market_weight: float,
) -> tuple[float, float, float]:
    if not 0.0 <= market_weight <= 1.0:
        raise ValueError("market_weight must be in [0, 1]")
    return normalize_probs(
        tuple(
            (1.0 - market_weight) * model + market_weight * market
            for model, market in zip(model_probs, market_probs)
        )
    )


def result_code(home_goals: int, away_goals: int) -> int:
    return 0 if home_goals > away_goals else (1 if home_goals == away_goals else 2)


def rps(probs: tuple[float, float, float], result: int) -> float:
    actual = [1 if result == idx else 0 for idx in range(3)]
    cp = co = score = 0.0
    for idx in range(2):
        cp += probs[idx]
        co += actual[idx]
        score += (cp - co) ** 2
    return score / 2.0


def log_loss(probs: tuple[float, float, float], result: int) -> float:
    return -math.log(max(probs[result], 1e-12))


def mean_and_stderr(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        raise ValueError("expected at least one value")
    n = len(values)
    mean = sum(values) / n
    if n == 1:
        return mean, 0.0
    variance = sum((value - mean) ** 2 for value in values) / (n - 1)
    return mean, math.sqrt(variance / n)


def evaluate_market_blend(
    profile: ModelProfile,
    matches: Sequence[tuple],
    contexts: dict[str, MatchContext],
    market_weight: float,
    use_context_adjustments: bool = True,
) -> dict:
    rows = []
    rps_sum = logloss_sum = 0.0
    argmax_hits = 0
    gap_abs = [0.0, 0.0, 0.0]

    for home, away, hg, ag, host_home, batch in matches:
        ctx = contexts.get(context_key(home, away))
        if not ctx or ctx.market_odds is None:
            continue

        effective_weight = effective_market_weight(market_weight, ctx.market_confidence)
        pred = predict_match(
            profile,
            home,
            away,
            host_home=host_home,
            lineup_home=ctx.lineup_home if use_context_adjustments else 1.0,
            lineup_away=ctx.lineup_away if use_context_adjustments else 1.0,
            weather_scale=ctx.weather_scale if use_context_adjustments else 1.0,
            market_odds=ctx.market_odds,
            market_method=ctx.market_method,
            competition_state=ctx.competition_state if use_context_adjustments else None,
        )
        if pred.market_prob is None:
            continue

        model_probs = (pred.home_prob, pred.draw_prob, pred.away_prob)
        blended = blend_probs(model_probs, pred.market_prob, effective_weight)
        result = result_code(hg, ag)
        row_rps = rps(blended, result)
        row_logloss = log_loss(blended, result)
        argmax = max(range(3), key=lambda idx: blended[idx])
        hit = argmax == result

        rps_sum += row_rps
        logloss_sum += row_logloss
        argmax_hits += hit
        if pred.market_gap is not None:
            for idx, gap in enumerate(pred.market_gap):
                gap_abs[idx] += abs(gap)

        rows.append(
            {
                "home": home,
                "away": away,
                "score": f"{hg}-{ag}",
                "batch": batch,
                "result": result,
                "hit": hit,
                "rps": row_rps,
                "log_loss": row_logloss,
                "market_confidence": ctx.market_confidence,
                "effective_market_weight": effective_weight,
                "market_method": ctx.market_method,
                "model_probs": model_probs,
                "market_probs": pred.market_prob,
                "blend_probs": blended,
                "market_gap": pred.market_gap,
                "notes": ctx.notes,
            }
        )

    n = len(rows)
    if not n:
        return {
            "profile": profile,
            "market_weight": market_weight,
            "n": 0,
            "rps": None,
            "log_loss": None,
            "argmax_hits": 0,
            "mean_abs_gap": None,
            "mean_market_confidence": None,
            "mean_effective_weight": None,
            "rows": rows,
        }

    mean_confidence, _ = mean_and_stderr([row["market_confidence"] for row in rows])
    mean_effective_weight, _ = mean_and_stderr([row["effective_market_weight"] for row in rows])

    return {
        "profile": profile,
        "market_weight": market_weight,
        "n": n,
        "rps": rps_sum / n,
        "log_loss": logloss_sum / n,
        "argmax_hits": argmax_hits,
        "mean_abs_gap": tuple(value / n for value in gap_abs),
        "mean_market_confidence": mean_confidence,
        "mean_effective_weight": mean_effective_weight,
        "rows": rows,
    }
