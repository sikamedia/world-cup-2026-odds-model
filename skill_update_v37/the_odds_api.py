"""The Odds API adapter for World Cup market context rows."""

from __future__ import annotations

from dataclasses import dataclass
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from team_aliases import resolve_team_name


DEFAULT_API_BASE = "https://api.the-odds-api.com/v4"
DEFAULT_REGIONS = "us,uk,eu"
DEFAULT_MARKETS = "h2h"
DEFAULT_ODDS_FORMAT = "decimal"
DEFAULT_DATE_FORMAT = "iso"
DEFAULT_PREFERRED_BOOKMAKERS = ("pinnacle", "bet365")


def normalize_text(raw: str) -> str:
    text = str(raw).strip().lower()
    text = text.replace("&", " and ")
    text = "".join(ch for ch in text if ch.isalnum() or ch.isspace())
    return " ".join(text.split())


def _normalize_bookmaker_key(raw: str) -> str:
    return normalize_text(raw).replace(" ", "")


def _cache_dir(path: str | Path | None) -> Path:
    if path is not None:
        return Path(path)
    env = os.environ.get("WORLD_CUP_2026_ODDS_CACHE_DIR")
    if env:
        return Path(env)
    return Path(".cache") / "the_odds_api"


def _cache_path(url: str, cache_dir: str | Path | None) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return _cache_dir(cache_dir) / f"{digest}.json"


def load_json_payload(path: str | Path) -> Any:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for key in ("payload", "events", "data"):
            if key in data:
                return data[key]
    return data


def fetch_json_payload(
    sport_key: str,
    api_key: str,
    *,
    regions: str = DEFAULT_REGIONS,
    markets: str = DEFAULT_MARKETS,
    odds_format: str = DEFAULT_ODDS_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
    bookmakers: str | None = None,
    api_base: str = DEFAULT_API_BASE,
    timeout: int = 30,
    cache_dir: str | Path | None = None,
    cache_ttl_seconds: int = 1800,
) -> Any:
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
        "dateFormat": date_format,
    }
    if bookmakers:
        params["bookmakers"] = bookmakers
    url = f"{api_base.rstrip('/')}/sports/{sport_key}/odds/?{urlencode(params)}"
    cache_file = _cache_path(url, cache_dir)
    if cache_ttl_seconds > 0 and cache_file.exists():
        try:
            stat = cache_file.stat()
            if (time.time() - stat.st_mtime) <= cache_ttl_seconds:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                return cached.get("payload", cached) if isinstance(cached, dict) else cached
        except Exception:
            pass

    with urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps(
            {
                "request_url": url,
                "payload": payload,
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return payload


@dataclass(frozen=True)
class OddsSelection:
    odds: tuple[float, float, float]
    bookmaker_key: str
    bookmaker_title: str
    market_key: str
    market_label: str
    confidence: float
    event_id: str | None = None
    commence_time: str | None = None


def _coerce_payload(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and "payload" in data:
        data = data["payload"]
    if not isinstance(data, list):
        raise ValueError("odds payload must be a list of events")
    return data


def load_events(data: Any) -> list[dict[str, Any]]:
    return _coerce_payload(data)


def _canonical_pair(home: str, away: str) -> tuple[str, str]:
    return resolve_team_name(home), resolve_team_name(away)


def _pair_key(home: str, away: str) -> tuple[str, str]:
    home_c, away_c = _canonical_pair(home, away)
    return tuple(sorted((home_c, away_c)))


def _event_pair(event: dict[str, Any]) -> tuple[str, str] | None:
    try:
        return _pair_key(event["home_team"], event["away_team"])
    except Exception:
        return None


def build_event_index(events: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for event in events:
        key = _event_pair(event)
        if key is None:
            continue
        index.setdefault(key, []).append(event)
    return index


def _event_order_score(event: dict[str, Any], fixture_home: str, fixture_away: str) -> tuple[int, int, str]:
    home_c, away_c = _canonical_pair(event["home_team"], event["away_team"])
    fixture_home_c, fixture_away_c = _canonical_pair(fixture_home, fixture_away)
    exact_order = 0 if (home_c, away_c) == (fixture_home_c, fixture_away_c) else 1
    commence_time = str(event.get("commence_time") or "")
    missing_commence = 1 if not commence_time else 0
    return exact_order, missing_commence, commence_time


def match_event_for_fixture(
    event_index: dict[tuple[str, str], list[dict[str, Any]]],
    fixture_home: str,
    fixture_away: str,
) -> dict[str, Any] | None:
    key = _pair_key(fixture_home, fixture_away)
    candidates = event_index.get(key, [])
    if not candidates:
        return None
    return sorted(candidates, key=lambda event: _event_order_score(event, fixture_home, fixture_away))[0]


def _bookmaker_candidates(bookmakers: list[dict[str, Any]], preferred: tuple[str, ...]) -> list[tuple[dict[str, Any], float]]:
    normalized_preferred = {_normalize_bookmaker_key(name): idx for idx, name in enumerate(preferred)}
    ranked: list[tuple[tuple[int, int, int], dict[str, Any], float]] = []
    for idx, bookmaker in enumerate(bookmakers):
        key = _normalize_bookmaker_key(str(bookmaker.get("key") or bookmaker.get("title") or ""))
        preferred_rank = normalized_preferred.get(key)
        if preferred_rank is not None:
            sort_key = (0, preferred_rank, idx)
            confidence = max(0.7, 1.0 - 0.05 * preferred_rank)
        else:
            sort_key = (1, idx, idx)
            confidence = 0.75
        ranked.append((sort_key, bookmaker, confidence))
    ranked.sort(key=lambda item: item[0])
    return [(bookmaker, confidence) for _, bookmaker, confidence in ranked]


def _is_draw_name(raw: Any) -> bool:
    text = normalize_text(raw)
    return text in {"draw", "tie", "x"}


def extract_h2h_selection(
    event: dict[str, Any],
    fixture_home: str,
    fixture_away: str,
    *,
    preferred_bookmakers: tuple[str, ...] = DEFAULT_PREFERRED_BOOKMAKERS,
) -> OddsSelection | None:
    bookmakers = event.get("bookmakers") or []
    if not isinstance(bookmakers, list):
        return None

    fixture_home_c, fixture_away_c = _canonical_pair(fixture_home, fixture_away)

    for bookmaker, confidence in _bookmaker_candidates(bookmakers, preferred_bookmakers):
        markets = bookmaker.get("markets") or []
        if not isinstance(markets, list):
            continue
        market = next((m for m in markets if normalize_text(m.get("key")) == "h2h"), None)
        if not market:
            continue
        outcomes = market.get("outcomes") or []
        if not isinstance(outcomes, list):
            continue
        home_odds = draw_odds = away_odds = None
        for outcome in outcomes:
            price = outcome.get("price")
            name = outcome.get("name")
            if price is None or name is None:
                continue
            if _is_draw_name(name):
                draw_odds = float(price)
                continue
            try:
                resolved = resolve_team_name(str(name))
            except Exception:
                continue
            if resolved == fixture_home_c:
                home_odds = float(price)
            elif resolved == fixture_away_c:
                away_odds = float(price)
        if home_odds is not None and draw_odds is not None and away_odds is not None:
            return OddsSelection(
                odds=(home_odds, draw_odds, away_odds),
                bookmaker_key=str(bookmaker.get("key") or ""),
                bookmaker_title=str(bookmaker.get("title") or bookmaker.get("key") or ""),
                market_key=str(market.get("key") or "h2h"),
                market_label=str(market.get("key") or "h2h"),
                confidence=confidence,
                event_id=str(event.get("id") or "") or None,
                commence_time=str(event.get("commence_time") or "") or None,
            )
    return None


def build_market_rows(
    fixture_rows: list[dict[str, str]],
    events: list[dict[str, Any]],
    *,
    preferred_bookmakers: tuple[str, ...] = DEFAULT_PREFERRED_BOOKMAKERS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    event_index = build_event_index(events)
    matched = 0
    missing = 0
    rows: list[dict[str, Any]] = []

    for row in fixture_rows:
        home = row.get("home") or row.get("team1") or row.get("side1")
        away = row.get("away") or row.get("team2") or row.get("side2")
        if not home or not away:
            raise ValueError("fixture rows require home and away columns")

        enriched = dict(row)
        event = match_event_for_fixture(event_index, home, away)
        selection = extract_h2h_selection(
            event, home, away, preferred_bookmakers=preferred_bookmakers
        ) if event else None

        if selection is not None:
            matched += 1
            enriched["market_odds"] = "/".join(f"{value}" for value in selection.odds)
            enriched["market_home"] = selection.odds[0]
            enriched["market_draw"] = selection.odds[1]
            enriched["market_away"] = selection.odds[2]
            enriched["market_confidence"] = selection.confidence
            enriched["odds_source_status"] = "matched"
            enriched["odds_bookmaker"] = selection.bookmaker_key
            enriched["odds_bookmaker_title"] = selection.bookmaker_title
            enriched["odds_event_id"] = selection.event_id or ""
            enriched["odds_commence_time"] = selection.commence_time or ""
        else:
            missing += 1
            enriched.setdefault("odds_source_status", "missing")
            enriched.setdefault("odds_bookmaker", "")
            enriched.setdefault("odds_bookmaker_title", "")
            enriched.setdefault("odds_event_id", "")
            enriched.setdefault("odds_commence_time", "")
        rows.append(enriched)

    report = {
        "matched": matched,
        "missing": missing,
        "total": len(fixture_rows),
    }
    return rows, report


def load_fixture_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_events_from_path(path: str | Path) -> list[dict[str, Any]]:
    return load_events(load_json_payload(path))


def write_market_rows_csv(rows: list[dict[str, Any]], path: str | Path) -> None:
    import csv

    fieldnames = [
        "home",
        "away",
        "source_key",
        "market_odds",
        "market_home",
        "market_draw",
        "market_away",
        "market_method",
        "market_confidence",
        "lineup_home",
        "lineup_away",
        "weather_scale",
        "competition_state",
        "notes",
        "odds_source_status",
        "odds_bookmaker",
        "odds_bookmaker_title",
        "odds_event_id",
        "odds_commence_time",
    ]
    extra_fields = sorted(
        {
            key
            for row in rows
            for key in row.keys()
            if key not in fieldnames
        }
    )
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames + extra_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
