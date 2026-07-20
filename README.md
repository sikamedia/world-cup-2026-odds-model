# World Cup 2026 Odds Model

Choose your language:

[English](README.en.md) | [中文](README.zh-CN.md)

Bookmaker-style football match modeling for the 2026 World Cup, with Elo,
Poisson/Dixon-Coles score probabilities, market-odds de-margining, a decoupled
match-context pipeline, and knockout-stage advancement + full-bracket tournament
simulation.

2026 世界杯赔率模型项目，包含 Elo、Poisson/Dixon-Coles 比分概率、盘口去水、
独立的比赛上下文管线，以及淘汰赛晋级概率与整个对阵树的锦标赛模拟。

The model shows useful discrimination for match-result direction: approximately 60.6% across 104 backtested matches and 78.1% for knockout-stage advancement. However, its over/under performance remains weak. The O/U 2.5 Brier score was 0.2487, only marginally better than the uninformed 0.2500 benchmark. Therefore, goal-total probabilities should be treated as mild leanings, not evidence of a stable over or under edge. Since most results came from a retrospective replay using frozen parameters, further strictly pre-match validation is required.

模型对胜负方向具有一定区分能力：104 场回测方向命中率约 60.6%，淘汰赛晋级判断为 78.1%。但大小球能力较弱，O/U 2.5 Brier 分数为 0.2487，仅略好于无信息基准 0.2500。因此，大小球概率只能视为轻微倾向，尚不能证明模型拥有稳定的大球或小球优势。并且该回测主要是赛后使用冻结参数统一重放，仍需更多严格的赛前预测验证。


Educational/analytical use only; not betting advice.

教育/分析用途，不构成投注建议。

## Quick Links

- [Skill installation](INSTALL_SKILL.md)
- [Packaged skill](football-odds-model.skill)
- [Current skill source](skill/)
- [Round-of-32 advancement table](predict_r32.py)
- [Full-bracket Monte Carlo](predict_bracket.py)
- [72-match group-stage backtest](backtest_72.py)
- [Knockout-stage backtest](backtest_ko.py)
- [Official automation runbook](AUTOMATION_RUNBOOK.md)
- [Knockout model governance](MODEL_GOVERNANCE.md)
