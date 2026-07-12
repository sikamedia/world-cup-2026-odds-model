# football-odds-model v3.9 安装说明

[English](INSTALL.en.md) | [中文](INSTALL.zh-CN.md)

本包把冻结的 v3.7A 小组赛 profile、锁定的 v3.9 淘汰赛晋级 profile，以及市场
上下文管线一起打包。核心引擎保持保守；`competition_state` 状态层只记录已出线、
已淘汰、必须赢、争小组第一和轮换风险，不重新拟合核心参数。

## 改动摘要

相对旧版本，核心默认值只涉及三个数字：

| 参数 | 旧 | 新 | 依据 |
|---|---:|---:|---|
| `gd_per_100` | 0.55 | **0.65** | 48 队小组赛强弱分化更明显。 |
| `draw_boost` | 0.07 | **0.06** | 模型平局率重新贴合 54 场样本。 |
| `avg_goals` | 2.85 | **2.90** | 大小球 2.5 校准更好。 |

72 场小组赛回归测试锁定 v3.7A profile。淘汰赛单独建批次：截至 2026-07-12，
`backtest_ko.py` 校验 KO n=28，晋级判对 22/28，v3.9 lambda floor 下 90 分钟
RPS 0.1472。graded-k 淘汰赛 profile 继续锁定；flat-k 仍只监控。

## 安装

使用以下任一方式：

1. 在 Codex/Claude 的 skill 界面中导入 `football-odds-model.skill`。
2. 或者把整个构建好的 `football-odds-model/` 目录复制到本地 skill 目录，并命名为
   `football-odds-model`。

手动复制时请包含：

- `SKILL.md` 和本 `INSTALL.md`
- `scripts/match_model.py` 和 `scripts/tournament_mc.py`
- 顶层模型和管线脚本
- `competition_state.py`、`match_context.py`、`team_aliases.py`、
  `worldcup_2026_data.py`、`worldcup_2026_data_jun26.py`、
  `worldcup_2026_data_ko.py`、`model_stability.py` 和 `market_blend.py`
- `pyproject.toml`、`tests/test_active_scripts.py`，以及两套测试入口所需的
  全部 active regression scripts

## 验证

在安装后的 skill 目录运行：

```bash
./run_tests.sh
python3 -m pytest -q
python3 backtest_ko.py
```

预期通过标记：

- `All tests passed.`
- skill 包内为 `10 passed`（仓库内为 `12 passed`；paper-ledger 和 release-tooling
  测试按设计不打包）
- `KNOCKOUT BACKTEST — 28 game(s)`

当前淘汰赛 finalization 运行 `create_context_template.py` 并传入
`--source sf_jul14_15 --fixture <slug>`。确认闭顶棚时必须记录 `roof_status=closed`、
精确的 `weather_evidence_fixture_id`，并保留开球前 6 小时内核查的官方证据。
一次性调度与 fail-closed 命令见 `AUTOMATION_RUNBOOK.md`。

## 快速上手

生成上下文模板并运行 6 月 26 日管线：

```bash
python3 create_context_template.py --source jun26 --format csv --output /tmp/jun26.csv
python3 run_context_pipeline.py \
  --fixture-source jun26 \
  --market-source odds-api \
  --odds-api-fixture-json odds_payload.json \
  --prediction-slate jun26
```

离线复现时传入录制的 Odds API fixture JSON。实时请求需要传入 `--api-key` 和
`--sport-key`，或设置：

```bash
export ODDS_API_KEY="..."
export ODDS_API_SPORT_KEY="..."
```

不要提交 API key 或 `.env` 文件。

## 市场上下文管线

该管线有意与核心引擎解耦。它只负责把 CSV 模板、录制的 Odds API payload 或实时
API 响应整理成 market/context JSON，不重新调核心模型参数。

可选的 `competition_state` CSV 列是一个 JSON 文本字段。它记录
`mathematical_state`、`stake_state` 和 `rotation_risk`，再映射为保守的动机和
阵容调整。

## 6 月 26 日赛果骨架

预测赛程保留在 `JUNE_26_MATCHES`。确认后的最终比分只填入 `JUNE_26_RESULTS`。
在 6 场比分确认前，`MATCHES_66` 仍等同于当前 60 场基线。

运行：

```bash
python3 backtest_66.py
```

如果赛果仍为空，脚本会输出当前 60 场基线，并跳过 batch-5 样本外部分。

## 包内文件

- `scripts/match_model.py`：当前分阶段引擎（`--stage group|knockout`）。
- `scripts/tournament_mc.py`：锦标赛蒙特卡洛辅助脚本。
- `SKILL.md`：中英文双语言 skill 指令。
- `competition_state.py`：出线状态和轮换风险上下文层。
- `worldcup_2026_data_ko.py` 和 `backtest_ko.py`：独立淘汰赛批次。
- 顶层 `*.py` 文件：市场上下文和预测管线。
- `test_*.py`：回归和管线测试。

教育/分析用途，不构成投注建议。
