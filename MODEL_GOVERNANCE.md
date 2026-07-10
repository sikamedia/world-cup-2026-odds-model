# Knockout Model Governance

This document is the current decision policy for the remaining 2026 knockout
matches. Historical daily reports remain immutable; corrections are recorded
here and in the next generated report.

## Tournament freeze

- `graded-k`, knockout `lambda_floor=0.30`, `draw_boost=0.06`, and ensemble
  `w=0.6` remain frozen through the tournament.
- The n=28 run is monitoring only. It reports paired graded-vs-flat Brier,
  prospective floor-active evidence, and the `floor {0.15,0.30} x draw_boost
  {0.06,0.07}` 2x2 interaction. It cannot change production defaults.
- A floor comparison gains identifying evidence only when the unfloored lambda
  is below 0.30. Only rows after the n=24 adoption baseline enter the shadow
  decision; historical floor-active rows cannot be reused as prospective data.
- The ensemble diagnostic uses only unique, settled, internally consistent
  `basis=live_current_elo` rows. At eligible n>=12 it reports a model-weight
  grid from 0.0 to 1.0 in 0.1 steps; `mixed_legacy` and counterfactual rows are
  excluded. The grid is a review output, not an automatic production refit.

## 90-minute style cohort

A fixture enters the prospective cohort only when all conditions were frozen
before kickoff:

- the weaker side's de-margined market 90-minute win probability exceeds the
  model by at least 5 percentage points;
- that side recorded two consecutive 90-minute clean sheets;
- an independent HTTP(S) source labels the approach `low_block`,
  `counterattack`, or `low_block_counter`;
- market and style sources are independent HTTP(S) hosts;
- registration, kickoff, market/style/rating check times prove all inputs were
  available before kickoff;
- the cohort side has a lower recorded Elo than its opponent; and
- market/style evidence SHA-256 values and the de-margin method are recorded.

The cohort remains `MONITOR_ONLY` until 20 distinct eligible resolved fixtures.
No single result, including a Belgium 90-minute win, can trigger an official or
shadow parameter adjustment.

## Shootouts and home advantage

- The structured shootout ledger currently contains four shootouts. The
  Elo-tilted side won 0/4, not 0/2. n=5 permits a descriptive review only; the
  ledger requires `resolution_type=shootout`, and the current resolver still
  models the whole 90-minute-draw-to-advancement path, not a standalone penalty
  model.
- The home ledger is scoped to prospective knockout calls. Home-crowd Elo and
  altitude Elo are separate fields. The legacy Azteca +90 value remains marked
  as combined and cannot identify either component. Home review counts only
  zero-altitude, home-only rows. With no true home fixtures remaining, the
  archive state is `ARCHIVED_NO_TRUE_HOMES_REMAINING`.

## Current checkpoint

- KO results are current through France 2-0 Morocco: n=25.
- Graded-k Brier is 0.1713 versus flat-1.00 at 0.1691 (displayed gap 0.0022;
  exact paired delta +0.0021). The n=28 gate is not reached and the paired 95%
  interval crosses zero.
- Post-adoption floor evidence has one prospective row and zero floor-active
  rows. The 2x2 interaction is also below its n=28 gate.
- The ensemble ledger has 7 eligible live-current-Elo rows out of 9 total, so
  the n=12 weight grid has not run.

## Historical corrections

- France-Morocco preview and final snapshots are one fixture, not independent
  cases. Morocco's preceding knockout results were 1-1 and 3-0, so it did not
  satisfy a two-clean-sheet cohort.
- Belgium's preceding knockout results were 2-2 and 4-1, so it also did not
  satisfy that cohort before Spain-Belgium.
- The France-Morocco weather entry motivates the close-evidence rule but is not
  a compliant positive example: its report-time point forecast was outside the
  new applied-rain window.
