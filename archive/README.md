# Archive — Frozen Historical Snapshots

These scripts are **frozen historical references** kept for backtest
reproducibility. Each backtest is paired with the model version it was validated
against. Do not edit them — their byte-level stability is what makes the old
results reproducible.

## Model versions

| File | Version | Paired backtests |
|------|---------|------------------|
| `match_model_v33.py` | v3.3 | `backtest_44.py` |
| `match_model_v34.py` | v3.4 | `backtest_48.py` |

The active model (v3.5, `match_model_v35.py`) lives at the repository root.

## Scripts needing the retired v3.2 engine

`backtest_v33.py`, `verify_fixes.py`, and `backtest_compare_v32_v33.py` import a
version-less `match_model` — the old v3.2 engine. No authoritative copy of v3.2
remains in the repository (the rolling `skill/scripts/match_model.py` has since
advanced to v3.6A, with different defaults), so these three are kept as
**historical source only** and raise `ImportError` if run. They were already in
that state before archiving.

## Running

The remaining scripts are self-contained (model math and match data are inlined,
or resolved within this folder). Run them from inside `archive/`:

```bash
cd archive
python3 backtest_44.py
```

If a future archived script imports the active `worldcup_2026_data` module at the
repository root, run it with `PYTHONPATH` pointing there:

```bash
PYTHONPATH=.. python3 some_backtest.py
```

## Contents

- `match_model_v33.py` (v3.3), `match_model_v34.py` (v3.4) — superseded model
  engines.
- `backtest_44/48/v3/v34_48/v34_50/v34_probe/full_40.py`,
  `backtest_compare_v32_v34.py`, `wdl_backtest_v31.py` — self-contained
  historical backtests across the v3.1–v3.4 iterations.
- `backtest_v33.py`, `verify_fixes.py`, `backtest_compare_v32_v33.py` — depend on
  the retired v3.2 engine (see above); historical source only.
- `current_form_elo.py` / `current_form_elo.json` — standalone form-Elo helper,
  no longer referenced by the active pipeline.
