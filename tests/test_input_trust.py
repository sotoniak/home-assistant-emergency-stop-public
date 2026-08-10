"""Input-trust contracts.

A rule that can switch load must only ever decide on a value that is parseable,
finite, fresh, plausible and physically reachable from the previous one. Anything
else has to surface as an untrusted input, never as a violation.
"""
from datetime import timedelta

import pytest

from homeassistant.util import dt as dt_util

from custom_components.emergency_stop.const import (
    DIRECTION_HIGHER_IS_WORSE,
    LEVEL_LIMIT,
    LEVEL_NOTIFY,
    LEVEL_SHUTDOWN,
    MAX_CONSECUTIVE_JUMP_REJECTS,
    PROTECTION_DEGRADED_GRACE_SECONDS,
    UNKNOWN_TREAT_VIOLATION,
)
from custom_components.emergency_stop.coordinator import (
    RuleConfig,
    RuleEngine,
    _load_rules,
    _parse_numeric_state,
)


class FakeState:
    def __init__(self, state, age_seconds=0.0):
        self.state = state
        self.attributes = {}
        self.last_reported = dt_util.utcnow() - timedelta(seconds=age_seconds)
        self.last_updated = self.last_reported
        self.last_changed = self.last_reported


class FakeHass:
    def __init__(self, mapping):
        self.states = _FakeStates(mapping)


class _FakeStates:
    def __init__(self, mapping):
        self._mapping = mapping

    def get(self, entity_id):
        return self._mapping.get(entity_id)


@pytest.fixture
def monotonic(monkeypatch):
    values = [0.0]
    monkeypatch.setattr(
        "custom_components.emergency_stop.coordinator.time.monotonic",
        lambda: values[-1],
    )
    return values


def _numeric_rule(**overrides):
    kwargs = dict(
        rule_id="cell_ov",
        name="Cell OV",
        data_type="numeric",
        entities=["sensor.a", "sensor.b", "sensor.c"],
        aggregate="max",
        condition="gte",
        thresholds=[3.6],
        duration_seconds=1,
        interval_seconds=1,
        level=LEVEL_SHUTDOWN,
        latched=False,
        unknown_handling="ignore",
        severity_mode="simple",
        direction=DIRECTION_HIGHER_IS_WORSE,
        levels={},
        text_case_sensitive=False,
        text_trim=True,
    )
    kwargs.update(overrides)
    return RuleConfig(**kwargs)


def test_not_finite_is_not_a_violation():
    assert _parse_numeric_state(FakeState("inf")) == (None, "not_finite")
    assert _parse_numeric_state(FakeState("nan")) == (None, "not_finite")
    assert _parse_numeric_state(FakeState("-inf")) == (None, "not_finite")


def test_infinite_input_cannot_trigger(monotonic):
    rule = _numeric_rule()
    hass = FakeHass(
        {
            "sensor.a": FakeState("inf"),
            "sensor.b": FakeState("3.29"),
            "sensor.c": FakeState("3.29"),
        }
    )
    engine = RuleEngine([rule])
    engine.evaluate(hass)
    monotonic.append(5.0)
    engine.evaluate(hass)

    state = engine.states[rule.rule_id]
    assert state.active is False
    assert state.untrusted_inputs == {"sensor.a": "not_finite"}
    assert state.trusted_sources == 2


def test_stale_input_is_dropped(monotonic):
    rule = _numeric_rule(max_age_seconds=60)
    hass = FakeHass(
        {
            "sensor.a": FakeState("3.99", age_seconds=600),
            "sensor.b": FakeState("3.29"),
            "sensor.c": FakeState("3.29"),
        }
    )
    engine = RuleEngine([rule])
    engine.evaluate(hass)
    monotonic.append(5.0)
    engine.evaluate(hass)

    state = engine.states[rule.rule_id]
    assert state.active is False
    assert state.untrusted_inputs == {"sensor.a": "stale"}


def test_unknown_age_counts_as_stale_when_freshness_required(monotonic):
    class NoStampState:
        state = "3.99"
        attributes: dict = {}

    rule = _numeric_rule(max_age_seconds=60, entities=["sensor.a"])
    engine = RuleEngine([rule])
    engine.evaluate(FakeHass({"sensor.a": NoStampState()}))

    assert engine.states[rule.rule_id].untrusted_inputs == {"sensor.a": "stale"}


def test_out_of_range_input_is_dropped(monotonic):
    rule = _numeric_rule(value_min=2.0, value_max=4.0)
    hass = FakeHass(
        {
            "sensor.a": FakeState("65535"),
            "sensor.b": FakeState("3.29"),
            "sensor.c": FakeState("3.29"),
        }
    )
    engine = RuleEngine([rule])
    engine.evaluate(hass)
    monotonic.append(5.0)
    engine.evaluate(hass)

    state = engine.states[rule.rule_id]
    assert state.active is False
    assert state.untrusted_inputs == {"sensor.a": "out_of_range"}


def test_impossible_jump_is_rejected_then_accepted(monotonic):
    rule = _numeric_rule(max_step=0.1, entities=["sensor.a"], duration_seconds=1)
    hass = FakeHass({"sensor.a": FakeState("3.29")})
    engine = RuleEngine([rule])
    engine.evaluate(hass)

    hass.states._mapping["sensor.a"] = FakeState("3.99")
    for index in range(MAX_CONSECUTIVE_JUMP_REJECTS - 1):
        monotonic.append(monotonic[-1] + 1.0)
        engine.evaluate(hass)
        assert engine.states[rule.rule_id].untrusted_inputs == {"sensor.a": "jump"}
        assert engine.states[rule.rule_id].active is False, index

    # A sustained new level is eventually believed, so a real fast rise is not
    # rejected forever.
    monotonic.append(monotonic[-1] + 1.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].untrusted_inputs == {}
    monotonic.append(monotonic[-1] + 5.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].active is True


def test_quorum_requires_two_agreeing_sources(monotonic):
    rule = _numeric_rule(min_sources=2, duration_seconds=1)
    hass = FakeHass(
        {
            "sensor.a": FakeState("3.99"),
            "sensor.b": FakeState("3.29"),
            "sensor.c": FakeState("3.29"),
        }
    )
    engine = RuleEngine([rule])
    engine.evaluate(hass)
    monotonic.append(5.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].active is False

    hass.states._mapping["sensor.b"] = FakeState("3.98")
    monotonic.append(monotonic[-1] + 1.0)
    engine.evaluate(hass)
    monotonic.append(monotonic[-1] + 5.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].active is True


def test_quorum_not_met_reports_instead_of_deciding(monotonic):
    rule = _numeric_rule(min_sources=2, entities=["sensor.a", "sensor.b"])
    hass = FakeHass(
        {
            "sensor.a": FakeState("3.99"),
            "sensor.b": FakeState("unavailable"),
        }
    )
    engine = RuleEngine([rule])
    engine.evaluate(hass)
    monotonic.append(5.0)
    engine.evaluate(hass)

    state = engine.states[rule.rule_id]
    assert state.active is False
    assert state.last_invalid_reason == "quorum_not_met"


def test_undecidable_shutdown_rule_is_tracked(monotonic):
    rule = _numeric_rule(entities=["sensor.a"])
    hass = FakeHass({"sensor.a": FakeState("unavailable")})
    engine = RuleEngine([rule])
    engine.evaluate(hass)

    state = engine.states[rule.rule_id]
    assert state.undecidable_since is not None

    hass.states._mapping["sensor.a"] = FakeState("3.29")
    monotonic.append(monotonic[-1] + 1.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].undecidable_since is None


def test_non_shutdown_rule_is_never_reported_as_degraded(monotonic):
    rule = _numeric_rule(level=LEVEL_NOTIFY, entities=["sensor.a"])
    engine = RuleEngine([rule])
    engine.evaluate(FakeHass({"sensor.a": FakeState("unavailable")}))

    assert engine.states[rule.rule_id].undecidable_since is None


def test_treat_violation_is_stripped_from_shutdown_rules():
    rules = _load_rules(
        {
            "rules": [
                {
                    "rule_id": "ov",
                    "rule_name": "OV",
                    "data_type": "numeric",
                    "entities": ["sensor.a"],
                    "aggregate": "max",
                    "condition": "gte",
                    "thresholds": [3.6],
                    "level": LEVEL_SHUTDOWN,
                    "unknown_handling": UNKNOWN_TREAT_VIOLATION,
                },
                {
                    "rule_id": "link",
                    "rule_name": "Link",
                    "data_type": "binary",
                    "entities": ["binary_sensor.a"],
                    "aggregate": "any",
                    "condition": "is_off",
                    "level": LEVEL_LIMIT,
                    "unknown_handling": UNKNOWN_TREAT_VIOLATION,
                },
            ]
        }
    )
    by_id = {rule.rule_id: rule for rule in rules}
    assert by_id["ov"].unknown_handling == "ignore"
    # Below shutdown it stays available: that is where it belongs.
    assert by_id["link"].unknown_handling == UNKNOWN_TREAT_VIOLATION


def test_one_broken_rule_does_not_drop_the_others():
    rules = _load_rules(
        {
            "rules": [
                {"rule_id": "", "rule_name": "no id"},
                {
                    "rule_id": "bad_duration",
                    "rule_name": "Bad",
                    "data_type": "numeric",
                    "entities": ["sensor.a"],
                    "duration_seconds": "not-a-number",
                },
                {
                    "rule_id": "good",
                    "rule_name": "Good",
                    "data_type": "numeric",
                    "entities": ["sensor.a"],
                    "aggregate": "max",
                    "condition": "gte",
                    "thresholds": [3.6],
                },
            ]
        }
    )
    assert [rule.rule_id for rule in rules] == ["good"]


def test_unknown_level_falls_back_instead_of_arming_nothing():
    rules = _load_rules(
        {
            "rules": [
                {
                    "rule_id": "typo",
                    "rule_name": "Typo",
                    "data_type": "numeric",
                    "entities": ["sensor.a"],
                    "aggregate": "max",
                    "condition": "gte",
                    "thresholds": [3.6],
                    "level": "shutdwon",
                }
            ]
        }
    )
    assert rules[0].level == LEVEL_NOTIFY
    assert rules[0].can_shutdown() is False


def test_per_level_quorum_from_levels_config():
    rules = _load_rules(
        {
            "rules": [
                {
                    "rule_id": "semafor",
                    "rule_name": "Semafor",
                    "data_type": "numeric",
                    "entities": ["sensor.a"],
                    "aggregate": "max",
                    "severity_mode": "semafor",
                    "direction": DIRECTION_HIGHER_IS_WORSE,
                    "levels": {
                        "notify": {"threshold": 3.58, "duration_seconds": 10},
                        "shutdown": {
                            "threshold": 3.61,
                            "duration_seconds": 5,
                            "min_sources": 2,
                        },
                    },
                }
            ]
        }
    )
    rule = rules[0]
    assert rule.can_shutdown() is True
    assert rule.level_min_sources(LEVEL_SHUTDOWN) == 2
    assert rule.level_min_sources(LEVEL_NOTIFY) == 1


def test_grace_is_long_enough_to_absorb_a_restart():
    # The degraded signal must not fire while HA is still starting up.
    assert PROTECTION_DEGRADED_GRACE_SECONDS >= 30
