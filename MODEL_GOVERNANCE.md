# Knockout Model Governance

This document is the current decision policy for the remaining 2026 knockout
matches. Historical daily reports remain immutable; corrections are recorded
here and in the next generated report.

## Tournament freeze

- `graded-k`, knockout `lambda_floor=0.30`, `draw_boost=0.06`, and ensemble
  `w=0.6` remain frozen through the tournament.
- The completed n=28 run is monitoring only. It reports paired graded-vs-flat
  Brier, prospective floor-active evidence, and the
  `floor {0.15,0.30} x draw_boost {0.06,0.07}` 2x2 interaction. It cannot change
  production defaults.
- A floor comparison gains identifying evidence only when the unfloored lambda
  is below 0.30. Only rows after the n=24 adoption baseline enter the shadow
  decision; historical floor-active rows cannot be reused as prospective data.
- The ensemble diagnostic uses only unique, settled, internally consistent
  `basis=live_current_elo` rows. At eligible n>=12 it reports a model-weight
  grid from 0.0 to 1.0 in 0.1 steps; `mixed_legacy` and counterfactual rows are
  excluded. The grid is a review output, not an automatic production refit.
- `basis` records the Elo input basis; it does not certify that an official
  finalization artifact exists. The two July 11 QF preview rows remain eligible
  because they were frozen pre-match with current Elo and market inputs. Their
  missing official artifacts are disclosed in notes and are not grounds for a
  post-result cohort change.
- Official schema-2 artifacts record model-minus-market 90-minute and
  advancement gaps. An absolute gap of at least 4 points sets a review flag for
  missing information; it does not authorize a parameter adjustment during the
  tournament freeze.

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

- KO results are current through Argentina 3-1 Switzerland after extra time:
  n=28. The 90-minute RPS is 0.1472; advancement Brier is 0.1606 and log-loss
  is 0.4930.
- The paired graded-minus-flat-1.00 Brier delta is +0.0036 with 95% CI
  [-0.0044, +0.0116]. The n=28 gate is reached, but the interval crosses zero:
  `NO_DECISION`; graded-k stays frozen. Flat 1.00's retrospective Brier of
  0.1570 is a post-tournament calibration candidate, not a live change.
- The floor shadow has four post-adoption prospective rows and zero floor-active
  rows. Its n=28 gate is reached without identifying evidence: `NO_DECISION`.
- The draw-boost x floor interaction gate is reached. Its RPS interaction is
  +0.00003, so the diagnostic state is `REVIEW_INTERACTION` but the measured
  effect is negligible and production parameters remain frozen.
- The ensemble ledger has 10 eligible `live_current_elo` rows out of 12 total;
  one `mixed_legacy` and one counterfactual row are excluded. The n=12 grid has
  not run, current w=0.6 Brier is 0.1635, and the state is `HOLD_W_0_6`. Two
  further eligible settled rows open the diagnostic grid review, not an
  automatic production refit.
- The style ledger contains three observations across two fixtures, but zero
  formally eligible fixtures. Any reported "low-block side 4/4" sequence is a
  descriptive watch item, not evidence from the pre-registered style cohort.
- In the repository, both active test entry points pass 12/12 scripts:
  `./run_tests.sh` and `python3 -m pytest -q`. The packaged skill passes 10/10;
  paper-ledger and release-tooling tests remain repository-only.

## Historical corrections

- France-Morocco preview and final snapshots are one fixture, not independent
  cases. Morocco's preceding knockout results were 1-1 and 3-0, so it did not
  satisfy a two-clean-sheet cohort.
- Belgium's preceding knockout results were 2-2 and 4-1, so it also did not
  satisfy that cohort before Spain-Belgium.
- The France-Morocco weather entry motivates the close-evidence rule but is not
  a compliant positive example: its report-time point forecast was outside the
  new applied-rain window.
- The July 11 QFs had no isolated official finalization artifacts. Their ledger
  rows use the frozen 07:00 preview values and must remain labelled as such.
- A draw alert and a shootout forecast are separate outcomes. Norway-England's
  and Argentina-Switzerland's 90-minute draws count as alert hits; both were
  resolved in extra time, so `shootout_occurred=false` in each case.
- The July 12 report's "36-year-old Messi" reference is incorrect; he was 39.
  Its "Courtois-style" Spain injury phrase, claimed Elo-update direction, and
  characterization of early England money as recreational were unsupported.
  Future reports must use verified player-status sources, treat World.tsv as
  having no intrinsic update timestamp, and describe reported money flow
  without inferring participant type.
- Four-team probabilities after the QFs are conditional on the semifinal field.
  Their increase from July 10 primarily reflects advancement and removal of
  eliminated teams, not evidence that all four teams strengthened.
