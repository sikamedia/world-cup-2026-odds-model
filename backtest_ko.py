#!/usr/bin/env python3
"""Knockout-stage backtest — SEPARATE batch from the 72 group-stage games.

Mirrors backtest_72.py's metrics (RPS / Tipset / draw / big-win) but runs on the
knockout profile (lower avg_goals, advancement resolver) over KO_RESULTS only.
It reuses the validated engine from skill/scripts/match_model.py — one source of
truth, no duplicated scoring code.

DISCIPLINE: do NOT tune knockout params on a handful of games. R32 is only 16
matches; treat the knockout profile (avg_goals~2.70) as a market-anchored prior
until the sample is large enough to mean something. No motivation/rotation in
the knockouts (everyone is full strength).

Run:  python3 backtest_ko.py
Educational/analytical use only - not betting advice.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "skill", "scripts"))
import match_model as mm  # noqa: E402

from worldcup_2026_data_ko import ELO, HOME, KO_RESULTS  # noqa: E402,F401

KO = mm.STAGE_PROFILES["knockout"]


def res(hg, ag):
    return 0 if hg > ag else (1 if hg == ag else 2)


def rps_hda(probs, result):
    oc = [1 if result == k else 0 for k in range(3)]
    cp = co = score = 0.0
    for k in range(2):
        cp += probs[k]
        co += oc[k]
        score += (cp - co) ** 2
    return score / 2


def predict(home, away):
    """Neutral-venue knockout prediction (no host bump, no motivation).
    Returns 90' probs, the score matrix, the Elo home win-expectation, and the
    advancement dict at the profile's ko_regress."""
    eh, ea = ELO[home], ELO[away]
    lh, la = mm.elo_to_lambdas(eh, ea, avg_goals=KO["avg_goals"],
                               gd_per_100=KO["gd_per_100"])
    style = "open" if abs(eh - ea) >= 266 else "balanced"
    P = mm.score_matrix(lh, la, opp_style=style, draw_boost=KO["draw_boost"])
    ph, pd, pa, _ov, _btts = mm.summarise(P)
    e_home = 1 / (1 + 10 ** (-(eh - ea) / 400))
    adv = mm.advancement(P, e_home, KO["ko_regress"], KO["pen_tilt"])
    return ph, pd, pa, P, e_home, adv


def adv_metrics(records, k):
    """Advancement Brier, log-loss, and expected upsets at a given ko_regress k.
    Favourite/underdog are defined by Elo (k-independent), so expected-upsets is
    comparable across k and against the fixed actual count. `records` items are
    (P, e_home, advanced)."""
    brier = ll = exp_ups = 0.0
    for P, e_home, advanced in records:
        p_home = mm.advancement(P, e_home, k, KO["pen_tilt"])["adv_reg"]
        o = 1.0 if advanced == "H" else 0.0
        brier += (p_home - o) ** 2
        ll += -(o * math.log(max(p_home, 1e-12))
                + (1 - o) * math.log(max(1 - p_home, 1e-12)))
        exp_ups += (1 - p_home) if e_home >= 0.5 else p_home  # P(Elo-underdog)
    m = len(records)
    return brier / m, ll / m, exp_ups


def main():
    games = KO_RESULTS
    n = len(games)
    print("#" * 64)
    print(f"# KNOCKOUT BACKTEST — {n} game(s)  (profile: avg_goals "
          f"{KO['avg_goals']}, ko_regress {KO['ko_regress']})")
    print("#" * 64)
    if n == 0:
        print("\nNo knockout results recorded yet. Append rows to KO_RESULTS in "
              "worldcup_2026_data_ko.py as games finish, then re-run.")
        ph, pd, pa, _P, _e, adv = predict("South Africa", "Canada")
        print("\nPipeline smoke-test (South Africa vs Canada, not yet played):")
        print(f"  90' W/D/L : {ph*100:.1f}% / {pd*100:.1f}% / {pa*100:.1f}%")
        print(f"  ADVANCE   : SA raw {adv['adv_raw']*100:.1f}% / "
              f"regressed {adv['adv_reg']*100:.1f}%  |  "
              f"Canada raw {(1-adv['adv_raw'])*100:.1f}% / "
              f"regressed {(1-adv['adv_reg'])*100:.1f}%")
        return

    # 90' scoreline metrics (independent of ko_regress) + per-tie advancement.
    rps = ll90 = dps = 0.0
    dir_hit = draws_act = blow_act = act_ups = adv_hit = 0
    blow_exp = 0.0
    records = []                       # (P, e_home, advanced)
    print(f"\n{'Tie':30}{'90':>5}   model advancement -> actual")
    for home, away, hg, ag, advanced, _stage in games:
        ph, pd, pa, P, e_home, adv = predict(home, away)
        r = res(hg, ag)
        rps += rps_hda((ph, pd, pa), r)
        ll90 += math.log(max(P[(hg, ag)], 1e-12))
        dps += pd
        dir_hit += max(range(3), key=lambda k: [ph, pd, pa][k]) == r
        draws_act += r == 1
        blow_act += abs(hg - ag) >= 3
        blow_exp += sum(p for (i, j), p in P.items() if abs(i - j) >= 3)
        records.append((P, e_home, advanced))
        p_home = adv["adv_reg"]
        fav_name, fav_p = (home, p_home) if p_home >= 0.5 else (away, 1 - p_home)
        act_name = home if advanced == "H" else away
        adv_hit += (p_home >= 0.5) == (advanced == "H")
        upset = (advanced == "H") != (e_home >= 0.5)   # Elo-underdog advanced
        act_ups += upset
        print(f"{(home[:13] + ' v ' + away[:13]):30}{f'{hg}-{ag}':>5}   "
              f"adv {fav_name[:12]} {fav_p*100:2.0f}% -> {act_name[:12]}"
              f"  {'UPSET' if upset else 'ok'}")

    print(f"\n90' scoreline: RPS {rps/n:.4f} | logL {ll90:.2f} "
          f"(avg {ll90/n:.3f}) | dir {dir_hit}/{n} | draws {draws_act}/{n} "
          f"| blowout>=3 {blow_act} (model exp {blow_exp:.1f})")

    b70, l70, e70 = adv_metrics(records, KO["ko_regress"])
    print(f"\nADVANCEMENT (k={KO['ko_regress']}):  called-right {adv_hit}/{n}  |  "
          f"Brier {b70:.4f}  |  log-loss {l70:.4f}")
    print(f"  upsets: actual {act_ups}  vs  model-expected {e70:.2f}")

    ks = [0.60, 0.70, 0.85, 1.00]
    print(f"\nk-sensitivity (advancement; n={n} — DIRECTION ONLY, not a refit):")
    print(f"  {'k':>5}{'Brier':>9}{'logLoss':>9}{'expUps':>9}   (actual ups {act_ups})")
    briers = {}
    for k in ks:
        b, l, e = adv_metrics(records, k)
        briers[k] = b
        print(f"  {k:>5.2f}{b:>9.4f}{l:>9.4f}{e:>9.2f}")
    best_k = min(briers, key=briers.get)

    print("\nVERDICT:")
    tone = "MORE" if act_ups > e70 else ("LESS" if act_ups < e70 else "as")
    print(f"  reality was {tone} upset-heavy than the regressed model "
          f"(actual {act_ups} vs {e70:.2f} expected at k=0.70).")
    print(f"  best-Brier k among {ks} = {best_k}  (n={n}, high variance).")
    if best_k <= 0.70 or act_ups >= e70:
        print("  => k=0.70 is NOT over-regressing — the original 'favourites are "
              "under-rated' hypothesis is contradicted; if anything the data "
              "leans to MORE regression. HOLD 0.70 (do not refit on n=7); "
              "revisit after R16.")
    else:
        print("  => data leans to LESS regression; consider a small, provisional "
              "nudge up, but HOLD until R16 accumulates (n too small to refit).")
    print("\nEducational/analytical use only; not betting advice.")


if __name__ == "__main__":
    main()
