#!/usr/bin/env python3
"""模型迭代回测:Poisson vs 全局负二项 vs 选择性加尾(v3 --opp-style open)。

用复盘的 10 场预测(赛前 lambda + 真实比分),比较三种比分分布对真实结果的
拟合度(总对数似然越高=真实结果在模型下越可能=校准越好)。

结论:全局负二项反而变差;只在赛前判断对手"打开比赛"时选择性加尾,才有效。
教育/分析用途,不构成投注建议。
"""
from math import lgamma, log, exp, factorial


def pois(k, mu):
    return exp(-mu) * mu ** k / factorial(k)


def negbin(k, mu, r):
    p = r / (r + mu)
    return exp(lgamma(k + r) - lgamma(r) - lgamma(k + 1)) * p ** r * (1 - p) ** k


# name, lam_fav, lam_dog, fav_goals, dog_goals, opp_style(赛前判断)
# "open" = 对手高位/必须追分/易崩鱼腩(赛前就能判断,非事后)
GAMES = [
    ("Qatar-Switzerland",  1.95, 0.55, 1, 1, "balanced"),
    ("Netherlands-Japan",  1.55, 1.10, 2, 2, "balanced"),
    ("Switzerland-Bosnia", 1.95, 0.85, 4, 1, "balanced"),  # 波黑非高位,赛前不flag open
    ("Canada-Qatar",       2.20, 0.55, 6, 0, "open"),       # 卡塔尔脆弱(被砍3.24 xG)
    ("Mexico-Korea",       1.45, 0.90, 1, 0, "park"),
    ("USA-Australia",      1.72, 0.78, 2, 0, "park"),
    ("Scotland-Morocco",   1.60, 0.72, 1, 0, "park"),
    ("Brazil-Haiti",       2.90, 0.45, 3, 0, "open"),
    ("Netherlands-Sweden", 1.80, 0.98, 5, 1, "open"),       # 瑞典3-5-2高位
    ("Germany-CdIvoire",   1.90, 0.85, 2, 1, "park"),       # 科特迪瓦低位铁桶
]

R = 5  # 加尾用的负二项 size(越小尾巴越肥)


def p_pois(lh, la, gh, ga):
    return pois(gh, lh) * pois(ga, la)


def p_negbin_global(lh, la, gh, ga):
    return negbin(gh, lh, R) * negbin(ga, la, R)


def p_v3(lh, la, gh, ga, style):
    pf = negbin(gh, lh, R) if style == "open" else pois(gh, lh)
    return pf * pois(ga, la)


if __name__ == "__main__":
    llp = sum(log(p_pois(lh, la, gh, ga)) for _, lh, la, gh, ga, _ in GAMES)
    lln = sum(log(p_negbin_global(lh, la, gh, ga))
              for _, lh, la, gh, ga, _ in GAMES)
    llv = sum(log(p_v3(lh, la, gh, ga, st)) for _, lh, la, gh, ga, st in GAMES)

    print(f"{'Game':<20}{'act':>5}{'style':>9}{'Pois':>8}{'gNB':>8}{'v3':>8}")
    for name, lh, la, gh, ga, st in GAMES:
        print(f"{name:<20}{f'{gh}-{ga}':>5}{st:>9}"
              f"{p_pois(lh,la,gh,ga)*100:>7.1f}%"
              f"{p_negbin_global(lh,la,gh,ga)*100:>7.1f}%"
              f"{p_v3(lh,la,gh,ga,st)*100:>7.1f}%")
    print(f"\nTotal logL:  Poisson={llp:.3f}   global-NegBin={lln:.3f}   "
          f"v3-selective={llv:.3f}")
    print(f"  global NegBin vs Poisson: {lln-llp:+.3f}  (worse — rejected)")
    print(f"  v3 selective vs Poisson : {llv-llp:+.3f}  (better — adopted)")
