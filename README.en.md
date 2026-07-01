# World Cup 2026 Odds Model

[English](README.en.md) | [中文](README.zh-CN.md)

Bookmaker-style football match modeling for the 2026 World Cup. This project
combines Elo-to-goals conversion, Poisson/Dixon-Coles score probabilities,
market-odds de-margining, a decoupled match-context pipeline for odds, lineups,
weather, and competition-state inputs, and knockout-stage advancement
(90'→extra time→penalties) plus full-bracket tournament Monte Carlo.

Educational and analytical use only. This repository does not provide betting
advice, staking advice, or guaranteed predictions.

## What v0.2 Includes

- Core match model (v3.7A) with stage profiles: a regression-locked group-stage
  profile and a separate `--stage knockout` profile.
- Full **72-game** group-stage backtest (final v3.7A calibration), plus a
  separate **knockout-stage** backtest batch that grows as games are played.
- **Knockout advancement resolver**: a level game after 90' goes to extra time
  then penalties, producing a true advancement probability (not a 90' W/D/L).
- **Round-of-32 advancement table** and **full-bracket Monte Carlo**
  (champion / deep-run odds) seeded from the official FIFA bracket order.
- Market-context CSV/JSON pipeline for templates, recorded Odds API fixture
  replay, import, validation, and one-command execution.
- Structured `competition_state` support for qualified, eliminated, must-win,
  top-spot, and rotation-risk scenarios.
- Installable Codex skill artifact: `football-odds-model.skill`.
- Skill source assets: `skill/` (run `python3 build_skill.py` to package).

## Repository Layout

```text
.
|-- skill/scripts/match_model.py    (active engine: v3.7A, --stage group|knockout)
|-- skill/scripts/tournament_mc.py  (tournament / bracket Monte Carlo)
|-- match_model_v35.py              (legacy standalone; not the active core)
|-- model_stability.py
|-- worldcup_2026_data.py           (+ _jun26 / _jun27 / _jun28 / _ko)
|-- backtest_72.py                  (final 72-game group-stage backtest)
|-- backtest_ko.py                  (knockout-stage batch, grows as games play)
|-- predict_r32.py                  (Round-of-32 advancement table)
|-- predict_bracket.py              (full-bracket champion / deep-run odds)
|-- create_context_template.py
|-- fetch_the_odds_api.py
|-- import_context_csv.py
|-- validate_context.py
|-- run_context_pipeline.py
|-- competition_state.py
|-- market_blend.py
|-- build_skill.py                  (builds football-odds-model.skill)
|-- football-odds-model.skill
|-- archive/                        (frozen historical models + backtests)
`-- test_*.py
```

Superseded backtests (`backtest_54/60/66.py`) and historical June prediction
slates (`predict_jun25/26/27.py`) are kept for auditability.

Historical reports are kept in the repository for auditability. Most historical
analysis notes are Chinese-first because they were written during live model
iteration.

Superseded model engines and historical backtests now live in `archive/`. Older
local skill bundles (`skill_update_v34/`, `skill_update_v35/`,
`skill_update_v36/`) are kept on disk but ignored by git.

## Quick Start

Price a single knockout tie (advancement, incl. extra time / penalties):

```bash
python3 skill/scripts/match_model.py --elo 1720 1870 --stage knockout
```

Round-of-32 advancement table (who reaches the Round of 16):

```bash
python3 predict_r32.py
```

Champion / deep-run odds over the full fixed bracket:

```bash
python3 predict_bracket.py
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

Do not commit API keys, `.env` files, or private recorded payloads.

## Backtesting

Final group-stage calibration (all 72 games, v3.7A, RPS 0.1479):

```bash
python3 backtest_72.py
```

Knockout-stage batch — kept separate from the group stage and grown as games are
played (empty until the first knockout result is recorded):

```bash
python3 backtest_ko.py
```

The 72 group-stage fixtures are de-duplicated and complete (every group 6/6).
Knockout parameters are tuned only on their own batch, never mixed into the
frozen group-stage profile. Superseded engines and historical backtests are
preserved under `archive/` (see `archive/README.md`).

## Validation

Run the whole active suite at once:

```bash
./run_tests.sh
```

Or run the individual checks:

```bash
python3 test_jun26_results_scaffold.py
python3 test_competition_state_context.py
python3 test_context_aliases.py
python3 test_odds_api_pipeline.py
python3 test_context_pipeline.py
python3 skill/test_regression.py
```

## Skill Installation

See [INSTALL_SKILL.md](INSTALL_SKILL.md) for the Codex skill installation and
update flow. Rebuild the bundle with `python3 build_skill.py`.

## Status

Version: `0.2`

Branch target: `release/0.2`

The group stage is complete (72/72), and the knockout stage is live: the engine
now emits advancement probabilities and full-bracket odds.

Current release policy:

- Keep core model tuning conservative; the group-stage profile is
  regression-locked and the knockout profile is tuned only on its own batch.
- Keep market context and competition state decoupled from core scoring.
- Do not add unverified final scores.
- Prefer confirmed match-day information over narrative assumptions.

## Disclaimer

This repository is for research, education, and model evaluation. It is not
financial advice, betting advice, or a recommendation to place any wager.
