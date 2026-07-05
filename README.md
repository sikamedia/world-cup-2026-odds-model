# World Cup 2026 Odds Model

Choose your language:

[English](README.en.md) | [中文](README.zh-CN.md)

Bookmaker-style football match modeling for the 2026 World Cup, with Elo,
Poisson/Dixon-Coles score probabilities, market-odds de-margining, a decoupled
match-context pipeline, and knockout-stage advancement + full-bracket tournament
simulation.

2026 世界杯赔率模型项目，包含 Elo、Poisson/Dixon-Coles 比分概率、盘口去水、
独立的比赛上下文管线，以及淘汰赛晋级概率与整个对阵树的锦标赛模拟。

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
