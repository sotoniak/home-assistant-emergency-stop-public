from datetime import datetime, timezone
from types import SimpleNamespace
from pathlib import Path

from custom_components.emergency_stop.coordinator import EmergencyStopCoordinator
from custom_components.emergency_stop.const import (
    CONF_BREVO_API_KEY,
    CONF_REPORT_MODE,
    CONF_RULES,
)


def test_build_rules_export_includes_rules(monkeypatch):
    fixed_now = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "custom_components.emergency_stop.coordinator.dt_util.utcnow",
        lambda: fixed_now,
    )

    coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
    coordinator.entry = SimpleNamespace(
        entry_id="entry_1",
        data={CONF_RULES: [{"rule_id": "rule_1"}]},
        options={},
    )

    export = coordinator._build_rules_export()

    assert export["rules"] == [{"rule_id": "rule_1"}]
    assert export["generated_at"] == fixed_now.isoformat()
    assert export["file_name"].startswith("emergency_stop_rules_entry_1_")


def test_build_settings_export_includes_brevo_and_excludes_rules(monkeypatch):
    fixed_now = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "custom_components.emergency_stop.coordinator.dt_util.utcnow",
        lambda: fixed_now,
    )

    coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
    coordinator.entry = SimpleNamespace(
        entry_id="entry_1",
        data={
            CONF_RULES: [{"rule_id": "rule_1"}],
            CONF_BREVO_API_KEY: "secret-key",
            CONF_REPORT_MODE: "basic",
        },
        options={},
    )

    export = coordinator._build_settings_export()

    assert export["generated_at"] == fixed_now.isoformat()
    assert export["file_name"].startswith("emergency_stop_settings_entry_1_")
    assert export["settings"][CONF_BREVO_API_KEY] == "secret-key"
    assert export["settings"][CONF_REPORT_MODE] == "basic"
    assert CONF_RULES not in export["settings"]


def test_async_export_settings_writes_file_and_returns_path(tmp_path):
    async def run():
        coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
        coordinator.entry = SimpleNamespace(
            entry_id="entry_1",
            data={CONF_RULES: [{"rule_id": "rule_1"}]},
            options={},
        )
        async def async_add_executor_job(func, *args):
            func(*args)
        coordinator.hass = SimpleNamespace(
            async_add_executor_job=async_add_executor_job
        )

        captured: dict[str, object] = {}

        def fake_write_report_file(path: Path, report: dict):
            captured["path"] = path
            captured["report"] = report

        coordinator._write_report_file = fake_write_report_file
        coordinator._build_settings_export = lambda: {
            "file_name": "emergency_stop_settings_entry_1_20260205T120000Z.json",
            "settings": {"x": 1},
        }

        export_path = await coordinator.async_export_settings()

        assert str(export_path).endswith(
            "/media/emergency-stop/config/emergency_stop_settings_entry_1_20260205T120000Z.json"
        )
        assert captured["path"] == export_path
        assert captured["report"]["settings"]["x"] == 1

    __import__("asyncio").run(run())
