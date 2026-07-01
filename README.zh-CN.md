# 2026 世界杯赔率模型

[English](README.en.md) | [中文](README.zh-CN.md)

这是一个从博彩公司定价视角出发的 2026 世界杯足球比赛模型。项目结合 Elo 到
预期进球的转换、Poisson/Dixon-Coles 比分分布、盘口去水，独立的比赛上下文
管线（处理赔率、阵容、天气和小组出线状态等信息），以及淘汰赛晋级概率
（90 分钟→加时→点球）和整个对阵树的锦标赛蒙特卡洛模拟。

仅用于教育和分析，不提供投注建议、资金建议或确定性预测。

## v0.2 内容

- 核心比赛模型（v3.7A），带 stage 档位：回归锁定的小组赛档，和独立的
  `--stage knockout` 淘汰赛档。
- 完整 **72 场**小组赛回测（v3.7A 定稿标定），外加独立的**淘汰赛**回测批次，
  随比赛进行逐步扩充。
- **淘汰赛晋级解析器**：90 分钟打平进加时、再点球，输出真正的“晋级概率”
  （而非 90 分钟胜平负）。
- **32 强赛晋级表**和**整个对阵树的蒙特卡洛**（冠军 / 深度晋级概率），
  按官方 FIFA 对阵树顺序播种。
- 市场上下文 CSV/JSON 管线，支持模板生成、录制 Odds API fixture JSON 回放、
  导入、验证和一键运行。
- 结构化 `competition_state`，用于表达已出线、已淘汰、必须赢、争小组第一和
  轮换风险。
- 可安装的 Codex skill 包：`football-odds-model.skill`。
- Skill 源文件：`skill/`（运行 `python3 build_skill.py` 打包）。

## 仓库结构

```text
.
|-- skill/scripts/match_model.py    (当前引擎：v3.7A，--stage group|knockout)
|-- skill/scripts/tournament_mc.py  (锦标赛 / 对阵树蒙特卡洛)
|-- match_model_v35.py              (旧的独立版本；非当前核心)
|-- model_stability.py
|-- worldcup_2026_data.py           (+ _jun26 / _jun27 / _jun28 / _ko)
|-- backtest_72.py                  (定稿的 72 场小组赛回测)
|-- backtest_ko.py                  (淘汰赛批次，随比赛进行扩充)
|-- predict_r32.py                  (32 强赛晋级表)
|-- predict_bracket.py              (整个对阵树的冠军 / 深度晋级概率)
|-- create_context_template.py
|-- fetch_the_odds_api.py
|-- import_context_csv.py
|-- validate_context.py
|-- run_context_pipeline.py
|-- competition_state.py
|-- market_blend.py
|-- build_skill.py                  (构建 football-odds-model.skill)
|-- football-odds-model.skill
|-- archive/                        (冻结的历史模型 + 回测)
`-- test_*.py
```

被取代的回测（`backtest_54/60/66.py`）和历史的 6 月预测批次
（`predict_jun25/26/27.py`）保留下来，便于追溯。

历史复盘报告保留在仓库中，便于追踪模型迭代过程。由于这些报告来自实时复盘，
多数正文以中文为主。

被取代的模型引擎和历史回测现在位于 `archive/`。旧的本地 skill 更新包
（`skill_update_v34/`、`skill_update_v35/`、`skill_update_v36/`）保留在磁盘上，
但被 git 忽略。

## 快速开始

给单场淘汰赛定价（晋级概率，含加时 / 点球）：

```bash
python3 skill/scripts/match_model.py --elo 1720 1870 --stage knockout
```

32 强赛晋级表（谁能进 16 强）：

```bash
python3 predict_r32.py
```

按固定对阵树跑出冠军 / 深度晋级概率：

```bash
python3 predict_bracket.py
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

小组赛定稿标定（全部 72 场，v3.7A，RPS 0.1479）：

```bash
python3 backtest_72.py
```

淘汰赛批次——与小组赛分开，随比赛进行逐步扩充（在录入第一场淘汰赛赛果前为空）：

```bash
python3 backtest_ko.py
```

72 场小组赛已去重且完整（每组 6/6）。淘汰赛参数只在自己的批次上调，绝不与
回归锁定的小组赛档混调。被取代的引擎及历史回测保留在 `archive/`
（见 `archive/README.md`）。

## 验证

一次运行整个活跃测试套件：

```bash
./run_tests.sh
```

或单独运行各项检查：

```bash
python3 test_jun26_results_scaffold.py
python3 test_competition_state_context.py
python3 test_context_aliases.py
python3 test_odds_api_pipeline.py
python3 test_context_pipeline.py
python3 skill/test_regression.py
```

## Skill 安装

Codex skill 的安装和更新流程见 [INSTALL_SKILL.md](INSTALL_SKILL.md)。用
`python3 build_skill.py` 重新构建 skill 包。

## 当前状态

版本：`0.2`

目标分支：`release/0.2`

小组赛已全部结束（72/72），淘汰赛阶段上线：引擎现在输出晋级概率和整个
对阵树的概率。

当前发布原则：

- 核心模型调参保持保守；小组赛档已回归锁定，淘汰赛档只在自己的批次上调。
- 市场上下文和比赛状态层与核心评分模型解耦。
- 不加入未确认的最终比分。
- 赛前确认信息优先于叙事性假设。

## 免责声明

本仓库仅用于研究、教育和模型评估，不构成金融建议、投注建议，也不建议下注。
