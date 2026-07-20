# Knockout Model Governance

This document is the current decision policy for the remaining 2026 knockout
matches. Historical daily reports remain immutable; corrections are recorded
here and in the next generated report.

## Versioning

Three independent version tracks exist; do not conflate them.

- **Parameter-regime label** (`v3.x`, next `v4.0`). Names the governed
  scoring-parameter regime — the frozen `STAGE_PROFILES` values plus the ensemble
  weight — and is used in the daily reports and `match_model.py` comments (v3.2
  draw inflation, v3.4 fixes, v3.7A frozen group profile, v3.8 knockout graded-k,
  v3.9 knockout `lambda_floor=0.30` and ensemble `w=0.6`). A *minor* increment
  records a governed adoption at a pre-registered review gate, and may adopt a
  coherent set of parameters sharing that gate: v3.8 locked graded-k at n=16
  (2026-07-04); v3.9 adopted both `lambda_floor=0.30` and `w=0.6` at the n=24
  review (2026-07-08). A *major* increment marks a
  tournament/cycle boundary: because in-tournament refits are forbidden, every
  `REVIEW_REFIT`/`NO_DECISION` change candidate accumulates until the event ends
  and is re-pre-registered for the next cycle as the next regime. That batch is
  `v4.0`; it is a review label only until each item passes its own gate.
- **Freeze engine string** (`predict_jul11._predict/v1`). The exact finalize
  implementation and frozen parameter set bound into every governed ensemble
  freeze and machine-verified by `summarize_ensemble_basis()` against
  `ENSEMBLE_MODEL_ENGINE`. Changing it is itself a governance event — it
  invalidates existing freezes and requires a new `/vN` with re-registration, not
  a documentation edit — and it is independent of the regime label above.
- **Package/release version** (`pyproject.toml`, currently `0.4.0rc1`). Repository
  and skill-bundle packaging only. It tracks releases, not the model regime, and
  moves on its own cadence.

Current state (2026 wrap-up): the regime is frozen at v3.9 for the completed
tournament; `v4.0` is an open review checklist whose items sit in their own
governed states — the ensemble weight `w` increase is `REVIEW_REFIT`, the `k`
flattening is `NO_DECISION`, and the third-place/dead-rubber `avg_goals` tier is
`MONITOR_ONLY` (below its n=12 gate) — none adopted. The freeze engine is
`predict_jul11._predict/v1`; the package is `0.4.0rc1`.

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
- Ensemble probabilities and `advanced_reference` are defined against
  `reference_side` (`H` or `A`). Readers continue to accept the legacy ledger
  field names `fav_side` and `advanced_fav`. When both new and legacy fields
  are populated, they must agree.
- The 11 live rows through France-Spain are the explicit pre-policy
  grandfather set. Every other `live_current_elo` fixture, and all fixtures
  dated 2026-07-15 or later, must name a repository-relative
  `pre_match_evidence` file under `evidence/`. The reader validates that file
  before counting the row and requires its fixture identity and kickoff to
  match the canonical fixture registry and ledger date. It may be a valid
  official pre-match artifact or a sealed `ensemble_pre_match_freeze` record;
  an official artifact is not required for admission.
- A freeze record must predate kickoff, declare that no live match state was
  used, bind the row's `reference_side` and three probabilities, retain a
  direct-HTTP World.tsv/receipt pair no more than 30 minutes old, contain
  non-estimated participant ratings matching those bytes, and retain the
  selected market odds/source/capture time/de-margin and advancement methods.
  Its exact model basis is `predict_jul11._predict/v1`, the frozen knockout
  profile and parameter set (including `style_threshold=266`); its exact context
  basis contains only the weather decision/scale and home/away lineup scales.
  The reader replays that model from the retained ratings, checks the probability
  for `reference_side`, recomputes the market probability (including the replayed
  draw split for `derived_from_90`), and requires the blend to equal frozen
  `w=0.6`. Missing, stale, mismatched, ignored extra context, post-kickoff, or
  post-result reconstructed evidence fails closed and cannot open the n=12 grid.
- A sealed payload hash proves internal integrity, not when the file first
  existed. `summarize_ensemble_basis()` therefore defaults to rejecting every
  freeze unless its caller supplies an external `trusted_anchor_resolver`. The
  resolver must return a `TrustedTimingAnchor` whose source and anchor ID match
  the freeze reference, whose digest matches the sealed payload, and whose
  observation satisfies `frozen_at <= observed_at < kickoff`. The resolver must
  read a trusted scheduler/Git/WORM system, never derive trust from the local
  freeze. Valid official artifacts do not require this freeze-only resolver.
- `basis` records the Elo input basis; it does not certify that an official
  finalization artifact exists. The two July 11 QF preview rows remain eligible
  because they were frozen pre-match with current Elo and market inputs. Their
  missing official artifacts are disclosed in notes and are not grounds for a
  post-result cohort change.
- QF and semifinal finalization remains on schema 3, including any compliant
  SF102 retry before kickoff. Schema 4 activates only for `third_place` and
  `final` artifacts, where it records structured weather provenance in addition
  to direct-HTTP Elo receipt provenance and signed model-minus-market gaps.
  Register those operational fixtures only after SF102 settles and the real
  participants are known; synthetic participants belong in tests only.
  Readers remain compatible with schemas 1-4 and reject a stage/schema mismatch.
  An absolute gap of at least 4 points sets a review flag for missing information;
  it does not authorize a parameter adjustment during the tournament freeze.
- For third-place/final artifacts, weather schema 4 validates source identity,
  exact canonical capture-method values, retained snapshots, hashes,
  timestamps, and the kickoff-covering period. It does not infer a heat or rain
  decision from forecast values. Those decisions continue to use the frozen
  analyst policy and must cite the retained kickoff period; schema adoption does
  not introduce a new weather threshold or model parameter.

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

SF1 and SF102 remain descriptive model-market disagreement observations. They
do not enter this cohort unless every formal criterion above was frozen before
kickoff. Reports must describe price movement or reported money flow neutrally;
they must not infer recreational, sharp, or narrative-driven participants
without independent evidence.

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

- KO results are current through Spain 1-0 Argentina (final): n=32. The 90-minute
  RPS is 0.1532 and advancement Brier is 0.1659. The completed n=28 parameter
  review remains the frozen decision checkpoint.
- The paired graded-minus-flat-1.00 Brier delta is +0.0044 with 95% CI
  [-0.0029, +0.0117]. The n=28 gate is reached, but the interval crosses zero:
  `NO_DECISION`; graded-k stays frozen. Flat 1.00's retrospective Brier of
  0.1615 is a post-tournament calibration candidate, not a live change.
- The floor shadow has eight post-adoption prospective rows and zero floor-active
  rows. Its n=28 gate is reached without identifying evidence: `NO_DECISION`.
- The draw-boost x floor interaction gate is reached. Its RPS interaction is
  +0.00002, so the diagnostic state is `REVIEW_INTERACTION` but the measured
  effect is negligible and production parameters remain frozen.
- The ensemble ledger has 13 eligible `live_current_elo` rows out of 16 total;
  one `mixed_legacy`, one counterfactual, and one `post_policy_no_freeze` row are
  excluded. The n=12 diagnostic grid has run: current w=0.6 Brier is 0.1872,
  raw grid-best w=1.0 Brier is 0.1778, and the state is `REVIEW_REFIT`.
  Production w=0.6 remains frozen pending a wider cross-tournament review.
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
- The July 14 17:18Z direct-HTTP Elo capture succeeded in a different network
  environment. It does not prove that the scheduled-task sandbox allowlist was
  restored.
- The July 15 report's SF102 numbers reuse the prior day's Elo snapshot. For
  governance purposes that run records no current daily preview; its published
  numbers can only be treated as historical replay values.
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
