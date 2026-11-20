"""Parse error entries and gzip logs that exceed a configured size."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

DEFAULT_LOG_FILE = Path("fleet_health.log")
DEFAULT_MAX_SIZE_MB = 5.0
ERROR_PATTERN = re.compile(r"\b(?:ERROR|CRITICAL)\b", re.IGNORECASE)


def find_error_lines(log_file: str | Path) -> list[str]:
    """Return log lines containing an ERROR or CRITICAL level marker.

    Args:
        log_file: UTF-8 log file to inspect.

    Returns:
        Matching lines without trailing newline characters.

    Raises:
        FileNotFoundError: If ``log_file`` does not exist.
        PermissionError: If the file cannot be read.
    """
    path = Path(log_file)
    with path.open(mode="r", encoding="utf-8", errors="replace") as stream:
        return [
            line.rstrip("\r\n")
            for line in stream
            if ERROR_PATTERN.search(line)
        ]


def rotate_log_if_needed(
    log_file: str | Path,
    *,
    max_size_mb: float = DEFAULT_MAX_SIZE_MB,
    archive_dir: str | Path | None = None,
) -> Path | None:
    """Compress and truncate a log when it exceeds ``max_size_mb``.

    The compressed archive is completed before the source log is truncated.

    Args:
        log_file: Log file to rotate.
        max_size_mb: Maximum size in mebibytes before rotation.
        archive_dir: Optional archive destination. Defaults to the log's
            directory.

    Returns:
        The created gzip archive path, or ``None`` when rotation is unnecessary.

    Raises:
        ValueError: If ``max_size_mb`` is not a finite positive number.
        FileNotFoundError: If ``log_file`` does not exist.
        PermissionError: If source or destination access is denied.
    """
    if not math.isfinite(max_size_mb) or max_size_mb <= 0:
        raise ValueError("max_size_mb must be a finite number greater than zero")

    source = Path(log_file)
    if source.stat().st_size <= max_size_mb * 1024 * 1024:
        return None

    destination_dir = (
        Path(archive_dir) if archive_dir is not None else source.parent
    )
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    archive = destination_dir / f"{source.name}.{timestamp}.gz"
    temporary_archive = archive.with_suffix(f"{archive.suffix}.tmp")

    try:
        with source.open(mode="rb") as input_stream:
            with gzip.open(temporary_archive, mode="wb") as output_stream:
                shutil.copyfileobj(input_stream, output_stream)
        temporary_archive.replace(archive)
    except Exception:
        temporary_archive.unlink(missing_ok=True)
        raise

    source.write_bytes(b"")
    return archive


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Find errors and rotate an oversized log into gzip.",
    )
    parser.add_argument(
        "log_file",
        nargs="?",
        type=Path,
        default=DEFAULT_LOG_FILE,
        help="Log to inspect (default: fleet_health.log).",
    )
    parser.add_argument(
        "--max-size-mb",
        type=float,
        default=DEFAULT_MAX_SIZE_MB,
        help="Rotate above this size in MiB (default: 5.0).",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        help="Optional archive directory (default: beside the log).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse a log, rotate it when needed, and print a JSON summary."""
    args = _build_parser().parse_args(argv)
    error_lines = find_error_lines(args.log_file)
    archive = rotate_log_if_needed(
        args.log_file,
        max_size_mb=args.max_size_mb,
        archive_dir=args.archive_dir,
    )
    print(
        json.dumps(
            {
                "archive": str(archive) if archive is not None else None,
                "error_count": len(error_lines),
                "errors": error_lines,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
