# World Cup 2026 Odds Model

Bookmaker-style football match modeling for the 2026 World Cup. This project
combines Elo-to-goals conversion, Poisson/Dixon-Coles score probabilities,
market-odds de-margining, and a decoupled match-context pipeline for odds,
lineups, weather, and competition-state inputs.

2026 世界杯赔率模型项目。它结合 Elo 到预期进球的转换、Poisson/Dixon-Coles
比分分布、盘口去水，以及独立的比赛上下文管线，用来处理赔率、阵容、天气和
小组出线状态等信息。

Educational and analytical use only. This repository does not provide betting
advice, staking advice, or guaranteed predictions.

仅用于教育和分析，不提供投注建议、资金建议或确定性预测。

## What v0.1 Includes / v0.1 内容

- Core match model scripts from the v3.6/v3.7 iteration.
- v3.6/v3.7 迭代后的核心比赛模型脚本。
- Backtests through 60 completed matches, plus a 66-match scaffold for June 26
  final scores once confirmed.
- 已完成 60 场回测，并预留 6 月 26 日赛果确认后的 66 场回测骨架。
- Market-context CSV/JSON pipeline for templates, recorded Odds API fixture
  replay, import, validation, and one-command execution.
- 市场上下文 CSV/JSON 管线，支持模板生成、录制 Odds API fixture JSON 回放、
  导入、验证和一键运行。
- Structured `competition_state` support for qualified, eliminated, must-win,
  top-spot, and rotation-risk scenarios.
- 结构化 `competition_state`，用于表达已出线、已淘汰、必须赢、争小组第一和
  轮换风险。
- Installable Codex skill artifact: `football-odds-model.skill`.
- 可安装的 Codex skill 包：`football-odds-model.skill`。
- Current skill source bundle: `skill_update_v37/`.
- 当前 skill 源码包：`skill_update_v37/`。

## Repository Layout / 仓库结构

```text
.
|-- match_model_v33.py / match_model_v34.py / match_model_v35.py
|-- model_stability.py
|-- worldcup_2026_data.py
|-- worldcup_2026_data_jun26.py
|-- backtest_54.py / backtest_60.py / backtest_66.py
|-- create_context_template.py
|-- fetch_the_odds_api.py
|-- import_context_csv.py
|-- validate_context.py
|-- run_context_pipeline.py
|-- competition_state.py
|-- market_blend.py
|-- skill_update_v37/
|-- football-odds-model.skill
`-- test_*.py
```

Historical reports are kept in the repository for auditability. Most historical
analysis notes are Chinese-first because they were written during live model
iteration.

历史复盘报告保留在仓库中，便于追踪模型迭代过程。由于这些报告来自实时复盘，
多数正文以中文为主。

Older local skill bundles (`skill_update_v34/`, `skill_update_v35/`,
`skill_update_v36/`) are intentionally ignored in the v0.1 GitHub release.

旧的本地 skill 更新包（`skill_update_v34/`、`skill_update_v35/`、
`skill_update_v36/`）不会进入 v0.1 GitHub 发布范围。

## Quick Start / 快速开始

Run the latest June 26 prediction slate:

运行最新的 6 月 26 日预测：

```bash
python3 predict_jun26.py
```

Generate a fillable market/context template:

生成可填写的市场/上下文模板：

```bash
python3 create_context_template.py --source jun26 --format csv --output /tmp/jun26.csv
```

Replay recorded Odds API fixture data into that template:

把录制的 Odds API fixture JSON 回放到模板中：

```bash
python3 fetch_the_odds_api.py \
  --fixture-csv /tmp/jun26.csv \
  --fixture-json odds_payload.json \
  --output-csv /tmp/jun26.odds.csv
```

Run the full context pipeline:

运行完整上下文管线：

```bash
python3 run_context_pipeline.py \
  --fixture-source jun26 \
  --market-source odds-api \
  --odds-api-fixture-json odds_payload.json \
  --prediction-slate jun26
```

Live Odds API requests require your own key:

实时 Odds API 请求需要你自己的 key：

```bash
export ODDS_API_KEY="..."
export ODDS_API_SPORT_KEY="..."
```

Do not commit API keys, `.env` files, or private recorded payloads.

不要提交 API key、`.env` 文件或包含私有账号信息的录制 payload。

## Backtesting / 回测

Current played-match baseline:

当前已完赛基线：

```bash
python3 backtest_60.py
```

Next update scaffold:

下一轮更新骨架：

```bash
python3 backtest_66.py
```

`backtest_66.py` currently reports the 60-match baseline because
`JUNE_26_RESULTS` is intentionally empty. After June 26 final scores are
confirmed, fill those six results in `worldcup_2026_data_jun26.py` and rerun the
script.

`backtest_66.py` 目前只输出 60 场基线，因为 `JUNE_26_RESULTS` 有意保持为空。
等 6 月 26 日 6 场最终比分确认后，把赛果填入 `worldcup_2026_data_jun26.py`
再重新运行即可。

## Validation / 验证

Recommended v0.1 checks:

建议运行以下 v0.1 检查：

```bash
python3 test_jun26_results_scaffold.py
python3 test_competition_state_context.py
python3 test_context_aliases.py
python3 test_odds_api_pipeline.py
python3 test_context_pipeline.py
python3 skill_update_v37/test_regression.py
```

## Skill Installation / Skill 安装

See [INSTALL_SKILL.md](INSTALL_SKILL.md) for the Codex skill installation and
update flow.

Codex skill 的安装和更新流程见 [INSTALL_SKILL.md](INSTALL_SKILL.md)。

## Status / 当前状态

Version: `0.1`

Branch target: `release/0.1`

Current release policy:

当前发布原则：

- Keep core model tuning conservative.
- 核心模型调参保持保守。
- Keep market context and competition state decoupled from core scoring.
- 市场上下文和比赛状态层与核心评分模型解耦。
- Do not add unverified final scores.
- 不加入未确认的最终比分。
- Prefer confirmed match-day information over narrative assumptions.
- 赛前确认信息优先于叙事性假设。

## Disclaimer / 免责声明

This repository is for research, education, and model evaluation. It is not
financial advice, betting advice, or a recommendation to place any wager.

本仓库仅用于研究、教育和模型评估，不构成金融建议、投注建议，也不建议下注。
