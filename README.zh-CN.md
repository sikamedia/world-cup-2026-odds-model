# 2026 世界杯赔率模型

[English](README.en.md) | [中文](README.zh-CN.md)

这是一个从博彩公司定价视角出发的 2026 世界杯足球比赛模型。项目结合 Elo 到
预期进球的转换、Poisson/Dixon-Coles 比分分布、盘口去水，以及独立的比赛
上下文管线，用来处理赔率、阵容、天气和小组出线状态等信息。

仅用于教育和分析，不提供投注建议、资金建议或确定性预测。

## v0.1 内容

- v3.6/v3.7 迭代后的核心比赛模型脚本。
- 已完成 60 场回测，并预留 6 月 26 日赛果确认后的 66 场回测骨架。
- 市场上下文 CSV/JSON 管线，支持模板生成、录制 Odds API fixture JSON 回放、
  导入、验证和一键运行。
- 结构化 `competition_state`，用于表达已出线、已淘汰、必须赢、争小组第一和
  轮换风险。
- 可安装的 Codex skill 包：`football-odds-model.skill`。
- 当前 skill 源码包：`skill_update_v37/`。

## 仓库结构

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

历史复盘报告保留在仓库中，便于追踪模型迭代过程。由于这些报告来自实时复盘，
多数正文以中文为主。

旧的本地 skill 更新包（`skill_update_v34/`、`skill_update_v35/`、
`skill_update_v36/`）不会进入 v0.1 GitHub 发布范围。

## 快速开始

运行最新的 6 月 26 日预测：

```bash
python3 predict_jun26.py
```

生成可填写的市场/上下文模板：

```bash
python3 create_context_template.py --source jun26 --format csv --output /tmp/jun26.csv
```

把录制的 Odds API fixture JSON 回放到模板中：

```bash
python3 fetch_the_odds_api.py \
  --fixture-csv /tmp/jun26.csv \
  --fixture-json odds_payload.json \
  --output-csv /tmp/jun26.odds.csv
```

运行完整上下文管线：

```bash
python3 run_context_pipeline.py \
  --fixture-source jun26 \
  --market-source odds-api \
  --odds-api-fixture-json odds_payload.json \
  --prediction-slate jun26
```

实时 Odds API 请求需要你自己的 key：

```bash
export ODDS_API_KEY="..."
export ODDS_API_SPORT_KEY="..."
```

不要提交 API key、`.env` 文件或包含私有账号信息的录制 payload。

## 回测

当前已完赛基线：

```bash
python3 backtest_60.py
```

下一轮更新骨架：

```bash
python3 backtest_66.py
```

`backtest_66.py` 目前只输出 60 场基线，因为 `JUNE_26_RESULTS` 有意保持为空。
等 6 月 26 日 6 场最终比分确认后，把赛果填入
`worldcup_2026_data_jun26.py` 再重新运行即可。

## 验证

建议运行以下 v0.1 检查：

```bash
python3 test_jun26_results_scaffold.py
python3 test_competition_state_context.py
python3 test_context_aliases.py
python3 test_odds_api_pipeline.py
python3 test_context_pipeline.py
python3 skill_update_v37/test_regression.py
```

## Skill 安装

Codex skill 的安装和更新流程见 [INSTALL_SKILL.md](INSTALL_SKILL.md)。

## 当前状态

版本：`0.1`

目标分支：`release/0.1`

当前发布原则：

- 核心模型调参保持保守。
- 市场上下文和比赛状态层与核心评分模型解耦。
- 不加入未确认的最终比分。
- 赛前确认信息优先于叙事性假设。

## 免责声明

本仓库仅用于研究、教育和模型评估，不构成金融建议、投注建议，也不建议下注。
