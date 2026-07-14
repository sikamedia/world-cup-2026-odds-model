#!/usr/bin/env python3
"""Regression checks for prediction-side Elo provenance and fail-closed use."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

from capture_elo_evidence import MAX_ELO_BODY_BYTES, capture_elo_evidence
from elo_snapshot import EloSnapshotError, OFFICIAL_ELO_SOURCE, load_elo_snapshot


ROOT = Path(__file__).resolve().parent
NOW = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
VALID_HASH = "a" * 64
CAPTURE_METHOD = "direct_http_response_body"
RECEIPT_ARTIFACT_TYPE = "elo_http_capture_receipt"


class _FakeResponse:
    """Small urllib-compatible response used to exercise byte capture."""

    def __init__(
        self,
        body: bytes,
        *,
        status: int = 200,
        final_url: str = OFFICIAL_ELO_SOURCE,
        fail_on_read: bool = False,
    ) -> None:
        self.status = status
        self._body = body
        self._offset = 0
        self._final_url = final_url
        self.url = final_url
        self._fail_on_read = fail_on_read
        self.headers: dict[str, str] = {}

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self._final_url

    def read(self, size: int = -1) -> bytes:
        if self._fail_on_read:
            raise OSError("synthetic interrupted response")
        if self._offset >= len(self._body):
            return b""
        if size is None or size < 0:
            size = len(self._body) - self._offset
        chunk = self._body[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


class _FakeOpener:
    """Supports both a callable opener and urllib's ``opener.open`` shape."""

    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[object, float | int | None]] = []

    def open(
        self,
        request: object,
        timeout: float | int | None = None,
    ) -> _FakeResponse:
        self.calls.append((request, timeout))
        return self.response

    def __call__(
        self,
        request: object,
        timeout: float | int | None = None,
    ) -> _FakeResponse:
        return self.open(request, timeout=timeout)


def _snapshot_text(
    *,
    fetched_at: datetime = NOW - timedelta(hours=1),
    source: str = OFFICIAL_ELO_SOURCE,
    source_sha256: str = VALID_HASH,
    estimates: tuple[str, ...] = (),
    include_switzerland: bool = True,
    argentina_rating: int = 2156,
    switzerland_rating: int = 1949,
) -> str:
    ratings = {f'"Argentina": {argentina_rating}'}
    if include_switzerland:
        ratings.add(f'"Switzerland": {switzerland_rating}')
    return "\n".join(
        [
            f"ELO_CURRENT = {{{', '.join(sorted(ratings))}}}",
            f"FETCHED_AT_UTC = {fetched_at.isoformat()!r}",
            f"SOURCE = {source!r}",
            f"SOURCE_SHA256 = {source_sha256!r}",
            f"ESTIMATES = {list(estimates)!r}",
            "",
        ]
    )


def _expect_error(path: Path, message: str, **kwargs) -> None:
    kwargs.setdefault("now_utc", NOW)
    try:
        load_elo_snapshot(path, **kwargs)
    except EloSnapshotError as exc:
        assert message in str(exc), str(exc)
    else:
        raise AssertionError(f"expected EloSnapshotError containing {message!r}")


def _world_tsv() -> str:
    """Minimal real-format fixture accepted by the production parser."""

    codes = [
        ("ES", 2177),
        ("AR", 2156),
        ("FR", 2143),
        ("EN", 2076),
        ("BR", 2050),
        ("PT", 2040),
        ("CO", 2003),
        ("NL", 1995),
        ("MX", 1980),
        ("CH", 1949),
        ("NO", 1972),
        ("BE", 1961),
        ("DE", 1950),
        ("JP", 1930),
        ("MA", 1921),
        ("HR", 1910),
    ]
    return "".join(
        f"{rank}\t{rank}\t{code}\t{rating}\n"
        for rank, (code, rating) in enumerate(codes, start=1)
    )


def _capture(
    tsv_path: Path,
    receipt_path: Path,
    *,
    body: bytes,
    completed_at: datetime,
    response: _FakeResponse | None = None,
) -> tuple[dict[str, object], _FakeOpener]:
    fake_response = response or _FakeResponse(body)
    opener = _FakeOpener(fake_response)
    capture_elo_evidence(
        tsv_path,
        receipt_path,
        timeout_seconds=7,
        opener=opener,
        clock=lambda: completed_at,
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    return receipt, opener


def _run_fetch(
    tsv_path: Path,
    output_path: Path,
    *,
    receipt_path: Path | None = None,
    fetched_at_utc: str | None = None,
    allow_unverified_replay: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(ROOT / "fetch_elo_current.py"),
        "--tsv",
        str(tsv_path),
        "--out",
        str(output_path),
        "--required-team",
        "Argentina",
        "--required-team",
        "Switzerland",
    ]
    if receipt_path is not None:
        command.extend(["--receipt", str(receipt_path)])
    if fetched_at_utc is not None:
        command.extend(["--fetched-at-utc", fetched_at_utc])
    if allow_unverified_replay:
        command.append("--allow-unverified-replay")
    return subprocess.run(
        command,
        cwd=tsv_path.parent,
        capture_output=True,
        text=True,
        check=False,
    )


def _expect_capture_error(
    tsv_path: Path,
    receipt_path: Path,
    response: _FakeResponse,
    *,
    message: str,
) -> None:
    opener = _FakeOpener(response)
    try:
        capture_elo_evidence(
            tsv_path,
            receipt_path,
            opener=opener,
            clock=lambda: NOW,
        )
    except Exception as exc:
        assert message.lower() in str(exc).lower(), str(exc)
    else:
        raise AssertionError(f"expected capture failure containing {message!r}")
    assert not tsv_path.exists()
    assert not receipt_path.exists()


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # The capture layer must preserve the HTTP response body exactly. BOM,
        # CRLF, trailing blank lines, and non-text bytes are deliberately kept.
        raw_body = b"\xef\xbb\xbf1\t1\tES\t2177\r\n2\t2\tAR\t2156\r\n\r\n\x00"
        byte_tsv = tmp / "elo_evidence_bytes_World.tsv"
        byte_receipt = tmp / "elo_evidence_bytes_World.receipt.json"
        completed_at = NOW - timedelta(minutes=5)
        receipt, opener = _capture(
            byte_tsv,
            byte_receipt,
            body=raw_body,
            completed_at=completed_at,
        )
        assert byte_tsv.read_bytes() == raw_body
        assert len(opener.calls) == 1
        request, timeout = opener.calls[0]
        assert timeout == 7
        assert getattr(request, "full_url", request) == OFFICIAL_ELO_SOURCE
        if hasattr(request, "get_header"):
            assert request.get_header("Accept-encoding") == "identity"
        expected_receipt = {
            "schema_version": 1,
            "artifact_type": RECEIPT_ARTIFACT_TYPE,
            "capture_method": CAPTURE_METHOD,
            "requested_url": OFFICIAL_ELO_SOURCE,
            "final_url": OFFICIAL_ELO_SOURCE,
            "http_status": 200,
            "response_completed_at_utc": "2026-07-10T11:55:00Z",
            "evidence_file": byte_tsv.name,
            "body_byte_count": len(raw_body),
            "body_sha256": hashlib.sha256(raw_body).hexdigest(),
        }
        for field, expected in expected_receipt.items():
            assert receipt[field] == expected, (field, receipt[field], expected)

        # Both outputs are create-only. An existing destination is never
        # overwritten, and a reserved receipt prevents creating its TSV peer.
        existing_tsv = tmp / "existing_World.tsv"
        existing_tsv.write_bytes(b"keep-existing-tsv")
        existing_receipt = tmp / "existing.receipt.json"
        existing_opener = _FakeOpener(_FakeResponse(raw_body))
        try:
            capture_elo_evidence(
                existing_tsv,
                existing_receipt,
                opener=existing_opener,
                clock=lambda: NOW,
            )
        except Exception as exc:
            assert "exist" in str(exc).lower(), str(exc)
        else:
            raise AssertionError("capture unexpectedly overwrote an existing TSV")
        assert existing_tsv.read_bytes() == b"keep-existing-tsv"
        assert not existing_receipt.exists()

        reserved_tsv = tmp / "reserved_World.tsv"
        reserved_receipt = tmp / "reserved.receipt.json"
        reserved_receipt.write_bytes(b"keep-existing-receipt")
        reserved_opener = _FakeOpener(_FakeResponse(raw_body))
        try:
            capture_elo_evidence(
                reserved_tsv,
                reserved_receipt,
                opener=reserved_opener,
                clock=lambda: NOW,
            )
        except Exception as exc:
            assert "exist" in str(exc).lower(), str(exc)
        else:
            raise AssertionError("capture unexpectedly overwrote an existing receipt")
        assert not reserved_tsv.exists()
        assert reserved_receipt.read_bytes() == b"keep-existing-receipt"

        _expect_capture_error(
            tmp / "status_World.tsv",
            tmp / "status.receipt.json",
            _FakeResponse(raw_body, status=503),
            message="503",
        )
        _expect_capture_error(
            tmp / "redirect_World.tsv",
            tmp / "redirect.receipt.json",
            _FakeResponse(raw_body, final_url="https://mirror.example/World.tsv"),
            message="final",
        )
        _expect_capture_error(
            tmp / "interrupted_World.tsv",
            tmp / "interrupted.receipt.json",
            _FakeResponse(raw_body, fail_on_read=True),
            message="interrupted",
        )
        truncated_response = _FakeResponse(raw_body)
        truncated_response.headers["Content-Length"] = str(len(raw_body) + 1)
        _expect_capture_error(
            tmp / "truncated_World.tsv",
            tmp / "truncated.receipt.json",
            truncated_response,
            message="Content-Length mismatch",
        )
        declared_oversized = _FakeResponse(raw_body)
        declared_oversized.headers["Content-Length"] = str(MAX_ELO_BODY_BYTES + 1)
        _expect_capture_error(
            tmp / "declared_oversized_World.tsv",
            tmp / "declared_oversized.receipt.json",
            declared_oversized,
            message="exceeds",
        )
        _expect_capture_error(
            tmp / "streamed_oversized_World.tsv",
            tmp / "streamed_oversized.receipt.json",
            _FakeResponse(b"x" * (MAX_ELO_BODY_BYTES + 1)),
            message="exceeds",
        )

        deadline_tsv = tmp / "deadline_World.tsv"
        deadline_receipt = tmp / "deadline.receipt.json"
        deadline_ticks = iter((0.0, 31.0))
        try:
            capture_elo_evidence(
                deadline_tsv,
                deadline_receipt,
                timeout_seconds=30,
                opener=_FakeOpener(_FakeResponse(raw_body)),
                clock=lambda: NOW,
                monotonic_clock=lambda: next(deadline_ticks),
            )
        except Exception as exc:
            assert "exceeded" in str(exc), str(exc)
        else:
            raise AssertionError("capture unexpectedly exceeded its wall-clock deadline")
        assert not deadline_tsv.exists()
        assert not deadline_receipt.exists()

        fresh = tmp / "fresh.py"
        fresh.write_text(_snapshot_text(), encoding="utf-8")
        loaded = load_elo_snapshot(
            fresh,
            required_teams=["Argentina", "Switzerland"],
            max_age_hours=24,
            now_utc=NOW,
        )
        assert loaded.ratings["Argentina"] == 2156
        assert loaded.fetched_at_utc == NOW - timedelta(hours=1)

        stale = tmp / "stale.py"
        stale.write_text(
            _snapshot_text(fetched_at=NOW - timedelta(hours=24, seconds=1)),
            encoding="utf-8",
        )
        _expect_error(stale, "stale", required_teams=["Argentina"])

        missing = tmp / "missing.py"
        missing.write_text(_snapshot_text(include_switzerland=False), encoding="utf-8")
        _expect_error(missing, "missing current Elo", required_teams=["Switzerland"])

        estimated = tmp / "estimated.py"
        estimated.write_text(
            _snapshot_text(estimates=("Switzerland",)), encoding="utf-8"
        )
        _expect_error(estimated, "estimated Elo", required_teams=["Switzerland"])

        wrong_source = tmp / "wrong_source.py"
        wrong_source.write_text(
            _snapshot_text(source="https://example.com/World.tsv"), encoding="utf-8"
        )
        _expect_error(wrong_source, "SOURCE must be exactly")

        invalid_hash = tmp / "invalid_hash.py"
        invalid_hash.write_text(_snapshot_text(source_sha256="not-a-hash"), encoding="utf-8")
        _expect_error(invalid_hash, "SOURCE_SHA256")
        _expect_error(
            fresh,
            "SHA-256 mismatch",
            expected_source_sha256="b" * 64,
        )

        naive_time = tmp / "naive_time.py"
        naive_time.write_text(
            _snapshot_text(fetched_at=datetime(2026, 7, 10, 11, 0)),
            encoding="utf-8",
        )
        _expect_error(naive_time, "timezone offset")

        future_time = tmp / "future.py"
        future_time.write_text(
            _snapshot_text(fetched_at=NOW + timedelta(minutes=1)),
            encoding="utf-8",
        )
        _expect_error(future_time, "in the future", required_teams=["Argentina"])

        tsv = tmp / "World.tsv"
        tsv.write_text(_world_tsv(), encoding="utf-8")
        tsv_sha256 = hashlib.sha256(tsv.read_bytes()).hexdigest()
        generated = tmp / "elo_current_latest.py"

        unstamped_output = tmp / "unstamped.py"
        unstamped_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "fetch_elo_current.py"),
                "--tsv",
                str(tsv),
                "--out",
                str(unstamped_output),
            ],
            cwd=tmp,
            capture_output=True,
            text=True,
            check=False,
        )
        assert unstamped_proc.returncode != 0
        assert (
            "--receipt" in unstamped_proc.stderr
            or "--fetched-at-utc" in unstamped_proc.stderr
        )
        assert not unstamped_output.exists()

        # Caller-stamped timestamps are replay-only and require an explicit
        # opt-in. They remain useful for historical work but are ineligible
        # for the official direct-capture contract.
        replay_denied = _run_fetch(
            tsv,
            generated,
            fetched_at_utc="2026-07-10T11:00:00Z",
        )
        assert replay_denied.returncode != 0
        assert "--allow-unverified-replay" in replay_denied.stderr
        assert not generated.exists()

        generated_proc = _run_fetch(
            tsv,
            generated,
            fetched_at_utc="2026-07-10T11:00:00Z",
            allow_unverified_replay=True,
        )
        assert generated_proc.returncode == 0, generated_proc.stderr
        emitted = runpy.run_path(str(generated))
        assert emitted["FETCHED_AT_UTC"] == "2026-07-10T11:00:00Z"
        assert emitted["SOURCE"] == OFFICIAL_ELO_SOURCE
        assert emitted["SOURCE_SHA256"] == tsv_sha256
        assert emitted["ESTIMATES"] == []
        assert emitted["FETCHED"] == "2026-07-10"
        assert emitted["FETCHED_BASE"] == "2026-07-10"
        load_elo_snapshot(
            generated,
            required_teams=["Argentina", "Switzerland"],
            now_utc=NOW,
            expected_source_sha256=tsv_sha256,
            source_tsv=tsv,
        )
        _expect_error(
            generated,
            "direct",
            required_teams=["Argentina", "Switzerland"],
            now_utc=NOW,
            source_tsv=tsv,
            require_direct_capture=True,
        )

        # A captured response and its receipt are the only inputs eligible for
        # official use. The generated module binds both the body and receipt.
        direct_body = _world_tsv().encode("utf-8")
        direct_tsv = tmp / "elo_evidence_20260710T1155Z_World.tsv"
        direct_receipt = tmp / "elo_evidence_20260710T1155Z_World.receipt.json"
        direct_receipt_payload, _ = _capture(
            direct_tsv,
            direct_receipt,
            body=direct_body,
            completed_at=completed_at,
        )
        direct_module = tmp / "elo_current_direct.py"
        direct_proc = _run_fetch(
            direct_tsv,
            direct_module,
            receipt_path=direct_receipt,
        )
        assert direct_proc.returncode == 0, direct_proc.stderr
        direct_emitted = runpy.run_path(str(direct_module))
        receipt_sha256 = hashlib.sha256(direct_receipt.read_bytes()).hexdigest()
        assert direct_emitted["FETCHED_AT_UTC"] == "2026-07-10T11:55:00Z"
        assert direct_emitted["SOURCE"] == OFFICIAL_ELO_SOURCE
        assert direct_emitted["SOURCE_SHA256"] == hashlib.sha256(direct_body).hexdigest()
        assert direct_emitted["SOURCE_RECEIPT_SHA256"] == receipt_sha256
        assert direct_emitted["CAPTURE_METHOD"] == CAPTURE_METHOD
        assert direct_emitted["SOURCE_BYTE_COUNT"] == len(direct_body)
        direct_loaded = load_elo_snapshot(
            direct_module,
            required_teams=["Argentina", "Switzerland"],
            now_utc=NOW,
            source_tsv=direct_tsv,
            source_receipt=direct_receipt,
            require_direct_capture=True,
        )
        assert direct_loaded.ratings["Argentina"] == 2156

        _expect_error(
            direct_module,
            "receipt",
            required_teams=["Argentina"],
            now_utc=NOW,
            source_tsv=direct_tsv,
            source_receipt=tmp / "missing.receipt.json",
            require_direct_capture=True,
        )
        _expect_error(
            direct_module,
            "receipt",
            required_teams=["Argentina"],
            now_utc=NOW,
            source_tsv=direct_tsv,
            require_direct_capture=True,
        )

        receipt_field_cases = (
            ("schema_bool", {"schema_version": True}, "schema_version"),
            ("artifact_type", {"artifact_type": "wrong"}, "artifact_type"),
            ("capture_method", {"capture_method": "copied_file"}, "capture_method"),
            ("requested_url", {"requested_url": "https://example.com/World.tsv"}, "requested_url"),
            ("final_url", {"final_url": "https://example.com/World.tsv"}, "final_url"),
            ("http_status", {"http_status": 201}, "http_status"),
        )
        for stem, changes, expected_message in receipt_field_cases:
            invalid_receipt = tmp / f"{stem}.receipt.json"
            invalid_payload = dict(direct_receipt_payload)
            invalid_payload.update(changes)
            invalid_receipt.write_text(
                json.dumps(invalid_payload, sort_keys=True) + "\n",
                encoding="ascii",
            )
            invalid_receipt_sha = hashlib.sha256(invalid_receipt.read_bytes()).hexdigest()
            invalid_module = tmp / f"{stem}.py"
            invalid_module.write_text(
                direct_module.read_text(encoding="utf-8").replace(
                    receipt_sha256,
                    invalid_receipt_sha,
                ),
                encoding="utf-8",
            )
            _expect_error(
                invalid_module,
                expected_message,
                required_teams=["Argentina"],
                now_utc=NOW,
                source_tsv=direct_tsv,
                source_receipt=invalid_receipt,
                require_direct_capture=True,
            )

        malformed_receipt = tmp / "malformed.receipt.json"
        malformed_receipt.write_bytes(b"{not-json\n")
        malformed_receipt_sha = hashlib.sha256(malformed_receipt.read_bytes()).hexdigest()
        malformed_module = tmp / "malformed_receipt.py"
        malformed_module.write_text(
            direct_module.read_text(encoding="utf-8").replace(
                receipt_sha256,
                malformed_receipt_sha,
            ),
            encoding="utf-8",
        )
        _expect_error(
            malformed_module,
            "cannot parse",
            required_teams=["Argentina"],
            now_utc=NOW,
            source_tsv=direct_tsv,
            source_receipt=malformed_receipt,
            require_direct_capture=True,
        )

        tampered_receipt = tmp / "tampered.receipt.json"
        tampered_payload = dict(direct_receipt_payload)
        tampered_payload["body_byte_count"] = len(direct_body) + 1
        tampered_receipt.write_text(
            json.dumps(tampered_payload, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        tampered_receipt_sha = hashlib.sha256(tampered_receipt.read_bytes()).hexdigest()
        tampered_module = tmp / "elo_current_tampered_receipt.py"
        tampered_module.write_text(
            direct_module.read_text(encoding="utf-8").replace(
                receipt_sha256,
                tampered_receipt_sha,
            ),
            encoding="utf-8",
        )
        _expect_error(
            tampered_module,
            "byte",
            required_teams=["Argentina"],
            now_utc=NOW,
            source_tsv=direct_tsv,
            source_receipt=tampered_receipt,
            require_direct_capture=True,
        )

        reserialized_receipt = tmp / "reserialized.receipt.json"
        reserialized_receipt.write_bytes(direct_receipt.read_bytes() + b"\n")
        _expect_error(
            direct_module,
            "receipt SHA-256 mismatch",
            required_teams=["Argentina"],
            now_utc=NOW,
            source_tsv=direct_tsv,
            source_receipt=reserialized_receipt,
            require_direct_capture=True,
        )

        bad_body_hash_receipt = tmp / "bad_body_hash.receipt.json"
        bad_body_hash_payload = dict(direct_receipt_payload)
        bad_body_hash_payload["body_sha256"] = "0" * 64
        bad_body_hash_receipt.write_text(
            json.dumps(bad_body_hash_payload, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        _expect_error(
            direct_module,
            "SHA-256 mismatch",
            required_teams=["Argentina"],
            now_utc=NOW,
            source_tsv=direct_tsv,
            source_receipt=bad_body_hash_receipt,
            require_direct_capture=True,
        )

        # Renaming an identical byte copy does not make it the response named
        # by the receipt. Reject it at both generation and load boundaries.
        renamed_tsv = tmp / "renamed_copy_World.tsv"
        shutil.copyfile(direct_tsv, renamed_tsv)
        renamed_module = tmp / "renamed_copy.py"
        renamed_proc = _run_fetch(
            renamed_tsv,
            renamed_module,
            receipt_path=direct_receipt,
        )
        assert renamed_proc.returncode != 0
        assert "evidence_file" in renamed_proc.stderr
        assert not renamed_module.exists()
        _expect_error(
            direct_module,
            "evidence_file",
            required_teams=["Argentina"],
            now_utc=NOW,
            source_tsv=renamed_tsv,
            source_receipt=direct_receipt,
            require_direct_capture=True,
        )

        stale_direct_tsv = tmp / "elo_evidence_20260710T1129Z_World.tsv"
        stale_direct_receipt = (
            tmp / "elo_evidence_20260710T1129Z_World.receipt.json"
        )
        _capture(
            stale_direct_tsv,
            stale_direct_receipt,
            body=direct_body,
            completed_at=NOW - timedelta(minutes=31),
        )
        stale_direct_module = tmp / "elo_current_stale_direct.py"
        stale_direct_proc = _run_fetch(
            stale_direct_tsv,
            stale_direct_module,
            receipt_path=stale_direct_receipt,
        )
        assert stale_direct_proc.returncode == 0, stale_direct_proc.stderr
        _expect_error(
            stale_direct_module,
            "stale",
            required_teams=["Argentina"],
            max_age_hours=0.5,
            now_utc=NOW,
            source_tsv=stale_direct_tsv,
            source_receipt=stale_direct_receipt,
            require_direct_capture=True,
        )

        future_direct_tsv = tmp / "elo_evidence_20260710T1201Z_World.tsv"
        future_direct_receipt = (
            tmp / "elo_evidence_20260710T1201Z_World.receipt.json"
        )
        _capture(
            future_direct_tsv,
            future_direct_receipt,
            body=direct_body,
            completed_at=NOW + timedelta(minutes=1),
        )
        future_direct_module = tmp / "elo_current_future_direct.py"
        future_direct_proc = _run_fetch(
            future_direct_tsv,
            future_direct_module,
            receipt_path=future_direct_receipt,
        )
        assert future_direct_proc.returncode == 0, future_direct_proc.stderr
        _expect_error(
            future_direct_module,
            "future",
            required_teams=["Argentina"],
            now_utc=NOW,
            source_tsv=future_direct_tsv,
            source_receipt=future_direct_receipt,
            require_direct_capture=True,
        )

        # A caller cannot pair an old receipt with a newly stamped module to
        # bypass freshness. The module timestamp must equal response completion.
        old_timestamp = "2026-07-10T11:29:00Z"
        restamped_timestamp = "2026-07-10T11:55:00Z"
        old_receipt_restamped_module = tmp / "elo_current_old_receipt_restamped.py"
        old_receipt_restamped_module.write_text(
            stale_direct_module.read_text(encoding="utf-8").replace(
                old_timestamp,
                restamped_timestamp,
            ),
            encoding="utf-8",
        )
        _expect_error(
            old_receipt_restamped_module,
            "receipt",
            required_teams=["Argentina"],
            max_age_hours=0.5,
            now_utc=NOW,
            source_tsv=stale_direct_tsv,
            source_receipt=stale_direct_receipt,
            require_direct_capture=True,
        )

        changed_tsv = tmp / "changed_World.tsv"
        changed_tsv.write_text(
            _world_tsv().replace("\tAR\t2156\n", "\tAR\t2155\n"),
            encoding="utf-8",
        )
        _expect_error(
            generated,
            "SHA-256 mismatch",
            required_teams=["Argentina"],
            source_tsv=changed_tsv,
        )

        handwritten = tmp / "handwritten.py"
        handwritten.write_text(
            _snapshot_text(source_sha256=tsv_sha256, argentina_rating=999),
            encoding="utf-8",
        )
        _expect_error(
            handwritten,
            "current Elo mismatch for Argentina",
            required_teams=["Argentina", "Switzerland"],
            source_tsv=tsv,
        )

        unparseable_tsv = tmp / "unparseable_World.tsv"
        unparseable_tsv.write_text("not an official World.tsv\n", encoding="utf-8")
        unparseable_module = tmp / "unparseable_source.py"
        unparseable_module.write_text(
            _snapshot_text(
                source_sha256=hashlib.sha256(unparseable_tsv.read_bytes()).hexdigest()
            ),
            encoding="utf-8",
        )
        _expect_error(
            unparseable_module,
            "cannot parse World.tsv",
            required_teams=["Argentina"],
            source_tsv=unparseable_tsv,
        )

        rejected_output = tmp / "must_not_exist.py"
        missing_team_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "fetch_elo_current.py"),
                "--tsv",
                str(tsv),
                "--out",
                str(rejected_output),
                "--required-team",
                "Scotland",
                "--fetched-at-utc",
                "2026-07-10T11:00:00Z",
                "--allow-unverified-replay",
            ],
            cwd=tmp,
            capture_output=True,
            text=True,
            check=False,
        )
        assert missing_team_proc.returncode != 0
        assert "Scotland" in missing_team_proc.stderr
        assert not rejected_output.exists()

        if not (ROOT / "generate_paper_signals.py").is_file():
            print("Elo provenance parser/helper tests passed (paper integration not bundled).")
            return

        context = tmp / "context.json"
        weather_snapshot = "synthetic kickoff-hour forecast"
        runtime_now = datetime.now(timezone.utc).replace(microsecond=0)
        kickoff_at = runtime_now + timedelta(hours=2)
        checked_at = runtime_now - timedelta(minutes=1)
        issued_at = runtime_now - timedelta(minutes=2)
        context.write_text(
            json.dumps(
                {
                    "matches": {
                        "Argentina|Switzerland": {
                            "market_odds": [1.8, 3.5, 4.5],
                            "market_method": "proportional",
                            "weather_scale": 1.0,
                            "kickoff_at_utc": kickoff_at.isoformat(),
                            "weather_checked_at_utc": checked_at.isoformat(),
                            "weather_forecast_issued_at_utc": issued_at.isoformat(),
                            "weather_forecast_valid_at_utc": kickoff_at.isoformat(),
                            "weather_source": "https://weather.example/hourly",
                            "weather_evidence_type": "hourly",
                            "weather_decision": "none",
                            "weather_evidence_snapshot": weather_snapshot,
                            "weather_evidence_sha256": hashlib.sha256(
                                weather_snapshot.encode("utf-8")
                            ).hexdigest(),
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        runtime_tsv = tmp / "runtime_World.tsv"
        runtime_receipt = tmp / "runtime_World.receipt.json"
        _capture(
            runtime_tsv,
            runtime_receipt,
            body=_world_tsv().encode("utf-8"),
            completed_at=runtime_now,
        )
        fresh_runtime = tmp / "fresh_runtime.py"
        fresh_runtime_proc = _run_fetch(
            runtime_tsv,
            fresh_runtime,
            receipt_path=runtime_receipt,
        )
        assert fresh_runtime_proc.returncode == 0, fresh_runtime_proc.stderr
        estimated_runtime = tmp / "estimated_runtime.py"
        estimated_runtime.write_text(
            fresh_runtime.read_text(encoding="utf-8").replace(
                "ESTIMATES = []",
                "ESTIMATES = ['Switzerland']",
            ),
            encoding="utf-8",
        )
        signals = tmp / "signals.csv"
        signal_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "generate_paper_signals.py"),
                "--context-file",
                str(context),
                "--output-csv",
                str(signals),
                "--date",
                "2026-07-10",
                "--stage",
                "QF",
                "--elo-module",
                str(estimated_runtime),
                "--elo-source-tsv",
                str(runtime_tsv),
                "--elo-receipt",
                str(runtime_receipt),
                "--max-odds-age-minutes",
                "0",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert signal_proc.returncode != 0
        assert "estimated Elo" in signal_proc.stderr
        assert not signals.exists()

        success_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "generate_paper_signals.py"),
                "--context-file",
                str(context),
                "--output-csv",
                str(signals),
                "--date",
                "2026-07-10",
                "--stage",
                "QF",
                "--elo-module",
                str(fresh_runtime),
                "--elo-source-tsv",
                str(runtime_tsv),
                "--elo-receipt",
                str(runtime_receipt),
                "--max-odds-age-minutes",
                "0",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert success_proc.returncode == 0, success_proc.stderr
        assert signals.exists()

        # Current-Elo official paths may not apply a fixture CSV's legacy heat
        # override on top of an auditable context decision, even when that
        # decision is the neutral scale=1.00 case.
        legacy_fixture = tmp / "legacy_heat_fixture.csv"
        legacy_fixture.write_text(
            "home,away,heat\nArgentina,Switzerland,severe\n",
            encoding="utf-8",
        )
        legacy_signals = tmp / "legacy_heat_signals.csv"
        legacy_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "generate_paper_signals.py"),
                "--context-file",
                str(context),
                "--fixture-csv",
                str(legacy_fixture),
                "--output-csv",
                str(legacy_signals),
                "--date",
                "2026-07-10",
                "--stage",
                "QF",
                "--elo-module",
                str(fresh_runtime),
                "--elo-source-tsv",
                str(runtime_tsv),
                "--elo-receipt",
                str(runtime_receipt),
                "--max-odds-age-minutes",
                "0",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert legacy_proc.returncode != 0
        assert "legacy heat=severe conflicts" in legacy_proc.stderr
        assert not legacy_signals.exists()

    print("Elo provenance tests passed.")


if __name__ == "__main__":
    main()
