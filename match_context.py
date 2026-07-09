"""Optional external match context helpers.

This module keeps market odds, lineup adjustments, and other non-core signals
out of the scoring engine. The core model can consume these signals, but it does
not own how they are sourced.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from competition_state import MatchCompetitionState, coerce_match_state
from team_aliases import resolve_team_name

DEMARGIN_METHODS = {"proportional", "power"}
WEATHER_EVIDENCE_TYPES = {"point_forecast", "hourly", "radar", "official_roof", "manual"}
WEATHER_DECISIONS = {
    "none",
    "heat_mild",
    "heat_moderate",
    "heat_severe",
    "rain_watch",
    "rain_applied",
    "indoor_no_weather",
}


@dataclass(frozen=True)
class MatchContext:
    market_odds: tuple[float, float, float] | None = None
    market_method: str = "proportional"
    lineup_home: float = 1.0
    lineup_away: float = 1.0
    weather_scale: float = 1.0
    kickoff_at_utc: str | None = None
    weather_checked_at_utc: str | None = None
    weather_source: str | None = None
    weather_evidence_type: str | None = None
    weather_decision: str = "none"
    market_confidence: float = 1.0
    competition_state: MatchCompetitionState | None = None
    source_key: str | None = None
    notes: str = ""


def context_key(home: str, away: str) -> str:
    return f"{resolve_team_name(home)}|{resolve_team_name(away)}"


def de_margin_odds(
    odds: tuple[float, float, float],
    method: str = "proportional",
) -> tuple[tuple[float, float, float], float]:
    if len(odds) != 3:
        raise ValueError("expected 3-way odds tuple (home, draw, away)")
    method = _coerce_market_method(method)
    odds = tuple(float(o) for o in odds)
    if any(o <= 1.0 for o in odds):
        raise ValueError("decimal odds must be greater than 1.0")
    inv = [1.0 / o for o in odds]
    total = sum(inv)
    if total <= 0:
        raise ValueError("odds must be positive")
    margin = total - 1.0
    if method == "proportional":
        return tuple(x / total for x in inv), margin

    lo, hi = 0.01, 10.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if sum(x ** mid for x in inv) > 1.0:
            lo = mid
        else:
            hi = mid
    exponent = (lo + hi) / 2.0
    probs = [x ** exponent for x in inv]
    prob_total = sum(probs)
    return tuple(x / prob_total for x in probs), margin


def market_gap(model_probs: tuple[float, float, float], market_probs: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(m - q for m, q in zip(model_probs, market_probs))


def _parse_key(raw_key: Any) -> tuple[str, str]:
    if isinstance(raw_key, (tuple, list)) and len(raw_key) == 2:
        return resolve_team_name(str(raw_key[0]).strip()), resolve_team_name(str(raw_key[1]).strip())
    text = str(raw_key).strip()
    for sep in ("|", " vs ", " - "):
        if sep in text:
            left, right = text.split(sep, 1)
            return resolve_team_name(left.strip()), resolve_team_name(right.strip())
    raise ValueError(f"cannot parse context key: {raw_key!r}")


def _coerce_odds(raw: Any) -> tuple[float, float, float] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        raw = raw.get("odds") or raw.get("market_odds")
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        raise ValueError("market_odds must be a 3-element list/tuple")
    return (float(raw[0]), float(raw[1]), float(raw[2]))


def _coerce_market_method(raw: Any) -> str:
    method = str(raw or "proportional").strip().lower().replace("-", "_")
    if method in {"prop", "proportional"}:
        return "proportional"
    if method in {"power", "power_method"}:
        return "power"
    allowed = ", ".join(sorted(DEMARGIN_METHODS))
    raise ValueError(f"market_method must be one of: {allowed}")


def _coerce_confidence(raw: Any, default: float = 1.0) -> float:
    if raw is None:
        return default
    value = float(raw)
    if not 0.0 <= value <= 1.0:
        raise ValueError("confidence must be in [0, 1]")
    return value


def _coerce_positive_scale(raw: Any, field: str) -> float:
    value = float(raw)
    if value <= 0.0:
        raise ValueError(f"{field} must be positive")
    return value


def _coerce_optional_text(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _coerce_weather_evidence_type(raw: Any) -> str | None:
    text = _coerce_optional_text(raw)
    if text is None:
        return None
    value = text.lower().replace("-", "_")
    if value not in WEATHER_EVIDENCE_TYPES:
        allowed = ", ".join(sorted(WEATHER_EVIDENCE_TYPES))
        raise ValueError(f"weather_evidence_type must be one of: {allowed}")
    return value


def _coerce_weather_decision(raw: Any) -> str:
    text = _coerce_optional_text(raw)
    if text is None:
        return "none"
    value = text.lower().replace("-", "_")
    if value not in WEATHER_DECISIONS:
        allowed = ", ".join(sorted(WEATHER_DECISIONS))
        raise ValueError(f"weather_decision must be one of: {allowed}")
    return value


def _coerce_context(payload: Any) -> MatchContext:
    if payload is None:
        return MatchContext()
    if isinstance(payload, (list, tuple)):
        return MatchContext(market_odds=_coerce_odds(payload))
    if not isinstance(payload, dict):
        raise ValueError("context payload must be a mapping or 3-way odds list")

    return MatchContext(
        market_odds=_coerce_odds(payload),
        market_method=_coerce_market_method(payload.get("market_method", payload.get("demargin", "proportional"))),
        lineup_home=_coerce_positive_scale(payload.get("lineup_home", 1.0), "lineup_home"),
        lineup_away=_coerce_positive_scale(payload.get("lineup_away", 1.0), "lineup_away"),
        weather_scale=_coerce_positive_scale(payload.get("weather_scale", 1.0), "weather_scale"),
        kickoff_at_utc=_coerce_optional_text(payload.get("kickoff_at_utc")),
        weather_checked_at_utc=_coerce_optional_text(payload.get("weather_checked_at_utc")),
        weather_source=_coerce_optional_text(payload.get("weather_source")),
        weather_evidence_type=_coerce_weather_evidence_type(payload.get("weather_evidence_type")),
        weather_decision=_coerce_weather_decision(payload.get("weather_decision")),
        market_confidence=_coerce_confidence(
            payload.get("market_confidence", payload.get("confidence", 1.0))
        ),
        competition_state=coerce_match_state(payload.get("competition_state")),
        source_key=str(payload.get("source_key", "")).strip() or None,
        notes=str(payload.get("notes", "")),
    )


def load_context_file(path: str | Path) -> dict[str, MatchContext]:
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if isinstance(data, dict) and "matches" in data and isinstance(data["matches"], dict):
        data = data["matches"]
    if not isinstance(data, dict):
        raise ValueError("context file must be a JSON object or {matches: {...}}")

    contexts: dict[str, MatchContext] = {}
    for raw_key, payload in data.items():
        home, away = _parse_key(raw_key)
        contexts[context_key(home, away)] = _coerce_context(payload)
    return contexts


def coerce_context_payload(payload: Any) -> MatchContext:
    return _coerce_context(payload)


def context_payload(context: MatchContext) -> dict[str, Any]:
    return asdict(context)


def load_context_payloads(path: str | Path) -> dict[str, dict[str, Any]]:
    return {key: context_payload(ctx) for key, ctx in load_context_file(path).items()}
