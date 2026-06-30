# Installing the `football-odds-model` Skill

[English](INSTALL_SKILL.en.md) | [中文](INSTALL_SKILL.zh-CN.md)

This repository ships the skill in two forms:

- `football-odds-model.skill`: packaged skill artifact (regenerate with
  `python3 build_skill.py`).
- `skill/`: skill-only source assets (SKILL.md, INSTALL docs, `scripts/`). The
  active model and pipeline code lives at the repository root; `build_skill.py`
  assembles both into the bundle.

Use the packaged `.skill` file when your Codex/Claude UI supports skill import.
Use the build output when you need to inspect files or manually copy the skill
into a local skill directory.

## Option 1: Packaged Skill

1. Open Codex or Claude settings.
2. Go to `Capabilities` or `Skills`.
3. Import `football-odds-model.skill`.
4. Enable the skill.
5. Ask for a football odds or World Cup model analysis.

The skill is educational and analytical only. It should not provide betting
advice.

## Option 2: Manual Install

Build the bundle, then copy it into your local skill directory:

```bash
python3 build_skill.py        # writes dist/football-odds-model/ and the .skill
cp -R dist/football-odds-model /path/to/your/skills/
```

Expected bundle layout:

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

From the repository root:

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

1. Run `python3 build_skill.py` to regenerate `football-odds-model.skill`.
2. Re-import the `.skill` artifact in the UI, or replace the manual
   `football-odds-model/` directory with the freshly built
   `dist/football-odds-model/`.
3. Run the four checks above.

## Current Skill Version

The v0.1 repository release ships the v3.7 skill bundle. The core model defaults
remain conservative and stay separate from market-context and competition-state
ingestion.
