from datetime import datetime, timezone
import pytest

from homeassistant.const import STATE_UNKNOWN
from homeassistant.util import dt as dt_util

from custom_components.emergency_stop.coordinator import (
    RuleConfig,
    RuleEngine,
    RuleRuntimeState,
    _build_stop_state,
    _deterministic_offset_seconds,
)
from custom_components.emergency_stop.const import (
    COND_BETWEEN,
    COND_CONTAINS,
    COND_GT,
    COND_IS_OFF,
    DATA_TYPE_BINARY,
    DATA_TYPE_NUMERIC,
    DATA_TYPE_TEXT,
    LEVEL_LIMIT,
    LEVEL_NOTIFY,
    LEVEL_SHUTDOWN,
    UNKNOWN_TREAT_OK,
    UNKNOWN_TREAT_VIOLATION,
)


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


@pytest.fixture
def base_times(monkeypatch):
    now = dt_util.utcnow()
    monotonic_values = [0.0]

    def fake_monotonic():
        return monotonic_values[-1]

    monkeypatch.setattr(
        "custom_components.emergency_stop.coordinator.time.monotonic", fake_monotonic
    )
    monkeypatch.setattr(
        "custom_components.emergency_stop.coordinator.dt_util.utcnow", lambda: now
    )
    return now, monotonic_values


def _rule(
    rule_id="rule_1",
    name="Rule 1",
    data_type=DATA_TYPE_NUMERIC,
    entities=None,
    aggregate="max",
    condition=COND_GT,
    thresholds=None,
    duration=2,
    interval=1,
    level=LEVEL_LIMIT,
    latched=True,
    unknown_handling="ignore",
    text_case_sensitive=False,
    text_trim=True,
    severity_mode="simple",
    direction=None,
    levels=None,
):
    return RuleConfig(
        rule_id=rule_id,
        name=name,
        data_type=data_type,
        entities=entities or [],
        aggregate=aggregate,
        condition=condition,
        thresholds=thresholds or [0],
        duration_seconds=duration,
        interval_seconds=interval,
        level=level,
        latched=latched,
        unknown_handling=unknown_handling,
        severity_mode=severity_mode,
        direction=direction,
        levels=levels or {},
        text_case_sensitive=text_case_sensitive,
        text_trim=text_trim,
    )


def test_deterministic_offset_in_range():
    offset = _deterministic_offset_seconds("rule_offset", 10)
    assert 0 <= offset < 10
    assert offset == _deterministic_offset_seconds("rule_offset", 10)


def test_numeric_rule_triggers_after_duration(base_times):
    _, monotonic_values = base_times
    hass = FakeHass({"sensor.voltage": FakeState("3.9")})
    rule = _rule(
        data_type=DATA_TYPE_NUMERIC,
        entities=["sensor.voltage"],
        aggregate="max",
        condition=COND_GT,
        thresholds=[3.5],
        duration=5,
        interval=1,
        level=LEVEL_SHUTDOWN,
    )
    engine = RuleEngine([rule])

    engine.evaluate(hass)
    assert engine.states[rule.rule_id].active is False

    monotonic_values.append(4.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].active is False

    monotonic_values.append(6.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].active is True


def test_binary_any_rule_non_latched_resets(base_times):
    _, monotonic_values = base_times
    hass = FakeHass(
        {
            "binary_sensor.a": FakeState("off"),
            "binary_sensor.b": FakeState("on"),
        }
    )
    rule = _rule(
        rule_id="rule_bin",
        name="Binary Rule",
        data_type=DATA_TYPE_BINARY,
        entities=["binary_sensor.a", "binary_sensor.b"],
        aggregate="any",
        condition=COND_IS_OFF,
        thresholds=[],
        duration=1,
        interval=1,
        level=LEVEL_NOTIFY,
        latched=False,
    )
    engine = RuleEngine([rule])

    engine.evaluate(hass)
    monotonic_values.append(2.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].active is True

    hass.states._mapping["binary_sensor.a"] = FakeState("on")
    monotonic_values.append(3.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].active is False


def test_text_contains_case_insensitive_trim(base_times):
    _, monotonic_values = base_times
    hass = FakeHass({"sensor.text": FakeState("  AHOJ sveta  ")})
    rule = _rule(
        rule_id="rule_text",
        name="Text Rule",
        data_type=DATA_TYPE_TEXT,
        entities=["sensor.text"],
        aggregate="any",
        condition=COND_CONTAINS,
        thresholds=["ahoj"],
        duration=1,
        interval=1,
        level=LEVEL_LIMIT,
        latched=True,
        text_case_sensitive=False,
        text_trim=True,
    )
    engine = RuleEngine([rule])

    engine.evaluate(hass)
    monotonic_values.append(2.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].active is True


def test_unknown_handling_treat_violation(base_times):
    _, monotonic_values = base_times
    hass = FakeHass({"sensor.bad": FakeState(STATE_UNKNOWN)})
    rule = _rule(
        rule_id="rule_unknown",
        name="Unknown Rule",
        data_type=DATA_TYPE_NUMERIC,
        entities=["sensor.bad"],
        aggregate="max",
        condition=COND_GT,
        thresholds=[3.0],
        duration=2,
        interval=1,
        level=LEVEL_LIMIT,
        unknown_handling=UNKNOWN_TREAT_VIOLATION,
    )
    engine = RuleEngine([rule])

    engine.evaluate(hass)
    monotonic_values.append(3.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].active is True


def test_unknown_handling_treat_ok(base_times):
    _, monotonic_values = base_times
    hass = FakeHass({"sensor.bad": FakeState(STATE_UNKNOWN)})
    rule = _rule(
        rule_id="rule_ok",
        name="OK Rule",
        data_type=DATA_TYPE_NUMERIC,
        entities=["sensor.bad"],
        aggregate="max",
        condition=COND_GT,
        thresholds=[3.0],
        duration=2,
        interval=1,
        level=LEVEL_LIMIT,
        unknown_handling=UNKNOWN_TREAT_OK,
    )
    engine = RuleEngine([rule])

    engine.evaluate(hass)
    monotonic_values.append(3.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].active is False


def test_per_rule_interval_delays_activation(base_times):
    _, monotonic_values = base_times
    hass = FakeHass({"sensor.voltage": FakeState("4.0")})
    rule = _rule(
        rule_id="rule_interval",
        name="Interval Rule",
        data_type=DATA_TYPE_NUMERIC,
        entities=["sensor.voltage"],
        aggregate="max",
        condition=COND_GT,
        thresholds=[3.5],
        duration=2,
        interval=5,
        level=LEVEL_LIMIT,
    )
    engine = RuleEngine([rule])
    offset = _deterministic_offset_seconds(rule.rule_id, rule.interval_seconds)

    monotonic_values.append(float(offset))
    engine.evaluate(hass)
    monotonic_values.append(float(offset) + 3.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].active is False

    monotonic_values.append(float(offset) + 5.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].active is True


def test_global_level_priority():
    rule_low = _rule(
        rule_id="rule_low",
        name="Low",
        level=LEVEL_NOTIFY,
        thresholds=[1],
    )
    rule_high = _rule(
        rule_id="rule_high",
        name="High",
        level=LEVEL_SHUTDOWN,
        thresholds=[1],
    )
    states = {
        "rule_low": RuleRuntimeState(active=True, active_since="2026-02-02T10:00:00"),
        "rule_high": RuleRuntimeState(active=True, active_since="2026-02-02T10:01:00"),
    }
    stop_state = _build_stop_state([rule_low, rule_high], states, False)
    assert stop_state.level == LEVEL_SHUTDOWN
    assert stop_state.primary_reason == "High"


def test_semafor_escalates_levels(base_times):
    _, monotonic_values = base_times
    hass = FakeHass({"sensor.voltage": FakeState("3.7")})
    rule = _rule(
        rule_id="rule_semafor",
        name="Voltage",
        data_type=DATA_TYPE_NUMERIC,
        entities=["sensor.voltage"],
        aggregate="max",
        condition=None,
        thresholds=[],
        duration=1,
        interval=1,
        level=LEVEL_NOTIFY,
        latched=True,
        severity_mode="semafor",
        direction="higher_is_worse",
        levels={
            "notify": {"threshold": 3.5, "duration_seconds": 1},
            "limit": {"threshold": 3.6, "duration_seconds": 1},
            "shutdown": {"threshold": 3.8, "duration_seconds": 1},
        },
    )
    engine = RuleEngine([rule])

    engine.evaluate(hass)
    monotonic_values.append(2.0)
    engine.evaluate(hass)
    state = engine.states[rule.rule_id]
    assert state.active is True
    assert state.current_level == LEVEL_LIMIT
    assert state.latched_level == LEVEL_LIMIT

    hass.states._mapping["sensor.voltage"] = FakeState("3.9")
    monotonic_values.append(3.0)
    engine.evaluate(hass)
    state = engine.states[rule.rule_id]
    assert state.current_level == LEVEL_LIMIT

    monotonic_values.append(4.0)
    engine.evaluate(hass)
    state = engine.states[rule.rule_id]
    assert state.current_level == LEVEL_SHUTDOWN
    assert state.latched_level == LEVEL_SHUTDOWN


def test_semafor_lower_is_worse(base_times):
    _, monotonic_values = base_times
    hass = FakeHass({"sensor.voltage": FakeState("2.7")})
    rule = _rule(
        rule_id="rule_uv",
        name="Under Voltage",
        data_type=DATA_TYPE_NUMERIC,
        entities=["sensor.voltage"],
        aggregate="min",
        condition=None,
        thresholds=[],
        duration=1,
        interval=1,
        level=LEVEL_NOTIFY,
        latched=False,
        severity_mode="semafor",
        direction="lower_is_worse",
        levels={
            "notify": {"threshold": 3.0, "duration_seconds": 1},
            "limit": {"threshold": 2.8, "duration_seconds": 1},
            "shutdown": {"threshold": 2.6, "duration_seconds": 1},
        },
    )
    engine = RuleEngine([rule])

    engine.evaluate(hass)
    monotonic_values.append(2.0)
    engine.evaluate(hass)
    state = engine.states[rule.rule_id]
    assert state.current_level == LEVEL_LIMIT


def test_numeric_between_inclusive(base_times):
    _, monotonic_values = base_times
    hass = FakeHass({"sensor.voltage": FakeState("3.0")})
    rule = _rule(
        data_type=DATA_TYPE_NUMERIC,
        entities=["sensor.voltage"],
        aggregate="max",
        condition=COND_BETWEEN,
        thresholds=[3.0, 4.0],
        duration=1,
        interval=1,
        level=LEVEL_LIMIT,
    )
    engine = RuleEngine([rule])

    engine.evaluate(hass)
    monotonic_values.append(1.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].active is True


def test_semafor_downgrade_when_value_drops(base_times):
    _, monotonic_values = base_times
    hass = FakeHass({"sensor.voltage": FakeState("3.9")})
    rule = _rule(
        rule_id="rule_semafor_drop",
        name="Voltage",
        data_type=DATA_TYPE_NUMERIC,
        entities=["sensor.voltage"],
        aggregate="max",
        condition=None,
        thresholds=[],
        duration=1,
        interval=1,
        level=LEVEL_NOTIFY,
        latched=False,
        severity_mode="semafor",
        direction="higher_is_worse",
        levels={
            "notify": {"threshold": 3.5, "duration_seconds": 1},
            "limit": {"threshold": 3.6, "duration_seconds": 1},
            "shutdown": {"threshold": 3.8, "duration_seconds": 1},
        },
    )
    engine = RuleEngine([rule])

    engine.evaluate(hass)
    monotonic_values.append(1.0)
    engine.evaluate(hass)
    state = engine.states[rule.rule_id]
    assert state.current_level == LEVEL_SHUTDOWN

    hass.states._mapping["sensor.voltage"] = FakeState("3.65")
    monotonic_values.append(2.0)
    engine.evaluate(hass)
    state = engine.states[rule.rule_id]
    assert state.current_level == LEVEL_LIMIT


def test_rule_runtime_last_update_stable_without_state_change(monkeypatch):
    monotonic_values = [0.0]
    now_values = [
        datetime(2026, 2, 2, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 2, 10, 0, 1, tzinfo=timezone.utc),
    ]

    def fake_monotonic():
        return monotonic_values[-1]

    def fake_utcnow():
        if len(now_values) > 1:
            return now_values.pop(0)
        return now_values[0]

    monkeypatch.setattr(
        "custom_components.emergency_stop.coordinator.time.monotonic", fake_monotonic
    )
    monkeypatch.setattr(
        "custom_components.emergency_stop.coordinator.dt_util.utcnow", fake_utcnow
    )

    hass = FakeHass({"sensor.voltage": FakeState("3.0")})
    rule = _rule(
        rule_id="stable_update_rule",
        name="Stable update rule",
        data_type=DATA_TYPE_NUMERIC,
        entities=["sensor.voltage"],
        aggregate="max",
        condition=COND_GT,
        thresholds=[3.5],
        duration=2,
        interval=1,
        level=LEVEL_LIMIT,
        latched=False,
    )
    engine = RuleEngine([rule])

    engine.evaluate(hass)
    first_update = engine.states[rule.rule_id].last_update
    assert first_update == "2026-02-02T10:00:00+00:00"

    monotonic_values.append(1.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].last_update == first_update


def test_build_stop_state_keeps_last_update_if_unchanged(monkeypatch):
    now_values = [
        datetime(2026, 2, 2, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 2, 10, 0, 5, tzinfo=timezone.utc),
    ]

    def fake_utcnow():
        if len(now_values) > 1:
            return now_values.pop(0)
        return now_values[0]

    monkeypatch.setattr(
        "custom_components.emergency_stop.coordinator.dt_util.utcnow", fake_utcnow
    )

    rule = _rule(
        rule_id="stop_state_rule",
        name="Stop state rule",
        level=LEVEL_LIMIT,
        thresholds=[1],
    )
    states = {
        rule.rule_id: RuleRuntimeState(
            active=True,
            active_since="2026-02-02T09:59:00+00:00",
            last_update="2026-02-02T09:59:30+00:00",
            last_entity="sensor.voltage",
            last_aggregate=4.0,
            last_detail="Stop state rule: max=4.000 gt 1",
        )
    }
    first = _build_stop_state([rule], states, acknowledged=False)
    second = _build_stop_state([rule], states, acknowledged=False, previous=first)

    assert first.last_update == "2026-02-02T10:00:00+00:00"
    assert second.last_update == first.last_update
