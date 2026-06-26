#!/usr/bin/env python3
"""Football-odds-model backtest scaffold for the next 66-game update.

This extends backtest_60.py once the six June-26 finals are confirmed and
entered in worldcup_2026_data_jun26.JUNE_26_RESULTS. Until then, it reports the
locked 60-game baseline and exits without fabricating scores.
Educational/analytical use only — not betting advice.
"""
import math

from worldcup_2026_data import ELO, HOME
from worldcup_2026_data_jun26 import JUNE_26_RESULTS, MATCHES_66


def pois(k, lam): return math.exp(-lam) * lam**k / math.factorial(k)


def negbin(k, mu, r):
    p = r / (r + mu)
    return math.exp(math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1)) * p**r * (1 - p) ** k


def dc_tau(i, j, lh, la, rho):
    if i == 0 and j == 0: return 1 - lh * la * rho
    if i == 0 and j == 1: return 1 + lh * rho
    if i == 1 and j == 0: return 1 + la * rho
    if i == 1 and j == 1: return 1 - rho
    return 1.0


def score_matrix(lh, la, n=11, rho=-0.05, opp_style="balanced", disp=5.0, draw_boost=0.08):
    fav_home = lh >= la

    def marg(k, lam, is_fav):
        if opp_style == "open" and is_fav:
            return negbin(k, lam, disp)
        return pois(k, lam)

    P, total = {}, 0.0
    for i in range(n):
        for j in range(n):
            p = marg(i, lh, fav_home) * marg(j, la, not fav_home) * dc_tau(i, j, lh, la, rho)
            P[(i, j)] = p
            total += p
    P = {k: v / total for k, v in P.items()}
    if draw_boost > 0:
        draw = sum(p for (i, j), p in P.items() if i == j)
        if 0 < draw < 1:
            target_draw = min(0.97, draw + draw_boost)
            draw_factor = target_draw / draw
            other_factor = (1 - target_draw) / (1 - draw)
            P = {(i, j): p * (draw_factor if i == j else other_factor) for (i, j), p in P.items()}
    return P


def elo_to_lambdas(eh, ea, avg_goals=2.90, gd_per_100=0.62):
    gd = (eh - ea) / 100.0 * gd_per_100
    base = avg_goals / 2.0
    return max(0.15, base + gd / 2), max(0.15, base - gd / 2)


def summarise(P):
    h = d = a = ov = 0.0
    for (i, j), p in P.items():
        if i > j:
            h += p
        elif i == j:
            d += p
        else:
            a += p
        if i + j >= 3:
            ov += p
    return h, d, a, ov


def predict(home, away, host_home, cfg):
    eh = ELO[home] + (HOME if host_home else 0)
    ea = ELO[away]
    lh, la = elo_to_lambdas(eh, ea, cfg["avg_goals"], cfg["gd_per_100"])
    style = "open" if cfg["auto_open"] and abs(eh - ea) >= cfg["open_delo"] else "balanced"
    P = score_matrix(lh, la, opp_style=style, draw_boost=cfg["draw_boost"])
    ph, pd, pa, pov = summarise(P)
    return ph, pd, pa, pov, P


def res(hg, ag): return 0 if hg > ag else (1 if hg == ag else 2)


def rps_hda(probs, result):
    pc = list(probs)
    oc = [1 if result == k else 0 for k in range(3)]
    cp = co = score = 0.0
    for k in range(2):
        cp += pc[k]
        co += oc[k]
        score += (cp - co) ** 2
    return score / 2


def tipset(h, d, a, gate):
    if d >= 0.26 and max(h, a) < gate:
        return 1
    return 0 if h > a else 2


def metrics(games, cfg):
    n = len(games)
    acc_hada = acc_arg3 = acc_rule = 0
    rps = ll = 0.0
    draws_act = 0
    dps = 0.0
    draws_picked = 0
    blow_act = 0
    blow_exp = 0.0
    brier_ou = 0.0
    ou_act = 0
    rows = []
    for home, away, hg, ag, host_home, batch in games:
        ph, pd, pa, pov, P = predict(home, away, host_home, cfg)
        r = res(hg, ag)
        am = 0 if ph > pa else 2
        arg3 = max(range(3), key=lambda k: [ph, pd, pa][k])
        acc_hada += am == r
        acc_arg3 += arg3 == r
        acc_rule += tipset(ph, pd, pa, cfg["draw_gate"]) == r
        rps += rps_hda((ph, pd, pa), r)
        ll += math.log(max(P[(hg, ag)], 1e-12))
        dps += pd
        draws_act += r == 1
        draws_picked += tipset(ph, pd, pa, cfg["draw_gate"]) == 1
        blow_act += abs(hg - ag) >= 3
        blow_exp += sum(p for (i, j), p in P.items() if abs(i - j) >= 3)
        actual_ov = 1 if (hg + ag) >= 3 else 0
        ou_act += actual_ov
        brier_ou += (pov - actual_ov) ** 2
        top = max(P.items(), key=lambda x: x[1])
        rows.append((home, away, hg, ag, ph, pd, pa, pov, top[0], P[(hg, ag)], batch))
    return dict(
        n=n,
        acc_hada=acc_hada,
        acc_arg3=acc_arg3,
        acc_rule=acc_rule,
        rps=rps / n,
        ll=ll,
        draws_act=draws_act,
        draw_prob=dps / n,
        draws_picked=draws_picked,
        blow_act=blow_act,
        blow_exp=blow_exp,
        brier_ou=brier_ou / n,
        ou_act=ou_act,
        rows=rows,
    )


V35 = dict(avg_goals=2.85, auto_open=True, open_delo=300, draw_boost=0.08, draw_gate=0.42, gd_per_100=0.60)
V36 = dict(avg_goals=2.90, auto_open=True, open_delo=266, draw_boost=0.08, draw_gate=0.42, gd_per_100=0.62)
V37A = dict(avg_goals=2.90, auto_open=True, open_delo=266, draw_boost=0.06, draw_gate=0.42, gd_per_100=0.65)


def show(title, m):
    n = m["n"]
    print(f"\n{'=' * 64}\n{title}  (n={n})\n{'=' * 64}")
    print(f"W/D/L argmax H/A-only  : {m['acc_hada']}/{n} = {m['acc_hada'] / n * 100:.0f}%")
    print(f"W/D/L true 3-way argmax: {m['acc_arg3']}/{n} = {m['acc_arg3'] / n * 100:.0f}%")
    print(f"W/D/L Tipset(draw rule): {m['acc_rule']}/{n} = {m['acc_rule'] / n * 100:.0f}%  (picked X {m['draws_picked']}x)")
    print(f"RPS (lower better)     : {m['rps']:.4f}")
    print(f"Scoreline logL (sum)   : {m['ll']:.2f}  (avg {m['ll'] / n:.3f})")
    print(f"Draws actual {m['draws_act']}/{n}={m['draws_act'] / n * 100:.1f}% | model avg draw {m['draw_prob'] * 100:.1f}%")
    print(f"Blowout net>=3 actual {m['blow_act']} | model exp {m['blow_exp']:.1f}")
    print(f"O/U2.5 Brier {m['brier_ou']:.4f} | actual over {m['ou_act']}/{n}={m['ou_act'] / n * 100:.0f}%")


def show_rows(title, games, cfg):
    print("\n" + "#" * 64)
    print(title)
    print("#" * 64)
    m = metrics(games, cfg)
    print(f"\n{'Match':28}{'Score':>6}{'  H/D/A model%':>16}{'arg':>5}{'topCS':>7}{'P(act)':>8}")
    for home, away, hg, ag, ph, pd, pa, _pov, top, pact, _batch in m["rows"]:
        r = res(hg, ag)
        arg3 = max(range(3), key=lambda k: [ph, pd, pa][k])
        hit = "OK" if arg3 == r else "X"
        print(f"{home + ' v ' + away:28}{str(hg) + '-' + str(ag):>6}{ph * 100:5.0f}/{pd * 100:3.0f}/{pa * 100:3.0f}{hit:>5}{str(top[0]) + '-' + str(top[1]):>7}{pact * 100:7.1f}%")
    show(title.replace("#", "").strip(), m)


if not JUNE_26_RESULTS:
    print("#" * 64)
    print("# June-26 results are not populated yet / 6月26日赛果尚未填入")
    print("#" * 64)
    print("JUNE_26_RESULTS is empty. Add confirmed final scores before using this as a 66-game backtest.")
    print("JUNE_26_RESULTS 为空。请先填入确认后的最终比分，再作为 66 场回测使用。")
    print("Reporting the current 60-game baseline only. / 当前仅输出 60 场基线。\n")

print("#" * 64)
print(f"# PART 1 — v3.5 / v3.6 / candidate v3.7A on {len(MATCHES_66)} played matches")
print("#" * 64)
show("v3.5 (gd .60, db .08, ag 2.85)", metrics(MATCHES_66, V35))
show("v3.6 (gd .62, db .08, ag 2.90)", metrics(MATCHES_66, V36))
show("candidate v3.7A (gd .65, db .06, ag 2.90)", metrics(MATCHES_66, V37A))

new6 = [g for g in MATCHES_66 if g[5] == 5]
if new6:
    show_rows("PART 2 — OUT-OF-SAMPLE: the 6 new Jun-26 games only (v3.7A)", new6, V37A)
else:
    print("\n" + "#" * 64)
    print("# PART 2 — OUT-OF-SAMPLE: Jun-26 batch")
    print("#" * 64)
    print("Skipped: no batch-5 games have been entered. / 已跳过：尚未录入 batch-5 比赛。")

print("\n" + "#" * 64)
print(f"# PART 3 — sweeps on {len(MATCHES_66)} games")
print("#" * 64)
print("\n[3a] gd_per_100 sweep")
print(f"{'gd/100':>10}{'RPS':>9}{'logL':>9}{'modelDraw%':>12}{'blowExp':>9}{'argmax':>8}")
for gd in [0.55, 0.60, 0.62, 0.65, 0.70, 0.75]:
    c = dict(V36)
    c["gd_per_100"] = gd
    m = metrics(MATCHES_66, c)
    print(f"{gd:>10.2f}{m['rps']:>9.4f}{m['ll']:>9.2f}{m['draw_prob'] * 100:>11.1f}%{m['blow_exp']:>9.1f}{m['acc_arg3']:>6}/{m['n']}")

print("\n[3b] draw_boost sweep")
print(f"{'draw_boost':>10}{'RPS':>9}{'logL':>9}{'modelDraw%':>12}")
for db in [0.04, 0.05, 0.06, 0.07, 0.08, 0.10]:
    c = dict(V36)
    c["draw_boost"] = db
    m = metrics(MATCHES_66, c)
    print(f"{db:>10.2f}{m['rps']:>9.4f}{m['ll']:>9.2f}{m['draw_prob'] * 100:>11.1f}%")

print("\n[3c] avg_goals sweep")
print(f"{'avg_goals':>10}{'P(over)avg':>12}{'Brier':>9}{'RPS':>9}")
for ag_ in [2.7, 2.8, 2.85, 2.9, 3.0, 3.1]:
    c = dict(V36)
    c["avg_goals"] = ag_
    m = metrics(MATCHES_66, c)
    povavg = sum(row[7] for row in m["rows"]) / m["n"]
    print(f"{ag_:>10.2f}{povavg * 100:>11.1f}%{m['brier_ou']:>9.4f}{m['rps']:>9.4f}")

print("\n[3d] worst-calibrated scorelines, candidate v3.7A")
worst = sorted(metrics(MATCHES_66, V37A)["rows"], key=lambda x: x[9])[:12]
for home, away, hg, ag, _ph, _pd, _pa, _pov, top, pact, batch in worst:
    tag = {0: "", 1: " [oos22]", 2: " [oos23]", 3: " [oos24]", 4: " [oos25]", 5: " [oos26]"}.get(batch, f" [batch{batch}]")
    print(f"  {home + ' v ' + away:28} {hg}-{ag}  P(act)={pact * 100:4.1f}%  model-top {top[0]}-{top[1]}{tag}")

print("\nEducational/analytical use only; not betting advice. / 教育/分析用途,不构成投注建议。")
