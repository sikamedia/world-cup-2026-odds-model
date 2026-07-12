"""Expose the standalone active test scripts through pytest."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_SCRIPTS = [
    *sorted(ROOT.glob("test_*.py")),
    ROOT / "skill" / "test_regression.py",
]


@pytest.mark.parametrize(
    "script",
    ACTIVE_SCRIPTS,
    ids=[path.relative_to(ROOT).as_posix() for path in ACTIVE_SCRIPTS],
)
def test_active_script(script: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    assert result.returncode == 0, f"{script.relative_to(ROOT)} failed:\n{output}"
