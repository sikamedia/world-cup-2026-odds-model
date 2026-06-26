# Installing the `football-odds-model` Skill / 安装 `football-odds-model` Skill

This repository includes two install formats:

本仓库包含两种安装形式：

- `football-odds-model.skill`: packaged skill artifact.
- `football-odds-model.skill`：已打包的 skill 安装文件。
- `skill_update_v37/`: unpacked skill source bundle.
- `skill_update_v37/`：未打包的 skill 源码目录。

Use the packaged `.skill` file when your Codex/Claude UI supports skill import.
Use the unpacked directory when you need to inspect files or manually copy the
skill into a local skill directory.

如果你的 Codex/Claude 界面支持导入 skill，请优先使用 `.skill` 文件。需要检查
源码或手动复制安装时，使用 `skill_update_v37/`。

## Option 1: Packaged Skill / 方式一：安装打包文件

1. Open Codex or Claude settings.
2. Go to `Capabilities` or `Skills`.
3. Import `football-odds-model.skill`.
4. Enable the skill.
5. Ask for a football odds or World Cup model analysis.

中文步骤：

1. 打开 Codex 或 Claude 设置。
2. 进入 `Capabilities` 或 `Skills`。
3. 导入 `football-odds-model.skill`。
4. 启用该 skill。
5. 询问足球赔率、比分概率或世界杯模型分析。

The skill is educational and analytical only. It should not provide betting
advice.

该 skill 仅用于教育和分析，不应提供投注建议。

## Option 2: Manual Install / 方式二：源码手动安装

Copy the contents of `skill_update_v37/` into your local skill directory under a
folder named `football-odds-model`.

把 `skill_update_v37/` 中的内容复制到本地 skill 目录，并将目标文件夹命名为
`football-odds-model`。

Expected source layout:

期望目录结构：

```text
football-odds-model/
|-- SKILL.md
|-- INSTALL.md
|-- scripts/
|   |-- match_model.py
|   `-- tournament_mc.py
|-- competition_state.py
|-- match_context.py
|-- model_stability.py
|-- worldcup_2026_data.py
|-- worldcup_2026_data_jun26.py
|-- run_context_pipeline.py
`-- test_*.py
```

Then run the bundled checks from inside that skill directory:

进入该 skill 目录后运行验证：

```bash
python3 test_regression.py
python3 test_odds_api_pipeline.py
python3 test_competition_state_context.py
python3 test_jun26_results_scaffold.py
```

## Using the Skill Scripts Directly / 直接运行 Skill 脚本

From `skill_update_v37/`:

在 `skill_update_v37/` 目录中运行：

```bash
python3 create_context_template.py --source jun26 --format csv --output /tmp/jun26.csv
python3 run_context_pipeline.py \
  --fixture-source jun26 \
  --market-source odds-api \
  --odds-api-fixture-json odds_payload.json \
  --prediction-slate jun26
```

For live Odds API enrichment, set your own credentials:

如果要实时拉取 Odds API，请设置你自己的凭据：

```bash
export ODDS_API_KEY="..."
export ODDS_API_SPORT_KEY="..."
```

Never commit `.env` files, API keys, or recorded payloads that contain private
account data.

不要提交 `.env` 文件、API key，或包含私有账号信息的录制 payload。

## Updating the Skill / 更新 Skill

1. Rebuild or replace `football-odds-model.skill`.
2. Re-import the `.skill` artifact in the UI, or replace the manual
   `football-odds-model/` directory with `skill_update_v37/`.
3. Run the four checks above.

中文步骤：

1. 重新构建或替换 `football-odds-model.skill`。
2. 在界面中重新导入 `.skill` 文件，或用 `skill_update_v37/` 替换手动安装的
   `football-odds-model/` 目录。
3. 运行上面的四个验证命令。

## Current Skill Version / 当前 Skill 版本

The v0.1 repository release ships the v3.7 skill bundle. The core model defaults
remain conservative and stay separate from market-context and competition-state
ingestion.

v0.1 仓库发布的是 v3.7 skill bundle。核心模型默认值保持保守，并与市场上下文
和比赛状态输入层保持解耦。
