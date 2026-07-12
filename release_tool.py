#!/usr/bin/env python3
"""Prepare and verify repository release metadata and the skill bundle."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


TAG_RE = re.compile(
    r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-rc\.([1-9][0-9]*))?$"
)
PEP440_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:rc([1-9][0-9]*))?$"
)
README_EN_RE = re.compile(r"(?m)^Version: `([^`]+)`$")
README_ZH_RE = re.compile(r"(?m)^版本：`([^`]+)`$")
README_EN_HEADING_RE = re.compile(r"(?m)^## What v([0-9]+\.[0-9]+) Includes$")
README_ZH_HEADING_RE = re.compile(r"(?m)^## v([0-9]+\.[0-9]+) 内容$")

PROJECT_FILE = "pyproject.toml"
README_EN = "README.en.md"
README_ZH = "README.zh-CN.md"
BUNDLE_FILE = "football-odds-model.skill"
BUNDLE_PROJECT_PATH = f"football-odds-model/{PROJECT_FILE}"


class ReleaseError(RuntimeError):
    """A release invariant was not satisfied."""


@dataclass(frozen=True)
class ReleaseVersion:
    major: int
    minor: int
    patch: int
    rc: Optional[int] = None

    @property
    def tag(self) -> str:
        suffix = f"-rc.{self.rc}" if self.rc is not None else ""
        return f"v{self.major}.{self.minor}.{self.patch}{suffix}"

    @property
    def display(self) -> str:
        return self.tag[1:]

    @property
    def heading(self) -> str:
        return f"{self.major}.{self.minor}"

    @property
    def pep440(self) -> str:
        suffix = f"rc{self.rc}" if self.rc is not None else ""
        return f"{self.major}.{self.minor}.{self.patch}{suffix}"

    @property
    def order_key(self) -> Tuple[int, int, int, int, int]:
        # A final release sorts after every release candidate of the same base.
        phase = 1 if self.rc is None else 0
        return (self.major, self.minor, self.patch, phase, self.rc or 0)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ReleaseVersion):
            return NotImplemented
        return self.order_key < other.order_key


def parse_tag(value: str) -> ReleaseVersion:
    match = TAG_RE.fullmatch(value)
    if not match:
        raise ReleaseError(
            f"invalid release tag {value!r}; expected vX.Y.Z-rc.N or vX.Y.Z"
        )
    major, minor, patch, rc = match.groups()
    return ReleaseVersion(int(major), int(minor), int(patch), int(rc) if rc else None)


def parse_pep440(value: str) -> ReleaseVersion:
    match = PEP440_RE.fullmatch(value)
    if not match:
        raise ReleaseError(
            f"unsupported project version {value!r}; expected X.Y.ZrcN or X.Y.Z"
        )
    major, minor, patch, rc = match.groups()
    return ReleaseVersion(int(major), int(minor), int(patch), int(rc) if rc else None)


def _project_section(lines: Sequence[str]) -> Tuple[int, int]:
    starts = [i for i, line in enumerate(lines) if line.strip() == "[project]"]
    if len(starts) != 1:
        raise ReleaseError(
            f"{PROJECT_FILE} must contain exactly one [project] section; found {len(starts)}"
        )
    start = starts[0]
    end = next(
        (i for i in range(start + 1, len(lines)) if re.fullmatch(r"\s*\[[^]]+\]\s*", lines[i])),
        len(lines),
    )
    return start, end


def _project_version(text: str) -> str:
    lines = text.splitlines(keepends=True)
    start, end = _project_section(lines)
    matches = []
    pattern = re.compile(r'^\s*version\s*=\s*"([^"]+)"\s*(?:#.*)?(?:\r?\n)?$')
    for index in range(start + 1, end):
        match = pattern.fullmatch(lines[index])
        if match:
            matches.append(match.group(1))
    if len(matches) != 1:
        raise ReleaseError(
            f"{PROJECT_FILE} [project] must contain exactly one string version; "
            f"found {len(matches)}"
        )
    return matches[0]


def _replace_project_version(text: str, version: str) -> str:
    lines = text.splitlines(keepends=True)
    start, end = _project_section(lines)
    pattern = re.compile(
        r'^(?P<prefix>\s*version\s*=\s*")[^"]+(?P<suffix>"\s*(?:#.*)?)(?P<eol>\r?\n)?$'
    )
    matches: List[int] = []
    for index in range(start + 1, end):
        if pattern.fullmatch(lines[index]):
            matches.append(index)
    if len(matches) != 1:
        raise ReleaseError(
            f"{PROJECT_FILE} [project] must contain exactly one string version; "
            f"found {len(matches)}"
        )
    index = matches[0]
    match = pattern.fullmatch(lines[index])
    assert match is not None
    lines[index] = (
        f"{match.group('prefix')}{version}{match.group('suffix')}"
        f"{match.group('eol') or ''}"
    )
    return "".join(lines)


def _read_single_marker(text: str, pattern: re.Pattern[str], label: str) -> str:
    matches = pattern.findall(text)
    if len(matches) != 1:
        raise ReleaseError(f"{label} must contain exactly one version marker; found {len(matches)}")
    return matches[0]


def _replace_single_marker(
    text: str,
    pattern: re.Pattern[str],
    replacement: str,
    label: str,
) -> str:
    if len(pattern.findall(text)) != 1:
        count = len(pattern.findall(text))
        raise ReleaseError(f"{label} must contain exactly one version marker; found {count}")
    return pattern.sub(replacement, text, count=1)


def _git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip() or "git command failed"
        raise ReleaseError(f"git {' '.join(args)}: {detail}")
    return process.stdout.strip()


def _replace_bytes(path: Path, data: bytes, mode: Optional[int] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temporary, stat.S_IMODE(mode))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _restore_files(originals: Mapping[Path, Optional[Tuple[bytes, int]]]) -> None:
    failures = []
    for path, original in originals.items():
        try:
            if original is None:
                path.unlink(missing_ok=True)
            else:
                data, mode = original
                _replace_bytes(path, data, mode)
        except OSError as exc:  # pragma: no cover - catastrophic filesystem failure
            failures.append(f"{path}: {exc}")
    if failures:
        raise ReleaseError("release rollback failed: " + "; ".join(failures))


def _load_builder(root: Path) -> Callable[..., None]:
    path = root / "build_skill.py"
    if not path.is_file():
        raise ReleaseError(f"missing bundle builder: {path}")
    spec = importlib.util.spec_from_file_location("_release_build_skill", path)
    if spec is None or spec.loader is None:
        raise ReleaseError(f"cannot load bundle builder: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    builder = getattr(module, "build", None)
    if not callable(builder):
        raise ReleaseError(f"{path} does not expose callable build(stage=..., out=...)")
    return builder


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ReleaseManager:
    def __init__(
        self,
        root: Path,
        builder: Optional[Callable[..., None]] = None,
    ) -> None:
        self.root = root.resolve()
        self.builder = builder if builder is not None else _load_builder(self.root)

    @property
    def metadata_paths(self) -> Tuple[Path, Path, Path]:
        return (
            self.root / PROJECT_FILE,
            self.root / README_EN,
            self.root / README_ZH,
        )

    @property
    def bundle_path(self) -> Path:
        return self.root / BUNDLE_FILE

    def current_version(self) -> ReleaseVersion:
        path = self.root / PROJECT_FILE
        if not path.is_file():
            raise ReleaseError(f"missing metadata file: {path}")
        return parse_pep440(_project_version(path.read_text(encoding="utf-8")))

    def render_metadata(self, target: ReleaseVersion) -> Dict[Path, str]:
        project, readme_en, readme_zh = self.metadata_paths
        for path in self.metadata_paths:
            if not path.is_file():
                raise ReleaseError(f"missing metadata file: {path}")
        project_text = project.read_text(encoding="utf-8")
        en_text = readme_en.read_text(encoding="utf-8")
        zh_text = readme_zh.read_text(encoding="utf-8")
        return {
            project: _replace_project_version(project_text, target.pep440),
            readme_en: _replace_single_marker(
                _replace_single_marker(
                    en_text,
                    README_EN_HEADING_RE,
                    f"## What v{target.heading} Includes",
                    f"{README_EN} release heading",
                ),
                README_EN_RE,
                f"Version: `{target.display}`",
                f"{README_EN} status",
            ),
            readme_zh: _replace_single_marker(
                _replace_single_marker(
                    zh_text,
                    README_ZH_HEADING_RE,
                    f"## v{target.heading} 内容",
                    f"{README_ZH} release heading",
                ),
                README_ZH_RE,
                f"版本：`{target.display}`",
                f"{README_ZH} status",
            ),
        }

    def validate_metadata(self, target: ReleaseVersion) -> None:
        project, readme_en, readme_zh = self.metadata_paths
        project_version = parse_pep440(_project_version(project.read_text(encoding="utf-8")))
        en_display = _read_single_marker(
            readme_en.read_text(encoding="utf-8"), README_EN_RE, README_EN
        )
        zh_display = _read_single_marker(
            readme_zh.read_text(encoding="utf-8"), README_ZH_RE, README_ZH
        )
        en_heading = _read_single_marker(
            readme_en.read_text(encoding="utf-8"),
            README_EN_HEADING_RE,
            f"{README_EN} release heading",
        )
        zh_heading = _read_single_marker(
            readme_zh.read_text(encoding="utf-8"),
            README_ZH_HEADING_RE,
            f"{README_ZH} release heading",
        )
        try:
            en_version = parse_tag(f"v{en_display}")
            zh_version = parse_tag(f"v{zh_display}")
        except ReleaseError as exc:
            raise ReleaseError(f"README release marker is invalid: {exc}") from exc
        mismatches = []
        for label, actual in (
            (PROJECT_FILE, project_version),
            (README_EN, en_version),
            (README_ZH, zh_version),
        ):
            if actual != target:
                mismatches.append(f"{label}={actual.tag}")
        if mismatches:
            raise ReleaseError(
                f"release metadata does not match {target.tag}: " + ", ".join(mismatches)
            )
        heading_mismatches = []
        if en_heading != target.heading:
            heading_mismatches.append(f"{README_EN} heading=v{en_heading}")
        if zh_heading != target.heading:
            heading_mismatches.append(f"{README_ZH} heading=v{zh_heading}")
        if heading_mismatches:
            raise ReleaseError(
                f"release headings do not match v{target.heading}: "
                + ", ".join(heading_mismatches)
            )

    def _validate_prepare_state(self, target: ReleaseVersion) -> None:
        branch = _git(self.root, "branch", "--show-current")
        if branch != "dev":
            current_branch = branch or "detached"
            raise ReleaseError(
                f"prepare must run on branch dev; current branch is {current_branch}"
            )
        dirty = _git(self.root, "status", "--porcelain", "--untracked-files=no")
        if dirty:
            raise ReleaseError("prepare requires a clean tracked worktree")
        if _git(self.root, "tag", "--list", target.tag):
            raise ReleaseError(f"local tag already exists: {target.tag}")

        current = self.current_version()
        if target.order_key <= current.order_key:
            raise ReleaseError(
                f"release target {target.tag} is not newer than current {current.tag}"
            )

        known_tags = []
        for tag in _git(self.root, "tag", "--list").splitlines():
            try:
                known_tags.append(parse_tag(tag))
            except ReleaseError:
                continue
        if known_tags:
            latest = max(known_tags, key=lambda version: version.order_key)
            if target < latest:
                raise ReleaseError(
                    f"release version regression: target {target.tag} is older "
                    f"than local {latest.tag}"
                )

    def _run_builder(self, stage: Path, out: Path) -> None:
        try:
            self.builder(stage=stage, out=out)
        except ReleaseError:
            raise
        except (Exception, SystemExit) as exc:
            raise ReleaseError(f"bundle build failed: {exc}") from exc
        if not out.is_file():
            raise ReleaseError("bundle builder completed without creating its output")

    @staticmethod
    def _validate_bundle_project(bundle: Path, target: ReleaseVersion) -> None:
        try:
            with zipfile.ZipFile(bundle) as archive:
                matches = [name for name in archive.namelist() if name == BUNDLE_PROJECT_PATH]
                if len(matches) != 1:
                    raise ReleaseError(
                        f"bundle must contain exactly one {BUNDLE_PROJECT_PATH}; "
                        f"found {len(matches)}"
                    )
                bundled_text = archive.read(BUNDLE_PROJECT_PATH).decode("utf-8")
        except (OSError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
            raise ReleaseError(f"invalid skill bundle {bundle}: {exc}") from exc
        bundled_version = parse_pep440(_project_version(bundled_text))
        if bundled_version != target:
            raise ReleaseError(
                f"bundle project version is {bundled_version.pep440}, expected {target.pep440}"
            )

    def prepare(self, tag: str) -> ReleaseVersion:
        target = parse_tag(tag)
        self._validate_prepare_state(target)
        rendered = self.render_metadata(target)

        protected_paths: Iterable[Path] = (*self.metadata_paths, self.bundle_path)
        originals: Dict[Path, Optional[Tuple[bytes, int]]] = {}
        for path in protected_paths:
            originals[path] = (
                (path.read_bytes(), path.stat().st_mode) if path.exists() else None
            )

        try:
            for path, text in rendered.items():
                original = originals[path]
                assert original is not None
                _replace_bytes(path, text.encode("utf-8"), original[1])

            with tempfile.TemporaryDirectory(prefix="release-prepare-") as temporary_dir:
                temporary = Path(temporary_dir)
                built = temporary / BUNDLE_FILE
                self._run_builder(temporary / "stage", built)
                self._validate_bundle_project(built, target)
                bundle_mode = originals[self.bundle_path]
                _replace_bytes(
                    self.bundle_path,
                    built.read_bytes(),
                    bundle_mode[1] if bundle_mode is not None else 0o644,
                )
            self.validate_metadata(target)
        except BaseException as exc:
            try:
                _restore_files(originals)
            except ReleaseError as rollback_exc:
                raise rollback_exc from exc
            raise
        return target

    def check(self, tag: Optional[str] = None) -> ReleaseVersion:
        current = self.current_version()
        target = parse_tag(tag) if tag is not None else current
        if current != target:
            raise ReleaseError(
                f"{PROJECT_FILE} version {current.pep440} does not match requested {target.tag}"
            )
        self.validate_metadata(target)
        if not self.bundle_path.is_file():
            raise ReleaseError(f"missing committed bundle: {self.bundle_path}")
        self._validate_bundle_project(self.bundle_path, target)

        with tempfile.TemporaryDirectory(prefix="release-check-") as temporary_dir:
            temporary = Path(temporary_dir)
            rebuilt = temporary / BUNDLE_FILE
            self._run_builder(temporary / "stage", rebuilt)
            self._validate_bundle_project(rebuilt, target)
            if rebuilt.read_bytes() != self.bundle_path.read_bytes():
                raise ReleaseError(
                    "committed bundle differs from a clean rebuild: "
                    f"committed sha256={_sha256(self.bundle_path)}, "
                    f"rebuilt sha256={_sha256(rebuilt)}"
                )
        return target


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or verify release metadata and the committed skill bundle."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="update metadata and rebuild the bundle")
    prepare.add_argument("tag", help="canonical tag, such as v0.4.0-rc.1 or v0.4.0")
    check = subparsers.add_parser("check", help="verify metadata and a clean bundle rebuild")
    check.add_argument("tag", nargs="?", help="optional canonical tag required by the release")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manager = ReleaseManager(Path(__file__).resolve().parent)
        if args.command == "prepare":
            version = manager.prepare(args.tag)
            print(f"prepared {version.tag}: metadata updated and {BUNDLE_FILE} rebuilt")
        else:
            version = manager.check(args.tag)
            print(f"verified {version.tag}: metadata and {BUNDLE_FILE} are reproducible")
    except ReleaseError as exc:
        print(f"release error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
