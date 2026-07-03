#!/usr/bin/env python3
"""July 3 2026 — final three R32 ties (completes R32 tonight).

  - Australia v Egypt      : AT&T Stadium, Arlington TX. Retractable roof CLOSED
                             (noon local kickoff during record central-US heat,
                             heat-index warnings) -> sealed / air-conditioned =
                             NEUTRAL, dry. Egypt patched defence -> raise AUS λ.
  - Argentina v Cabo Verde : Hard Rock, Miami Gardens FL. Canopy over SEATS only,
                             pitch OPEN. 6pm ET, hot/humid ~31C + July afternoon
                             thunderstorm risk -> heat mild x0.95 (+ rain watch).
  - Colombia v Ghana       : Arrowhead, Kansas City MO. OPEN-AIR. Daytime high
                             ~91F/33C record heat but 8:30pm LOCAL kickoff (cooler
                             evening), storms clear by ~1pm (20% PoP) -> heat mild
                             x0.95, no rain flag.

Team news (verified 2-3 Jul 2026 previews: FIFA/ESPN/Goal/Sports Mole/RotoWire):
  - Australia : full squad, no notable absences. No change.
  - Egypt     : Salah PASSED fitness test (hamstring), trained full pace ->
                AVAILABLE, no cut. BUT Fattouh (hamstring tear) OUT + Abdelmonem
                (ankle) patched -> defence weakened -> raise Australia λ x1.04.
  - Argentina : Romero fit and returns, Messi starts, no concerns. No change.
  - Cabo Verde: Arcanjo (muscle) OUT; Monteiro/Lenini fit. Thin squad -> x0.97,
                but ΔElo +495 makes it immaterial.
  - Colombia  : full projected XI, no fresh concerns. No change.
  - Ghana     : Semenyo knock but expected to start -> doubt x0.97 (half-weight
                winger). Kudus was PRE-tournament out -> already in Ghana's Elo,
                do NOT double-count.

Advancement shown TWO ways:
  (a) flat k=0.70  — the current frozen knockout default.
  (b) GRADED k     — proposed fix, k_eff = 0.70 + 0.30*min(1,|ΔElo|/350):
      huge favourites barely regress (k->1.0), coin-flips keep the full cushion.
      Validated this run on n=13 (Brier 0.1957 -> 0.1911, logLoss 0.5791->0.5643).
Educational/analytical use only - not betting advice.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "skill", "scripts"))
import match_model as mm  # noqa: E402
from worldcup_2026_data_ko import ELO  # noqa: E402

KO = mm.STAGE_PROFILES["knockout"]


def graded_k(d_elo, k_min=0.70, k_max=1.00, scale=350):
    return k_min + (k_max - k_min) * min(1.0, abs(d_elo) / scale)


def game(home, away, eh, ea, heat=None, rain=1.0, inj_h=1.0, inj_a=1.0, label=""):
    lh, la = mm.elo_to_lambdas(eh, ea, avg_goals=KO["avg_goals"],
                               gd_per_100=KO["gd_per_100"])
    hs = {"mild": 0.95, "moderate": 0.90, "severe": 0.85}.get(heat, 1.0)
    lh, la = lh * hs * rain * inj_h, la * hs * rain * inj_a
    style = "open" if abs(eh - ea) >= 266 else "balanced"
    P = mm.score_matrix(lh, la, opp_style=style, draw_boost=KO["draw_boost"])
    ph, pd, pa, ov, btts = mm.summarise(P)
    e = 1 / (1 + 10 ** (-(eh - ea) / 400))
    adv70 = mm.advancement(P, e, 0.70, KO["pen_tilt"])
    kg = graded_k(eh - ea)
    advg = mm.advancement(P, e, kg, KO["pen_tilt"])
    top = sorted(P.items(), key=lambda kv: -kv[1])[:5]
    print(f"\n=== {home} v {away}   {label}")
    print(f"  Elo {eh} vs {ea} (Δ{eh-ea:+d})  λ {lh:.2f}/{la:.2f}"
          f"  heat={heat or '-'} rain×{rain} inj {inj_h}/{inj_a}  style={style}")
    print(f"  90' W/D/L : {ph*100:.1f}% / {pd*100:.1f}% / {pa*100:.1f}%")
    print(f"  ADVANCE (flat k0.70) : {home} {adv70['adv_reg']*100:.1f}% / "
          f"{away} {(1-adv70['adv_reg'])*100:.1f}%")
    print(f"  ADVANCE (GRADED k{kg:.2f}): {home} {advg['adv_reg']*100:.1f}% / "
          f"{away} {(1-advg['adv_reg'])*100:.1f}%   (raw90 {advg['adv_raw']*100:.1f}%)")
    print(f"  O/U2.5    : Over {ov*100:.1f}% / Under {(1-ov)*100:.1f}%  BTTS {btts*100:.1f}%")
    print("  top scores: " + ", ".join(f"{i}-{j} {p*100:.1f}%" for (i, j), p in top))
    fair = (1/ph, 1/pd, 1/pa)
    mgn = [1/(x*1.05) for x in (ph, pd, pa)]
    print(f"  fair odds H {fair[0]:.2f} / D {fair[1]:.2f} / A {fair[2]:.2f}"
          f"  | +5% margin H {mgn[0]:.2f} / D {mgn[1]:.2f} / A {mgn[2]:.2f}")
    if pd >= 0.25:
        print(f"  ** PEN/ET WATCH: 90' draw {pd*100:.1f}% ≥25% → elevated "
              f"extra-time/shootout risk (favourite can be dragged to a coin-flip).")


print("#" * 68)
print("# JULY 3 2026 — final three R32 ties (R32 completes tonight → n=16)")
print("#" * 68)

# 1) Australia v Egypt — AT&T roof CLOSED = neutral/dry; Egypt defence patched.
print("\n--- Australia v Egypt: neutral baseline (full strength both) ---")
game("Australia", "Egypt", ELO["Australia"], ELO["Egypt"],
     label="[AT&T Arlington, roof CLOSED = neutral/dry]")
print("\n--- Australia v Egypt: team-news (Egypt DEF out → AUS λ ×1.04; Salah fit) ---")
game("Australia", "Egypt", ELO["Australia"], ELO["Egypt"], inj_h=1.04,
     label="[Egypt Fattouh out/Abdelmonem doubt → raise AUS λ; Salah available]")

# 2) Argentina v Cabo Verde — Miami open pitch, hot/humid + storm risk.
print("\n--- Argentina v Cabo Verde: heat mild + Cabo Verde thin (Arcanjo out) ---")
game("Argentina", "Cabo Verde", ELO["Argentina"], ELO["Cabo Verde"], heat="mild",
     inj_a=0.97, label="[Hard Rock Miami, hot/humid + PM storm watch; ΔElo +495]")

# 3) Colombia v Ghana — Arrowhead evening, mild heat; Ghana Semenyo doubt.
print("\n--- Colombia v Ghana: mild evening heat + Ghana Semenyo doubt ×0.97 ---")
game("Colombia", "Ghana", ELO["Colombia"], ELO["Ghana"], heat="mild", inj_a=0.97,
     label="[Arrowhead KC, 8:30pm eve ~28C, storms cleared; Kudus already in Elo]")
