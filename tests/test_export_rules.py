from datetime import datetime, timezone
from types import SimpleNamespace

from custom_components.emergency_stop.coordinator import EmergencyStopCoordinator
from custom_components.emergency_stop.const import CONF_RULES


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
