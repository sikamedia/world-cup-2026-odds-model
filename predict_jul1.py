#!/usr/bin/env python3
"""July 1 2026 R32 predictions — England-DR Congo, Belgium-Senegal, USA-Bosnia.

Knockout profile (match_model.py --stage knockout). Weather + host handled per
match as explicit assumptions (printed). USA at Levi's = co-host home game -> Elo
bump, shown alongside the neutral baseline for contrast.
Educational/analytical use only - not betting advice.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "skill", "scripts"))
import match_model as mm  # noqa: E402
from worldcup_2026_data_ko import ELO  # noqa: E402

KO = mm.STAGE_PROFILES["knockout"]


def game(home, away, eh, ea, rain=1.0, label=""):
    lh, la = mm.elo_to_lambdas(eh, ea, avg_goals=KO["avg_goals"],
                               gd_per_100=KO["gd_per_100"])
    lh, la = lh * rain, la * rain
    style = "open" if abs(eh - ea) >= 266 else "balanced"
    P = mm.score_matrix(lh, la, opp_style=style, draw_boost=KO["draw_boost"])
    ph, pd, pa, ov, btts = mm.summarise(P)
    e = 1 / (1 + 10 ** (-(eh - ea) / 400))
    adv = mm.advancement(P, e, KO["ko_regress"], KO["pen_tilt"])
    top = sorted(P.items(), key=lambda kv: -kv[1])[:5]
    print(f"\n=== {home} v {away}  {label}")
    print(f"  Elo {eh} vs {ea} (d{eh-ea:+d})  lambda {lh:.2f}/{la:.2f}  rain x{rain}")
    print(f"  90' W/D/L : {ph*100:.1f}% / {pd*100:.1f}% / {pa*100:.1f}%")
    print(f"  ADVANCE   : {home} {adv['adv_reg']*100:.1f}% / "
          f"{away} {(1-adv['adv_reg'])*100:.1f}%")
    print(f"  O/U2.5    : Over {ov*100:.1f}% / Under {(1-ov)*100:.1f}%  BTTS {btts*100:.1f}%")
    print("  top scores: " + ", ".join(f"{i}-{j} {p*100:.1f}%" for (i, j), p in top))
    fair = (1/ph, 1/pd, 1/pa)
    mgn = [1/(x*1.05) for x in (ph, pd, pa)]
    print(f"  fair odds H {fair[0]:.2f} / D {fair[1]:.2f} / A {fair[2]:.2f}"
          f"  | +5% margin H {mgn[0]:.2f} / D {mgn[1]:.2f} / A {mgn[2]:.2f}")


# 1) England v DR Congo — Mercedes-Benz Atlanta, roof CLOSED (summer heat) = neutral indoor, dry
game("England", "DR Congo", ELO["England"], ELO["DR Congo"], rain=1.0,
     label="[Atlanta, roof closed = neutral/dry]")

# 2) Belgium v Senegal — Lumen Field Seattle, ~68F mild, dry, light wind = no weather effect
game("Belgium", "Senegal", ELO["Belgium"], ELO["Senegal"], rain=1.0,
     label="[Seattle Lumen, ~68F mild/dry = neutral]")

# 3) USA v Bosnia — Levi's Santa Clara, evening ~70F dry. USA co-host -> +85 host Elo.
print("\n--- USA v Bosnia: neutral baseline (for contrast) ---")
game("USA", "Bosnia", ELO["USA"], ELO["Bosnia"], rain=1.0,
     label="[NEUTRAL baseline, no host bump]")
print("\n--- USA v Bosnia: HOST-ADJUSTED (USA +85 Elo, de-facto home) ---")
game("USA", "Bosnia", ELO["USA"] + 85, ELO["Bosnia"], rain=1.0,
     label="[Levi's Santa Clara eve ~70F dry, USA co-host +85]")
