# football-odds-model v3.9 Install Guide

[English](INSTALL.en.md) | [中文](INSTALL.zh-CN.md)

This bundle packages the frozen v3.7A group-stage profile, the locked v3.9
knockout advancement profile, and the market-context pipeline. The core engine
stays conservative; `competition_state` records qualified, eliminated,
must-win, top-spot, and rotation-risk context without refitting core
parameters.

## What Changed

Only three core defaults changed from older bundles:

| Parameter | Old | New | Rationale |
|---|---:|---:|---|
| `gd_per_100` | 0.55 | **0.65** | Stronger separation in the 48-team group stage. |
| `draw_boost` | 0.07 | **0.06** | Model draw rate re-aligns with the 54-game sample. |
| `avg_goals` | 2.85 | **2.90** | Better O/U 2.5 calibration. |

The 72-game group-stage regression locks the v3.7A profile. Knockout games are
kept in a separate batch: as of 2026-07-08, `backtest_ko.py` validates KO n=24,
advancement 18/24, and 90-minute RPS 0.1502 under the v3.9 lambda floor. The
graded-k knockout profile remains locked; flat-k is still monitor-only.

## Install

Use one of two paths:

1. Import the packaged `football-odds-model.skill` artifact in your
   Codex/Claude skill UI.
2. Copy the entire built `football-odds-model/` directory into a local skill
   folder named `football-odds-model`.

If you manually copy files, include:

- `SKILL.md` and this `INSTALL.md`
- `scripts/match_model.py` and `scripts/tournament_mc.py`
- top-level model and pipeline scripts
- `competition_state.py`, `match_context.py`, `team_aliases.py`,
  `worldcup_2026_data.py`, `worldcup_2026_data_jun26.py`,
  `worldcup_2026_data_ko.py`, `model_stability.py`, and `market_blend.py`
- tests: `test_regression.py`, `test_odds_api_pipeline.py`,
  `test_competition_state_context.py`, `test_jun26_results_scaffold.py`

## Validate

Run these checks from the installed skill directory:

```bash
python3 test_regression.py
python3 backtest_ko.py
python3 test_odds_api_pipeline.py
python3 test_competition_state_context.py
python3 test_jun26_results_scaffold.py
```

Expected pass markers:

- `ALL v3.6 REGRESSION CHECKS PASSED`
- `KNOCKOUT BACKTEST — 24 game(s)`
- `ODDS_API_PIPELINE_REGRESSION PASS`
- `COMPETITION_STATE_CONTEXT_REGRESSION PASS`
- `JUN26_RESULTS_SCAFFOLD PASS`

## Quick Start

Generate a context template and run the June 26 pipeline:

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

```bash
export ODDS_API_KEY="..."
export ODDS_API_SPORT_KEY="..."
```

Never commit API keys or `.env` files.

## Market Context

The pipeline is deliberately decoupled from the core engine. It prepares
market/context JSON from CSV templates, recorded Odds API payloads, or live API
responses. It does not retune core model parameters.

The optional `competition_state` CSV column is a single JSON text field. It
captures `mathematical_state`, `stake_state`, and `rotation_risk`, then maps
those values into conservative motivation and lineup adjustments.

## June 26 Result Scaffold

Keep predictions in `JUNE_26_MATCHES`. Enter confirmed final scores only in
`JUNE_26_RESULTS`. `MATCHES_66` remains a 60-game baseline until those six final
scores are verified.

Run:

```bash
python3 backtest_66.py
```

If results are still missing, the script reports the 60-game baseline and skips
the batch-5 out-of-sample section.

## Package Contents

- `scripts/match_model.py`: active staged engine (`--stage group|knockout`).
- `scripts/tournament_mc.py`: tournament Monte Carlo helper.
- `SKILL.md`: bilingual skill instructions.
- `competition_state.py`: qualification and rotation-risk context layer.
- `worldcup_2026_data_ko.py` and `backtest_ko.py`: separate knockout batch.
- top-level `*.py` files: market-context and prediction pipeline.
- `test_*.py`: regression and pipeline tests.

Educational/analytical use only; not betting advice.
