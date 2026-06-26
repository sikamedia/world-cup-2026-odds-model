# World Cup 2026 Odds Model

Bookmaker-style football match model for the 2026 World Cup. The project
combines an Elo-to-goals model, Poisson/Dixon-Coles score probabilities,
market-odds de-margining, and a decoupled match-context pipeline for odds,
lineups, weather, and competition-state inputs.

Educational and analytical use only. This project does not provide betting
advice, staking advice, or guaranteed predictions.

## What v0.1 Includes

- Core match model scripts through the v3.6/v3.7 bundle work.
- Backtests through 60 completed matches, with a 66-match scaffold ready for
  June 26 final scores once they are confirmed.
- Market-context CSV/JSON pipeline:
  - create templates
  - replay recorded Odds API fixture JSON
  - import and validate context files
  - run the end-to-end context pipeline
- Structured `competition_state` support for qualified, eliminated, must-win,
  top-spot, and rotation-risk scenarios.
- Installable Codex skill artifact: `football-odds-model.skill`.
- Current skill source bundle: `skill_update_v37/`.

## Repository Layout

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

Older local skill bundles (`skill_update_v34/`, `skill_update_v35/`,
`skill_update_v36/`) are intentionally ignored for the v0.1 GitHub release.

## Quick Start

Run the latest June 26 prediction slate:

```bash
python3 predict_jun26.py
```

Generate a fillable market/context template:

```bash
python3 create_context_template.py --source jun26 --format csv --output /tmp/jun26.csv
```

Replay recorded Odds API fixture data into that template:

```bash
python3 fetch_the_odds_api.py \
  --fixture-csv /tmp/jun26.csv \
  --fixture-json odds_payload.json \
  --output-csv /tmp/jun26.odds.csv
```

Run the full context pipeline:

```bash
python3 run_context_pipeline.py \
  --fixture-source jun26 \
  --market-source odds-api \
  --odds-api-fixture-json odds_payload.json \
  --prediction-slate jun26
```

Live Odds API requests require your own key:

```bash
export ODDS_API_KEY="..."
export ODDS_API_SPORT_KEY="..."
```

Do not commit API keys or `.env` files.

## Backtesting

Current played-match baseline:

```bash
python3 backtest_60.py
```

Next update scaffold:

```bash
python3 backtest_66.py
```

`backtest_66.py` currently reports the 60-match baseline because
`JUNE_26_RESULTS` is intentionally empty. After June 26 final scores are
confirmed, fill those six results in `worldcup_2026_data_jun26.py` and rerun the
script.

## Validation

Recommended v0.1 checks:

```bash
python3 test_jun26_results_scaffold.py
python3 test_competition_state_context.py
python3 test_context_aliases.py
python3 test_odds_api_pipeline.py
python3 test_context_pipeline.py
python3 skill_update_v37/test_regression.py
```

## Skill Installation

See [INSTALL_SKILL.md](INSTALL_SKILL.md) for the Codex skill installation and
update flow.

## Status

Version: `0.1`

Branch target: `release/0.1`

Current release policy:

- keep core model tuning conservative
- keep market context and competition state decoupled from core scoring
- do not add unverified final scores
- prefer confirmed match-day information over narrative assumptions

## Disclaimer

This repository is for research, education, and model evaluation. It is not
financial advice, betting advice, or a recommendation to place any wager.
