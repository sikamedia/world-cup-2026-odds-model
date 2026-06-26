# football-odds-model v3.7 Install Guide / 安装说明

This bundle packages the backtested v3.6A core defaults together with the
v3.7 market-context pipeline. The core engine stays conservative; the added
`competition_state` layer records qualified, eliminated, must-win, top-spot,
and rotation-risk context without refitting the core parameters.

本包把已回测验证的 v3.6A 核心默认值和 v3.7 市场上下文管线一起打包。核心引擎
保持保守；新增的 `competition_state` 状态层只记录已出线、已淘汰、必须赢、
争小组第一和轮换风险，不重新拟合核心参数。

## What Changed / 改动摘要

Only three core defaults changed from older bundles:

相对旧版本，核心默认值只涉及三个数字：

| Parameter / 参数 | Old / 旧 | New / 新 | Rationale / 依据 |
|---|---:|---:|---|
| `gd_per_100` | 0.55 | **0.65** | Stronger separation in the 48-team group stage. / 48 队小组赛强弱分化更明显。 |
| `draw_boost` | 0.07 | **0.06** | Model draw rate re-aligns with the 54-game sample. / 模型平局率重新贴合 54 场样本。 |
| `avg_goals` | 2.85 | **2.90** | Better O/U 2.5 calibration. / 大小球 2.5 校准更好。 |

The 54-game regression locks the v3.6A core: direction 33/54, RPS 0.1537,
model draw rate 25.7%, and blowout expectation 13.3.

54 场回归测试锁定 v3.6A 核心表现：方向 33/54，RPS 0.1537，模型平局率
25.7%，大比分期望 13.3。

## Install / 安装

Use one of two paths:

使用以下任一方式：

1. Import the packaged `football-odds-model.skill` artifact in your
   Codex/Claude skill UI.
2. Copy the entire `skill_update_v37/` directory into a local skill folder named
   `football-odds-model`.

中文：

1. 在 Codex/Claude 的 skill 界面中导入 `football-odds-model.skill`。
2. 或者把整个 `skill_update_v37/` 目录复制到本地 skill 目录，并命名为
   `football-odds-model`。

If you manually copy files, include:

手动复制时请包含：

- `SKILL.md` and this `INSTALL.md`
- `scripts/match_model.py` and `scripts/tournament_mc.py`
- top-level model and pipeline scripts
- `competition_state.py`, `match_context.py`, `team_aliases.py`,
  `worldcup_2026_data.py`, `worldcup_2026_data_jun26.py`,
  `model_stability.py`, and `market_blend.py`
- tests: `test_regression.py`, `test_odds_api_pipeline.py`,
  `test_competition_state_context.py`, `test_jun26_results_scaffold.py`

## Validate / 验证

Run these checks from the installed skill directory:

在安装后的 skill 目录运行：

```bash
python3 test_regression.py
python3 test_odds_api_pipeline.py
python3 test_competition_state_context.py
python3 test_jun26_results_scaffold.py
```

Expected pass markers:

预期通过标记：

- `ALL v3.6 REGRESSION CHECKS PASSED`
- `ODDS_API_PIPELINE_REGRESSION PASS`
- `COMPETITION_STATE_CONTEXT_REGRESSION PASS`
- `JUN26_RESULTS_SCAFFOLD PASS`

## Quick Start / 快速上手

Generate a context template and run the June 26 pipeline:

生成上下文模板并运行 6 月 26 日管线：

```bash
python3 create_context_template.py --source jun26 --format csv --output /tmp/jun26.csv
python3 run_context_pipeline.py \
  --fixture-source jun26 \
  --market-source odds-api \
  --odds-api-fixture-json odds_payload.json \
  --prediction-slate jun26
```

For deterministic/offline use, pass a recorded Odds API fixture JSON. For live
requests, provide `--api-key` and `--sport-key`, or set:

离线复现时传入录制的 Odds API fixture JSON。实时请求需要传入 `--api-key` 和
`--sport-key`，或设置：

```bash
export ODDS_API_KEY="..."
export ODDS_API_SPORT_KEY="..."
```

Never commit API keys or `.env` files.

不要提交 API key 或 `.env` 文件。

## Market Context / 市场上下文管线

The pipeline is deliberately decoupled from the core engine. It prepares
market/context JSON from CSV templates, recorded Odds API payloads, or live API
responses. It does not retune core model parameters.

该管线有意与核心引擎解耦。它只负责把 CSV 模板、录制的 Odds API payload 或实时
API 响应整理成 market/context JSON，不重新调核心模型参数。

The optional `competition_state` CSV column is a single JSON text field. It
captures `mathematical_state`, `stake_state`, and `rotation_risk`, then maps
those values into conservative motivation and lineup adjustments.

可选的 `competition_state` CSV 列是一个 JSON 文本字段。它记录
`mathematical_state`、`stake_state` 和 `rotation_risk`，再映射为保守的动机和
阵容调整。

## June 26 Result Scaffold / 6 月 26 日赛果骨架

Keep predictions in `JUNE_26_MATCHES`. Enter confirmed final scores only in
`JUNE_26_RESULTS`. `MATCHES_66` remains a 60-game baseline until those six final
scores are verified.

预测赛程保留在 `JUNE_26_MATCHES`。确认后的最终比分只填入 `JUNE_26_RESULTS`。
在 6 场比分确认前，`MATCHES_66` 仍等同于当前 60 场基线。

Run:

运行：

```bash
python3 backtest_66.py
```

If results are still missing, the script reports the 60-game baseline and skips
the batch-5 out-of-sample section.

如果赛果仍为空，脚本会输出当前 60 场基线，并跳过 batch-5 样本外部分。

## Package Contents / 包内文件

- `scripts/match_model.py`: patched v3.6A core engine.
- `scripts/match_model.py`：已打补丁的 v3.6A 核心引擎。
- `scripts/tournament_mc.py`: tournament Monte Carlo helper.
- `scripts/tournament_mc.py`：锦标赛蒙特卡洛辅助脚本。
- `SKILL.md`: bilingual skill instructions.
- `SKILL.md`：中英文双语言 skill 指令。
- `competition_state.py`: qualification and rotation-risk context layer.
- `competition_state.py`：出线状态和轮换风险上下文层。
- top-level `*.py` files: market-context and prediction pipeline.
- 顶层 `*.py` 文件：市场上下文和预测管线。
- `test_*.py`: regression and pipeline tests.
- `test_*.py`：回归和管线测试。

Educational/analytical use only; not betting advice.

教育/分析用途，不构成投注建议。
