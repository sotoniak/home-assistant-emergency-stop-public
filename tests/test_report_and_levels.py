from datetime import datetime, timezone
from types import SimpleNamespace

from custom_components.emergency_stop.coordinator import EmergencyStopState, RuleConfig, RuleRuntimeState
from custom_components.emergency_stop.const import (
    CONF_REPORT_DOMAINS,
    CONF_REPORT_ENTITY_IDS,
    CONF_REPORT_MODE,
    CONF_REPORT_RETENTION_MAX_AGE_DAYS,
    CONF_REPORT_RETENTION_MAX_FILES,
    CONF_BREVO_RECIPIENT,
    CONF_BREVO_RECIPIENT_LIMIT,
    CONF_BREVO_RECIPIENT_NOTIFY,
    CONF_BREVO_RECIPIENT_SHUTDOWN,
    CONF_EMAIL_LEVELS,
    CONF_RULES,
    LEVEL_LIMIT,
    LEVEL_NORMAL,
    LEVEL_NOTIFY,
    LEVEL_SHUTDOWN,
    DEFAULT_EMAIL_LEVELS,
    DEFAULT_REPORT_RETENTION_MAX_AGE_DAYS,
    DEFAULT_REPORT_RETENTION_MAX_FILES,
    REPORT_MODE_EXTENDED,
)
from custom_components.emergency_stop.sensor import EmergencyStopLevelSensor


class FakeState:
    def __init__(self, state, attributes=None):
        self.state = state
        self.attributes = attributes or {}


class FakeStates:
    def __init__(self, mapping):
        self._mapping = mapping

    def get(self, entity_id):
        return self._mapping.get(entity_id)


class FakeHass:
    def __init__(self, mapping):
        self.states = FakeStates(mapping)


class DummyCoordinator:
    def __init__(self, level):
        self.stop_state = EmergencyStopState(level=level)

    def async_add_listener(self, update_callback):
        return lambda: None


def test_level_sensor_reflects_action_levels():
    coordinator = DummyCoordinator(LEVEL_LIMIT)
    level_sensor = EmergencyStopLevelSensor(coordinator)

    assert level_sensor.native_value == LEVEL_LIMIT

    coordinator.stop_state.level = None
    assert level_sensor.native_value == LEVEL_NORMAL


def test_level_sensor_icon_by_level():
    coordinator = DummyCoordinator(LEVEL_NORMAL)
    level_sensor = EmergencyStopLevelSensor(coordinator)

    assert level_sensor.icon == "mdi:checkbox-blank-circle-outline"

    coordinator.stop_state.level = LEVEL_NOTIFY
    assert level_sensor.icon == "mdi:alpha-i-circle-outline"

    coordinator.stop_state.level = LEVEL_LIMIT
    assert level_sensor.icon == "mdi:alert-circle"

    coordinator.stop_state.level = LEVEL_SHUTDOWN
    assert level_sensor.icon == "mdi:alert-octagon"


def test_report_generation_contains_config_and_states(monkeypatch):
    fixed_now = datetime(2026, 2, 2, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "custom_components.emergency_stop.coordinator.dt_util.utcnow",
        lambda: fixed_now,
    )

    rules = [
        {
            "rule_id": "voltage_high",
            "rule_name": "Voltage High",
            "data_type": "numeric",
            "entities": ["sensor.pack1_max", "sensor.pack1_max_b"],
            "aggregate": "max",
            "condition": "gt",
            "thresholds": [3.5],
            "duration_seconds": 5,
            "interval_seconds": 1,
            "level": "shutdown",
            "latched": True,
            "unknown_handling": "ignore",
            "text_case_sensitive": False,
            "text_trim": True,
        }
    ]

    states = {
        "sensor.pack1_max": FakeState("3.4", {"friendly_name": "Pack 1 Max"}),
        "sensor.pack1_max_b": FakeState("3.6", {"friendly_name": "Pack 1 Max B"}),
    }

    rule_configs = [
        RuleConfig(
            rule_id="voltage_high",
            name="Voltage High",
            data_type="numeric",
            entities=["sensor.pack1_max", "sensor.pack1_max_b"],
            aggregate="max",
            condition="gt",
            thresholds=[3.5],
            duration_seconds=5,
            interval_seconds=1,
            level="shutdown",
            latched=True,
            unknown_handling="ignore",
            severity_mode="simple",
            direction=None,
            levels={},
            text_case_sensitive=False,
            text_trim=True,
        )
    ]
    rule_states = {
        "voltage_high": RuleRuntimeState(active=False),
    }

    fake = SimpleNamespace(
        hass=FakeHass(states),
        entry=SimpleNamespace(
            data={
                CONF_RULES: rules,
                CONF_REPORT_MODE: REPORT_MODE_EXTENDED,
                CONF_REPORT_DOMAINS: [],
                CONF_REPORT_ENTITY_IDS: [],
            },
            options={},
        ),
        _stop_state=EmergencyStopState(level=LEVEL_NORMAL),
        _rule_engine=SimpleNamespace(rules=rule_configs, states=rule_states),
        _build_extended_snapshot=lambda _config: None,
    )

    report = __import__(
        "custom_components.emergency_stop.coordinator", fromlist=["EmergencyStopCoordinator"]
    ).EmergencyStopCoordinator._build_report(fake)

    assert report["generated_at"] == fixed_now.isoformat()
    assert report["file_name"].startswith("emergency_stop_report_20260202T120000Z")
    assert report["config"][CONF_RULES] == rules
    assert len(report["states"]) == 2
    assert report["outputs"]["active"] is False
    assert report["outputs"]["active_reasons"] == []
    assert report["outputs"]["events_by_reason"] == {}
    assert report["config"][CONF_REPORT_MODE] == REPORT_MODE_EXTENDED
    assert report["config"][CONF_REPORT_DOMAINS] == []
    assert report["config"][CONF_REPORT_ENTITY_IDS] == []
    assert report["config"]["email"][CONF_EMAIL_LEVELS] == DEFAULT_EMAIL_LEVELS
    assert report["config"]["email"][CONF_BREVO_RECIPIENT] is None
    assert report["config"]["email"][CONF_BREVO_RECIPIENT_NOTIFY] is None
    assert report["config"]["email"][CONF_BREVO_RECIPIENT_LIMIT] is None
    assert report["config"]["email"][CONF_BREVO_RECIPIENT_SHUTDOWN] is None
    assert report["config"]["report_retention"][CONF_REPORT_RETENTION_MAX_FILES] == DEFAULT_REPORT_RETENTION_MAX_FILES
    assert report["config"]["report_retention"][CONF_REPORT_RETENTION_MAX_AGE_DAYS] == DEFAULT_REPORT_RETENTION_MAX_AGE_DAYS
