"""Team-name normalization helpers for the World Cup context pipeline."""

from __future__ import annotations

import re
import unicodedata

from worldcup_2026_data import ELO


def normalize_team_text(raw: str) -> str:
    text = unicodedata.normalize("NFKD", str(raw))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = text.replace("&", " and ")
    text = re.sub(r"[.'`’]+", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


CANONICAL_TEAM_NAMES = tuple(sorted(ELO))

TEAM_ALIASES: dict[str, str] = {normalize_team_text(name): name for name in CANONICAL_TEAM_NAMES}
TEAM_ALIASES.update(
    {
        "united states": "USA",
        "united states of america": "USA",
        "usa": "USA",
        "u s a": "USA",
        "us": "USA",
        "korea republic": "Korea",
        "republic of korea": "Korea",
        "south korea": "Korea",
        "czech republic": "Czechia",
        "ivory coast": "Cote dIvoire",
        "cote divoire": "Cote dIvoire",
        "cote d ivoire": "Cote dIvoire",
        "cote d ivoire fc": "Cote dIvoire",
        "curacao": "Curacao",
        "turkey": "Turkiye",
        "turkiye": "Turkiye",
        "t rkiye": "Turkiye",
        "cape verde": "Cabo Verde",
        "bosnia and herzegovina": "Bosnia",
        "dr congo": "DR Congo",
        "democratic republic of congo": "DR Congo",
        "democratic republic of the congo": "DR Congo",
        "congo dr": "DR Congo",
        "congo democratic republic": "DR Congo",
        "holland": "Netherlands",
        "netherlands": "Netherlands",
        "new zealand": "New Zealand",
        "saudi arabia": "Saudi Arabia",
        "south africa": "South Africa",
        "cabo verde": "Cabo Verde",
    }
)


def resolve_team_name(raw: str) -> str:
    normalized = normalize_team_text(raw)
    if normalized in TEAM_ALIASES:
        return TEAM_ALIASES[normalized]
    raise ValueError(f"unknown team name: {raw!r}")
