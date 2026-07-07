# 安装 `football-odds-model` Skill

[English](INSTALL_SKILL.en.md) | [中文](INSTALL_SKILL.zh-CN.md)

本仓库提供两种安装形式：

- `football-odds-model.skill`：已打包的 skill 文件（用 `python3 build_skill.py`
  重新生成）。
- `skill/`：skill 专属源文件（SKILL.md、INSTALL 文档、`scripts/`）。活跃的模型
  和管线代码位于仓库根目录；`build_skill.py` 会把两者组装成完整的 skill 包。

如果你的 Codex/Claude 界面支持导入 skill，请优先使用 `.skill` 文件。需要检查
源码或手动复制安装时，使用构建产物。

## 方式一：安装打包文件

1. 打开 Codex 或 Claude 设置。
2. 进入 `Capabilities` 或 `Skills`。
3. 导入 `football-odds-model.skill`。
4. 启用该 skill。
5. 询问足球赔率、比分概率或世界杯模型分析。

该 skill 仅用于教育和分析，不应提供投注建议。

## 方式二：源码手动安装

先构建 skill 包，再复制到本地 skill 目录：

```bash
python3 build_skill.py        # 生成 dist/football-odds-model/ 和 .skill 文件
cp -R dist/football-odds-model /path/to/your/skills/
```

期望的包目录结构：

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

进入该 skill 目录后运行验证：

```bash
python3 test_regression.py
python3 test_odds_api_pipeline.py
python3 test_competition_state_context.py
python3 test_jun26_results_scaffold.py
```

## 直接运行 Skill 脚本

在仓库根目录运行：

```bash
python3 create_context_template.py --source jun26 --format csv --output /tmp/jun26.csv
python3 run_context_pipeline.py \
  --fixture-source jun26 \
  --market-source odds-api \
  --odds-api-fixture-json odds_payload.json \
  --prediction-slate jun26
```

如果要实时拉取 Odds API，请设置你自己的凭据：

```bash
export ODDS_API_KEY="..."
export ODDS_API_SPORT_KEY="..."
```

不要提交 `.env` 文件、API key，或包含私有账号信息的录制 payload。

## 更新 Skill

1. 运行 `python3 build_skill.py` 重新生成 `football-odds-model.skill`。
2. 在界面中重新导入 `.skill` 文件，或用新构建的 `dist/football-odds-model/`
   替换手动安装的 `football-odds-model/` 目录。
3. 运行上面的四个验证命令。

## 当前 Skill 版本

当前 dev 分支提供 v3.8 skill bundle：冻结的 v3.7A 小组赛 profile、锁定的
graded-k 淘汰赛晋级 profile、KO 回测 n=22，以及市场上下文管线。paper-trading
账本工具保留在仓库侧，不打包成 skill 能力。
