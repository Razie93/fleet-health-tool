"""Unit tests for the system monitor."""

import json
from unittest.mock import patch

import pytest

from src.monitor import check_system_health, main


@patch("src.monitor.psutil.disk_usage")
@patch("src.monitor.psutil.virtual_memory")
@patch("src.monitor.psutil.cpu_percent")
def test_returns_empty_dictionary_when_usage_is_within_thresholds(
    mock_cpu_percent,
    mock_virtual_memory,
    mock_disk_usage,
) -> None:
    """No alerts are returned when all readings are within their limits."""
    mock_cpu_percent.return_value = 40.0
    mock_virtual_memory.return_value.percent = 50.0
    mock_disk_usage.return_value.percent = 60.0

    alerts = check_system_health(
        cpu_threshold=80.0,
        memory_threshold=80.0,
        disk_threshold=80.0,
        disk_path="/",
    )

    assert alerts == {}


@patch("src.monitor.psutil.disk_usage")
@patch("src.monitor.psutil.virtual_memory")
@patch("src.monitor.psutil.cpu_percent")
def test_returns_structured_alerts_for_each_exceeded_threshold(
    mock_cpu_percent,
    mock_virtual_memory,
    mock_disk_usage,
) -> None:
    """Every breached resource is represented by a structured alert."""
    mock_cpu_percent.return_value = 95.0
    mock_virtual_memory.return_value.percent = 88.0
    mock_disk_usage.return_value.percent = 90.0

    alerts = check_system_health(
        cpu_threshold=80.0,
        memory_threshold=75.0,
        disk_threshold=70.0,
        disk_path="/",
    )

    assert alerts == {
        "cpu": {"value": 95.0, "threshold": 80.0, "unit": "percent"},
        "memory": {"value": 88.0, "threshold": 75.0, "unit": "percent"},
        "disk": {"value": 90.0, "threshold": 70.0, "unit": "percent"},
    }


@patch("src.monitor.psutil.disk_usage")
@patch("src.monitor.psutil.virtual_memory")
@patch("src.monitor.psutil.cpu_percent")
def test_usage_equal_to_threshold_does_not_trigger_an_alert(
    mock_cpu_percent,
    mock_virtual_memory,
    mock_disk_usage,
) -> None:
    """A reading must be greater than its threshold to trigger an alert."""
    mock_cpu_percent.return_value = 80.0
    mock_virtual_memory.return_value.percent = 80.0
    mock_disk_usage.return_value.percent = 80.0

    alerts = check_system_health(disk_path="/")

    assert alerts == {}


@pytest.mark.parametrize("invalid_threshold", [-1.0, 101.0])
def test_rejects_thresholds_outside_percentage_range(
    invalid_threshold: float,
) -> None:
    """Percentage thresholds must remain between zero and one hundred."""
    with pytest.raises(ValueError, match="between 0 and 100"):
        check_system_health(cpu_threshold=invalid_threshold)


@patch("src.monitor.psutil.disk_usage")
@patch("src.monitor.psutil.virtual_memory")
@patch("src.monitor.psutil.cpu_percent")
def test_cli_writes_alerts_to_json_output_and_log_file(
    mock_cpu_percent,
    mock_virtual_memory,
    mock_disk_usage,
    tmp_path,
    capsys,
) -> None:
    """The CLI reports threshold breaches to stdout and a log file."""
    mock_cpu_percent.return_value = 25.0
    mock_virtual_memory.return_value.percent = 30.0
    mock_disk_usage.return_value.percent = 35.0
    log_file = tmp_path / "monitor.log"

    exit_code = main(
        [
            "--threshold",
            "1",
            "--cpu-sample-interval",
            "0",
            "--log-file",
            str(log_file),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert set(output) == {"cpu", "memory", "disk"}
    assert "exceeded threshold 1.00%" in log_file.read_text(encoding="utf-8")
