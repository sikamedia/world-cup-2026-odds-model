#!/usr/bin/env python3
"""Tournament Monte Carlo: simulate a 12-group + knockout World Cup from Elo.

Requires numpy:  pip install numpy --break-system-packages

Groups are simulated as round-robins (Poisson goals from Elo); top 2 of each
group + 8 best third-placed teams advance to a 32-team single-elimination
bracket. Knockout matches use Elo win prob regressed toward a coin-flip to add
realistic upset variance (without it, favourites are systematically over-rated).

Edit TEAMS below (or pass --json path to a [["Group","Team",elo], ...] file)
and run:  python tournament_mc.py --sims 40000
"""
import argparse
import json
import numpy as np

# (group, team, Elo) — 2026 default; replace with live ratings as needed.
TEAMS = [
    ("A", "Mexico", 1880), ("A", "South Africa", 1720),
    ("A", "Korea Republic", 1790), ("A", "Czechia", 1800),
    ("B", "Canada", 1870), ("B", "Bosnia", 1775),
    ("B", "Qatar", 1640), ("B", "Switzerland", 1891),
    ("C", "Brazil", 1991), ("C", "Morocco", 1860),
    ("C", "Haiti", 1480), ("C", "Scotland", 1780),
    ("D", "USA", 1860), ("D", "Paraguay", 1730),
    ("D", "Australia", 1720), ("D", "Turkiye", 1850),
    ("E", "Germany", 1960), ("E", "Curacao", 1500),
    ("E", "Cote d'Ivoire", 1820), ("E", "Ecuador", 1850),
    ("F", "Netherlands", 1970), ("F", "Japan", 1840),
    ("F", "Sweden", 1810), ("F", "Tunisia", 1720),
    ("G", "Belgium", 1930), ("G", "Egypt", 1628),
    ("G", "Iran", 1810), ("G", "New Zealand", 1500),
    ("H", "Spain", 2157), ("H", "Cabo Verde", 1620),
    ("H", "Saudi Arabia", 1660), ("H", "Uruguay", 1920),
    ("I", "France", 2063), ("I", "Senegal", 1880),
    ("I", "Iraq", 1620), ("I", "Norway", 1880),
    ("J", "Argentina", 2115), ("J", "Algeria", 1800),
    ("J", "Austria", 1820), ("J", "Jordan", 1640),
    ("K", "Portugal", 1989), ("K", "DR Congo", 1700),
    ("K", "Uzbekistan", 1690), ("K", "Colombia", 1982),
    ("L", "England", 2024), ("L", "Croatia", 1900),
    ("L", "Ghana", 1750), ("L", "Panama", 1640),
]


def run(teams, N=40000, seed=42, ko_damp=0.72):
    rng = np.random.default_rng(seed)
    names = [t[1] for t in teams]
    elo = np.array([t[2] for t in teams], float)
    groups = {}
    for i, (g, _, _) in enumerate(teams):
        groups.setdefault(g, []).append(i)
    glist = list(groups)

    champ = np.zeros(len(teams)); fin = np.zeros(len(teams))
    sf = np.zeros(len(teams)); qf = np.zeros(len(teams))
    r16 = np.zeros(len(teams)); r32 = np.zeros(len(teams))

    def goals(ea, eb, n):
        gd = (ea - eb) / 100.0 * 0.35
        la = np.clip(1.4 + gd / 2, 0.18, None)
        lb = np.clip(1.4 - gd / 2, 0.18, None)
        return rng.poisson(la, n), rng.poisson(lb, n)

    def ko(ia, ib, n):
        E = 1 / (1 + 10 ** (-(elo[ia] - elo[ib]) / 400))
        E = 0.5 + (E - 0.5) * ko_damp          # regress toward coin-flip
        return np.where(rng.random(n) < E, ia, ib)

    grank = {}
    t_idx, t_pts, t_gd, t_gf = [], [], [], []
    for g in glist:
        ids = groups[g]; k = len(ids)
        pts = np.zeros((k, N)); gf = np.zeros((k, N)); ga = np.zeros((k, N))
        for a in range(k):
            for b in range(a + 1, k):
                xa, xb = goals(elo[ids[a]], elo[ids[b]], N)
                gf[a] += xa; ga[a] += xb; gf[b] += xb; ga[b] += xa
                pts[a] += np.where(xa > xb, 3, np.where(xa == xb, 1, 0))
                pts[b] += np.where(xb > xa, 3, np.where(xa == xb, 1, 0))
        gd = gf - ga
        key = pts * 1e6 + gd * 1e3 + gf + rng.random((k, N)) * 0.1
        order = np.argsort(-key, axis=0)
        arr = np.array(ids)[order]
        grank[g] = arr
        t_idx.append(arr[2])
        t_pts.append(np.take_along_axis(pts, order, axis=0)[2])
        t_gd.append(np.take_along_axis(gd, order, axis=0)[2])
        t_gf.append(np.take_along_axis(gf, order, axis=0)[2])

    TI = np.array(t_idx)
    TK = (np.stack(t_pts) * 1e6 + np.stack(t_gd) * 1e3 +
          np.stack(t_gf) + rng.random((12, N)) * 0.1)
    best = np.argsort(-TK, axis=0)[:8]
    qual_third = np.take_along_axis(TI, best, axis=0)
    winners = np.stack([grank[g][0] for g in glist])
    runners = np.stack([grank[g][1] for g in glist])
    qual = np.concatenate([winners, runners, qual_third], axis=0)
    for arr in (winners, runners, qual_third):
        for row in arr:
            np.add.at(r32, row, 1)

    cur = qual.copy()
    for n in range(N):
        rng.shuffle(cur[:, n])
    tally = {16: r16, 8: qf, 4: sf, 2: fin}
    size = 32
    while size > 1:
        half = size // 2
        nxt = np.empty((half, N), int)
        for m in range(half):
            nxt[m] = ko(cur[2 * m], cur[2 * m + 1], N)
        cur = nxt; size = half
        if size in tally:
            for row in cur:
                np.add.at(tally[size], row, 1)
    for row in cur:
        np.add.at(champ, row, 1)

    order = np.argsort(-champ)
    print(f"{'Team':<15}{'Champ':>7}{'Final':>7}{'SF':>6}{'QF':>6}"
          f"{'R16':>6}{'R32':>6}")
    for i in order[:24]:
        print(f"{names[i]:<15}{champ[i]/N*100:6.1f}%{fin[i]/N*100:6.1f}%"
              f"{sf[i]/N*100:5.1f}%{qf[i]/N*100:5.1f}%"
              f"{r16[i]/N*100:5.1f}%{r32[i]/N*100:5.1f}%")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=40000)
    ap.add_argument("--json", help="path to [[group,team,elo],...] JSON")
    ap.add_argument("--damp", type=float, default=0.72,
                    help="knockout upset damping (1=pure Elo, lower=more upsets)")
    a = ap.parse_args()
    teams = json.load(open(a.json)) if a.json else TEAMS
    teams = [tuple(t) for t in teams]
    run(teams, N=a.sims, ko_damp=a.damp)
