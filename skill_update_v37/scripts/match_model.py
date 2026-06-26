#!/usr/bin/env python3
"""Single-match bookmaker model: Poisson + Dixon-Coles, market de-margin.

Pure standard library (no numpy needed).

Examples
--------
# From lambdas + market odds (decimal):
python match_model.py --lh 1.95 --la 0.85 --odds 1.53 4.25 6.70

# Derive lambdas from Elo (with optional home-advantage Elo bump for home team):
python match_model.py --elo 1891 1775 --home 85 --odds 1.53 4.25 6.70

# Just the model, no market:
python match_model.py --lh 1.45 --la 0.90
"""
import argparse
import math


def pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def negbin(k, mu, r):
    """Negative-binomial pmf, mean mu, size r. var = mu + mu^2/r.
    r->inf approaches Poisson. Used to fatten the favourite's right tail
    when the opponent will open the game up (see --opp-style open)."""
    p = r / (r + mu)
    return (math.exp(math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1))
            * p ** r * (1 - p) ** k)


def dc_tau(i, j, lh, la, rho):
    """Dixon-Coles low-score correction."""
    if i == 0 and j == 0:
        return 1 - lh * la * rho
    if i == 0 and j == 1:
        return 1 + lh * rho
    if i == 1 and j == 0:
        return 1 + la * rho
    if i == 1 and j == 1:
        return 1 - rho
    return 1.0


def score_matrix(lh, la, n=11, rho=-0.05, opp_style="auto", disp=5.0,
                 draw_boost=0.06):
    """Build the score matrix. opp_style fattens ONLY the favourite's
    (higher-lambda side's) right tail via negative binomial when "open".
    BACKTEST FINDING: a *global* negbin swap hurts (it spreads mass off the
    common small scores the Poisson already nails). Fattening selectively,
    only when the opponent is flagged open/fragile pre-match, is what improves
    calibration. So "open" is opt-in, default is plain Poisson."""
    fav_home = lh >= la
    # v3.4 FIX 1: opp-style "auto" fattens the favourite tail when the gap is
    # large (|lambda_h - lambda_a| >= 1.65 ~ effective dElo >= 300 at gd 0.55).
    auto_open = opp_style == "auto" and abs(lh - la) >= 1.65
    use_open = opp_style == "open" or auto_open

    def marg(k, lam, is_fav):
        if use_open and is_fav:
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
    # Draw inflation (v3.2, backtest-validated): independent Poisson puts ~22%
    # on draws but 2026 actual draw rate is ~33% (RPS 0.1653->0.1640 with a
    # +6% boost). Real teams draw more than independent goals imply (cagey play,
    # game state). Scale the diagonal up to add `draw_boost` of probability.
    if draw_boost > 0:
        d = sum(p for (i, j), p in P.items() if i == j)
        if 0 < d < 1:
            td = min(0.97, d + draw_boost)
            fd, fo = td / d, (1 - td) / (1 - d)
            P = {(i, j): p * (fd if i == j else fo) for (i, j), p in P.items()}
    return P


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


def elo_to_lambdas(elo_h, elo_a, home_bump=0.0, avg_goals=2.90,
                   gd_per_100=0.65):
    """Convert Elo (+home advantage) into home/away expected goals."""
    d = (elo_h + home_bump) - elo_a
    gd = d / 100.0 * gd_per_100          # expected goal difference
    base = avg_goals / 2.0
    lh = max(0.15, base + gd / 2)
    la = max(0.15, base - gd / 2)
    return lh, la


def demargin(odds):
    """Proportional + power de-margin of 1X2 decimal odds. Returns dict."""
    inv = [1 / o for o in odds]
    s = sum(inv)
    prop = [x / s for x in inv]
    # power: find c so sum((1/odds)^c) == 1
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
    ap = argparse.ArgumentParser(description="Bookmaker single-match model")
    ap.add_argument("--lh", type=float, help="home expected goals (lambda)")
    ap.add_argument("--la", type=float, help="away expected goals (lambda)")
    ap.add_argument("--elo", type=float, nargs=2, metavar=("HOME", "AWAY"),
                    help="Elo ratings; derives lambdas")
    ap.add_argument("--home", type=float, default=0.0,
                    help="home-advantage Elo bump for the home team")
    ap.add_argument("--odds", type=float, nargs=3,
                    metavar=("H", "D", "A"),
                    help="market decimal odds for home/draw/away")
    ap.add_argument("--margin", type=float, default=0.05,
                    help="margin to add when offering odds (default 0.05)")
    ap.add_argument("--rho", type=float, default=-0.05,
                    help="Dixon-Coles rho (default -0.05)")
    # v3.4 engine params (used when deriving lambda from --elo)
    ap.add_argument("--gd-per-100", type=float, default=0.65, dest="gd_per_100",
                    help="Elo->goal-diff slope (v3.6 default 0.65; FIX 4->6)")
    ap.add_argument("--avg-goals", type=float, default=2.90, dest="avg_goals",
                    help="baseline goals/game (v3.6 default 2.90; FIX 3->6)")
    # --- adjustment flags (applied AFTER lambdas are set) ---
    ap.add_argument("--heat", choices=["mild", "moderate", "severe"],
                    help="hot/humid game: scale total goals 0.95/0.90/0.85")
    ap.add_argument("--rain", action="store_true",
                    help="rain: slick/low-scoring, scale total goals ~0.95")
    ap.add_argument("--inj-home", type=float, default=1.0, dest="inj_home",
                    help="multiply home lambda (e.g. 0.90 = key player out)")
    ap.add_argument("--inj-away", type=float, default=1.0, dest="inj_away",
                    help="multiply away lambda (e.g. 0.90 = key player out)")
    ap.add_argument("--opp-style", choices=["auto", "park", "balanced", "open"],
                    default="auto", dest="opp_style",
                    help="underdog game-plan (v3.4 default 'auto': fatten the "
                         "favourite tail when |lh-la|>=1.65 ~ dElo>=300). 'open' "
                         "forces it; 'park'/'balanced' keep Poisson.")
    ap.add_argument("--dispersion", type=float, default=5.0,
                    help="negbin size r for --opp-style open (lower=fatter tail)")
    mot = ["normal", "through", "eliminated", "mustwin"]
    ap.add_argument("--mot-home", choices=mot, default="normal", dest="mot_home",
                    help="home motivation (matchday-3): through/eliminated lower "
                         "lambda (rotation/low stakes), mustwin raises it")
    ap.add_argument("--mot-away", choices=mot, default="normal", dest="mot_away",
                    help="away motivation (see --mot-home)")
    ap.add_argument("--draw-boost", type=float, default=0.06, dest="draw_boost",
                    help="inflate draw probability (v3.4 default 0.07; FIX 4b; "
                         "0 = pure Poisson). Corrects Poisson's draw under-count.")
    args = ap.parse_args()

    if args.elo:
        lh, la = elo_to_lambdas(args.elo[0], args.elo[1], args.home,
                                avg_goals=args.avg_goals,
                                gd_per_100=args.gd_per_100)
        E = 1 / (1 + 10 ** (-((args.elo[0] + args.home) - args.elo[1]) / 400))
        print(f"Elo: home {args.elo[0]} (+{args.home}) vs away {args.elo[1]} "
              f"-> E(home, incl draw)={E:.3f}")
        print(f"Derived lambdas: home={lh:.2f}  away={la:.2f}")
    elif args.lh is not None and args.la is not None:
        lh, la = args.lh, args.la
    else:
        ap.error("provide either --lh/--la or --elo HOME AWAY")

    # apply adjustments (see SKILL.md Discipline A: put these on the
    # Elo-derived lambda, then compare to market — do not double-count)
    notes = []
    heat_scale = {"mild": 0.95, "moderate": 0.90, "severe": 0.85}
    if args.heat:
        s = heat_scale[args.heat]
        lh *= s; la *= s
        notes.append(f"heat={args.heat} (x{s} total goals)")
    if args.rain:
        lh *= 0.95; la *= 0.95
        notes.append("rain (x0.95 total goals)")
    if args.inj_home != 1.0:
        lh *= args.inj_home
        notes.append(f"inj-home (home lambda x{args.inj_home})")
    if args.inj_away != 1.0:
        la *= args.inj_away
        notes.append(f"inj-away (away lambda x{args.inj_away})")
    # matchday-3 motivation: qualified side rotates, eliminated downs tools,
    # must-win side lifts intensity (apply to Elo-derived lambda; see Disc. A)
    mot_mult = {"normal": 1.0, "through": 0.88, "eliminated": 0.90,
                "mustwin": 1.06}
    if args.mot_home != "normal":
        lh *= mot_mult[args.mot_home]
        notes.append(f"mot-home={args.mot_home} (x{mot_mult[args.mot_home]})")
    if args.mot_away != "normal":
        la *= mot_mult[args.mot_away]
        notes.append(f"mot-away={args.mot_away} (x{mot_mult[args.mot_away]})")
    if notes:
        print("Adjustments: " + "; ".join(notes))
        print(f"Adjusted lambdas: home={lh:.2f}  away={la:.2f}")
    print()

    if args.opp_style == "open" or (args.opp_style == "auto"
                                    and abs(lh - la) >= 1.65):
        print(f"Scoreline model: favourite tail FATTENED ("
              f"opp-style={args.opp_style}, negbin r={args.dispersion}) — "
              f"large gap / blowout-prone")

    P = score_matrix(lh, la, rho=args.rho,
                     opp_style=args.opp_style, disp=args.dispersion,
                     draw_boost=args.draw_boost)
    h, d, a, ov, btts = summarise(P)

    print(f"lambda home={lh:.2f}  away={la:.2f}  (total {lh+la:.2f})")
    print(f"1X2 :  Home {h*100:.1f}%   Draw {d*100:.1f}%   Away {a*100:.1f}%")
    # Tipset 1X2 pick with a DRAW rule. Plain argmax never picks the draw
    # (draw is rarely the single max), yet ~31% of 2026 games drew. Rule:
    # call X for genuinely even games (no side >52% and draw not negligible).
    # NOTE (validated by backtest): this only catches "evenly-matched" draws;
    # it cannot catch a clear favourite being held by a low block (the bulk of
    # 2026's draws) — that's irreducible variance.
    if d >= 0.26 and max(h, a) < 0.42:   # v3.4 FIX 2: gate 0.52 -> 0.42
        pick = "X (draw / coin-flip)"
    else:
        pick = "1 (home)" if h > a else "2 (away)"
    print(f"Tipset pick: {pick}")
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

    # total goals + margin distributions ("会不会有大比分")
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
    print(f"Blowout (margin>=3): {sum(v for k,v in mg.items() if k>=3)*100:.1f}%")

    if args.odds:
        dm = demargin(args.odds)
        print(f"\nMarket de-margin (overround {dm['overround']*100:.1f}%):")
        labels = ["Home", "Draw", "Away"]
        print("           " + "  ".join(f"{l:>7}" for l in labels))
        print("  prop   : " + "  ".join(f"{x*100:6.1f}%" for x in dm["prop"]))
        print(f"  power  : " + "  ".join(f"{x*100:6.1f}%" for x in dm["power"])
              + f"   (c={dm['c']:.3f})")
        print("  model  : " + "  ".join(
            f"{x*100:6.1f}%" for x in (h, d, a)))


if __name__ == "__main__":
    main()
