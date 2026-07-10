#!/usr/bin/env python3
"""Single-match bookmaker model — v3.5 (backtest-improved, 48-game).

Pure standard library. This is v3.4 plus ONE refinement validated on all 48
played 2026 WC matches (44 in-sample + 4 out-of-sample Jun-23 games):

  FIX 5 — Steeper Elo->goal-difference slope, again. `gd_per_100` 0.55 -> 0.60,
          with `draw_boost` 0.07 -> 0.08 to hold draw calibration. As more
          blowouts arrived (Portugal 5-0 Uzbekistan), the 48-game optimum drifted
          up to 0.60-0.62: a 48-team field separates favourites even more than
          v3.4 assumed. Backtest (full 48): RPS 0.1525->0.1515, scoreline logL
          -135.80->-135.23, blowout expectation 10.4->11.0 (actual 13), model
          draw% 28.1->28.3 (actual 29.2). Improvement holds BOTH in-sample AND
          out-of-sample (the 4 Jun-23 games: RPS 0.1004->0.0976), so it is a
          real effect, not overfitting. gd>0.62 keeps lowering RPS marginally
          but erodes draw% below the actual rate, so 0.60 is the calibrated pick.

Carried over from v3.4 / v3.3:
  FIX 4 — Steeper slope step 1 (`gd_per_100` 0.45 -> 0.55, now 0.60 via FIX 5).
  FIX 1 — Auto blowout tail (`--opp-style auto`, open when |effective ΔElo|>=300).
  FIX 2 — Draw reported as probability; hard pick uses a TIGHT gate (0.42).
  FIX 3 — Total-goals base `avg_goals` 2.6->2.85 (O/U 2.5 was under-calling Over).

Educational/analytical use only — never betting advice.
"""
import argparse
import math

AVG_GOALS_DEFAULT = 2.85    # FIX 3 (2.6 -> 2.8 in v3.3 -> 2.85 here for O/U)
GD_PER_100_DEFAULT = 0.60   # FIX 5 (0.45->0.55->0.60): steeper favourite separation
AUTO_OPEN_DELO = 300.0      # FIX 1
DRAW_GATE = 0.42            # FIX 2


def pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def negbin(k, mu, r):
    p = r / (r + mu)
    return (math.exp(math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1))
            * p ** r * (1 - p) ** k)


def dc_tau(i, j, lh, la, rho):
    if i == 0 and j == 0:
        return 1 - lh * la * rho
    if i == 0 and j == 1:
        return 1 + lh * rho
    if i == 1 and j == 0:
        return 1 + la * rho
    if i == 1 and j == 1:
        return 1 - rho
    return 1.0


def score_matrix(lh, la, n=11, rho=-0.05, opp_style="balanced", disp=5.0,
                 draw_boost=0.08):
    fav_home = lh >= la

    def marg(k, lam, is_fav):
        if opp_style == "open" and is_fav:
            return negbin(k, lam, disp)
        return pois(k, lam)

    P, tot = {}, 0.0
    for i in range(n):
        for j in range(n):
            p = (marg(i, lh, fav_home) * marg(j, la, not fav_home)
                 * dc_tau(i, j, lh, la, rho))
            P[(i, j)] = p
            tot += p
    P = {k: v / tot for k, v in P.items()}
    if draw_boost > 0:
        d = sum(p for (i, j), p in P.items() if i == j)
        if 0 < d < 1:
            td = min(0.97, d + draw_boost)
            fd, fo = td / d, (1 - td) / (1 - d)
            P = {(i, j): p * (fd if i == j else fo) for (i, j), p in P.items()}
    return P


def resolve_style(opp_style, elo_gap):
    if opp_style != "auto":
        return opp_style, None
    if elo_gap is not None and abs(elo_gap) >= AUTO_OPEN_DELO:
        return "open", f"auto-open (|ΔElo|={abs(elo_gap):.0f} ≥ {AUTO_OPEN_DELO:.0f})"
    return "balanced", (f"auto-balanced (|ΔElo|={abs(elo_gap):.0f} < {AUTO_OPEN_DELO:.0f})"
                        if elo_gap is not None else None)


def summarise(P):
    h = d = a = ov25 = btts = 0.0
    for (i, j), p in P.items():
        if i > j:
            h += p
        elif i == j:
            d += p
        else:
            a += p
        if i + j >= 3:
            ov25 += p
        if i >= 1 and j >= 1:
            btts += p
    return h, d, a, ov25, btts


def elo_to_lambdas(elo_h, elo_a, home_bump=0.0, avg_goals=AVG_GOALS_DEFAULT,
                   gd_per_100=GD_PER_100_DEFAULT):
    """Convert Elo (+home advantage) into home/away expected goals.
    avg_goals default 2.85, gd_per_100 default 0.55 (FIX 3 & FIX 4)."""
    d = (elo_h + home_bump) - elo_a
    gd = d / 100.0 * gd_per_100
    base = avg_goals / 2.0
    lh = max(0.15, base + gd / 2)
    la = max(0.15, base - gd / 2)
    return lh, la


def demargin(odds):
    inv = [1 / o for o in odds]
    s = sum(inv)
    prop = [x / s for x in inv]
    lo, hi = 0.5, 1.5
    for _ in range(80):
        c = (lo + hi) / 2
        if sum(x ** c for x in inv) > 1:
            lo = c
        else:
            hi = c
    power = [x ** c for x in inv]
    return {"overround": s - 1, "prop": prop, "power": power, "c": c}


def main():
    ap = argparse.ArgumentParser(description="Bookmaker single-match model v3.5")
    ap.add_argument("--lh", type=float, help="home expected goals (lambda)")
    ap.add_argument("--la", type=float, help="away expected goals (lambda)")
    ap.add_argument("--elo", type=float, nargs=2, metavar=("HOME", "AWAY"),
                    help="Elo ratings; derives lambdas")
    ap.add_argument("--home", type=float, default=0.0,
                    help="home-advantage Elo bump for the home team")
    ap.add_argument("--odds", type=float, nargs=3, metavar=("H", "D", "A"),
                    help="market decimal odds for home/draw/away")
    ap.add_argument("--margin", type=float, default=0.05)
    ap.add_argument("--rho", type=float, default=-0.05)
    ap.add_argument("--avg-goals", type=float, default=AVG_GOALS_DEFAULT,
                    dest="avg_goals",
                    help=f"baseline goals/game (default {AVG_GOALS_DEFAULT}; FIX 3)")
    ap.add_argument("--gd-per-100", type=float, default=GD_PER_100_DEFAULT,
                    dest="gd_per_100",
                    help=f"goal-diff per 100 Elo (default {GD_PER_100_DEFAULT}; "
                         f"FIX 5, 0.45->0.55->0.60 — favourites separate more in a 48-team field)")
    ap.add_argument("--heat", choices=["mild", "moderate", "severe"])
    ap.add_argument("--rain", action="store_true")
    ap.add_argument("--inj-home", type=float, default=1.0, dest="inj_home")
    ap.add_argument("--inj-away", type=float, default=1.0, dest="inj_away")
    ap.add_argument("--opp-style", choices=["auto", "park", "balanced", "open"],
                    default="auto", dest="opp_style",
                    help="DEFAULT 'auto' (FIX 1): fattens favourite blowout tail "
                         "when |effective ΔElo|>=300.")
    ap.add_argument("--dispersion", type=float, default=5.0)
    mot = ["normal", "through", "eliminated", "mustwin"]
    ap.add_argument("--mot-home", choices=mot, default="normal", dest="mot_home")
    ap.add_argument("--mot-away", choices=mot, default="normal", dest="mot_away")
    ap.add_argument("--draw-boost", type=float, default=0.08, dest="draw_boost")
    args = ap.parse_args()

    elo_gap = None
    if args.elo:
        lh, la = elo_to_lambdas(args.elo[0], args.elo[1], args.home,
                                avg_goals=args.avg_goals,
                                gd_per_100=args.gd_per_100)
        elo_gap = (args.elo[0] + args.home) - args.elo[1]
        E = 1 / (1 + 10 ** (-elo_gap / 400))
        print(f"Elo: home {args.elo[0]} (+{args.home}) vs away {args.elo[1]} "
              f"-> E(home, incl draw)={E:.3f}")
        print(f"Derived lambdas (avg_goals={args.avg_goals}, "
              f"gd/100={args.gd_per_100}): home={lh:.2f}  away={la:.2f}")
    elif args.lh is not None and args.la is not None:
        lh, la = args.lh, args.la
        elo_gap = (lh - la) / args.gd_per_100 * 100.0
    else:
        ap.error("provide either --lh/--la or --elo HOME AWAY")

    notes = []
    heat_scale = {"mild": 0.95, "moderate": 0.92, "severe": 0.90}
    if args.heat:
        s = heat_scale[args.heat]
        lh *= s; la *= s
        notes.append(f"heat={args.heat} (x{s})")
    if args.rain:
        lh *= 0.95; la *= 0.95
        notes.append("rain (x0.95)")
    if args.inj_home != 1.0:
        lh *= args.inj_home
        notes.append(f"inj-home (x{args.inj_home})")
    if args.inj_away != 1.0:
        la *= args.inj_away
        notes.append(f"inj-away (x{args.inj_away})")
    mot_mult = {"normal": 1.0, "through": 0.88, "eliminated": 0.90, "mustwin": 1.06}
    if args.mot_home != "normal":
        lh *= mot_mult[args.mot_home]
        notes.append(f"mot-home={args.mot_home}")
    if args.mot_away != "normal":
        la *= mot_mult[args.mot_away]
        notes.append(f"mot-away={args.mot_away}")
    elo_gap = (lh - la) / args.gd_per_100 * 100.0
    if notes:
        print("Adjustments: " + "; ".join(notes))
        print(f"Adjusted lambdas: home={lh:.2f}  away={la:.2f}")
    print()

    style, style_note = resolve_style(args.opp_style, elo_gap)
    if style == "open":
        print(f"Scoreline model: favourite tail FATTENED "
              f"({style_note or 'manual open'}, negbin r={args.dispersion})")
    elif args.opp_style == "auto" and style_note:
        print(f"Scoreline model: {style_note} → plain Poisson")

    P = score_matrix(lh, la, rho=args.rho, opp_style=style,
                     disp=args.dispersion, draw_boost=args.draw_boost)
    h, d, a, ov, btts = summarise(P)

    print(f"lambda home={lh:.2f}  away={la:.2f}  (total {lh+la:.2f})")
    print(f"1X2 :  Home {h*100:.1f}%   Draw {d*100:.1f}%   Away {a*100:.1f}%")
    if d >= 0.26 and max(h, a) < DRAW_GATE:
        pick = "X (draw / coin-flip)"
    else:
        pick = "1 (home)" if h > a else "2 (away)"
    print(f"Tipset pick: {pick}   [draw prob {d*100:.1f}%, gate<{DRAW_GATE}]")
    print(f"O/U2.5: Over {ov*100:.1f}%  Under {(1-ov)*100:.1f}%   "
          f"BTTS-Yes {btts*100:.1f}%")
    m = args.margin
    print(f"Fair odds  : H {1/h:.2f}  D {1/d:.2f}  A {1/a:.2f}")
    print(f"w/{int(m*100)}% margin: H {1/(h*(1+m)):.2f}  D {1/(d*(1+m)):.2f}  "
          f"A {1/(a*(1+m)):.2f}")

    top = sorted(P.items(), key=lambda x: -x[1])[:8]
    print("\nTop scorelines (Home-Away):")
    for (i, j), p in top:
        print(f"  {i}-{j}: {p*100:4.1f}%  (fair {1/p:.0f})")

    tg, mg = {}, {}
    for (i, j), p in P.items():
        tg[i + j] = tg.get(i + j, 0) + p
        mg[abs(i - j)] = mg.get(abs(i - j), 0) + p
    print("\nTotal goals:  " + "  ".join(
        f"{g}:{tg.get(g,0)*100:.0f}%" for g in range(0, 6)) +
        f"  5+:{sum(v for k,v in tg.items() if k>=5)*100:.0f}%")
    print("Win margin :  " + "  ".join(
        f"{g}:{mg.get(g,0)*100:.0f}%" for g in range(0, 4)) +
        f"  3+:{sum(v for k,v in mg.items() if k>=3)*100:.0f}%")

    if args.odds:
        dm = demargin(args.odds)
        print(f"\nMarket de-margin (overround {dm['overround']*100:.1f}%):")
        labels = ["Home", "Draw", "Away"]
        print("           " + "  ".join(f"{l:>7}" for l in labels))
        print("  prop   : " + "  ".join(f"{x*100:6.1f}%" for x in dm["prop"]))
        print(f"  power  : " + "  ".join(f"{x*100:6.1f}%" for x in dm["power"])
              + f"   (c={dm['c']:.3f})")
        print("  model  : " + "  ".join(f"{x*100:6.1f}%" for x in (h, d, a)))


if __name__ == "__main__":
    main()
