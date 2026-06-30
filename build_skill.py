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
ROOT_PY = [
    "backtest_66.py",
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
    "run_context_pipeline.py",
    "team_aliases.py",
    "test_competition_state_context.py",
    "test_context_aliases.py",
    "test_context_pipeline.py",
    "test_jun26_results_scaffold.py",
    "test_odds_api_pipeline.py",
    "the_odds_api.py",
    "train_market_blend.py",
    "train_stable_profile.py",
    "validate_context.py",
    "worldcup_2026_data.py",
    "worldcup_2026_data_jun26.py",
]


def _is_cache(path: Path) -> bool:
    return "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}


def build() -> None:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    # 1) active root code
    for name in ROOT_PY:
        src = REPO / name
        if not src.exists():
            raise SystemExit(f"manifest error: missing root file {name}")
        shutil.copy2(src, STAGE / name)

    # 2) skill-only assets, copied verbatim into the bundle root
    if not SKILL_DIR.is_dir():
        raise SystemExit(f"missing skill assets dir: {SKILL_DIR}")
    for src in sorted(SKILL_DIR.rglob("*")):
        if _is_cache(src):
            continue
        dst = STAGE / src.relative_to(SKILL_DIR)
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # 3) zip (store-compressed, matching the original bundle)
    if SKILL_FILE.exists():
        SKILL_FILE.unlink()
    with zipfile.ZipFile(SKILL_FILE, "w", zipfile.ZIP_STORED) as zf:
        for path in sorted(STAGE.rglob("*")):
            if _is_cache(path):
                continue
            zf.write(path, path.relative_to(DIST))

    n_files = sum(1 for p in STAGE.rglob("*") if p.is_file())
    print(f"built {SKILL_FILE.name}: {n_files} files staged in "
          f"{STAGE.relative_to(REPO)}/")


if __name__ == "__main__":
    build()
