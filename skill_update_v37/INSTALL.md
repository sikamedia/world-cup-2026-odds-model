# football-odds-model v3.7 — 安装说明（核心模型 + 市场上下文管线）

本包把回测验证过的 **v3.6A** 参数固化进 skill 默认值，并把市场上下文管线
一起打包。核心引擎仍是 v3.6，v3.7 是技能包版本；本次增量还加入了
`competition_state` 状态层，用来显式记录已出线、已淘汰、必须赢和轮换风险，
不重新拟合核心参数。
当前只读 skill 仍是 v3.4，本会话无法直接写入；需要你在 **设置 → Capabilities（功能）**
里编辑该 skill。

## 改了什么（仅 3 个数字，5 处默认值）

| 参数 | 旧 (v3.4) | 新 (v3.6) | 依据（54 场回测） |
|---|---|---|---|
| `gd_per_100`（Elo→净胜球斜率） | 0.55 | **0.65** | 48 队第三轮强弱分化更大；大胜期望 11.5→13.3，更贴近真实 15 |
| `draw_boost`（平局加成） | 0.07 | **0.06** | 真实平局率掉到 25.9%；模型平局率回到 25.7%，几乎完美对齐 |
| `avg_goals`（场均进球基线） | 2.85 | **2.90** | O/U 2.5 Brier 在 2.9 最低（0.2502），真实大球率 56% |

效果（全 54 场，含 6 场样本外）：RPS 0.1551→**0.1537**，方向 **33/54**，
O/U Brier 0.2525→**0.2502**，样本外 6 场 RPS 0.1834→**0.1758**。**每项指标都不劣于
或优于 v3.5，且样本外同样改善**（非过拟合）。

## 落地步骤

1. 打开 **设置 → Capabilities → football-odds-model → 编辑**。
2. 直接用 `skill_update_v37/` 整个目录覆盖 skill 内容，或者按下面分组复制：
   - `scripts/match_model.py` 和 `scripts/tournament_mc.py`
   - `match_model_v33.py`、`match_model_v34.py`、`match_model_v35.py`
   - 顶层模型/管线脚本：`create_context_template.py`、`fetch_the_odds_api.py`、`run_context_pipeline.py`
   - 顶层依赖模块：`competition_state.py`、`match_context.py`、`team_aliases.py`、`worldcup_2026_data.py`、`model_stability.py`、`market_blend.py`
   - 管线辅助脚本：`import_context_csv.py`、`validate_context.py`、`predict_jun25.py`、`predict_jun26.py`、`train_stable_profile.py`、`evaluate_market_context.py`、`train_market_blend.py`、`predict_stryktipset_8.py`
   - skill 文档：`SKILL.md`
3. 如果你只想手动改而不整包覆盖，按 `CHANGES.diff` 改核心引擎那 5 行即可；管线文件是新增能力，不在这个 diff 里。
   - `score_matrix(... draw_boost=0.07)` → `0.06`
   - `elo_to_lambdas(... avg_goals=2.85, gd_per_100=0.55)` → `2.90, 0.65`
   - CLI `--gd-per-100 default=0.55` → `0.65`
   - CLI `--avg-goals default=2.85` → `2.90`
   - CLI `--draw-boost default=0.07` → `0.06`
4. 保存后验证：
   - `python3 test_regression.py` —— 应打印 `ALL v3.6 REGRESSION CHECKS PASSED`
   - `python3 test_odds_api_pipeline.py` —— 应打印 `ODDS_API_PIPELINE_REGRESSION PASS`
   - `python3 test_competition_state_context.py` —— 应打印 `COMPETITION_STATE_CONTEXT_REGRESSION PASS`
   - `python3 test_jun26_results_scaffold.py` —— 应打印 `JUN26_RESULTS_SCAFFOLD PASS`
   这四条一起锁定核心引擎、市场上下文管线、比赛状态层和 6/26 赛果接入骨架。

## 快速上手

从安装后的 skill 目录或 `skill_update_v37/` 目录运行：

```bash
python3 create_context_template.py --source jun25 --format csv --output /tmp/jun25.csv
python3 fetch_the_odds_api.py --fixture-csv /tmp/jun25.csv --fixture-json odds_payload.json --output-csv /tmp/jun25.odds.csv
python3 run_context_pipeline.py --fixture-source jun25 --market-source odds-api --odds-api-fixture-json odds_payload.json

python3 create_context_template.py --source jun26 --format csv --output /tmp/jun26.csv
python3 run_context_pipeline.py --fixture-source jun26 --market-source odds-api --odds-api-fixture-json odds_payload.json --prediction-slate jun26
```

第一条生成可填写的比赛模板；第二条用录制的 Odds API fixture JSON 离线回放；
第三条把生成、赔率补全、导入、验证、训练建议和预测串成一条命令。没有
`--fixture-json` 时才会走 live Odds API，并需要 `--api-key/--sport-key` 或环境变量
`ODDS_API_KEY`、`ODDS_API_SPORT_KEY`。

## 新增：市场上下文管线

这次更新还加了一个和模型解耦的赔率数据管线。它不改核心引擎默认值，
只负责把模板 CSV、录制的 Odds API JSON、或 live Odds API 数据整理成可导入的
`market_context` JSON。

模板 CSV 现在包含可选 `competition_state` JSON 文本列。它用于描述
`mathematical_state`（`alive`/`qualified`/`eliminated`）、`stake_state`
（`normal`/`advance`/`top_spot`/`seed_only`/`dead_rubber`/`mustwin`）和
`rotation_risk`（`low`/`medium`/`high`）。状态层只转成保守的 motivation/lineup
调整，不会参与参数拟合。

常用入口：

```bash
python3 create_context_template.py --source jun25 --format csv --output /tmp/jun25.csv
python3 fetch_the_odds_api.py --fixture-csv /tmp/jun25.csv --fixture-json odds_payload.json --output-csv /tmp/jun25.odds.csv
python3 import_context_csv.py --input /tmp/jun25.odds.csv --output /tmp/context.json
python3 validate_context.py --context-file /tmp/context.json
python3 run_context_pipeline.py --fixture-source jun25 --market-source odds-api --odds-api-fixture-json odds_payload.json

python3 create_context_template.py --source jun26 --format csv --output /tmp/jun26.csv
python3 run_context_pipeline.py --fixture-source jun26 --market-source odds-api --odds-api-fixture-json odds_payload.json --prediction-slate jun26
```

live 拉取时，设置：

```bash
export ODDS_API_KEY="..."
export ODDS_API_SPORT_KEY="..."
```

这套管线脚本在 `skill_update_v37` 里是完整 bundle 的一部分；在主项目根目录里，
它们仍然只是可选的、与核心模型解耦的分析工具。

## 包内文件
- `scripts/match_model.py` — 已打补丁的引擎（v3.6 默认值）
- `scripts/tournament_mc.py` — 蒙特卡洛冠军盘（未改，原样副本）
- `SKILL.md` — 已更新 banner 和 market-context pipeline 的 skill 文档
- `competition_state.py` — 可选比赛状态层（出线/淘汰/必须赢/轮换风险）
- 顶层 `*.py` 管线脚本 — v3.7 的完整 market-context bundle
- `CHANGES.diff` — 核心引擎相对旧版本的精确 unified diff（仅 5 行变更）
- `test_regression.py` — 回归测试，锁定 v3.6 回测数字（33/54）
- `test_odds_api_pipeline.py` — 端到端管线回归，锁定 Odds API/fixture 流程
- `test_competition_state_context.py` — 锁定状态层 schema、CSV 导入和预测生效
- `test_jun26_results_scaffold.py` — 锁定 6/26 赛果批次必须对应赛程且使用 batch 5
- `INSTALL.md` — 本文件

教育/分析用途，不构成投注建议。
