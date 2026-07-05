"""Confirmed team-news → λ multipliers (standing pre-prediction step).

Turns a confirmed availability list (injuries, suspensions, rotation) into the
`--inj-home` / `--inj-away` multipliers used by match_model.py, following the
SKILL "Injuries / lineups" rules so we STOP running predictions on bare Elo:

  - key attacker / playmaker OUT  → LOWER that team's λ (depth-scaled: a deep
    squad that can replace like-for-like loses less than a one-star team).
  - first-choice keeper / key defender OUT → RAISE the OPPONENT's λ (do NOT
    lower your own — you concede more, you don't score less).
  - confirmed strongest XI / rested stars returning → NO change (Elo already
    reflects full strength; don't double-count — Discipline A).
  - ⚠ don't over-stack: apply EITHER a rotation Elo cut OR a λ mult, not both.

Multipliers are deliberately conservative. Educational/analytical only.
"""
from dataclasses import dataclass

# --- rule constants (conservative, depth-scaled) --------------------------
ATTACKER_OUT = 0.90        # star attacker/playmaker out, average depth  (−10%)
ATTACKER_OUT_DEEP = 0.94   # same, but deep squad with a real replacement (−6%)
KEY_ATTACKER_OUT_THIN = 0.85  # one-star team loses its talisman (−15%)
KEEPER_OUT_OPP = 1.06      # first-choice keeper out → +6% opponent λ
DEFENDER_OUT_OPP = 1.04    # key defender out → +4% opponent λ


@dataclass
class Absence:
    side: str      # 'home' or 'away'  (the team the player belongs to)
    role: str      # 'attacker' | 'playmaker' | 'keeper' | 'defender'
    depth: str = "avg"   # 'avg' | 'deep' | 'thin'
    player: str = ""
    status: str = "out"  # 'out' | 'doubt'  (doubt applies half weight)


def _mult_for(a: Absence):
    """Return (home_factor, away_factor) contribution for one absence."""
    if a.role in ("attacker", "playmaker"):
        base = {"deep": ATTACKER_OUT_DEEP, "avg": ATTACKER_OUT,
                "thin": KEY_ATTACKER_OUT_THIN}[a.depth]
        f = base if a.status == "out" else (1 + (base - 1) * 0.5)  # doubt = half
        return (f, 1.0) if a.side == "home" else (1.0, f)
    if a.role in ("keeper", "defender"):
        base = KEEPER_OUT_OPP if a.role == "keeper" else DEFENDER_OUT_OPP
        f = base if a.status == "out" else (1 + (base - 1) * 0.5)
        # keeper/defender out RAISES the OPPONENT's λ
        return (1.0, f) if a.side == "home" else (f, 1.0)
    return (1.0, 1.0)


def availability_to_mult(absences):
    """Combine a list of Absence into (inj_home, inj_away) λ multipliers."""
    inj_home = inj_away = 1.0
    for a in absences:
        h, w = _mult_for(a)
        inj_home *= h
        inj_away *= w
    return round(inj_home, 4), round(inj_away, 4)


# --- confirmed team news, 2026-07-01 evening R32 (verified match-day) -------
# Sources: ESPN / Goal / Sports Mole / US Soccer / FIFA previews (1 Jul 2026).
TEAM_NEWS = {
    "USA v Bosnia": {
        # USA: rested stars RETURN (Adams, Balogun, Richards, Pulisic fit from
        # calf). Minor doubts Roldan/McKenzie/Trusty are squad players. Bosnia:
        # no injuries; Muharemovic back from suspension; Dedic thigh-doubt but
        # expected to start, Dzeko starts. → BOTH effectively full strength.
        "absences": [],
        "note": "both full strength; USA's rested starters all return → Elo baseline holds",
    },
    "Belgium v Senegal": {
        # Belgium full strength (Courtois, De Bruyne, Doku, Trossard). Senegal:
        # No.1 GK Edouard Mendy (knee) left camp → likely OUT; backup Diaw in.
        # Keeper out → raise Belgium (home) λ.
        "absences": [Absence("away", "keeper", depth="avg",
                             player="Edouard Mendy", status="out")],
        "note": "Belgium full strength; Senegal lose No.1 GK Mendy (knee) → raise BEL λ ~+6%",
    },
}


if __name__ == "__main__":
    for match, tn in TEAM_NEWS.items():
        ih, iw = availability_to_mult(tn["absences"])
        print(f"{match:22} inj-home {ih}  inj-away {iw}   # {tn['note']}")
