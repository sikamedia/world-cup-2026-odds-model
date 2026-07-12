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
import math
from pathlib import Path
import re
from types import ModuleType


OFFICIAL_ELO_SOURCE = "https://www.eloratings.net/World.tsv"
_SHA256_RE = re.compile(r"[0-9a-f]{64}")

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
class EloSnapshot:
    """Validated prediction-side Elo data and its provenance."""

    ratings: dict[str, float]
    fetched_at_utc: datetime
    source: str
    source_sha256: str
    estimates: frozenset[str]
    module_ref: str

    @property
    def provenance_note(self) -> str:
        return (
            f"current Elo fetched {self.fetched_at_utc.isoformat()} "
            f"from {self.source} sha256={self.source_sha256}"
        )


def parse_world_tsv(path: str | Path) -> dict[str, int]:
    """Parse mapped current ratings from an official World.tsv file."""

    source = Path(path)
    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise EloSnapshotError(f"cannot read World.tsv {source}: {exc}") from exc
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise EloSnapshotError(f"cannot parse World.tsv {source}: invalid UTF-8") from exc

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
                f"cannot parse World.tsv {source}: conflicting {team} ratings "
                f"on line {line_number}"
            )
        ratings[team] = rating

    if len(ratings) < 16:
        raise EloSnapshotError(
            f"cannot parse World.tsv {source}: only {len(ratings)} recognized current Elo rows"
        )
    return ratings


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


def _parse_fetched_at(raw: object) -> datetime:
    if not isinstance(raw, str) or not raw.strip():
        raise EloSnapshotError("Elo snapshot must define FETCHED_AT_UTC")
    text = raw.strip().replace("Z", "+00:00")
    try:
        fetched = datetime.fromisoformat(text)
    except ValueError as exc:
        raise EloSnapshotError(f"invalid FETCHED_AT_UTC: {raw!r}") from exc
    if fetched.tzinfo is None or fetched.utcoffset() is None:
        raise EloSnapshotError("FETCHED_AT_UTC must include a timezone offset")
    return fetched.astimezone(timezone.utc)


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
) -> EloSnapshot:
    """Load an Elo module and enforce the official prediction contract.

    ``expected_source_sha256`` remains available for callers that independently
    calculate a digest. Official workflows should pass ``source_tsv`` so this
    function can verify both the raw bytes and each required team's rating.
    """

    if not math.isfinite(max_age_hours) or max_age_hours < 0:
        raise EloSnapshotError("max_age_hours must be a finite non-negative number")

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
        source_tsv_ratings = parse_world_tsv(source_path)

    fetched_at = _parse_fetched_at(getattr(module, "FETCHED_AT_UTC", None))
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise EloSnapshotError("now_utc must include a timezone offset")
    now = now.astimezone(timezone.utc)
    if fetched_at > now:
        raise EloSnapshotError(
            f"Elo snapshot timestamp is in the future: {fetched_at.isoformat()}"
        )
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
    )
