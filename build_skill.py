#!/usr/bin/env python3
"""Build the installable ``football-odds-model.skill`` bundle.

The skill is assembled from two sources of truth so nothing is hand-copied:

  - active model + pipeline code at the repository root (``ROOT_PY``)
  - skill-only assets under ``skill/`` (SKILL.md, INSTALL docs, scripts/, ...)

Output:
  - ``dist/football-odds-model/`` — staging tree (gitignored)
  - ``football-odds-model.skill`` — store-compressed zip at the repo root

Run: ``python3 build_skill.py``
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent
SKILL_NAME = "football-odds-model"
DIST = REPO / "dist"
STAGE = DIST / SKILL_NAME
SKILL_FILE = REPO / f"{SKILL_NAME}.skill"
SKILL_DIR = REPO / "skill"

# Active root files shipped inside the skill (model + pipeline + tests).
# Excludes archived history (match_model_v33/v34, now under archive/) and the
# root-only backtests (backtest_54/60) that are not part of the skill surface.
# DELIBERATELY EXCLUDED: the paper-trading ledger suite (bet_ledger.py,
# generate_paper_signals.py, settle_bet_ledger.py, evaluate_bet_ledger.py,
# test_bet_ledger_pipeline.py) — the skill's constitution is "never tell
# anyone what to bet"; the paper ledger is project-side calibration
# infrastructure and must not ship as a skill capability.
ROOT_PY = [
    "AUTOMATION_RUNBOOK.md",
    "MODEL_GOVERNANCE.md",
    "backtest_66.py",
    "backtest_72.py",
    "backtest_ko.py",
    "experiment_graded_k.py",
    "elo_snapshot.py",
    "ensemble_ledger.csv",
    "fetch_elo_current.py",
    "home_advantage_ledger.csv",
    "model_governance.py",
    "predict_bracket.py",
    "predict_jul11.py",
    "predict_r16_bracket.py",
    "predict_r32.py",
    "team_news.py",
    "worldcup_2026_data_jun28.py",
    "worldcup_2026_data_ko.py",
    "competition_state.py",
    "create_context_template.py",
    "evaluate_market_context.py",
    "fetch_the_odds_api.py",
    "import_context_csv.py",
    "market_blend.py",
    "match_context.py",
    "match_model_v35.py",
    "model_stability.py",
    "predict_jun25.py",
    "predict_jun26.py",
    "predict_stryktipset_8.py",
    "run_tests.sh",
    "run_context_pipeline.py",
    "shootout_ledger.csv",
    "style_divergence_ledger.csv",
    "team_aliases.py",
    "test_competition_state_context.py",
    "test_context_aliases.py",
    "test_context_pipeline.py",
    "test_elo_provenance.py",
    "test_jun26_results_scaffold.py",
    "test_odds_api_pipeline.py",
    "test_model_governance.py",
    "test_predict_jul11.py",
    "test_weather_evidence.py",
    "the_odds_api.py",
    "train_market_blend.py",
    "train_stable_profile.py",
    "validate_context.py",
    "worldcup_2026_data.py",
    "worldcup_2026_data_jun26.py",
]


def _is_cache(path: Path) -> bool:
    return "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}


def build(stage: Path = STAGE, out: Path = SKILL_FILE) -> None:
    if stage.exists():
        try:
            shutil.rmtree(stage)
        except PermissionError:
            # Sandbox mounts may forbid deleting files created by an earlier
            # session. Fall back to a fresh sibling staging dir.
            i = 2
            while (alt := stage.parent / f"{stage.name}-build{i}").exists():
                i += 1
            stage = alt
    stage.mkdir(parents=True)

    # 1) active root code
    for name in ROOT_PY:
        src = REPO / name
        if not src.exists():
            raise SystemExit(f"manifest error: missing root file {name}")
        shutil.copy2(src, stage / name)

    # 2) skill-only assets, copied verbatim into the bundle root
    if not SKILL_DIR.is_dir():
        raise SystemExit(f"missing skill assets dir: {SKILL_DIR}")
    for src in sorted(SKILL_DIR.rglob("*")):
        if _is_cache(src):
            continue
        dst = stage / src.relative_to(SKILL_DIR)
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # 3) zip (store-compressed, matching the original bundle). Inside the zip
    # the top-level dir is always the canonical skill name.
    if out.exists():
        try:
            out.unlink()
        except PermissionError:
            i = 2
            while (alt := out.with_name(f"{out.stem}-{i}.skill")).exists():
                i += 1
            out = alt
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
        for path in sorted(stage.rglob("*")):
            if _is_cache(path):
                continue
            zf.write(path, Path(SKILL_NAME) / path.relative_to(stage))

    n_files = sum(1 for p in stage.rglob("*") if p.is_file())
    print(f"built {out.name}: {n_files} files staged in "
          f"{stage.relative_to(REPO)}/")


if __name__ == "__main__":
    import sys
    out = SKILL_FILE
    if len(sys.argv) > 1:
        out = REPO / sys.argv[1]
    build(out=out)
