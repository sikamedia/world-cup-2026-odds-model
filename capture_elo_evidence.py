#!/usr/bin/env python3
"""Capture the official World.tsv response body and an audit receipt."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Callable
from urllib.request import Request, urlopen

from elo_snapshot import (
    DIRECT_HTTP_CAPTURE_METHOD,
    ELO_CAPTURE_RECEIPT_TYPE,
    ELO_CAPTURE_RECEIPT_VERSION,
    MAX_ELO_BODY_BYTES,
    OFFICIAL_ELO_SOURCE,
)


class EloCaptureError(RuntimeError):
    """Raised when the raw HTTP evidence cannot be captured safely."""


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise EloCaptureError("response completion time must include a timezone offset")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _canonical_receipt_bytes(receipt: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            receipt,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )


def _response_status(response: Any) -> int:
    status = getattr(response, "status", None)
    if status is None:
        getcode = getattr(response, "getcode", None)
        status = getcode() if callable(getcode) else None
    if isinstance(status, bool) or not isinstance(status, int):
        raise EloCaptureError(f"HTTP response has invalid status: {status!r}")
    return status


def capture_elo_evidence(
    tsv_out: str | Path,
    receipt_out: str | Path,
    *,
    timeout_seconds: float = 30.0,
    opener: Callable[..., Any] | None = None,
    clock: Callable[[], datetime] | None = None,
    monotonic_clock: Callable[[], float] | None = None,
) -> dict[str, Any]:
    """Write the unmodified response body and its create-only receipt."""

    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise EloCaptureError("timeout_seconds must be a positive finite number")
    timeout = float(timeout_seconds)
    if not math.isfinite(timeout) or timeout <= 0:
        raise EloCaptureError("timeout_seconds must be a positive finite number")

    tsv_path = Path(tsv_out)
    receipt_path = Path(receipt_out)
    if tsv_path.resolve() == receipt_path.resolve():
        raise EloCaptureError("TSV evidence and receipt paths must be different")
    for path in (tsv_path, receipt_path):
        if path.exists():
            raise EloCaptureError(
                f"capture output already exists and will not be overwritten: {path}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)

    open_request = opener or urlopen
    now = clock or (lambda: datetime.now(timezone.utc))
    monotonic = monotonic_clock or time.monotonic
    started_at = monotonic()
    request = Request(
        OFFICIAL_ELO_SOURCE,
        headers={
            "Accept-Encoding": "identity",
            "User-Agent": "world-cup-2026-odds-model/elo-evidence",
        },
    )
    created_tsv = False
    created_receipt = False
    try:
        with open_request(request, timeout=timeout) as response:
            status = _response_status(response)
            final_url = response.geturl()
            if status != 200:
                raise EloCaptureError(f"World.tsv HTTP status must be 200; got {status}")
            if final_url != OFFICIAL_ELO_SOURCE:
                raise EloCaptureError(
                    f"World.tsv final URL must be exactly {OFFICIAL_ELO_SOURCE!r}; "
                    f"got {final_url!r}"
                )
            headers = getattr(response, "headers", {})
            raw_content_length = headers.get("Content-Length") if headers is not None else None
            declared_length = None
            if raw_content_length is not None:
                try:
                    declared_length = int(raw_content_length)
                except (TypeError, ValueError) as exc:
                    raise EloCaptureError(
                        f"World.tsv has invalid Content-Length: {raw_content_length!r}"
                    ) from exc
                if declared_length < 0:
                    raise EloCaptureError(
                        f"World.tsv has invalid Content-Length: {raw_content_length!r}"
                    )
                if declared_length > MAX_ELO_BODY_BYTES:
                    raise EloCaptureError(
                        f"World.tsv Content-Length exceeds {MAX_ELO_BODY_BYTES} bytes"
                    )

            digest = hashlib.sha256()
            byte_count = 0
            with tsv_path.open("xb") as evidence:
                created_tsv = True
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    if not isinstance(chunk, bytes):
                        raise EloCaptureError("HTTP response body reader returned non-bytes data")
                    if monotonic() - started_at > timeout:
                        raise EloCaptureError(
                            f"World.tsv capture exceeded {timeout:g} seconds"
                        )
                    if byte_count + len(chunk) > MAX_ELO_BODY_BYTES:
                        raise EloCaptureError(
                            f"World.tsv response body exceeds {MAX_ELO_BODY_BYTES} bytes"
                        )
                    evidence.write(chunk)
                    digest.update(chunk)
                    byte_count += len(chunk)
                completed_at = _utc_text(now())
                evidence.flush()
                os.fsync(evidence.fileno())

        if byte_count == 0:
            raise EloCaptureError("World.tsv HTTP response body is empty")
        if declared_length is not None and byte_count != declared_length:
            raise EloCaptureError(
                f"World.tsv Content-Length mismatch: header={declared_length}, "
                f"body={byte_count}"
            )
        receipt = {
            "schema_version": ELO_CAPTURE_RECEIPT_VERSION,
            "artifact_type": ELO_CAPTURE_RECEIPT_TYPE,
            "capture_method": DIRECT_HTTP_CAPTURE_METHOD,
            "requested_url": OFFICIAL_ELO_SOURCE,
            "final_url": OFFICIAL_ELO_SOURCE,
            "http_status": 200,
            "response_completed_at_utc": completed_at,
            "evidence_file": tsv_path.name,
            "body_byte_count": byte_count,
            "body_sha256": digest.hexdigest(),
        }
        with receipt_path.open("xb") as receipt_file:
            created_receipt = True
            receipt_file.write(_canonical_receipt_bytes(receipt))
            receipt_file.flush()
            os.fsync(receipt_file.fileno())
        os.chmod(tsv_path, 0o444)
        os.chmod(receipt_path, 0o444)
        return receipt
    except Exception:
        if created_receipt:
            receipt_path.unlink(missing_ok=True)
        if created_tsv:
            tsv_path.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tsv-out", required=True, help="create-only raw World.tsv output")
    parser.add_argument("--receipt-out", required=True, help="create-only capture receipt JSON")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    try:
        receipt = capture_elo_evidence(
            args.tsv_out,
            args.receipt_out,
            timeout_seconds=args.timeout_seconds,
        )
    except (EloCaptureError, OSError) as exc:
        parser.error(str(exc))
    print(
        f"captured {args.tsv_out}: {receipt['body_byte_count']} bytes "
        f"sha256={receipt['body_sha256']} receipt={args.receipt_out}"
    )


if __name__ == "__main__":
    main()
