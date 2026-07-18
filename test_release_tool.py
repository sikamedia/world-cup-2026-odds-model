#!/usr/bin/env python3
"""Focused tests for release_tool.py; uses only temporary local repositories."""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

import build_skill
from release_tool import (
    BUNDLE_FILE,
    BUNDLE_PROJECT_PATH,
    ReleaseError,
    ReleaseManager,
    parse_pep440,
    parse_tag,
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )


def _fake_bundle_bytes(root: Path) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as archive:
        for source_name, archive_name in (
            ("pyproject.toml", BUNDLE_PROJECT_PATH),
            ("README.en.md", "football-odds-model/README.en.md"),
            ("README.zh-CN.md", "football-odds-model/README.zh-CN.md"),
        ):
            info = zipfile.ZipInfo(archive_name, date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (root / source_name).read_bytes())
    return output.getvalue()


def _write_evidence_fixture(
    root: Path,
    *,
    basis: str = "live_current_elo",
    evidence_ref: str = "evidence/sf102.freeze.json",
) -> tuple[Path, Path]:
    skill_dir = root / "skill"
    evidence_dir = root / "evidence"
    skill_dir.mkdir(parents=True)
    evidence_dir.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.4.0rc1"\n',
        encoding="utf-8",
    )
    (skill_dir / "SKILL.md").write_text("# Fixture\n", encoding="utf-8")
    (root / "ensemble_ledger.csv").write_text(
        "basis,pre_match_evidence\n" f"{basis},{evidence_ref}\n",
        encoding="utf-8",
    )
    (evidence_dir / "World.tsv").write_bytes(b"raw response")
    (evidence_dir / "World.receipt.json").write_text("{}\n", encoding="ascii")
    (evidence_dir / "sf102.freeze.json").write_text(
        json.dumps(
            {
                "payload": {
                    "elo_provenance": {
                        "retained_tsv_name": "World.tsv",
                        "retained_receipt_name": "World.receipt.json",
                    }
                },
                "payload_sha256": "synthetic",
            }
        ),
        encoding="ascii",
    )
    return skill_dir, evidence_dir


def _collect_evidence_files(root: Path) -> tuple[Path, ...]:
    original_repo = build_skill.REPO
    try:
        build_skill.REPO = root
        return build_skill._ensemble_evidence_files()
    finally:
        build_skill.REPO = original_repo


class FixtureRepo:
    def __init__(
        self,
        version: str = "0.3.0",
        display: str = "0.3.0",
        include_zh_marker: bool = True,
    ) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "pyproject.toml").write_text(
            "[project]\n"
            'name = "fixture"\n'
            f'version = "{version}"\n'
            "\n[tool.fixture]\n"
            'version = "unrelated"\n',
            encoding="utf-8",
        )
        (self.root / "README.en.md").write_text(
            f"# Fixture\n\n## What v{display.split('.')[0]}.{display.split('.')[1]} Includes\n"
            f"\n## Status\n\nVersion: `{display}`\n",
            encoding="utf-8",
        )
        zh_line = f"版本：`{display}`\n" if include_zh_marker else "尚未发布\n"
        (self.root / "README.zh-CN.md").write_text(
            f"# Fixture\n\n## v{display.split('.')[0]}.{display.split('.')[1]} 内容\n"
            f"\n## 当前状态\n\n{zh_line}",
            encoding="utf-8",
        )
        (self.root / BUNDLE_FILE).write_bytes(_fake_bundle_bytes(self.root))
        _git(self.root, "init", "-q")
        _git(self.root, "config", "user.email", "release-test@example.invalid")
        _git(self.root, "config", "user.name", "Release Test")
        _git(self.root, "checkout", "-q", "-b", "dev")
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-qm", "fixture")

    def close(self) -> None:
        self.temporary.cleanup()

    def build(self, *, stage: Path, out: Path) -> None:
        stage.mkdir(parents=True, exist_ok=True)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(_fake_bundle_bytes(self.root))

    def snapshot(self) -> dict[str, bytes]:
        return {
            name: (self.root / name).read_bytes()
            for name in ("pyproject.toml", "README.en.md", "README.zh-CN.md", BUNDLE_FILE)
        }


class ReleaseVersionTests(unittest.TestCase):
    def test_tag_and_pep440_conversion(self) -> None:
        rc = parse_tag("v0.4.0-rc.1")
        self.assertEqual(rc.pep440, "0.4.0rc1")
        self.assertEqual(rc.display, "0.4.0-rc.1")
        self.assertEqual(parse_pep440("0.4.0rc1"), rc)
        final = parse_tag("v0.4.0")
        self.assertEqual(final.pep440, "0.4.0")
        self.assertLess(rc, final)

    def test_invalid_tags_are_rejected(self) -> None:
        invalid = (
            "0.4.0-rc.1",
            "v0.4.0-rc1",
            "v0.4.0-rc.0",
            "v0.4.0-rc.01",
            "v0.4",
            "v01.4.0",
            "v0.4.0+build",
        )
        for tag in invalid:
            with self.subTest(tag=tag), self.assertRaises(ReleaseError):
                parse_tag(tag)


class BundleReproducibilityTests(unittest.TestCase):
    def test_real_builder_ignores_source_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            temporary = Path(temporary_dir)
            root = temporary / "source"
            root.mkdir()
            external = temporary / "external-build"
            external.mkdir()
            skill_dir = root / "skill"
            skill_dir.mkdir()
            (root / "pyproject.toml").write_text(
                '[project]\nname = "fixture"\nversion = "0.4.0rc1"\n',
                encoding="utf-8",
            )
            (skill_dir / "SKILL.md").write_text("# Fixture\n", encoding="utf-8")

            original_repo = build_skill.REPO
            original_skill_dir = build_skill.SKILL_DIR
            original_root_py = build_skill.ROOT_PY
            try:
                build_skill.REPO = root
                build_skill.SKILL_DIR = skill_dir
                build_skill.ROOT_PY = ["pyproject.toml"]
                first = external / "first.skill"
                second = external / "second.skill"
                build_skill.build(stage=external / "stage-one", out=first)

                os.utime(root / "pyproject.toml", (1_700_000_000, 1_700_000_000))
                os.utime(skill_dir / "SKILL.md", (1_800_000_000, 1_800_000_000))
                build_skill.build(stage=external / "stage-two", out=second)
                self.assertEqual(first.read_bytes(), second.read_bytes())
            finally:
                build_skill.REPO = original_repo
                build_skill.SKILL_DIR = original_skill_dir
                build_skill.ROOT_PY = original_root_py

    def test_real_builder_carries_ledger_bound_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            temporary = Path(temporary_dir)
            root = temporary / "source"
            skill_dir, _evidence_dir = _write_evidence_fixture(root)

            original_repo = build_skill.REPO
            original_skill_dir = build_skill.SKILL_DIR
            original_root_py = build_skill.ROOT_PY
            try:
                build_skill.REPO = root
                build_skill.SKILL_DIR = skill_dir
                build_skill.ROOT_PY = ["pyproject.toml", "ensemble_ledger.csv"]
                bundle = temporary / "fixture.skill"
                build_skill.build(stage=temporary / "stage", out=bundle)
                with zipfile.ZipFile(bundle) as archive:
                    names = set(archive.namelist())
                self.assertIn(
                    "football-odds-model/evidence/sf102.freeze.json", names
                )
                self.assertIn("football-odds-model/evidence/World.tsv", names)
                self.assertIn(
                    "football-odds-model/evidence/World.receipt.json", names
                )
            finally:
                build_skill.REPO = original_repo
                build_skill.SKILL_DIR = original_skill_dir
                build_skill.ROOT_PY = original_root_py

    def test_evidence_manifest_rejects_non_live_and_symlink_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir) / "non-live"
            _write_evidence_fixture(root, basis="mixed_legacy")
            with self.assertRaisesRegex(SystemExit, "only valid for basis"):
                _collect_evidence_files(root)

            root = Path(temporary_dir) / "symlink"
            _skill_dir, evidence_dir = _write_evidence_fixture(root)
            target = Path(temporary_dir) / "outside.tsv"
            target.write_bytes(b"outside")
            (evidence_dir / "World.tsv").unlink()
            (evidence_dir / "World.tsv").symlink_to(target)
            with self.assertRaisesRegex(SystemExit, "cannot use symlinks"):
                _collect_evidence_files(root)

    def test_evidence_manifest_requires_tracked_release_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir) / "source"
            _write_evidence_fixture(root)
            _git(root, "init", "-q")
            _git(root, "add", "pyproject.toml", "ensemble_ledger.csv", "skill/SKILL.md")
            with self.assertRaisesRegex(SystemExit, "must be git-tracked"):
                _collect_evidence_files(root)


class ReleaseManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = FixtureRepo()

    def tearDown(self) -> None:
        self.fixture.close()

    def manager(self) -> ReleaseManager:
        return ReleaseManager(self.fixture.root, builder=self.fixture.build)

    def test_prepare_updates_exact_markers_and_builds_bundle(self) -> None:
        (self.fixture.root / "untracked.txt").write_text("ignored\n", encoding="utf-8")
        target = self.manager().prepare("v0.4.0-rc.1")
        self.assertEqual(target.pep440, "0.4.0rc1")
        self.assertIn('version = "0.4.0rc1"', (self.fixture.root / "pyproject.toml").read_text())
        readme_en = (self.fixture.root / "README.en.md").read_text()
        readme_zh = (self.fixture.root / "README.zh-CN.md").read_text()
        self.assertIn("## What v0.4 Includes", readme_en)
        self.assertIn("Version: `0.4.0-rc.1`", readme_en)
        self.assertIn("## v0.4 内容", readme_zh)
        self.assertIn("版本：`0.4.0-rc.1`", readme_zh)
        self.assertEqual(
            (self.fixture.root / BUNDLE_FILE).read_bytes(),
            _fake_bundle_bytes(self.fixture.root),
        )

    def test_prepare_rolls_back_when_build_fails(self) -> None:
        before = self.fixture.snapshot()

        def fail_build(*, stage: Path, out: Path) -> None:
            raise RuntimeError("synthetic failure")

        manager = ReleaseManager(self.fixture.root, builder=fail_build)
        with self.assertRaisesRegex(ReleaseError, "synthetic failure"):
            manager.prepare("v0.4.0-rc.1")
        self.assertEqual(self.fixture.snapshot(), before)

    def test_missing_marker_fails_before_any_write(self) -> None:
        self.fixture.close()
        self.fixture = FixtureRepo(include_zh_marker=False)
        before = self.fixture.snapshot()
        with self.assertRaisesRegex(ReleaseError, "README.zh-CN.md"):
            self.manager().prepare("v0.4.0-rc.1")
        self.assertEqual(self.fixture.snapshot(), before)

    def test_prepare_rejects_tracked_dirty_state(self) -> None:
        readme = self.fixture.root / "README.en.md"
        readme.write_text(readme.read_text() + "dirty\n", encoding="utf-8")
        with self.assertRaisesRegex(ReleaseError, "clean tracked worktree"):
            self.manager().prepare("v0.4.0-rc.1")

    def test_prepare_rejects_same_version_without_a_tag(self) -> None:
        with self.assertRaisesRegex(ReleaseError, "not newer"):
            self.manager().prepare("v0.3.0")

    def test_prepare_rejects_existing_tag_and_version_regression(self) -> None:
        _git(self.fixture.root, "tag", "v0.4.0-rc.1")
        with self.assertRaisesRegex(ReleaseError, "already exists"):
            self.manager().prepare("v0.4.0-rc.1")

        self.fixture.close()
        self.fixture = FixtureRepo(version="0.4.0rc2", display="0.4.0-rc.2")
        with self.assertRaisesRegex(ReleaseError, "not newer"):
            self.manager().prepare("v0.4.0-rc.1")

    def test_check_is_non_mutating_and_idempotent(self) -> None:
        before = self.fixture.snapshot()
        first = self.manager().check()
        middle = self.fixture.snapshot()
        second = self.manager().check("v0.3.0")
        self.assertEqual(first, second)
        self.assertEqual(before, middle)
        self.assertEqual(before, self.fixture.snapshot())

    def test_check_rejects_heading_mismatch(self) -> None:
        readme = self.fixture.root / "README.en.md"
        readme.write_text(
            readme.read_text().replace("## What v0.3 Includes", "## What v0.2 Includes"),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ReleaseError, "release headings do not match"):
            self.manager().check()

    def test_check_rejects_requested_version_and_bundle_mismatch(self) -> None:
        with self.assertRaisesRegex(ReleaseError, "does not match requested"):
            self.manager().check("v0.4.0-rc.1")
        bundle = self.fixture.root / BUNDLE_FILE
        bundle.write_bytes(bundle.read_bytes() + b"stale")
        with self.assertRaisesRegex(ReleaseError, "differs from a clean rebuild"):
            self.manager().check()


if __name__ == "__main__":
    unittest.main()
