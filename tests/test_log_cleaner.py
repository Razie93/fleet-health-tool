"""Unit tests for log parsing and rotation."""

import gzip

from src.log_cleaner import find_error_lines, rotate_log_if_needed


def test_find_error_lines_returns_error_and_critical_entries(tmp_path) -> None:
    """Only error-level log entries are returned."""
    log_file = tmp_path / "fleet_health.log"
    log_file.write_text(
        "INFO Service started\n"
        "WARNING CPU threshold exceeded\n"
        "ERROR Disk check failed\n"
        "CRITICAL Host unavailable\n",
        encoding="utf-8",
    )

    assert find_error_lines(log_file) == [
        "ERROR Disk check failed",
        "CRITICAL Host unavailable",
    ]


def test_rotate_log_if_needed_creates_gzip_and_truncates_source(tmp_path) -> None:
    """An oversized log is archived losslessly before being truncated."""
    log_file = tmp_path / "fleet_health.log"
    original_content = "WARNING threshold exceeded\n" * 20
    log_file.write_text(original_content, encoding="utf-8")

    archive = rotate_log_if_needed(log_file, max_size_mb=0.0001)

    assert archive is not None
    assert archive.suffix == ".gz"
    assert log_file.read_text(encoding="utf-8") == ""
    with gzip.open(archive, mode="rt", encoding="utf-8") as compressed:
        assert compressed.read() == original_content


def test_rotate_log_if_needed_leaves_small_log_unchanged(tmp_path) -> None:
    """A log below the configured maximum is not rotated."""
    log_file = tmp_path / "fleet_health.log"
    log_file.write_text("INFO Healthy\n", encoding="utf-8")

    archive = rotate_log_if_needed(log_file, max_size_mb=5.0)

    assert archive is None
    assert log_file.read_text(encoding="utf-8") == "INFO Healthy\n"
