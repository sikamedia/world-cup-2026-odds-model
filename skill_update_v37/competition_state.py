"""Competition-state helpers for rotation and motivation adjustments."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any, Mapping


MOTIVATION_LABELS = {"normal", "through", "eliminated", "mustwin"}
MATH_STATES = {"alive", "qualified", "eliminated"}
STAKE_STATES = {"normal", "advance", "top_spot", "seed_only", "dead_rubber", "mustwin"}
ROTATION_RISK = {"low", "medium", "high"}

# These are deliberately conservative. The existing MOT_SCALE already carries
# the main motivation effect; rotation risk only nudges lineup strength.
ROTATION_SCALE = {"low": 1.0, "medium": 0.97, "high": 0.94}


@dataclass(frozen=True)
class SideCompetitionState:
    points: int | None = None
    mathematical_state: str = "alive"
    stake_state: str = "normal"
    rotation_risk: str = "low"
    notes: str = ""


@dataclass(frozen=True)
class MatchCompetitionState:
    home: SideCompetitionState = field(default_factory=SideCompetitionState)
    away: SideCompetitionState = field(default_factory=SideCompetitionState)


def _normalize_token(raw: Any, allowed: set[str], default: str) -> str:
    text = str(raw if raw is not None else default).strip().lower().replace("-", "_").replace(" ", "_")
    if not text:
        text = default
    if text == "must_win":
        text = "mustwin"
    if text not in allowed:
        raise ValueError(f"unsupported competition-state value: {raw!r}")
    return text


def _coerce_points(raw: Any) -> int | None:
    if raw in {None, ""}:
        return None
    return int(raw)


def _side_from_motivation(
    motivation: str,
    *,
    points: int | None = None,
    rotation_risk: str | None = None,
    notes: str = "",
) -> SideCompetitionState:
    label = _normalize_token(motivation, MOTIVATION_LABELS, "normal")
    if label == "through":
        return SideCompetitionState(
            points=points,
            mathematical_state="qualified",
            stake_state="advance",
            rotation_risk=rotation_risk or "medium",
            notes=notes,
        )
    if label == "eliminated":
        return SideCompetitionState(
            points=points,
            mathematical_state="eliminated",
            stake_state="dead_rubber",
            rotation_risk=rotation_risk or "high",
            notes=notes,
        )
    if label == "mustwin":
        return SideCompetitionState(
            points=points,
            mathematical_state="alive",
            stake_state="mustwin",
            rotation_risk=rotation_risk or "low",
            notes=notes,
        )
    return SideCompetitionState(
        points=points,
        mathematical_state="alive",
        stake_state="normal",
        rotation_risk=rotation_risk or "low",
        notes=notes,
    )


def match_state_from_motivation(
    home_motivation: str = "normal",
    away_motivation: str = "normal",
    *,
    home_points: int | None = None,
    away_points: int | None = None,
    home_notes: str = "",
    away_notes: str = "",
    home_rotation_risk: str | None = None,
    away_rotation_risk: str | None = None,
) -> MatchCompetitionState:
    return MatchCompetitionState(
        home=_side_from_motivation(
            home_motivation,
            points=home_points,
            rotation_risk=home_rotation_risk,
            notes=home_notes,
        ),
        away=_side_from_motivation(
            away_motivation,
            points=away_points,
            rotation_risk=away_rotation_risk,
            notes=away_notes,
        ),
    )


def _coerce_side(raw: Any) -> SideCompetitionState:
    if raw is None:
        return SideCompetitionState()
    if isinstance(raw, SideCompetitionState):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return SideCompetitionState()
        raw = json.loads(text)
    if not isinstance(raw, Mapping):
        raise ValueError("competition state side must be a mapping")

    return SideCompetitionState(
        points=_coerce_points(raw.get("points")),
        mathematical_state=_normalize_token(raw.get("mathematical_state", "alive"), MATH_STATES, "alive"),
        stake_state=_normalize_token(raw.get("stake_state", "normal"), STAKE_STATES, "normal"),
        rotation_risk=_normalize_token(raw.get("rotation_risk", "low"), ROTATION_RISK, "low"),
        notes=str(raw.get("notes", "")).strip(),
    )


def coerce_match_state(raw: Any) -> MatchCompetitionState | None:
    if raw is None:
        return None
    if isinstance(raw, MatchCompetitionState):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        raw = json.loads(text)
    if not isinstance(raw, Mapping):
        raise ValueError("competition_state must be a mapping with home/away keys")

    return MatchCompetitionState(
        home=_coerce_side(raw.get("home")),
        away=_coerce_side(raw.get("away")),
    )


def competition_state_payload(state: MatchCompetitionState | None) -> dict[str, Any] | None:
    coerced = coerce_match_state(state)
    return asdict(coerced) if coerced is not None else None


def motivation_label(side: SideCompetitionState) -> str:
    if side.stake_state == "mustwin":
        return "mustwin"
    if side.mathematical_state == "eliminated" or side.stake_state == "dead_rubber":
        return "eliminated"
    if side.stake_state == "top_spot":
        return "normal"
    if side.mathematical_state == "qualified" or side.stake_state in {"advance", "seed_only"}:
        return "through"
    return "normal"


def lineup_scale(side: SideCompetitionState) -> float:
    return ROTATION_SCALE.get(side.rotation_risk, 1.0)


def match_adjustments(state: MatchCompetitionState | Mapping[str, Any] | str | None) -> dict[str, Any]:
    match_state = coerce_match_state(state)
    if match_state is None:
        return {
            "mot_home": "normal",
            "mot_away": "normal",
            "lineup_home": 1.0,
            "lineup_away": 1.0,
            "home": None,
            "away": None,
        }
    return {
        "mot_home": motivation_label(match_state.home),
        "mot_away": motivation_label(match_state.away),
        "lineup_home": lineup_scale(match_state.home),
        "lineup_away": lineup_scale(match_state.away),
        "home": match_state.home,
        "away": match_state.away,
    }


def match_state_summary(state: MatchCompetitionState | Mapping[str, Any] | str | None) -> str:
    match_state = coerce_match_state(state)
    if match_state is None:
        return "none"
    home = match_state.home
    away = match_state.away
    return (
        f"home={home.mathematical_state}/{home.stake_state}/{home.rotation_risk}"
        f" pts={home.points if home.points is not None else '?'}; "
        f"away={away.mathematical_state}/{away.stake_state}/{away.rotation_risk}"
        f" pts={away.points if away.points is not None else '?'}"
    )
