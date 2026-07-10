"""Optional external match context helpers.

This module keeps market odds, lineup adjustments, and other non-core signals
out of the scoring engine. The core model can consume these signals, but it does
not own how they are sourced.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
WEATHER_DECISION_SCALES = {
    "none": 1.0,
    "heat_mild": 0.95,
    "heat_moderate": 0.92,
    "heat_severe": 0.90,
    "rain_watch": 1.0,
    "rain_applied": 0.95,
    "indoor_no_weather": 1.0,
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
    weather_forecast_issued_at_utc: str | None = None
    weather_forecast_valid_at_utc: str | None = None
    weather_source: str | None = None
    weather_evidence_type: str | None = None
    weather_evidence_snapshot: str | None = None
    weather_evidence_sha256: str | None = None
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
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{field} must be finite and positive")
    return value


def _coerce_optional_text(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _coerce_optional_snapshot(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw)
    return text if text.strip() else None


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


def _is_http_url(raw: str | None) -> bool:
    if not raw:
        return False
    parsed = urlparse(raw)
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def weather_context_has_evidence(context: MatchContext) -> bool:
    """Return whether a row asserts any auditable weather input or decision."""

    return any(
        (
            not math.isfinite(context.weather_scale) or abs(context.weather_scale - 1.0) > 1e-9,
            context.weather_decision != "none",
            context.weather_checked_at_utc,
            context.weather_forecast_issued_at_utc,
            context.weather_forecast_valid_at_utc,
            context.weather_source,
            context.weather_evidence_type,
            context.weather_evidence_snapshot,
            context.weather_evidence_sha256,
        )
    )


def validate_weather_context(
    context: MatchContext,
    *,
    require_evidence: bool = False,
    legacy_heat: str | None = None,
    now_utc: datetime | None = None,
) -> list[str]:
    """Validate auditable matchday weather evidence.

    Empty legacy contexts remain loadable unless ``require_evidence`` is set.
    Once any weather override/evidence is asserted, all relevant provenance
    failures are blocking and returned to the caller.
    """

    issues: list[str] = []
    has_evidence = weather_context_has_evidence(context)
    if not has_evidence and not require_evidence:
        return issues

    decision = context.weather_decision or "none"
    expected_scale = WEATHER_DECISION_SCALES.get(decision)
    if expected_scale is None:
        issues.append(
            f"weather_decision must be one of: {', '.join(sorted(WEATHER_DECISION_SCALES))}"
        )
    elif not math.isfinite(context.weather_scale):
        issues.append("weather_scale must be finite")
    elif abs(context.weather_scale - expected_scale) > 1e-9:
        issues.append(
            f"weather_decision={decision} requires weather_scale={expected_scale:.2f}; "
            f"got {context.weather_scale:.2f}"
        )

    if legacy_heat and legacy_heat != "none" and (has_evidence or require_evidence):
        issues.append(
            f"legacy heat={legacy_heat} conflicts with context weather_decision={decision}/"
            f"weather_scale={context.weather_scale:.2f}; use exactly one weather adjustment path"
        )

    required_common = {
        "kickoff_at_utc": context.kickoff_at_utc,
        "weather_checked_at_utc": context.weather_checked_at_utc,
        "weather_source": context.weather_source,
        "weather_evidence_type": context.weather_evidence_type,
        "weather_evidence_snapshot": context.weather_evidence_snapshot,
        "weather_evidence_sha256": context.weather_evidence_sha256,
    }
    for field, value in required_common.items():
        if not value:
            issues.append(f"weather evidence requires {field}")

    if context.weather_source and not _is_http_url(context.weather_source):
        issues.append("weather_source must be an http(s) URL")

    snapshot = context.weather_evidence_snapshot
    digest = context.weather_evidence_sha256
    if digest:
        normalized_digest = digest.strip().lower()
        if len(normalized_digest) != 64 or any(ch not in "0123456789abcdef" for ch in normalized_digest):
            issues.append("weather_evidence_sha256 must be a 64-character hexadecimal SHA-256")
        elif snapshot:
            actual_digest = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
            if normalized_digest != actual_digest:
                issues.append(
                    "weather_evidence_sha256 does not match weather_evidence_snapshot "
                    f"(expected {actual_digest})"
                )

    timestamps: dict[str, datetime | None] = {}
    for field, raw in (
        ("kickoff_at_utc", context.kickoff_at_utc),
        ("weather_checked_at_utc", context.weather_checked_at_utc),
        ("weather_forecast_issued_at_utc", context.weather_forecast_issued_at_utc),
        ("weather_forecast_valid_at_utc", context.weather_forecast_valid_at_utc),
    ):
        try:
            timestamps[field] = _parse_utc_timestamp(raw, field)
        except ValueError as exc:
            issues.append(str(exc))
            timestamps[field] = None

    kickoff = timestamps["kickoff_at_utc"]
    checked = timestamps["weather_checked_at_utc"]
    issued = timestamps["weather_forecast_issued_at_utc"]
    valid = timestamps["weather_forecast_valid_at_utc"]

    if now_utc is not None:
        if now_utc.tzinfo is None or now_utc.utcoffset() is None:
            issues.append("now_utc must include timezone")
        else:
            now = now_utc.astimezone(timezone.utc)
            if kickoff is not None and now >= kickoff:
                issues.append(
                    "current prediction run is at or after kickoff: "
                    f"now={now.isoformat()}, kickoff={kickoff.isoformat()}"
                )
            for field, value in (
                ("weather_checked_at_utc", checked),
                ("weather_forecast_issued_at_utc", issued),
            ):
                if value is not None and value > now:
                    issues.append(
                        f"{field} is later than run time: "
                        f"{value.isoformat()} > {now.isoformat()}"
                    )

    if kickoff is not None and checked is not None:
        evidence_age_hours = (kickoff - checked).total_seconds() / 3600.0
        if evidence_age_hours < 0:
            issues.append(f"weather_checked_at_utc is after kickoff by {-evidence_age_hours:.1f}h")
        else:
            max_age_hours = None
            if decision == "rain_applied":
                max_age_hours = 3.0
            elif decision != "indoor_no_weather":
                max_age_hours = 6.0
            if max_age_hours is not None and evidence_age_hours > max_age_hours:
                issues.append(
                    f"{decision} evidence is stale: checked {evidence_age_hours:.1f}h before "
                    f"kickoff (>{max_age_hours:.0f}h)"
                )

    if decision == "indoor_no_weather":
        if context.weather_evidence_type != "official_roof":
            issues.append("indoor_no_weather requires weather_evidence_type=official_roof")
    else:
        if not context.weather_forecast_issued_at_utc:
            issues.append("outdoor weather evidence requires weather_forecast_issued_at_utc")
        if not context.weather_forecast_valid_at_utc:
            issues.append("outdoor weather evidence requires weather_forecast_valid_at_utc")
        if issued is not None and checked is not None:
            if issued > checked:
                issues.append("weather_forecast_issued_at_utc cannot be after weather_checked_at_utc")
            elif (checked - issued).total_seconds() > 24.0 * 3600.0:
                issue_age_hours = (checked - issued).total_seconds() / 3600.0
                issues.append(
                    f"weather forecast issue is stale: issued {issue_age_hours:.1f}h "
                    "before it was checked (>24h)"
                )
        if kickoff is not None and valid is not None:
            kickoff_hour = kickoff.replace(minute=0, second=0, microsecond=0)
            valid_hour = valid.replace(minute=0, second=0, microsecond=0)
            if valid_hour != kickoff_hour:
                issues.append("weather_forecast_valid_at_utc must cover the kickoff hour")

    if decision.startswith("heat_") and context.weather_evidence_type not in {"point_forecast", "hourly"}:
        issues.append(f"{decision} requires weather_evidence_type=point_forecast or hourly")
    if decision == "none" and context.weather_evidence_type not in {"point_forecast", "hourly"}:
        issues.append("weather_decision=none requires weather_evidence_type=point_forecast or hourly")
    if decision == "rain_applied" and context.weather_evidence_type not in {"hourly", "radar"}:
        issues.append("rain_applied requires weather_evidence_type=hourly or radar")
    if decision == "rain_watch" and context.weather_evidence_type not in {"point_forecast", "hourly", "radar"}:
        issues.append("rain_watch requires weather_evidence_type=point_forecast, hourly, or radar")

    return issues


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
        weather_forecast_issued_at_utc=_coerce_optional_text(payload.get("weather_forecast_issued_at_utc")),
        weather_forecast_valid_at_utc=_coerce_optional_text(payload.get("weather_forecast_valid_at_utc")),
        weather_source=_coerce_optional_text(payload.get("weather_source")),
        weather_evidence_type=_coerce_weather_evidence_type(payload.get("weather_evidence_type")),
        weather_evidence_snapshot=_coerce_optional_snapshot(payload.get("weather_evidence_snapshot")),
        weather_evidence_sha256=_coerce_optional_text(payload.get("weather_evidence_sha256")),
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
