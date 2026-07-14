#!/usr/bin/env python3
"""Load and validate prediction-side Elo snapshots.

Official prediction paths must use a recent, directly sourced World.tsv
snapshot.  This module centralizes that fail-closed contract so match runners
and signal generation apply the same provenance checks.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import importlib.util
import json
import math
from pathlib import Path
import re
from types import ModuleType


OFFICIAL_ELO_SOURCE = "https://www.eloratings.net/World.tsv"
ELO_CAPTURE_RECEIPT_VERSION = 1
ELO_CAPTURE_RECEIPT_TYPE = "elo_http_capture_receipt"
DIRECT_HTTP_CAPTURE_METHOD = "direct_http_response_body"
UNVERIFIED_REPLAY_METHOD = "unverified_replay"
MAX_ELO_BODY_BYTES = 5 * 1024 * 1024
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_RECEIPT_FIELDS = {
    "schema_version",
    "artifact_type",
    "capture_method",
    "requested_url",
    "final_url",
    "http_status",
    "response_completed_at_utc",
    "evidence_file",
    "body_byte_count",
    "body_sha256",
}

# eloratings.net country code -> project team name. Keep parsing here so the
# snapshot generator and verifier cannot silently disagree about team identity.
CODE_TO_TEAM = {
    "ES": "Spain", "AR": "Argentina", "FR": "France", "EN": "England",
    "BR": "Brazil", "PT": "Portugal", "CO": "Colombia", "NL": "Netherlands",
    "MX": "Mexico", "CH": "Switzerland", "NO": "Norway", "BE": "Belgium",
    "DE": "Germany", "JP": "Japan", "MA": "Morocco", "HR": "Croatia",
    "EC": "Ecuador", "TR": "Turkiye", "UY": "Uruguay", "PY": "Paraguay",
    "AT": "Austria", "SN": "Senegal", "AU": "Australia", "US": "USA",
    "EG": "Egypt", "CA": "Canada", "DZ": "Algeria", "GH": "Ghana",
    "CV": "Cabo Verde", "CI": "Cote dIvoire", "KR": "Korea", "SE": "Sweden",
    "CZ": "Czechia", "PA": "Panama", "JO": "Jordan", "UZ": "Uzbekistan",
    "CD": "DR Congo", "IR": "Iran", "IQ": "Iraq", "TN": "Tunisia",
    "HT": "Haiti", "SA": "Saudi Arabia", "NZ": "New Zealand", "QA": "Qatar",
    "BA": "Bosnia",
}


class EloSnapshotError(ValueError):
    """Raised when an Elo snapshot is unsuitable for official predictions."""


@dataclass(frozen=True)
class EloCaptureReceipt:
    """Validated binding between one HTTP response and its retained bytes."""

    capture_method: str
    requested_url: str
    final_url: str
    http_status: int
    response_completed_at_utc: datetime
    evidence_file: str
    body_byte_count: int
    body_sha256: str
    receipt_sha256: str
    receipt_ref: str


@dataclass(frozen=True)
class EloSnapshot:
    """Validated prediction-side Elo data and its provenance."""

    ratings: dict[str, float]
    fetched_at_utc: datetime
    source: str
    source_sha256: str
    estimates: frozenset[str]
    module_ref: str
    capture_receipt: EloCaptureReceipt | None = None

    @property
    def provenance_note(self) -> str:
        note = (
            f"current Elo fetched {self.fetched_at_utc.isoformat()} "
            f"from {self.source} sha256={self.source_sha256}"
        )
        if self.capture_receipt is not None:
            note += (
                f" capture={self.capture_receipt.capture_method}"
                f" receipt_sha256={self.capture_receipt.receipt_sha256}"
            )
        return note


def parse_world_tsv_bytes(raw: bytes, source_label: object = "<World.tsv bytes>") -> dict[str, int]:
    """Parse mapped current ratings from one immutable byte string."""

    if not isinstance(raw, bytes):
        raise EloSnapshotError("World.tsv input must be bytes")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise EloSnapshotError(
            f"cannot parse World.tsv {source_label}: invalid UTF-8"
        ) from exc

    ratings: dict[str, int] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        team = CODE_TO_TEAM.get(parts[2].strip())
        if team is None:
            continue
        raw_rating = parts[3].strip()
        try:
            rating = int(raw_rating)
        except ValueError:
            continue
        previous = ratings.get(team)
        if previous is not None and previous != rating:
            raise EloSnapshotError(
                f"cannot parse World.tsv {source_label}: conflicting {team} ratings "
                f"on line {line_number}"
            )
        ratings[team] = rating

    if len(ratings) < 16:
        raise EloSnapshotError(
            f"cannot parse World.tsv {source_label}: "
            f"only {len(ratings)} recognized current Elo rows"
        )
    return ratings


def parse_world_tsv(path: str | Path) -> dict[str, int]:
    """Read and parse mapped current ratings from an official World.tsv file."""

    source = Path(path)
    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise EloSnapshotError(f"cannot read World.tsv {source}: {exc}") from exc
    return parse_world_tsv_bytes(raw, source)


def _load_module(module_ref: str | Path) -> ModuleType:
    ref = str(module_ref)
    path = Path(ref).expanduser()
    is_path = path.exists() or path.suffix == ".py" or path.parent != Path(".")
    if not is_path:
        try:
            return importlib.import_module(ref)
        except Exception as exc:
            raise EloSnapshotError(f"cannot import Elo module {ref!r}: {exc}") from exc

    if not path.is_file():
        raise EloSnapshotError(f"Elo module does not exist: {path}")
    resolved = path.resolve()
    module_name = f"_elo_snapshot_{abs(hash(resolved))}"
    spec = importlib.util.spec_from_file_location(module_name, resolved)
    if spec is None or spec.loader is None:
        raise EloSnapshotError(f"cannot load Elo module: {resolved}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise EloSnapshotError(f"cannot execute Elo module {resolved}: {exc}") from exc
    return module


def _parse_utc_timestamp(raw: object, field: str) -> datetime:
    if not isinstance(raw, str) or not raw.strip():
        raise EloSnapshotError(f"{field} must be a non-empty ISO-8601 timestamp")
    text = raw.strip().replace("Z", "+00:00")
    try:
        value = datetime.fromisoformat(text)
    except ValueError as exc:
        raise EloSnapshotError(f"invalid {field}: {raw!r}") from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise EloSnapshotError(f"{field} must include a timezone offset")
    return value.astimezone(timezone.utc)


def _parse_fetched_at(raw: object) -> datetime:
    if raw is None:
        raise EloSnapshotError("Elo snapshot must define FETCHED_AT_UTC")
    return _parse_utc_timestamp(raw, "FETCHED_AT_UTC")


def load_elo_capture_receipt(
    receipt_ref: str | Path,
    *,
    source_tsv: str | Path,
    source_bytes: bytes | None = None,
    now_utc: datetime | None = None,
) -> EloCaptureReceipt:
    """Validate a direct HTTP capture receipt against its retained TSV bytes."""

    receipt_path = Path(receipt_ref)
    source_path = Path(source_tsv)
    try:
        receipt_bytes = receipt_path.read_bytes()
    except OSError as exc:
        raise EloSnapshotError(f"cannot read Elo capture receipt {receipt_path}: {exc}") from exc
    try:
        payload = json.loads(receipt_bytes.decode("ascii"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise EloSnapshotError(f"cannot parse Elo capture receipt {receipt_path}: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != _RECEIPT_FIELDS:
        raise EloSnapshotError(
            f"Elo capture receipt must contain exactly {sorted(_RECEIPT_FIELDS)!r}"
        )
    schema_version = payload["schema_version"]
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != ELO_CAPTURE_RECEIPT_VERSION
    ):
        raise EloSnapshotError("unsupported Elo capture receipt schema_version")
    if payload["artifact_type"] != ELO_CAPTURE_RECEIPT_TYPE:
        raise EloSnapshotError("invalid Elo capture receipt artifact_type")
    if payload["capture_method"] != DIRECT_HTTP_CAPTURE_METHOD:
        raise EloSnapshotError(
            f"Elo capture_method must be {DIRECT_HTTP_CAPTURE_METHOD!r}"
        )
    if payload["requested_url"] != OFFICIAL_ELO_SOURCE:
        raise EloSnapshotError(
            f"Elo receipt requested_url must be exactly {OFFICIAL_ELO_SOURCE!r}"
        )
    if payload["final_url"] != OFFICIAL_ELO_SOURCE:
        raise EloSnapshotError(
            f"Elo receipt final_url must be exactly {OFFICIAL_ELO_SOURCE!r}"
        )
    status = payload["http_status"]
    if isinstance(status, bool) or not isinstance(status, int) or status != 200:
        raise EloSnapshotError("Elo capture receipt http_status must be 200")
    completed_at = _parse_utc_timestamp(
        payload["response_completed_at_utc"], "response_completed_at_utc"
    )
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise EloSnapshotError("now_utc must include a timezone offset")
    now = now.astimezone(timezone.utc)
    if completed_at > now:
        raise EloSnapshotError(
            "Elo capture receipt timestamp is in the future: "
            f"{completed_at.isoformat()}"
        )

    evidence_file = payload["evidence_file"]
    if (
        not isinstance(evidence_file, str)
        or not evidence_file
        or Path(evidence_file).name != evidence_file
        or evidence_file != source_path.name
    ):
        raise EloSnapshotError(
            f"Elo receipt evidence_file does not match retained TSV: "
            f"receipt={evidence_file!r}, TSV={source_path.name!r}"
        )
    body_byte_count = payload["body_byte_count"]
    if (
        isinstance(body_byte_count, bool)
        or not isinstance(body_byte_count, int)
        or body_byte_count <= 0
        or body_byte_count > MAX_ELO_BODY_BYTES
    ):
        raise EloSnapshotError(
            f"Elo receipt body_byte_count must be between 1 and {MAX_ELO_BODY_BYTES}"
        )
    body_sha256 = payload["body_sha256"]
    if not isinstance(body_sha256, str) or _SHA256_RE.fullmatch(body_sha256) is None:
        raise EloSnapshotError("Elo receipt body_sha256 must be a lowercase SHA-256 digest")
    if source_bytes is None:
        try:
            source_bytes = source_path.read_bytes()
        except OSError as exc:
            raise EloSnapshotError(f"cannot read World.tsv {source_path}: {exc}") from exc
    elif not isinstance(source_bytes, bytes):
        raise EloSnapshotError("source_bytes must be bytes")
    if len(source_bytes) != body_byte_count:
        raise EloSnapshotError(
            f"World.tsv byte-count mismatch: receipt={body_byte_count}, raw={len(source_bytes)}"
        )
    actual_body_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if actual_body_sha256 != body_sha256:
        raise EloSnapshotError(
            f"World.tsv SHA-256 mismatch: receipt={body_sha256}, raw={actual_body_sha256}"
        )
    return EloCaptureReceipt(
        capture_method=payload["capture_method"],
        requested_url=payload["requested_url"],
        final_url=payload["final_url"],
        http_status=status,
        response_completed_at_utc=completed_at,
        evidence_file=evidence_file,
        body_byte_count=body_byte_count,
        body_sha256=body_sha256,
        receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
        receipt_ref=str(receipt_ref),
    )


def _validate_ratings(raw: object) -> dict[str, float]:
    if not isinstance(raw, Mapping) or not raw:
        raise EloSnapshotError("Elo snapshot must define a non-empty ELO_CURRENT mapping")
    ratings: dict[str, float] = {}
    for team, rating in raw.items():
        if not isinstance(team, str) or not team.strip():
            raise EloSnapshotError("ELO_CURRENT contains an invalid team name")
        if isinstance(rating, bool) or not isinstance(rating, (int, float)):
            raise EloSnapshotError(f"invalid Elo rating for {team}: {rating!r}")
        value = float(rating)
        if not math.isfinite(value):
            raise EloSnapshotError(f"non-finite Elo rating for {team}")
        ratings[team] = value
    return ratings


def _validate_estimates(raw: object) -> frozenset[str]:
    if raw is None:
        raise EloSnapshotError("Elo snapshot must define ESTIMATES (use [] when empty)")
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Iterable):
        raise EloSnapshotError("ESTIMATES must be a sequence of team names")
    items = tuple(raw)
    if any(not isinstance(team, str) or not team.strip() for team in items):
        raise EloSnapshotError("ESTIMATES contains an invalid team name")
    return frozenset(items)


def load_elo_snapshot(
    module_ref: str | Path,
    *,
    required_teams: Iterable[str] = (),
    max_age_hours: float = 24.0,
    now_utc: datetime | None = None,
    expected_source_sha256: str | None = None,
    source_tsv: str | Path | None = None,
    source_receipt: str | Path | None = None,
    require_direct_capture: bool = False,
) -> EloSnapshot:
    """Load an Elo module and enforce the official prediction contract.

    ``expected_source_sha256`` remains available for callers that independently
    calculate a digest. Official workflows pass ``source_tsv`` and
    ``source_receipt`` with ``require_direct_capture=True`` so this function can
    verify the HTTP receipt, raw bytes, generated module, and participant ratings.
    """

    if not math.isfinite(max_age_hours) or max_age_hours < 0:
        raise EloSnapshotError("max_age_hours must be a finite non-negative number")
    if require_direct_capture and source_tsv is None:
        raise EloSnapshotError("direct Elo capture validation requires source_tsv")
    if require_direct_capture and source_receipt is None:
        raise EloSnapshotError("direct Elo capture validation requires source_receipt")
    if source_receipt is not None and source_tsv is None:
        raise EloSnapshotError("source_receipt requires source_tsv")

    module = _load_module(module_ref)
    source = getattr(module, "SOURCE", None)
    if source != OFFICIAL_ELO_SOURCE:
        raise EloSnapshotError(
            f"Elo SOURCE must be exactly {OFFICIAL_ELO_SOURCE!r}; got {source!r}"
        )

    source_sha256 = getattr(module, "SOURCE_SHA256", None)
    if not isinstance(source_sha256, str) or _SHA256_RE.fullmatch(source_sha256) is None:
        raise EloSnapshotError("SOURCE_SHA256 must be a lowercase 64-character SHA-256 digest")
    if expected_source_sha256 is not None and source_sha256 != expected_source_sha256:
        raise EloSnapshotError(
            f"World.tsv SHA-256 mismatch: snapshot={source_sha256}, "
            f"expected={expected_source_sha256}"
        )

    source_tsv_ratings: dict[str, int] | None = None
    raw_sha256: str | None = None
    if source_tsv is not None:
        source_path = Path(source_tsv)
        try:
            source_bytes = source_path.read_bytes()
        except OSError as exc:
            raise EloSnapshotError(f"cannot read World.tsv {source_path}: {exc}") from exc
        raw_sha256 = hashlib.sha256(source_bytes).hexdigest()
        if source_sha256 != raw_sha256:
            raise EloSnapshotError(
                f"World.tsv SHA-256 mismatch: snapshot={source_sha256}, raw={raw_sha256}"
            )
        source_tsv_ratings = parse_world_tsv_bytes(source_bytes, source_path)

    fetched_at = _parse_fetched_at(getattr(module, "FETCHED_AT_UTC", None))
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise EloSnapshotError("now_utc must include a timezone offset")
    now = now.astimezone(timezone.utc)
    if fetched_at > now:
        raise EloSnapshotError(
            f"Elo snapshot timestamp is in the future: {fetched_at.isoformat()}"
        )

    capture_receipt: EloCaptureReceipt | None = None
    if source_receipt is not None:
        assert source_tsv is not None
        capture_receipt = load_elo_capture_receipt(
            source_receipt,
            source_tsv=source_tsv,
            source_bytes=source_bytes,
            now_utc=now,
        )
        if source_sha256 != capture_receipt.body_sha256:
            raise EloSnapshotError(
                "World.tsv SHA-256 mismatch: "
                f"snapshot={source_sha256}, receipt={capture_receipt.body_sha256}"
            )
        if fetched_at != capture_receipt.response_completed_at_utc:
            raise EloSnapshotError(
                "Elo timestamp mismatch: "
                f"snapshot={fetched_at.isoformat()}, "
                f"receipt={capture_receipt.response_completed_at_utc.isoformat()}"
            )
        module_receipt_sha256 = getattr(module, "SOURCE_RECEIPT_SHA256", None)
        if module_receipt_sha256 != capture_receipt.receipt_sha256:
            raise EloSnapshotError(
                "Elo receipt SHA-256 mismatch: "
                f"snapshot={module_receipt_sha256}, receipt={capture_receipt.receipt_sha256}"
            )
        module_capture_method = getattr(module, "CAPTURE_METHOD", None)
        if module_capture_method != capture_receipt.capture_method:
            raise EloSnapshotError(
                "Elo capture method mismatch: "
                f"snapshot={module_capture_method!r}, receipt={capture_receipt.capture_method!r}"
            )
        module_byte_count = getattr(module, "SOURCE_BYTE_COUNT", None)
        if module_byte_count != capture_receipt.body_byte_count:
            raise EloSnapshotError(
                "World.tsv byte-count mismatch: "
                f"snapshot={module_byte_count!r}, receipt={capture_receipt.body_byte_count}"
            )
    elif require_direct_capture:
        raise EloSnapshotError("direct Elo capture validation requires a valid source_receipt")

    age = now - fetched_at
    if age > timedelta(hours=max_age_hours):
        age_hours = age.total_seconds() / 3600.0
        raise EloSnapshotError(
            f"Elo snapshot is stale: age={age_hours:.2f}h > {max_age_hours:.2f}h"
        )

    ratings = _validate_ratings(getattr(module, "ELO_CURRENT", None))
    estimates = _validate_estimates(getattr(module, "ESTIMATES", None))
    required_raw = tuple(required_teams)
    invalid_required = [
        team for team in required_raw if not isinstance(team, str) or not team.strip()
    ]
    if invalid_required:
        raise EloSnapshotError("required_teams contains an invalid team name")
    required = tuple(dict.fromkeys(required_raw))
    missing = [team for team in required if team not in ratings]
    if missing:
        raise EloSnapshotError(f"missing current Elo for {', '.join(missing)}")
    estimated = [team for team in required if team in estimates]
    if estimated:
        raise EloSnapshotError(
            f"estimated Elo is forbidden for official predictions: {', '.join(estimated)}"
        )
    if source_tsv_ratings is not None:
        missing_from_tsv = [team for team in required if team not in source_tsv_ratings]
        if missing_from_tsv:
            raise EloSnapshotError(
                f"required team missing from World.tsv: {', '.join(missing_from_tsv)}"
            )
        for team in required:
            raw_rating = float(source_tsv_ratings[team])
            if ratings[team] != raw_rating:
                raise EloSnapshotError(
                    f"current Elo mismatch for {team}: "
                    f"snapshot={ratings[team]:g}, World.tsv={raw_rating:g}"
                )

    return EloSnapshot(
        ratings=ratings,
        fetched_at_utc=fetched_at,
        source=source,
        source_sha256=source_sha256,
        estimates=estimates,
        module_ref=str(module_ref),
        capture_receipt=capture_receipt,
    )
