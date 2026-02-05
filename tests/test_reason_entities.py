from homeassistant.helpers.entity import EntityCategory

from custom_components.emergency_stop.binary_sensor import (
    EmergencyStopActiveBinarySensor,
    EmergencyStopRuleBinarySensor,
)
from custom_components.emergency_stop.button import EmergencyStopReportButton
from custom_components.emergency_stop.coordinator import EmergencyStopState, RuleConfig, RuleRuntimeState
from custom_components.emergency_stop.const import DATA_TYPE_NUMERIC, LEVEL_LIMIT


class DummyCoordinator:
    def __init__(self, stop_state, rules=None, rule_states=None) -> None:
        self.stop_state = stop_state
        self.rules = rules or []
        self.rule_states = rule_states or {}

    def async_add_listener(self, update_callback):
        return lambda: None


def test_rule_binary_sensor_attributes(monkeypatch):
    monkeypatch.setattr(
        "custom_components.emergency_stop.binary_sensor.time.monotonic",
        lambda: 105.0,
    )
    monkeypatch.setattr(
        "custom_components.emergency_stop.binary_sensor.dt_util.utcnow",
        lambda: __import__("datetime").datetime(
            2026, 2, 2, 10, 0, 5, tzinfo=__import__("datetime").timezone.utc
        ),
    )
    rule = RuleConfig(
        rule_id="temp_rule",
        name="Temperature Rule",
        data_type=DATA_TYPE_NUMERIC,
        entities=["sensor.temp"],
        aggregate="max",
        condition="gt",
        thresholds=[60.0],
        duration_seconds=5,
        interval_seconds=10,
        level=LEVEL_LIMIT,
        latched=True,
        unknown_handling="ignore",
        severity_mode="simple",
        direction=None,
        levels={},
        text_case_sensitive=False,
        text_trim=True,
    )
    runtime = RuleRuntimeState(
        active=True,
        active_since="2026-02-02T10:00:00+00:00",
        last_match=True,
        last_aggregate=61.2,
        last_entity="sensor.temp",
        last_detail="Temperature Rule: max=61.200 gt 60.0",
        last_update="2026-02-02T10:00:01+00:00",
        last_eval_monotonic=100.0,
        violation_started_at=90.0,
    )
    coordinator = DummyCoordinator(
        EmergencyStopState(active=True, level=LEVEL_LIMIT),
        rules=[rule],
        rule_states={"temp_rule": runtime},
    )
    sensor = EmergencyStopRuleBinarySensor(coordinator, rule)

    assert sensor.is_on is True
    attrs = sensor.extra_state_attributes
    assert attrs["rule_id"] == "temp_rule"
    assert attrs["rule_name"] == "Temperature Rule"
    assert attrs["last_aggregate"] == 61.2
    assert attrs["active_since"] == "2026-02-02T10:00:00+00:00"
    assert attrs["active_for_seconds"] == 5.0
    assert attrs["violation_for_seconds"] == 15.0
    assert attrs["next_evaluation_in_seconds"] == 5.0
    assert attrs["evaluation"]["match"] is True


def test_active_binary_sensor_exposes_attributes():
    stop_state = EmergencyStopState(active=True, level=LEVEL_LIMIT, primary_reason="Test")
    coordinator = DummyCoordinator(stop_state)
    sensor = EmergencyStopActiveBinarySensor(coordinator)
    assert sensor.is_on is True
    assert sensor.extra_state_attributes["primary_reason"] == "Test"


def test_report_button_is_diagnostic_entity():
    coordinator = DummyCoordinator(EmergencyStopState())
    report_button = EmergencyStopReportButton(coordinator)
    assert report_button.entity_category == EntityCategory.DIAGNOSTIC
