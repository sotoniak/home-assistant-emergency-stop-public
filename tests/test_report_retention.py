import os
import time

from custom_components.emergency_stop.coordinator import EmergencyStopCoordinator


def _touch(path, mtime):
    path.write_text("{}\n")
    os.utime(path, (mtime, mtime))


def test_report_retention_max_files(monkeypatch, tmp_path):
    monkeypatch.setattr("custom_components.emergency_stop.coordinator.REPORT_LOG_DIR", tmp_path)
    coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
    coordinator._report_retention_max_files = 2
    coordinator._report_retention_max_age_days = 0

    now = time.time()
    _touch(tmp_path / "emergency_stop_report_1.json", now - 30)
    _touch(tmp_path / "emergency_stop_report_2.json", now - 20)
    _touch(tmp_path / "emergency_stop_report_3.json", now - 10)

    coordinator._cleanup_reports()

    remaining = sorted(p.name for p in tmp_path.iterdir())
    assert remaining == [
        "emergency_stop_report_2.json",
        "emergency_stop_report_3.json",
    ]


def test_report_retention_max_age(monkeypatch, tmp_path):
    monkeypatch.setattr("custom_components.emergency_stop.coordinator.REPORT_LOG_DIR", tmp_path)
    coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
    coordinator._report_retention_max_files = 0
    coordinator._report_retention_max_age_days = 1

    now = time.time()
    _touch(tmp_path / "emergency_stop_report_old.json", now - 90000)
    _touch(tmp_path / "emergency_stop_report_new.json", now - 3600)

    coordinator._cleanup_reports()

    remaining = sorted(p.name for p in tmp_path.iterdir())
    assert remaining == ["emergency_stop_report_new.json"]
