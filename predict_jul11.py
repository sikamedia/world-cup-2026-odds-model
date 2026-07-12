#!/usr/bin/env python3
"""Fail-closed knockout finalization and July 11 artifact-based bracket MC."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import sys
import tempfile
from typing import Any, Sequence

from elo_snapshot import EloSnapshot, EloSnapshotError, OFFICIAL_ELO_SOURCE, load_elo_snapshot
from match_context import (
    MatchContext,
    context_key,
    de_margin_odds,
    de_margin_two_way_odds,
    load_context_file,
    validate_weather_context,
)

try:
    from skill.scripts import match_model as mm
except ModuleNotFoundError:
    scripts_dir = Path(__file__).resolve().parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import match_model as mm


KO = mm.STAGE_PROFILES["knockout"]
MODEL_WEIGHT = 0.6
MARKET_WEIGHT = 1.0 - MODEL_WEIGHT
MARKET_GAP_REVIEW_THRESHOLD = 0.04
ARTIFACT_SCHEMA_VERSION = 2
ARTIFACT_TYPE = "pre_registered_match_prediction"
LEGACY_QF_ARTIFACT_SCHEMA_VERSION = 1
LEGACY_QF_ARTIFACT_TYPE = "pre_registered_qf_prediction"
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class Fixture:
    slug: str
    fixture_id: str
    stage: str
    home: str
    away: str
    kickoff_at_utc: str


FIXTURES = {
    fixture.slug: fixture
    for fixture in (
        Fixture(
            "norway-england",
            "2026-QF99-Norway-England",
            "quarterfinal",
            "Norway",
            "England",
            "2026-07-11T21:00:00Z",
        ),
        Fixture(
            "argentina-switzerland",
            "2026-QF100-Argentina-Switzerland",
            "quarterfinal",
            "Argentina",
            "Switzerland",
            "2026-07-12T01:00:00Z",
        ),
        Fixture(
            "france-spain",
            "2026-SF101-France-Spain",
            "semifinal",
            "France",
            "Spain",
            "2026-07-14T19:00:00Z",
        ),
        Fixture(
            "england-argentina",
            "2026-SF102-England-Argentina",
            "semifinal",
            "England",
            "Argentina",
            "2026-07-15T19:00:00Z",
        ),
    )
}
QF_FIXTURES = tuple(fixture for fixture in FIXTURES.values() if fixture.stage == "quarterfinal")
QF_FIXTURE_SLUGS = frozenset(fixture.slug for fixture in QF_FIXTURES)


class PredictionRunError(ValueError):
    """Raised when an official runner contract is not satisfied."""


class ArtifactError(PredictionRunError):
    """Raised when a pre-registered prediction artifact is invalid."""


def _parse_utc(raw: str, field: str = "timestamp") -> datetime:
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        value = datetime.fromisoformat(text)
    except ValueError as exc:
        raise PredictionRunError(f"{field} must be ISO-8601: {raw!r}") from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise PredictionRunError(f"{field} must include timezone: {raw!r}")
    return value.astimezone(timezone.utc)


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _now_utc(value: datetime | None = None) -> datetime:
    now = value or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise PredictionRunError("now_utc must include a timezone")
    return now.astimezone(timezone.utc)


def _predict(home: str, away: str, ratings: dict[str, float], context: MatchContext | None = None) -> dict[str, Any]:
    eh, ea = ratings[home], ratings[away]
    lambda_home, lambda_away = mm.elo_to_lambdas(
        eh,
        ea,
        avg_goals=KO["avg_goals"],
        gd_per_100=KO["gd_per_100"],
        floor=KO["lambda_floor"],
    )
    weather_scale = context.weather_scale if context is not None else 1.0
    lineup_home = context.lineup_home if context is not None else 1.0
    lineup_away = context.lineup_away if context is not None else 1.0
    lambda_home *= weather_scale * lineup_home
    lambda_away *= weather_scale * lineup_away
    style = "open" if abs(eh - ea) >= 266 else "balanced"
    matrix = mm.score_matrix(
        lambda_home,
        lambda_away,
        opp_style=style,
        draw_boost=KO["draw_boost"],
    )
    home_prob, draw_prob, away_prob, over_prob, btts_prob = mm.summarise(matrix)
    elo_expectation = 1.0 / (1.0 + 10 ** (-(eh - ea) / 400.0))
    k_eff = mm.graded_ko_regress(
        eh - ea,
        KO["ko_regress"],
        KO["ko_regress_max"],
        KO["ko_elo_scale"],
    )
    advancement = mm.advancement(matrix, elo_expectation, k_eff, KO["pen_tilt"])
    draw_resolution_home = 0.5 + KO["pen_tilt"] * (elo_expectation - 0.5)
    return {
        "home": home,
        "away": away,
        "lambda_home": lambda_home,
        "lambda_away": lambda_away,
        "home_prob": home_prob,
        "draw_prob": draw_prob,
        "away_prob": away_prob,
        "over_prob": over_prob,
        "btts_prob": btts_prob,
        "advance_home": advancement["adv_reg"],
        "draw_resolution_home": draw_resolution_home,
        "k_eff": k_eff,
        "style": style,
        "matrix": matrix,
        "weather_scale": weather_scale,
        "lineup_home": lineup_home,
        "lineup_away": lineup_away,
    }


def _official_prediction(model: dict[str, Any], context: MatchContext) -> dict[str, Any]:
    if context.market_odds is None:
        raise PredictionRunError(
            "official w=0.6 ensemble requires three-way market_odds in match context"
        )
    try:
        market_wdl, margin = de_margin_odds(context.market_odds, context.market_method)
        if context.market_advance_odds is not None:
            market_advance, advance_margin = de_margin_two_way_odds(
                context.market_advance_odds,
                context.market_method,
            )
            market_advance_home = market_advance[0]
            advance_method = "direct_two_way"
        else:
            market_advance_home = (
                market_wdl[0] + market_wdl[1] * model["draw_resolution_home"]
            )
            advance_margin = None
            advance_method = "derived_from_90"
    except ValueError as exc:
        raise PredictionRunError(f"official market validation failed: {exc}") from exc
    model_wdl = (model["home_prob"], model["draw_prob"], model["away_prob"])
    official_wdl = tuple(
        MODEL_WEIGHT * model_prob + MARKET_WEIGHT * market_prob
        for model_prob, market_prob in zip(model_wdl, market_wdl)
    )
    official_advance_home = (
        MODEL_WEIGHT * model["advance_home"] + MARKET_WEIGHT * market_advance_home
    )
    market_gap_wdl = tuple(
        model_prob - market_prob
        for model_prob, market_prob in zip(model_wdl, market_wdl)
    )
    market_gap_advance_home = model["advance_home"] - market_advance_home
    max_market_gap = max(
        max(abs(value) for value in market_gap_wdl),
        abs(market_gap_advance_home),
    )
    market_gap_review_required = max_market_gap >= MARKET_GAP_REVIEW_THRESHOLD
    return {
        **model,
        "market_wdl": market_wdl,
        "market_margin": margin,
        "market_advance_home": market_advance_home,
        "market_advance_margin": advance_margin,
        "market_advance_method": advance_method,
        "market_gap_wdl": market_gap_wdl,
        "market_gap_advance_home": market_gap_advance_home,
        "market_gap_review_required": market_gap_review_required,
        "official_wdl": official_wdl,
        "official_advance_home": official_advance_home,
    }


def _canonical_payload_bytes(payload: dict[str, Any]) -> bytes:
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ArtifactError(f"artifact payload is not canonical JSON: {exc}") from exc
    return encoded.encode("ascii")


def _payload_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_payload_bytes(payload)).hexdigest()


def _seal_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    return {"payload": payload, "payload_sha256": _payload_sha256(payload)}


def _weather_payload(context: MatchContext) -> dict[str, Any]:
    return {
        "decision": context.weather_decision,
        "scale": context.weather_scale,
        "checked_at_utc": context.weather_checked_at_utc,
        "forecast_issued_at_utc": context.weather_forecast_issued_at_utc,
        "forecast_valid_at_utc": context.weather_forecast_valid_at_utc,
        "source": context.weather_source,
        "evidence_type": context.weather_evidence_type,
        "roof_status": context.roof_status,
        "evidence_fixture_id": context.weather_evidence_fixture_id,
        "evidence_snapshot": context.weather_evidence_snapshot,
        "evidence_sha256": context.weather_evidence_sha256,
    }


def _build_artifact(
    fixture: Fixture,
    prediction: dict[str, Any],
    context: MatchContext,
    snapshot: EloSnapshot,
    source_tsv: Path,
    generated_at: datetime,
) -> dict[str, Any]:
    top_scores = sorted(prediction["matrix"].items(), key=lambda item: -item[1])[:5]
    payload = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_type": ARTIFACT_TYPE,
        "fixture": {
            "slug": fixture.slug,
            "fixture_id": fixture.fixture_id,
            "stage": fixture.stage,
            "home": fixture.home,
            "away": fixture.away,
            "kickoff_at_utc": fixture.kickoff_at_utc,
        },
        "generated_at_utc": _utc_text(generated_at),
        "live_match_state_incorporated": False,
        "model": {
            "profile": "knockout",
            "lambda_home": prediction["lambda_home"],
            "lambda_away": prediction["lambda_away"],
            "wdl_90": {
                "home": prediction["home_prob"],
                "draw": prediction["draw_prob"],
                "away": prediction["away_prob"],
            },
            "advance_home": prediction["advance_home"],
            "over_2_5": prediction["over_prob"],
            "btts": prediction["btts_prob"],
            "graded_k": prediction["k_eff"],
            "style": prediction["style"],
            "top_scores": [
                {"home_goals": score[0], "away_goals": score[1], "probability": probability}
                for score, probability in top_scores
            ],
        },
        "market": {
            "odds_90": list(context.market_odds or ()),
            "odds_advance": list(context.market_advance_odds or ()),
            "demargin_method": context.market_method,
            "margin": prediction["market_margin"],
            "wdl_90": {
                "home": prediction["market_wdl"][0],
                "draw": prediction["market_wdl"][1],
                "away": prediction["market_wdl"][2],
            },
            "advance_home": prediction["market_advance_home"],
            "advance_margin": prediction["market_advance_margin"],
            "advance_method": prediction["market_advance_method"],
            "draw_resolution_home": (
                prediction["draw_resolution_home"]
                if prediction["market_advance_method"] == "derived_from_90"
                else None
            ),
            "model_gap_90": {
                "home": prediction["market_gap_wdl"][0],
                "draw": prediction["market_gap_wdl"][1],
                "away": prediction["market_gap_wdl"][2],
            },
            "model_gap_advance_home": prediction["market_gap_advance_home"],
            "review_threshold": MARKET_GAP_REVIEW_THRESHOLD,
            "review_required": prediction["market_gap_review_required"],
            "source_key": context.source_key,
        },
        "official": {
            "model_weight": MODEL_WEIGHT,
            "market_weight": MARKET_WEIGHT,
            "wdl_90": {
                "home": prediction["official_wdl"][0],
                "draw": prediction["official_wdl"][1],
                "away": prediction["official_wdl"][2],
            },
            "advance_home": prediction["official_advance_home"],
        },
        "context": {
            "lineup_home": context.lineup_home,
            "lineup_away": context.lineup_away,
            "weather": _weather_payload(context),
            "notes": context.notes,
        },
        "elo_provenance": {
            "source": snapshot.source,
            "source_sha256": snapshot.source_sha256,
            "fetched_at_utc": _utc_text(snapshot.fetched_at_utc),
            "retained_tsv_name": source_tsv.name,
            "ratings": {
                fixture.home: snapshot.ratings[fixture.home],
                fixture.away: snapshot.ratings[fixture.away],
            },
            "estimates": sorted(snapshot.estimates),
        },
    }
    return _seal_artifact(payload)


def _write_immutable_artifact(path: str | Path, artifact: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ArtifactError(f"artifact output already exists and will not be overwritten: {output}")
    encoded = (json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o444)
        try:
            os.link(temp_path, output)
        except FileExistsError as exc:
            raise ArtifactError(
                f"artifact output already exists and will not be overwritten: {output}"
            ) from exc
        try:
            directory_fd = os.open(output.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
    return output


def _load_snapshot(
    *,
    elo_module: str,
    elo_source_tsv: str,
    required_teams: Sequence[str],
    max_age_hours: float,
    now: datetime,
) -> tuple[EloSnapshot, Path]:
    source_tsv = Path(elo_source_tsv)
    if not source_tsv.is_file():
        raise PredictionRunError(f"retained World.tsv does not exist: {source_tsv}")
    try:
        snapshot = load_elo_snapshot(
            elo_module,
            required_teams=required_teams,
            max_age_hours=max_age_hours,
            now_utc=now,
            source_tsv=source_tsv,
        )
    except EloSnapshotError as exc:
        raise PredictionRunError(f"official Elo validation failed: {exc}") from exc
    return snapshot, source_tsv


def _validate_finalize_context(
    fixture: Fixture,
    context: MatchContext,
    now: datetime,
) -> None:
    issues = validate_weather_context(
        context,
        require_evidence=True,
        now_utc=now,
        expected_fixture_id=fixture.fixture_id,
    )
    try:
        actual_kickoff = _parse_utc(context.kickoff_at_utc or "", "kickoff_at_utc")
        expected_kickoff = _parse_utc(fixture.kickoff_at_utc, "fixture kickoff")
        if actual_kickoff != expected_kickoff:
            issues.append(
                f"kickoff_at_utc must be {fixture.kickoff_at_utc}; got {context.kickoff_at_utc!r}"
            )
        if now >= expected_kickoff:
            issues.append(
                f"finalization is closed at kickoff ({fixture.kickoff_at_utc}); now={_utc_text(now)}"
            )
    except PredictionRunError as exc:
        issues.append(str(exc))

    if context.market_odds is None:
        issues.append("official w=0.6 ensemble requires market_odds")
    if issues:
        raise PredictionRunError(
            f"official context validation failed for {fixture.home}|{fixture.away}:\n  "
            + "\n  ".join(issues)
        )


def _finalize(
    fixture: Fixture,
    *,
    elo_module: str,
    elo_source_tsv: str,
    context_file: str,
    artifact_out: str,
    max_elo_age_hours: float,
    now: datetime,
) -> tuple[dict[str, Any], Path]:
    snapshot, source_tsv = _load_snapshot(
        elo_module=elo_module,
        elo_source_tsv=elo_source_tsv,
        required_teams=[fixture.home, fixture.away],
        max_age_hours=max_elo_age_hours,
        now=now,
    )
    try:
        contexts = load_context_file(context_file)
    except Exception as exc:
        raise PredictionRunError(f"cannot load context: {exc}") from exc
    key = context_key(fixture.home, fixture.away)
    context = contexts.get(key)
    if context is None:
        raise PredictionRunError(f"official context validation failed: {key}: missing match context")
    _validate_finalize_context(fixture, context, now)
    prediction = _official_prediction(
        _predict(fixture.home, fixture.away, snapshot.ratings, context),
        context,
    )
    artifact = _build_artifact(fixture, prediction, context, snapshot, source_tsv, now)
    output = _write_immutable_artifact(artifact_out, artifact)
    return artifact, output


def _show_finalized(artifact: dict[str, Any], output: Path) -> None:
    payload = artifact["payload"]
    fixture = payload["fixture"]
    model = payload["model"]
    market = payload["market"]
    official = payload["official"]
    weather = payload["context"]["weather"]
    print("OFFICIAL PRE-KICKOFF FINALIZATION")
    print(f"{fixture['home']} vs {fixture['away']} | kickoff {fixture['kickoff_at_utc']}")
    print(f"  lambda {model['lambda_home']:.3f}/{model['lambda_away']:.3f}")
    print(
        f"  model 90' {model['wdl_90']['home'] * 100:.1f}% / "
        f"{model['wdl_90']['draw'] * 100:.1f}% / {model['wdl_90']['away'] * 100:.1f}%"
    )
    print(
        f"  market 90' {market['wdl_90']['home'] * 100:.1f}% / "
        f"{market['wdl_90']['draw'] * 100:.1f}% / {market['wdl_90']['away'] * 100:.1f}%"
    )
    print(
        f"  OFFICIAL w=0.6 model/0.4 market 90' "
        f"{official['wdl_90']['home'] * 100:.1f}% / "
        f"{official['wdl_90']['draw'] * 100:.1f}% / {official['wdl_90']['away'] * 100:.1f}%"
    )
    print(
        f"  OFFICIAL advance {fixture['home']} {official['advance_home'] * 100:.1f}% / "
        f"{fixture['away']} {(1.0 - official['advance_home']) * 100:.1f}%"
    )
    if market["review_required"]:
        max_gap = max(
            abs(market["model_gap_90"][side]) for side in ("home", "draw", "away")
        )
        max_gap = max(max_gap, abs(market["model_gap_advance_home"]))
        print(
            f"  REVIEW FLAG model-market gap {max_gap * 100:.1f}pt >= "
            f"{market['review_threshold'] * 100:.1f}pt; investigate missing information"
        )
    print(
        f"  weather {weather['decision']} x{weather['scale']:.2f}; "
        f"checked {weather['checked_at_utc']}; sha256={weather['evidence_sha256']}"
    )
    print(
        f"Artifact: {output} | payload_sha256={artifact['payload_sha256']} "
        "| create-only/read-only"
    )
    print("Educational/analytical use only; not betting advice. / 教育/分析用途，不构成投注建议。")


def _number_probability(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArtifactError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ArtifactError(f"{field} must be finite and in [0, 1]")
    return result


def _load_artifact(path: str | Path, *, now: datetime) -> tuple[Fixture, float, str]:
    artifact_path = Path(path)
    try:
        artifact = json.loads(artifact_path.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"cannot read artifact {artifact_path}: {exc}") from exc
    if not isinstance(artifact, dict) or set(artifact) != {"payload", "payload_sha256"}:
        raise ArtifactError(f"artifact {artifact_path} must contain only payload and payload_sha256")
    payload = artifact["payload"]
    digest = artifact["payload_sha256"]
    if not isinstance(payload, dict) or not isinstance(digest, str):
        raise ArtifactError(f"artifact {artifact_path} has invalid envelope types")
    actual_digest = _payload_sha256(payload)
    if digest != actual_digest:
        raise ArtifactError(
            f"artifact hash mismatch for {artifact_path}: stored={digest}, actual={actual_digest}"
        )
    schema_identity = (payload.get("schema_version"), payload.get("artifact_type"))
    is_current = schema_identity == (ARTIFACT_SCHEMA_VERSION, ARTIFACT_TYPE)
    is_legacy_qf = schema_identity == (
        LEGACY_QF_ARTIFACT_SCHEMA_VERSION,
        LEGACY_QF_ARTIFACT_TYPE,
    )
    if not is_current and not is_legacy_qf:
        raise ArtifactError(f"artifact {artifact_path} has unsupported schema/type")
    fixture_payload = payload.get("fixture")
    if not isinstance(fixture_payload, dict):
        raise ArtifactError(f"artifact {artifact_path} is missing fixture identity")
    slug = fixture_payload.get("slug")
    fixture = FIXTURES.get(slug)
    expected_identity = (
        fixture is not None
        and fixture_payload.get("fixture_id") == fixture.fixture_id
        and fixture_payload.get("home") == fixture.home
        and fixture_payload.get("away") == fixture.away
        and fixture_payload.get("kickoff_at_utc") == fixture.kickoff_at_utc
    )
    if is_current:
        expected_identity = expected_identity and fixture_payload.get("stage") == fixture.stage
    else:
        expected_identity = (
            expected_identity
            and fixture.slug in QF_FIXTURE_SLUGS
            and "stage" not in fixture_payload
        )
    if not expected_identity:
        raise ArtifactError(f"artifact {artifact_path} has an unexpected fixture identity")
    generated = _parse_utc(payload.get("generated_at_utc", ""), "generated_at_utc")
    kickoff = _parse_utc(fixture.kickoff_at_utc, "kickoff_at_utc")
    if generated >= kickoff:
        raise ArtifactError(f"artifact {artifact_path} was generated at/after kickoff")
    if generated > now:
        raise ArtifactError(f"artifact {artifact_path} was generated after the MC run time")
    if payload.get("live_match_state_incorporated") is not False:
        raise ArtifactError(f"artifact {artifact_path} must declare no live match state")
    elo = payload.get("elo_provenance")
    if not isinstance(elo, dict) or elo.get("source") != OFFICIAL_ELO_SOURCE:
        raise ArtifactError(f"artifact {artifact_path} has invalid Elo source provenance")
    if not isinstance(elo.get("source_sha256"), str) or _SHA256_RE.fullmatch(elo["source_sha256"]) is None:
        raise ArtifactError(f"artifact {artifact_path} has invalid Elo SHA-256 provenance")
    official = payload.get("official")
    if not isinstance(official, dict):
        raise ArtifactError(f"artifact {artifact_path} is missing official probabilities")
    if official.get("model_weight") != MODEL_WEIGHT or official.get("market_weight") != MARKET_WEIGHT:
        raise ArtifactError(f"artifact {artifact_path} does not use frozen w=0.6 ensemble")
    advance_home = _number_probability(official.get("advance_home"), "official.advance_home")
    wdl = official.get("wdl_90")
    if not isinstance(wdl, dict):
        raise ArtifactError(f"artifact {artifact_path} is missing official.wdl_90")
    wdl_values = [_number_probability(wdl.get(side), f"official.wdl_90.{side}") for side in ("home", "draw", "away")]
    if abs(sum(wdl_values) - 1.0) > 1e-9:
        raise ArtifactError(f"artifact {artifact_path} official WDL does not sum to one")
    return fixture, advance_home, digest


def _simulate(
    ratings: dict[str, float],
    qf_probabilities: dict[tuple[str, str], float | dict[str, float]],
    qf98_winner: str,
    *,
    sims: int,
    seed: int,
) -> dict[str, dict[str, int]]:
    teams = ["France", qf98_winner, "Norway", "England", "Argentina", "Switzerland"]
    tally = {team: {"SF": 0, "Final": 0, "Champion": 0} for team in teams}
    tally["France"]["SF"] = sims
    tally[qf98_winner]["SF"] = sims
    rng = random.Random(seed)
    future_cache: dict[tuple[str, str], float] = {}

    def p_advance(home: str, away: str) -> float:
        key = (home, away)
        if key in qf_probabilities:
            value = qf_probabilities[key]
            return float(value["advance_home"] if isinstance(value, dict) else value)
        reverse = (away, home)
        if reverse in qf_probabilities:
            value = qf_probabilities[reverse]
            probability = float(value["advance_home"] if isinstance(value, dict) else value)
            return 1.0 - probability
        if key not in future_cache:
            future_cache[key] = _predict(home, away, ratings)["advance_home"]
        return future_cache[key]

    for _ in range(sims):
        lower_qf_winners = []
        for fixture in QF_FIXTURES:
            winner = fixture.home if rng.random() < p_advance(fixture.home, fixture.away) else fixture.away
            tally[winner]["SF"] += 1
            lower_qf_winners.append(winner)
        finalist_one = "France" if rng.random() < p_advance("France", qf98_winner) else qf98_winner
        tally[finalist_one]["Final"] += 1
        finalist_two = lower_qf_winners[0] if rng.random() < p_advance(lower_qf_winners[0], lower_qf_winners[1]) else lower_qf_winners[1]
        tally[finalist_two]["Final"] += 1
        champion = finalist_one if rng.random() < p_advance(finalist_one, finalist_two) else finalist_two
        tally[champion]["Champion"] += 1
    return tally


def _run_mc(args: argparse.Namespace, *, now: datetime) -> None:
    artifacts: dict[str, tuple[Fixture, float, str]] = {}
    for path in args.artifacts:
        fixture, advance_home, digest = _load_artifact(path, now=now)
        if fixture.slug in artifacts:
            raise ArtifactError(f"duplicate artifact for {fixture.fixture_id}")
        artifacts[fixture.slug] = (fixture, advance_home, digest)
    if set(artifacts) != QF_FIXTURE_SLUGS:
        missing = sorted(QF_FIXTURE_SLUGS - set(artifacts))
        raise ArtifactError(f"exactly one artifact per July 11 QF is required; missing={missing}")

    required_teams = [
        "France",
        args.qf98_winner,
        "Norway",
        "England",
        "Argentina",
        "Switzerland",
    ]
    snapshot, _source_tsv = _load_snapshot(
        elo_module=args.elo_module,
        elo_source_tsv=args.elo_source_tsv,
        required_teams=required_teams,
        max_age_hours=args.max_elo_age_hours,
        now=now,
    )
    qf_probabilities = {
        (fixture.home, fixture.away): probability
        for fixture, probability, _digest in artifacts.values()
    }
    tally = _simulate(
        snapshot.ratings,
        qf_probabilities,
        args.qf98_winner,
        sims=args.sims,
        seed=args.seed,
    )
    print("PRE-REGISTERED ARTIFACT MC")
    print("Remaining QF probabilities are consumed from finalized artifacts; they are not recalculated or republished.")
    print("Live match state is not incorporated. Fresh validated Elo is used only for future SF/final simulations.")
    for slug in sorted(artifacts):
        fixture, _probability, digest = artifacts[slug]
        print(f"  {fixture.fixture_id}: payload_sha256={digest}")
    print(f"Future-round Elo provenance: {snapshot.provenance_note}")
    print(f"{'Team':14}{'Champion':>10}{'Final':>10}{'SF':>10}")
    for team in sorted(tally, key=lambda item: -tally[item]["Champion"]):
        values = tally[team]
        print(
            f"{team:14}{values['Champion'] / args.sims * 100:>9.1f}%"
            f"{values['Final'] / args.sims * 100:>9.1f}%"
            f"{values['SF'] / args.sims * 100:>9.1f}%"
        )
    print("Educational/analytical use only; not betting advice. / 教育/分析用途，不构成投注建议。")


def _add_elo_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--elo-module", default="elo_current_latest.py")
    parser.add_argument("--elo-source-tsv", required=True)
    parser.add_argument("--max-elo-age-hours", type=float, default=24.0)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    finalize = subparsers.add_parser("finalize", help="Finalize exactly one pre-kickoff fixture")
    finalize.add_argument("--fixture", choices=sorted(FIXTURES), required=True)
    finalize.add_argument("--context-file", required=True)
    finalize.add_argument("--artifact-out", required=True)
    _add_elo_args(finalize)

    mc = subparsers.add_parser("mc", help="Run bracket MC from two finalized QF artifacts")
    mc.add_argument("--artifacts", nargs=2, metavar=("QF99_JSON", "QF100_JSON"), required=True)
    mc.add_argument("--qf98-winner", choices=["Spain", "Belgium"], required=True)
    mc.add_argument("--sims", type=int, default=50_000)
    mc.add_argument("--seed", type=int, default=42)
    _add_elo_args(mc)
    return parser


def main(argv: Sequence[str] | None = None, *, now_utc: datetime | None = None) -> None:
    parser = _parser()
    args = parser.parse_args(argv)
    now = _now_utc(now_utc)
    if args.max_elo_age_hours < 0 or not math.isfinite(args.max_elo_age_hours):
        parser.error("--max-elo-age-hours must be finite and non-negative")
    try:
        if args.command == "finalize":
            artifact, output = _finalize(
                FIXTURES[args.fixture],
                elo_module=args.elo_module,
                elo_source_tsv=args.elo_source_tsv,
                context_file=args.context_file,
                artifact_out=args.artifact_out,
                max_elo_age_hours=args.max_elo_age_hours,
                now=now,
            )
            _show_finalized(artifact, output)
            return
        if args.sims <= 0:
            parser.error("--sims must be positive")
        _run_mc(args, now=now)
    except (PredictionRunError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
