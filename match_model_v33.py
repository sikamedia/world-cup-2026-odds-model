#!/usr/bin/env python3
"""Single-match bookmaker model — v3.3 (backtest-improved).

Pure standard library (no numpy needed). This is the v3.2 skill engine with the
THREE fixes validated by the 40-game backtest (see
`2026世界杯_回测与改进建议_到6月21日.md` and `backtest_v33.py`):

  FIX 1 — Auto blowout tail. `--opp-style` now defaults to `auto`: it turns on
          the favourite's fat right tail (negbin) automatically when the
          effective Elo gap is large (>= AUTO_OPEN_DELO, default 300), instead of
          requiring a manual `open` flag. Backtest: scoreline logL -117.6→-116.5,
          RPS 0.1639→0.1626. `balanced`/`open`/`park` still selectable manually.

  FIX 2 — Draw is reported as a probability, not force-picked. The Tipset hard
          pick now uses a TIGHT gate (DRAW_GATE = 0.42) so it only calls X on
          genuinely even games. Backtest: hard W/D/L 42%→57% (the old 0.52 gate
          over-fired, calling 20 draws for 5 hits). Draw % is still printed.

  FIX 3 — Total-goals level recalibrated. `avg_goals` base 2.6→2.8 to match the
          ~2.7-2.8 goals/game pace of 2026 and fix a systematic Over under-call
          (model gave P(Over2.5)<50% on ALL 40 games; actual 52.5% over).
          Backtest: O/U 2.5 Brier 0.2545→0.2500.

Educational/analytical use only — never betting advice.
"""
import argparse
import math

AVG_GOALS_DEFAULT = 2.8     # FIX 3 (was 2.6)
AUTO_OPEN_DELO = 300.0      # FIX 1: effective Elo gap that auto-enables open tail
DRAW_GATE = 0.42            # FIX 2 (was 0.52): tighter gate for the hard draw pick


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


def score_matrix(lh, la, n=11, rho=-0.05, opp_style="balanced", disp=5.0,
                 draw_boost=0.06):
    """Build the score matrix. opp_style fattens ONLY the favourite's
    (higher-lambda side's) right tail via negative binomial when "open".
    Resolve "auto" to "open"/"balanced" BEFORE calling this (see resolve_style).
    BACKTEST FINDING: a *global* negbin swap hurts; fattening selectively (only
    when the opponent is open/fragile, or auto on a large Elo gap) is what helps."""
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
    # Draw inflation (v3.2, backtest-validated): scale the diagonal up to add
    # `draw_boost` of probability so model draw% (~23% raw) matches the ~33%
    # actual 2026 rate. NOTE (FIX 3): this slightly suppresses Over; the
    # avg_goals 2.8 base compensates so O/U stays calibrated.
    if draw_boost > 0:
        d = sum(p for (i, j), p in P.items() if i == j)
        if 0 < d < 1:
            td = min(0.97, d + draw_boost)
            fd, fo = td / d, (1 - td) / (1 - d)
            P = {(i, j): p * (fd if i == j else fo) for (i, j), p in P.items()}
    return P


def resolve_style(opp_style, elo_gap):
    """FIX 1: turn the default `auto` into a concrete style from the effective
    Elo gap (already including home bump / adjustments). Manual park/balanced/
    open are passed through unchanged."""
    if opp_style != "auto":
        return opp_style, None
    if elo_gap is not None and abs(elo_gap) >= AUTO_OPEN_DELO:
        return "open", f"auto-open (|ΔElo|={abs(elo_gap):.0f} ≥ {AUTO_OPEN_DELO:.0f})"
    return "balanced", f"auto-balanced (|ΔElo|={abs(elo_gap):.0f} < {AUTO_OPEN_DELO:.0f})" \
        if elo_gap is not None else ("balanced", None)


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
                   gd_per_100=0.45):
    """Convert Elo (+home advantage) into home/away expected goals.
    avg_goals default 2.8 (FIX 3, was 2.6)."""
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
    ap = argparse.ArgumentParser(description="Bookmaker single-match model v3.3")
    ap.add_argument("--lh", type=float, help="home expected goals (lambda)")
    ap.add_argument("--la", type=float, help="away expected goals (lambda)")
    ap.add_argument("--elo", type=float, nargs=2, metavar=("HOME", "AWAY"),
                    help="Elo ratings; derives lambdas")
    ap.add_argument("--home", type=float, default=0.0,
                    help="home-advantage Elo bump for the home team")
    ap.add_argument("--odds", type=float, nargs=3, metavar=("H", "D", "A"),
                    help="market decimal odds for home/draw/away")
    ap.add_argument("--margin", type=float, default=0.05,
                    help="margin to add when offering odds (default 0.05)")
    ap.add_argument("--rho", type=float, default=-0.05,
                    help="Dixon-Coles rho (default -0.05)")
    ap.add_argument("--avg-goals", type=float, default=AVG_GOALS_DEFAULT,
                    dest="avg_goals",
                    help=f"baseline goals/game for Elo->lambda (default "
                         f"{AVG_GOALS_DEFAULT}; FIX 3)")
    ap.add_argument("--heat", choices=["mild", "moderate", "severe"],
                    help="hot/humid game: scale total goals 0.95/0.90/0.85")
    ap.add_argument("--rain", action="store_true",
                    help="rain: slick/low-scoring, scale total goals ~0.95")
    ap.add_argument("--inj-home", type=float, default=1.0, dest="inj_home",
                    help="multiply home lambda (e.g. 0.90 = key player out)")
    ap.add_argument("--inj-away", type=float, default=1.0, dest="inj_away",
                    help="multiply away lambda (e.g. 0.90 = key player out)")
    ap.add_argument("--opp-style",
                    choices=["auto", "park", "balanced", "open"],
                    default="auto", dest="opp_style",
                    help="underdog game-plan. DEFAULT 'auto' (FIX 1): fattens the "
                         "favourite's blowout tail automatically when the effective "
                         "Elo gap >= 300. 'open' forces it on; 'park'/'balanced' "
                         "keep pure Poisson.")
    ap.add_argument("--dispersion", type=float, default=5.0,
                    help="negbin size r for open tail (lower=fatter tail)")
    mot = ["normal", "through", "eliminated", "mustwin"]
    ap.add_argument("--mot-home", choices=mot, default="normal", dest="mot_home",
                    help="home motivation (matchday-3)")
    ap.add_argument("--mot-away", choices=mot, default="normal", dest="mot_away",
                    help="away motivation (matchday-3)")
    ap.add_argument("--draw-boost", type=float, default=0.06, dest="draw_boost",
                    help="inflate draw probability (backtest-optimal ~0.06)")
    args = ap.parse_args()

    elo_gap = None
    if args.elo:
        lh, la = elo_to_lambdas(args.elo[0], args.elo[1], args.home,
                                avg_goals=args.avg_goals)
        elo_gap = (args.elo[0] + args.home) - args.elo[1]
        E = 1 / (1 + 10 ** (-elo_gap / 400))
        print(f"Elo: home {args.elo[0]} (+{args.home}) vs away {args.elo[1]} "
              f"-> E(home, incl draw)={E:.3f}")
        print(f"Derived lambdas (avg_goals={args.avg_goals}): "
              f"home={lh:.2f}  away={la:.2f}")
    elif args.lh is not None and args.la is not None:
        lh, la = args.lh, args.la
        # infer an effective Elo gap from the lambda difference so `auto` works
        elo_gap = (lh - la) / 0.45 * 100.0
    else:
        ap.error("provide either --lh/--la or --elo HOME AWAY")

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
    mot_mult = {"normal": 1.0, "through": 0.88, "eliminated": 0.90,
                "mustwin": 1.06}
    if args.mot_home != "normal":
        lh *= mot_mult[args.mot_home]
        notes.append(f"mot-home={args.mot_home} (x{mot_mult[args.mot_home]})")
    if args.mot_away != "normal":
        la *= mot_mult[args.mot_away]
        notes.append(f"mot-away={args.mot_away} (x{mot_mult[args.mot_away]})")
    # recompute effective Elo gap from the ADJUSTED lambdas so auto-open reflects
    # injuries/motivation/weather too
    elo_gap = (lh - la) / 0.45 * 100.0
    if notes:
        print("Adjustments: " + "; ".join(notes))
        print(f"Adjusted lambdas: home={lh:.2f}  away={la:.2f}")
    print()

    style, style_note = resolve_style(args.opp_style, elo_gap)
    if style == "open":
        tag = style_note or "manual open"
        print(f"Scoreline model: favourite tail FATTENED ({tag}, "
              f"negbin r={args.dispersion}) — blowout-prone matchup")
    elif args.opp_style == "auto" and style_note:
        print(f"Scoreline model: {style_note} → plain Poisson")

    P = score_matrix(lh, la, rho=args.rho, opp_style=style,
                     disp=args.dispersion, draw_boost=args.draw_boost)
    h, d, a, ov, btts = summarise(P)

    print(f"lambda home={lh:.2f}  away={la:.2f}  (total {lh+la:.2f})")
    print(f"1X2 :  Home {h*100:.1f}%   Draw {d*100:.1f}%   Away {a*100:.1f}%")
    # FIX 2: tighter draw gate (0.42). Draw is primarily a PROBABILITY; the hard
    # pick only calls X on genuinely even games to avoid over-firing.
    if d >= 0.26 and max(h, a) < DRAW_GATE:
        pick = "X (draw / coin-flip)"
    else:
        pick = "1 (home)" if h > a else "2 (away)"
    print(f"Tipset pick: {pick}   "
          f"[draw shown as probability {d*100:.1f}%, gate<{DRAW_GATE}]")
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
