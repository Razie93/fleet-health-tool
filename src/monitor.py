"""Monitor CPU, memory, and disk utilization with configurable thresholds."""

from __future__ import annotations

import argparse
import json
import logging
import math
from os import PathLike
from pathlib import Path
from typing import Sequence, TypedDict

import psutil

LOGGER = logging.getLogger(__name__)
DEFAULT_THRESHOLD = 80.0


class Alert(TypedDict):
    """Structured details for a resource threshold breach."""

    value: float
    threshold: float
    unit: str


def _validate_threshold(name: str, threshold: float) -> None:
    """Raise ``ValueError`` when a percentage threshold is invalid."""
    if not math.isfinite(threshold) or not 0.0 <= threshold <= 100.0:
        raise ValueError(f"{name} threshold must be between 0 and 100")


def check_system_health(
    *,
    cpu_threshold: float = DEFAULT_THRESHOLD,
    memory_threshold: float = DEFAULT_THRESHOLD,
    disk_threshold: float = DEFAULT_THRESHOLD,
    disk_path: str | PathLike[str] = "/",
    cpu_sample_interval: float = 0.1,
) -> dict[str, Alert]:
    """Check system utilization and return alerts for breached thresholds.

    Args:
        cpu_threshold: Maximum allowed CPU utilization percentage.
        memory_threshold: Maximum allowed memory utilization percentage.
        disk_threshold: Maximum allowed disk utilization percentage.
        disk_path: Filesystem path whose disk utilization should be checked.
        cpu_sample_interval: Seconds over which CPU utilization is sampled.

    Returns:
        A dictionary keyed by resource name. Each value contains the measured
        percentage, configured threshold, and measurement unit. The dictionary
        is empty when no threshold is exceeded.

    Raises:
        ValueError: If a threshold is outside the inclusive range 0 to 100.
    """
    thresholds = {
        "cpu": float(cpu_threshold),
        "memory": float(memory_threshold),
        "disk": float(disk_threshold),
    }
    for resource, threshold in thresholds.items():
        _validate_threshold(resource, threshold)

    readings = {
        "cpu": float(psutil.cpu_percent(interval=cpu_sample_interval)),
        "memory": float(psutil.virtual_memory().percent),
        "disk": float(psutil.disk_usage(disk_path).percent),
    }

    alerts: dict[str, Alert] = {}
    for resource, value in readings.items():
        threshold = thresholds[resource]
        if value > threshold:
            alerts[resource] = {
                "value": value,
                "threshold": threshold,
                "unit": "percent",
            }
            LOGGER.warning(
                "%s usage %.2f%% exceeded threshold %.2f%%",
                resource.capitalize(),
                value,
                threshold,
            )

    if not alerts:
        LOGGER.info("System utilization is within configured thresholds")

    return alerts


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Check CPU, memory, and disk utilization.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="Alert threshold percentage for every resource (default: 80).",
    )
    parser.add_argument(
        "--disk-path",
        default="/",
        help="Filesystem path to inspect (default: /).",
    )
    parser.add_argument(
        "--cpu-sample-interval",
        type=float,
        default=0.1,
        help="CPU sampling duration in seconds (default: 0.1).",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("monitor.log"),
        help="Destination for monitor logs (default: monitor.log).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a health check from the command line.

    Args:
        argv: Optional command-line arguments. Uses process arguments when
            omitted.

    Returns:
        ``1`` when at least one alert is raised; otherwise ``0``.
    """
    args = _build_parser().parse_args(argv)
    file_handler = logging.FileHandler(args.log_file, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    LOGGER.addHandler(file_handler)
    LOGGER.setLevel(logging.INFO)

    try:
        alerts = check_system_health(
            cpu_threshold=args.threshold,
            memory_threshold=args.threshold,
            disk_threshold=args.threshold,
            disk_path=args.disk_path,
            cpu_sample_interval=args.cpu_sample_interval,
        )
    finally:
        LOGGER.removeHandler(file_handler)
        file_handler.close()

    print(json.dumps(alerts, indent=2, sort_keys=True))
    return 1 if alerts else 0


if __name__ == "__main__":
    raise SystemExit(main())
