"""External rating audit helpers.

External ratings such as Opta Power Rankings are useful as second opinions, not
as a direct replacement for the transparent Elo source. This module compares an
external rank/rating direction with the model and market directions and emits a
manual-review flag when they materially disagree.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from team_aliases import resolve_team_name


@dataclass(frozen=True)
class ExternalRating:
    team: str
    rank: int | None = None
    rating: float | None = None
    source: str = "external"


@dataclass(frozen=True)
class RatingAudit:
    home: str
    away: str
    source: str
    external_pick: str | None
    model_pick: str
    market_pick: str
    rank_gap: int | None
    rating_gap: float | None
    rating_disagreement: bool
    manual_review: bool
    confidence_penalty: float
    reason: str


def _first_non_empty(row: dict[str, str], keys: Iterable[str]) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _optional_int(raw: str) -> int | None:
    if not raw:
        return None
    return int(float(raw))


def _optional_float(raw: str) -> float | None:
    if not raw:
        return None
    return float(raw)


def load_external_ratings_csv(path: str | Path) -> dict[str, ExternalRating]:
    """Load a flexible ratings CSV.

    Supported columns:
      - team/name
      - rank/opta_rank/ranking (lower is better)
      - rating/opta_rating/power_rating/score (higher is better)
      - source/provider
    """
    ratings: dict[str, ExternalRating] = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row_num, row in enumerate(csv.DictReader(handle), 2):
            raw_team = _first_non_empty(row, ("team", "name", "country", "side"))
            if not raw_team:
                raise ValueError(f"row {row_num}: missing team/name column")
            team = resolve_team_name(raw_team)
            rank = _optional_int(_first_non_empty(row, ("rank", "opta_rank", "ranking")))
            rating = _optional_float(
                _first_non_empty(row, ("rating", "opta_rating", "power_rating", "score"))
            )
            if rank is None and rating is None:
                raise ValueError(f"row {row_num} ({raw_team}): expected rank or rating")
            source = _first_non_empty(row, ("source", "provider")) or "external"
            ratings[team] = ExternalRating(team=team, rank=rank, rating=rating, source=source)
    return ratings


def _fav_from_probs(probs: tuple[float, float, float]) -> str:
    return "H" if probs[0] >= probs[2] else "A"


def _external_pick(
    home_rating: ExternalRating,
    away_rating: ExternalRating,
    *,
    rank_gap_threshold: int,
    rating_gap_threshold: float,
) -> tuple[str | None, int | None, float | None, str]:
    rank_gap = None
    if home_rating.rank is not None and away_rating.rank is not None:
        # Lower rank is better; negative means home is rated higher.
        rank_gap = home_rating.rank - away_rating.rank

    rating_gap = None
    if home_rating.rating is not None and away_rating.rating is not None:
        # Higher rating is better; positive means home is rated higher.
        rating_gap = home_rating.rating - away_rating.rating

    if rating_gap is not None and abs(rating_gap) >= rating_gap_threshold:
        pick = "H" if rating_gap > 0 else "A"
        return pick, rank_gap, rating_gap, f"rating_gap={rating_gap:+.2f}"
    if rank_gap is not None and abs(rank_gap) >= rank_gap_threshold:
        pick = "H" if rank_gap < 0 else "A"
        return pick, rank_gap, rating_gap, f"rank_gap={rank_gap:+d}"
    return None, rank_gap, rating_gap, "external gap below threshold"


def audit_fixture_ratings(
    home: str,
    away: str,
    *,
    model_probs: tuple[float, float, float],
    market_probs: tuple[float, float, float],
    ratings: dict[str, ExternalRating],
    rank_gap_threshold: int = 8,
    rating_gap_threshold: float = 2.0,
    confidence_penalty: float = 0.25,
) -> RatingAudit:
    home = resolve_team_name(home)
    away = resolve_team_name(away)
    model_pick = _fav_from_probs(model_probs)
    market_pick = _fav_from_probs(market_probs)
    home_rating = ratings.get(home)
    away_rating = ratings.get(away)
    if home_rating is None or away_rating is None:
        missing = ", ".join(team for team, rating in ((home, home_rating), (away, away_rating)) if rating is None)
        return RatingAudit(
            home=home,
            away=away,
            source="external",
            external_pick=None,
            model_pick=model_pick,
            market_pick=market_pick,
            rank_gap=None,
            rating_gap=None,
            rating_disagreement=False,
            manual_review=False,
            confidence_penalty=0.0,
            reason=f"external_rating_missing={missing}",
        )

    external_pick, rank_gap, rating_gap, basis = _external_pick(
        home_rating,
        away_rating,
        rank_gap_threshold=rank_gap_threshold,
        rating_gap_threshold=rating_gap_threshold,
    )
    source = home_rating.source if home_rating.source == away_rating.source else f"{home_rating.source}/{away_rating.source}"
    if external_pick is None:
        return RatingAudit(
            home=home,
            away=away,
            source=source,
            external_pick=None,
            model_pick=model_pick,
            market_pick=market_pick,
            rank_gap=rank_gap,
            rating_gap=rating_gap,
            rating_disagreement=False,
            manual_review=False,
            confidence_penalty=0.0,
            reason=f"rating_audit ok; {basis}",
        )

    disagreements = []
    if external_pick != model_pick:
        disagreements.append(f"external_vs_model {external_pick}!={model_pick}")
    if external_pick != market_pick:
        disagreements.append(f"external_vs_market {external_pick}!={market_pick}")
    rating_disagreement = bool(disagreements)
    reason = (
        f"rating_audit {'manual_review' if rating_disagreement else 'ok'}; "
        f"source={source}; external={external_pick}; model={model_pick}; "
        f"market={market_pick}; {basis}"
    )
    if disagreements:
        reason += "; " + "; ".join(disagreements)
    return RatingAudit(
        home=home,
        away=away,
        source=source,
        external_pick=external_pick,
        model_pick=model_pick,
        market_pick=market_pick,
        rank_gap=rank_gap,
        rating_gap=rating_gap,
        rating_disagreement=rating_disagreement,
        manual_review=rating_disagreement,
        confidence_penalty=confidence_penalty if rating_disagreement else 0.0,
        reason=reason,
    )
