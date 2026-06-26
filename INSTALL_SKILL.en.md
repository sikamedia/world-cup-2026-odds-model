# Installing the `football-odds-model` Skill

[English](INSTALL_SKILL.en.md) | [中文](INSTALL_SKILL.zh-CN.md)

This repository includes two install formats:

- `football-odds-model.skill`: packaged skill artifact.
- `skill_update_v37/`: unpacked skill source bundle.

Use the packaged `.skill` file when your Codex/Claude UI supports skill import.
Use the unpacked directory when you need to inspect files or manually copy the
skill into a local skill directory.

## Option 1: Packaged Skill

1. Open Codex or Claude settings.
2. Go to `Capabilities` or `Skills`.
3. Import `football-odds-model.skill`.
4. Enable the skill.
5. Ask for a football odds or World Cup model analysis.

The skill is educational and analytical only. It should not provide betting
advice.

## Option 2: Manual Install

Copy the contents of `skill_update_v37/` into your local skill directory under a
folder named `football-odds-model`.

Expected source layout:

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

```bash
python3 test_regression.py
python3 test_odds_api_pipeline.py
python3 test_competition_state_context.py
python3 test_jun26_results_scaffold.py
```

## Using the Skill Scripts Directly

From `skill_update_v37/`:

```bash
python3 create_context_template.py --source jun26 --format csv --output /tmp/jun26.csv
python3 run_context_pipeline.py \
  --fixture-source jun26 \
  --market-source odds-api \
  --odds-api-fixture-json odds_payload.json \
  --prediction-slate jun26
```

For live Odds API enrichment, set your own credentials:

```bash
export ODDS_API_KEY="..."
export ODDS_API_SPORT_KEY="..."
```

Never commit `.env` files, API keys, or recorded payloads that contain private
account data.

## Updating the Skill

1. Rebuild or replace `football-odds-model.skill`.
2. Re-import the `.skill` artifact in the UI, or replace the manual
   `football-odds-model/` directory with `skill_update_v37/`.
3. Run the four checks above.

## Current Skill Version

The v0.1 repository release ships the v3.7 skill bundle. The core model defaults
remain conservative and stay separate from market-context and competition-state
ingestion.
