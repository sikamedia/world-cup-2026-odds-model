"""Paper-trading ledger helpers for model-vs-market signals.

This layer deliberately does not place real bets. It records auditable paper
signals, applies conservative risk gates, and settles those signals after
results are known.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Iterable


LEDGER_FIELDNAMES = [
    "signal_id",
    "date",
    "stage",
    "market_type",
    "home",
    "away",
    "selection",
    "bookmaker",
    "odds_decimal",
    "p_model",
    "p_market",
    "edge_raw",
    "edge_net",
    "stake_units",
    "status",
    "result",
    "clv",
    "roi",
    "notes",
]

VALID_MARKET_TYPES = {"h2h_90", "advance"}
VALID_STATUSES = {"watchlist", "paper_bet", "no_bet", "settled", "void"}
VALID_SELECTIONS = {"H", "X", "A"}
VALID_RESULTS = {"", "win", "loss", "void"}
UPDATABLE_STATUSES = {"no_bet", "watchlist"}
STATUS_PRIORITY = {"no_bet": 0, "watchlist": 1, "paper_bet": 2, "settled": 3, "void": 3}


@dataclass(frozen=True)
class RiskPolicy:
    uncertainty_discount: float = 0.02
    min_edge_net: float = 0.03
    max_stake_units: float = 0.5
    daily_risk_limit_units: float = 2.0
    max_market_margin: float = 0.08
    max_model_market_gap: float = 0.15


DEFAULT_RISK_POLICY = RiskPolicy()


def normalize_selection(raw: str) -> str:
    text = str(raw).strip().upper()
    aliases = {
        "HOME": "H",
        "1": "H",
        "DRAW": "X",
        "TIE": "X",
        "D": "X",
        "AWAY": "A",
        "2": "A",
    }
    text = aliases.get(text, text)
    if text not in VALID_SELECTIONS:
        raise ValueError(f"selection must be one of H/X/A, got {raw!r}")
    return text


def selection_index(selection: str) -> int:
    return {"H": 0, "X": 1, "A": 2}[normalize_selection(selection)]


def format_float(value: float | int | str | None, digits: int = 4) -> str:
    if value in {None, ""}:
        return ""
    return f"{float(value):.{digits}f}"


def parse_float(raw: str | float | int | None, default: float = 0.0) -> float:
    if raw in {None, ""}:
        return default
    return float(raw)


def make_signal_id(
    date: str,
    market_type: str,
    home: str,
    away: str,
    selection: str,
    bookmaker: str,
) -> str:
    basis = "|".join(
        [
            str(date).strip(),
            str(market_type).strip().lower(),
            str(home).strip(),
            str(away).strip(),
            normalize_selection(selection),
            str(bookmaker).strip().lower(),
        ]
    )
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]
    return f"sig_{digest}"


def edge_values(
    p_model: float,
    p_market: float,
    uncertainty_discount: float = DEFAULT_RISK_POLICY.uncertainty_discount,
) -> tuple[float, float]:
    p_model = float(p_model)
    p_market = float(p_market)
    if not 0.0 <= p_model <= 1.0:
        raise ValueError("p_model must be in [0, 1]")
    if not 0.0 <= p_market <= 1.0:
        raise ValueError("p_market must be in [0, 1]")
    if uncertainty_discount < 0.0:
        raise ValueError("uncertainty_discount must be non-negative")
    edge_raw = p_model - p_market
    return edge_raw, edge_raw - uncertainty_discount


def suggested_stake_units(
    edge_net: float,
    *,
    min_edge_net: float = DEFAULT_RISK_POLICY.min_edge_net,
    max_stake_units: float = DEFAULT_RISK_POLICY.max_stake_units,
) -> float:
    if edge_net < min_edge_net:
        return 0.0
    # Conservative linear sizing: 3pp net edge ~= 0.30u, 5pp+ caps at 0.50u.
    return round(min(max_stake_units, max(0.1, edge_net * 10.0)), 2)


def risk_status(
    *,
    market_type: str,
    edge_raw: float,
    edge_net: float,
    market_margin: float,
    max_abs_gap: float,
    blocked: bool = False,
    blocked_reason: str = "",
    policy: RiskPolicy = DEFAULT_RISK_POLICY,
) -> tuple[str, str]:
    reasons: list[str] = []
    if market_type not in VALID_MARKET_TYPES:
        reasons.append(f"unsupported market_type={market_type}")
    if market_type != "h2h_90":
        reasons.append("only h2h_90 is automatic in v1")
    if market_margin > policy.max_market_margin:
        reasons.append(f"market margin {market_margin:.1%} > {policy.max_market_margin:.1%}")
    if max_abs_gap > policy.max_model_market_gap:
        reasons.append(f"model/market gap {max_abs_gap:.1%} > {policy.max_model_market_gap:.1%}")
    if blocked:
        reasons.append(blocked_reason or "risk gate blocked")

    if reasons:
        return "no_bet", "; ".join(reasons)
    if edge_net >= policy.min_edge_net:
        return "paper_bet", f"net edge {edge_net:.1%} >= {policy.min_edge_net:.1%}"
    if edge_raw > 0.0:
        return "watchlist", f"raw edge {edge_raw:.1%}, net edge below threshold"
    return "no_bet", "no positive model edge"


def build_ledger_row(
    *,
    date: str,
    stage: str,
    market_type: str,
    home: str,
    away: str,
    selection: str,
    bookmaker: str,
    odds_decimal: float,
    p_model: float,
    p_market: float,
    edge_raw: float,
    edge_net: float,
    stake_units: float,
    status: str,
    notes: str = "",
) -> dict[str, str]:
    selection = normalize_selection(selection)
    signal_id = make_signal_id(date, market_type, home, away, selection, bookmaker)
    row = {
        "signal_id": signal_id,
        "date": str(date),
        "stage": str(stage),
        "market_type": str(market_type),
        "home": str(home),
        "away": str(away),
        "selection": selection,
        "bookmaker": str(bookmaker),
        "odds_decimal": format_float(odds_decimal),
        "p_model": format_float(p_model),
        "p_market": format_float(p_market),
        "edge_raw": format_float(edge_raw),
        "edge_net": format_float(edge_net),
        "stake_units": format_float(stake_units, digits=2),
        "status": str(status),
        "result": "",
        "clv": "",
        "roi": "",
        "notes": str(notes),
    }
    validate_ledger_row(row)
    return row


def validate_ledger_row(row: dict[str, str]) -> None:
    missing = [field for field in LEDGER_FIELDNAMES if field not in row]
    if missing:
        raise ValueError(f"ledger row missing fields: {', '.join(missing)}")
    if row["market_type"] not in VALID_MARKET_TYPES:
        raise ValueError(f"invalid market_type: {row['market_type']!r}")
    normalize_selection(row["selection"])
    if row["status"] not in VALID_STATUSES:
        raise ValueError(f"invalid status: {row['status']!r}")
    if row["result"] not in VALID_RESULTS:
        raise ValueError(f"invalid result: {row['result']!r}")
    odds = parse_float(row["odds_decimal"])
    if odds <= 1.0:
        raise ValueError("odds_decimal must be > 1.0")
    for key in ("p_model", "p_market"):
        value = parse_float(row[key])
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{key} must be in [0, 1]")
    parse_float(row["edge_raw"])
    parse_float(row["edge_net"])
    stake = parse_float(row["stake_units"])
    if stake < 0.0:
        raise ValueError("stake_units must be non-negative")
    if row["status"] == "paper_bet" and stake <= 0.0:
        raise ValueError("paper_bet rows require positive stake_units")


def read_ledger(path: str | Path) -> list[dict[str, str]]:
    ledger_path = Path(path)
    if not ledger_path.exists():
        return []
    with ledger_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
    for row in rows:
        validate_ledger_row(_coerce_row(row))
    return [_coerce_row(row) for row in rows]


def write_ledger(path: str | Path, rows: Iterable[dict[str, str]]) -> None:
    ledger_path = Path(path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    clean_rows = [_coerce_row(row) for row in rows]
    for row in clean_rows:
        validate_ledger_row(row)
    with ledger_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDNAMES)
        writer.writeheader()
        writer.writerows(clean_rows)


def append_ledger_rows(path: str | Path, rows: Iterable[dict[str, str]]) -> tuple[int, int]:
    existing = read_ledger(path)
    index_by_id = {row["signal_id"]: idx for idx, row in enumerate(existing)}
    written = 0
    skipped = 0
    for raw in rows:
        row = _coerce_row(raw)
        validate_ledger_row(row)
        existing_idx = index_by_id.get(row["signal_id"])
        if existing_idx is None:
            existing.append(row)
            index_by_id[row["signal_id"]] = len(existing) - 1
            written += 1
            continue

        old = existing[existing_idx]
        old_priority = STATUS_PRIORITY.get(old["status"], -1)
        new_priority = STATUS_PRIORITY.get(row["status"], -1)
        if old["status"] in UPDATABLE_STATUSES and new_priority > old_priority:
            existing[existing_idx] = row
            written += 1
        else:
            skipped += 1
    write_ledger(path, existing)
    return written, skipped


def settle_row(
    row: dict[str, str],
    actual_selection: str,
    *,
    closing_odds_decimal: float | None = None,
) -> dict[str, str]:
    clean = _coerce_row(row)
    if clean["status"] != "paper_bet":
        return clean
    actual = normalize_selection(actual_selection)
    stake = parse_float(clean["stake_units"])
    odds = parse_float(clean["odds_decimal"])
    if actual == clean["selection"]:
        clean["result"] = "win"
        clean["roi"] = format_float(stake * (odds - 1.0))
    else:
        clean["result"] = "loss"
        clean["roi"] = format_float(-stake)
    clean["status"] = "settled"
    if closing_odds_decimal is not None and not math.isnan(closing_odds_decimal):
        clean["clv"] = format_float(odds - float(closing_odds_decimal))
    validate_ledger_row(clean)
    return clean


def _coerce_row(row: dict[str, str]) -> dict[str, str]:
    return {field: str(row.get(field, "")) for field in LEDGER_FIELDNAMES}
