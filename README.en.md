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
- Paper-trading workflow for model-vs-market signals: conservative edge gates,
  ledger append/de-duplication, settlement, and performance evaluation.
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
|-- generate_paper_signals.py      (paper-trading signal generation)
|-- settle_bet_ledger.py           (paper ledger settlement)
|-- evaluate_bet_ledger.py         (paper ledger performance report)
|-- bet_ledger.py                  (shared ledger schema + risk gates)
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

Weather adjustments are auditable context, not model parameters. Current
predictions must record kickoff/check/forecast issue and valid times, an
HTTP(S) source, evidence type, evidence snapshot plus SHA-256, decision, and
scale. Heat evidence must be checked within 6 hours and cover the kickoff hour;
the forecast issue may be no more than 24 hours old when checked;
`rain_applied` requires hourly/radar evidence within 3 hours. Missing or stale
evidence is a blocking error, not a warning.

Use `create_context_template.py --source qf_jul11 --fixture <slug>` to create
one July 11 QF finalization template, then import the completed CSV with
`--require-weather-evidence --context-only`. `predict_jul11.py finalize` writes
a hashed, create-only artifact for exactly that fixture. After both independent
finalizations, `predict_jul11.py mc` consumes their stored QF advancement
probabilities and uses fresh validated Elo only for future rounds. See
[AUTOMATION_RUNBOOK.md](AUTOMATION_RUNBOOK.md) for the external scheduler
contract and finalization times.
See [MODEL_GOVERNANCE.md](MODEL_GOVERNANCE.md) for the tournament freeze,
style-cohort, shootout, and home-advantage decision rules.

## Paper Trading Workflow

The trading layer is **paper-only**. It records candidate model-vs-market
signals and does not place real bets.

Generate conservative signals from a context JSON:

```bash
python3 generate_paper_signals.py \
  --context-file /tmp/jun26.merged.json \
  --elo-module elo_current_latest.py \
  --elo-source-tsv evidence/World.tsv \
  --output-csv /tmp/paper_signals.csv \
  --append-ledger paper_bet_ledger.csv \
  --date 2026-07-05 \
  --stage R16
```

By default, `generate_paper_signals.py` reads `elo_current_latest.py` and
validates the exact World.tsv source, SHA-256, 24-hour freshness, required-team
coverage, and `ESTIMATES=[]`. Any failure exits before a CSV is written.
Group-stage labels select `group_v37a`; knockout labels select
`knockout_locked`. Use `--elo-source snapshot` only for historical replay.

Default gates:

- `edge_net = p_model - p_market - 0.02`
- `edge_net >= 0.03` to become `paper_bet`
- max stake `0.5u`, daily paper risk `2.0u`
- no bet when market margin is above `8%` or model/market gap is above `15pp`

Optional second-opinion ratings, such as an Opta export, can be supplied as an
audit file:

```bash
python3 generate_paper_signals.py \
  --context-file /tmp/jun26.merged.json \
  --elo-module elo_current_latest.py \
  --elo-source-tsv evidence/World.tsv \
  --output-csv /tmp/paper_signals.csv \
  --date 2026-07-05 \
  --stage R16 \
  --external-ratings-csv opta_ratings.csv
```

The external ratings file is not blended into `p_model`. It only flags
material rating disagreements; a `paper_bet` with a strong external-rating
disagreement is downgraded to `watchlist` with an audit note.
Supported CSV columns are `team` plus `rank` and/or `rating`, with optional
`source`.

Settle after confirmed results:

```bash
python3 settle_bet_ledger.py \
  --ledger-csv paper_bet_ledger.csv \
  --results-csv confirmed_results.csv \
  --output-csv paper_bet_ledger.settled.csv
```

Evaluate paper performance:

```bash
python3 evaluate_bet_ledger.py --ledger-csv paper_bet_ledger.settled.csv
```

Version 1 auto-generates only `h2h_90` signals. Advancement markets can be
recorded manually in the same ledger schema until a reliable market feed is
added.

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

With the `test` optional dependencies installed, the equivalent pytest entry
point is:

```bash
python3 -m pytest -q
```

Both commands execute every root `test_*.py` script plus
`skill/test_regression.py`. Individual scripts can still be run directly.

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
