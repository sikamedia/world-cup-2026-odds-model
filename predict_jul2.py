#!/usr/bin/env python3
"""July 2 2026 R32 predictions — Spain-Austria, Portugal-Croatia, Switzerland-Algeria.

Knockout profile (match_model.py --stage knockout). Weather + team-news handled
per match as EXPLICIT, printed assumptions (Discipline A: don't double-count what
the market already knows; Discipline B: use the day's forecast, not reputation).

Venues (all neutral — no host bump):
  - Spain v Austria      : SoFi Stadium, LA. Fixed translucent canopy = shade,
                           open sides. 12pm PT (hottest slot) but LA coastal
                           marine layer + shade -> treat as mild/neutral, dry.
  - Portugal v Croatia   : BMO Field, Toronto. OPEN-AIR. 40% showers +
                           thunderstorm risk, warm/humid ~24C, wind gust 40km/h
                           -> rain x0.95 (slick, slightly fewer goals).
  - Switzerland v Algeria: BC Place, Vancouver. Retractable roof CLOSED for ALL
                           WC matches -> sealed, weather-proof = neutral/dry.

Team news:
  - Spain : Nico Williams (adductor), Y. Pino (shoulder), V. Munoz (thigh)
            doubtful. DEEP squad; front three Yamal/Oyarzabal/Baena intact ->
            mild x0.96 (one genuine starter out, depth-scaled). Elo +337 over
            Austria = negligible impact on advancement.
  - Austria: no injury concerns, full squad. No change.
  - Switzerland: no major concerns (Widmer minor doubt). Full strength.
  - Algeria: striker Amoura highly doubtful; Mahrez/Maza/Chaibi/Gouiri front
             still available -> mild x0.97. Underdog anyway.
Educational/analytical use only - not betting advice.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "skill", "scripts"))
import match_model as mm  # noqa: E402
from worldcup_2026_data_ko import ELO  # noqa: E402

KO = mm.STAGE_PROFILES["knockout"]


def game(home, away, eh, ea, rain=1.0, inj_h=1.0, inj_a=1.0, label=""):
    lh, la = mm.elo_to_lambdas(eh, ea, avg_goals=KO["avg_goals"],
                               gd_per_100=KO["gd_per_100"])
    lh, la = lh * rain * inj_h, la * rain * inj_a
    style = "open" if abs(eh - ea) >= 266 else "balanced"
    P = mm.score_matrix(lh, la, opp_style=style, draw_boost=KO["draw_boost"])
    ph, pd, pa, ov, btts = mm.summarise(P)
    e = 1 / (1 + 10 ** (-(eh - ea) / 400))
    adv = mm.advancement(P, e, KO["ko_regress"], KO["pen_tilt"])
    top = sorted(P.items(), key=lambda kv: -kv[1])[:5]
    print(f"\n=== {home} v {away}  {label}")
    print(f"  Elo {eh} vs {ea} (d{eh-ea:+d})  lambda {lh:.2f}/{la:.2f}"
          f"  rain x{rain} inj {inj_h}/{inj_a}  style={style}")
    print(f"  90' W/D/L : {ph*100:.1f}% / {pd*100:.1f}% / {pa*100:.1f}%")
    print(f"  ADVANCE   : {home} {adv['adv_reg']*100:.1f}% / "
          f"{away} {(1-adv['adv_reg'])*100:.1f}%   (raw {adv['adv_raw']*100:.1f}%)")
    print(f"  O/U2.5    : Over {ov*100:.1f}% / Under {(1-ov)*100:.1f}%  BTTS {btts*100:.1f}%")
    print("  top scores: " + ", ".join(f"{i}-{j} {p*100:.1f}%" for (i, j), p in top))
    fair = (1/ph, 1/pd, 1/pa)
    mgn = [1/(x*1.05) for x in (ph, pd, pa)]
    print(f"  fair odds H {fair[0]:.2f} / D {fair[1]:.2f} / A {fair[2]:.2f}"
          f"  | +5% margin H {mgn[0]:.2f} / D {mgn[1]:.2f} / A {mgn[2]:.2f}")
    if pd >= 0.25:
        print(f"  ** PEN/ET WATCH: 90' draw {pd*100:.1f}% >=25% -> elevated "
              f"extra-time/shootout risk (fav can be dragged to a coin-flip).")


# 1) Spain v Austria — SoFi LA, canopy shade/dry = neutral. Spain mild injury.
print("--- Spain v Austria: neutral baseline (full strength) ---")
game("Spain", "Austria", ELO["Spain"], ELO["Austria"], rain=1.0,
     label="[SoFi LA, canopy shade/dry = neutral]")
print("\n--- Spain v Austria: team-news adjusted (Spain x0.96, N.Williams out) ---")
game("Spain", "Austria", ELO["Spain"], ELO["Austria"], rain=1.0, inj_h=0.96,
     label="[Spain x0.96 depth-scaled; call unchanged]")

# 2) Portugal v Croatia — BMO Toronto, open-air, showers/storm risk -> rain x0.95
game("Portugal", "Croatia", ELO["Portugal"], ELO["Croatia"], rain=0.95,
     label="[BMO Toronto, 40% showers + storm risk, rain x0.95]")

# 3) Switzerland v Algeria — BC Place roof CLOSED = neutral/dry. Algeria x0.97.
print("\n--- Switzerland v Algeria: neutral baseline ---")
game("Switzerland", "Algeria", ELO["Switzerland"], ELO["Algeria"], rain=1.0,
     label="[BC Place Vancouver, roof closed = neutral/dry]")
print("\n--- Switzerland v Algeria: team-news adjusted (Algeria x0.97, Amoura doubt) ---")
game("Switzerland", "Algeria", ELO["Switzerland"], ELO["Algeria"], rain=1.0,
     inj_a=0.97, label="[Algeria x0.97; call unchanged]")
