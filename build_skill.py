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

import csv
import json
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent
SKILL_NAME = "football-odds-model"
DIST = REPO / "dist"
STAGE = DIST / SKILL_NAME
SKILL_FILE = REPO / f"{SKILL_NAME}.skill"
SKILL_DIR = REPO / "skill"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

# Active root files shipped inside the skill (model + pipeline + tests).
# Excludes archived history (match_model_v33/v34, now under archive/) and the
# root-only backtests (backtest_54/60) that are not part of the skill surface.
# DELIBERATELY EXCLUDED: the paper-trading ledger suite (bet_ledger.py,
# generate_paper_signals.py, settle_bet_ledger.py, evaluate_bet_ledger.py,
# test_bet_ledger_pipeline.py) — the skill's constitution is "never tell
# anyone what to bet"; the paper ledger is project-side calibration
# infrastructure and must not ship as a skill capability.
ROOT_PY = [
    "pyproject.toml",
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
    "capture_elo_evidence.py",
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
    "stakes_goals_ledger.csv",
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
    "tests/test_active_scripts.py",
    "the_odds_api.py",
    "train_market_blend.py",
    "train_stable_profile.py",
    "validate_context.py",
    "worldcup_2026_data.py",
    "worldcup_2026_data_jun26.py",
]


def _safe_evidence_file(relative: Path, *, line: int, label: str) -> Path:
    """Validate one manifest path without following links outside evidence/."""

    if (
        relative.is_absolute()
        or not relative.parts
        or relative.parts[0] != "evidence"
        or ".." in relative.parts
    ):
        raise SystemExit(
            f"ensemble ledger line {line}: {label} must be under repository evidence/"
        )

    candidate = REPO / relative
    current = REPO
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise SystemExit(
                f"ensemble ledger line {line}: {label} cannot use symlinks: {relative}"
            )

    try:
        evidence_root = (REPO / "evidence").resolve(strict=True)
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise SystemExit(
            f"ensemble ledger line {line}: missing {label} {relative}"
        ) from exc
    if evidence_root != resolved and evidence_root not in resolved.parents:
        raise SystemExit(
            f"ensemble ledger line {line}: {label} escapes repository evidence/: "
            f"{relative}"
        )
    if not resolved.is_file():
        raise SystemExit(
            f"ensemble ledger line {line}: missing {label} {relative}"
        )
    return relative


def _require_tracked_evidence(files: set[Path]) -> None:
    """Reject local-only evidence when building from a real Git worktree."""

    git_marker = REPO / ".git"
    if not git_marker.exists():
        return
    for relative in sorted(files):
        result = subprocess.run(
            [
                "git",
                "-C",
                str(REPO),
                "ls-files",
                "--error-unmatch",
                "--",
                relative.as_posix(),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise SystemExit(
                "ensemble evidence dependency must be git-tracked for release: "
                f"{relative}"
            )


def _ensemble_evidence_files() -> tuple[Path, ...]:
    """Return governed live-ledger evidence that must travel with the bundle."""

    ledger = REPO / "ensemble_ledger.csv"
    if not ledger.exists():
        return ()
    with ledger.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    files: set[Path] = set()
    for line, row in enumerate(rows, 2):
        raw = str(row.get("pre_match_evidence") or "").strip()
        if str(row.get("basis") or "").strip() != "live_current_elo":
            if raw:
                raise SystemExit(
                    f"ensemble ledger line {line}: pre_match_evidence is only valid "
                    "for basis=live_current_elo"
                )
            continue
        if not raw:
            continue
        relative = Path(raw)
        _safe_evidence_file(relative, line=line, label="pre_match_evidence")
        artifact = REPO / relative
        files.add(relative)
        try:
            envelope = json.loads(artifact.read_text(encoding="ascii"))
            elo = envelope["payload"]["elo_provenance"]
            retained = (
                elo["retained_tsv_name"],
                elo["retained_receipt_name"],
            )
        except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            raise SystemExit(
                f"ensemble ledger line {line}: invalid pre_match_evidence envelope: {exc}"
            ) from exc
        for name in retained:
            if not isinstance(name, str) or not name or Path(name).name != name:
                raise SystemExit(
                    f"ensemble ledger line {line}: invalid retained Elo file name"
                )
            retained_relative = relative.parent / name
            _safe_evidence_file(
                retained_relative,
                line=line,
                label="retained Elo evidence",
            )
            files.add(retained_relative)
    _require_tracked_evidence(files)
    return tuple(sorted(files))


def _is_cache(path: Path) -> bool:
    return "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}


def _zip_info(path: Path, archive_name: Path) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(archive_name.as_posix(), date_time=ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    permissions = 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644
    info.external_attr = (stat.S_IFREG | permissions) << 16
    return info


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
        dst = stage / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # Ledger rows admitted under the pre-match provenance policy must remain
    # verifiable after installation, so copy only their referenced artifacts
    # and Elo response/receipt pairs.
    for relative in _ensemble_evidence_files():
        src = REPO / relative
        dst = stage / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

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
            if _is_cache(path) or not path.is_file():
                continue
            archive_name = Path(SKILL_NAME) / path.relative_to(stage)
            zf.writestr(_zip_info(path, archive_name), path.read_bytes())

    n_files = sum(1 for p in stage.rglob("*") if p.is_file())
    try:
        stage_display = stage.relative_to(REPO)
    except ValueError:
        stage_display = stage
    print(f"built {out.name}: {n_files} files staged in {stage_display}/")


if __name__ == "__main__":
    import argparse

    # argparse (not raw argv[1]) so `build_skill.py --help` prints help instead
    # of writing a 700KB file literally named "--help".
    parser = argparse.ArgumentParser(
        description="Build the installable football-odds-model.skill bundle.",
    )
    parser.add_argument(
        "output",
        nargs="?",
        help="output .skill path (default: football-odds-model.skill)",
    )
    args = parser.parse_args()
    build(out=REPO / args.output if args.output else SKILL_FILE)
