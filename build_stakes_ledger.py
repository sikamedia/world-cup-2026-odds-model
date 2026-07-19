#!/usr/bin/env python3
"""Build stakes_goals_ledger.csv — seed the friendly-like goal cohort.

Ex-ante stakes label per game (competition_state.stakes_profile); goals from the
recorded 90' result. KO: every tie is win-or-go-home = competitive, except the
third-place playoff (3P = dead rubber). Group: the matchday-3 games that carry
competition_state. The label NEVER uses the score. Record-only.

This is also the append-going-forward integration point: at grade time, call
stakes_profile(state, stage) and append a row here.
Run:  python3 build_stakes_ledger.py
Educational/analytical use only - not betting advice.
"""
import csv
from collections import Counter
from pathlib import Path

from competition_state import stakes_profile
from match_context import context_key
from worldcup_2026_data import ELO
from worldcup_2026_data_jun26 import JUNE_26_COMPETITION_STATE
from worldcup_2026_data_jun27 import JUNE_27_COMPETITION_STATE
from worldcup_2026_data_jun28 import MATCHES_72
from worldcup_2026_data_ko import KO_RESULTS

OUT = Path(__file__).resolve().parent / "stakes_goals_ledger.csv"
FIELDS = [
    "date", "stage", "home", "away", "stakes_label", "delta_elo",
    "total_goals", "over_2_5", "margin", "basis", "notes",
]


def _row(stage, home, away, label, hg, ag, basis):
    total = hg + ag
    return {
        "date": "",
        "stage": stage,
        "home": home,
        "away": away,
        "stakes_label": label,
        "delta_elo": f"{ELO[home] - ELO[away]:.0f}",
        "total_goals": total,
        "over_2_5": int(total >= 3),
        "margin": abs(hg - ag),
        "basis": basis,
        "notes": "",
    }


def build():
    rows = []
    # KO: only the third-place playoff is a dead rubber; every other tie is
    # win-or-go-home. Label is fully stage-determined (no state needed).
    for home, away, hg, ag, _adv, stage in KO_RESULTS:
        label = stakes_profile(None, stage)
        rows.append(_row(stage, home, away, label, hg, ag, "ko_stage"))
    # Group matchday-3 games that carry recorded competition_state.
    score = {context_key(h, a): (h, a, hg, ag) for (h, a, hg, ag, *_) in MATCHES_72}
    for state in (JUNE_26_COMPETITION_STATE, JUNE_27_COMPETITION_STATE):
        for key, payload in state.items():
            if key not in score:
                continue
            h, a, hg, ag = score[key]
            label = stakes_profile(payload, "group")
            rows.append(_row("group", h, a, label, hg, ag, "competition_state"))
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return rows


if __name__ == "__main__":
    built = build()
    counts = Counter(r["stakes_label"] for r in built)
    print(f"wrote {OUT.name}: {len(built)} rows  {dict(counts)}")
