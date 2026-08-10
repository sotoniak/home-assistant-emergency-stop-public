"""Recovery hysteresis and the cumulative flap window.

Motivating incident: a balancer link dropped ~24 times in an evening, ~12 minutes
offline in total, but never for the 60 s the rule asked for in one go - so nothing
was ever reported.
"""
import pytest

from custom_components.emergency_stop.const import COND_IS_OFF, LEVEL_NOTIFY
from custom_components.emergency_stop.coordinator import RuleConfig, RuleEngine


class FakeState:
    def __init__(self, state):
        self.state = state
        self.attributes = {}


class _FakeStates:
    def __init__(self, mapping):
        self._mapping = mapping

    def get(self, entity_id):
        return self._mapping.get(entity_id)


class FakeHass:
    def __init__(self, mapping):
        self.states = _FakeStates(mapping)


@pytest.fixture
def monotonic(monkeypatch):
    values = [0.0]
    monkeypatch.setattr(
        "custom_components.emergency_stop.coordinator.time.monotonic",
        lambda: values[-1],
    )
    return values


def _rule(**overrides):
    kwargs = dict(
        rule_id="link",
        name="Link",
        data_type="binary",
        entities=["binary_sensor.a"],
        aggregate="any",
        condition=COND_IS_OFF,
        thresholds=[],
        duration_seconds=60,
        interval_seconds=1,
        level=LEVEL_NOTIFY,
        latched=False,
        unknown_handling="ignore",
        severity_mode="simple",
        direction=None,
        levels={},
        text_case_sensitive=False,
        text_trim=True,
    )
    kwargs.update(overrides)
    return RuleConfig(**kwargs)


def _drive(engine, hass, monotonic, seconds, value):
    """Advance `seconds` one evaluation per second with the input at `value`."""
    hass.states._mapping["binary_sensor.a"] = FakeState(value)
    for _ in range(seconds):
        monotonic.append(monotonic[-1] + 1.0)
        engine.evaluate(hass)


def test_short_failures_do_not_accumulate_without_recovery(monotonic):
    rule = _rule()
    engine = RuleEngine([rule])
    hass = FakeHass({"binary_sensor.a": FakeState("on")})

    for _ in range(4):
        _drive(engine, hass, monotonic, 40, "off")
        _drive(engine, hass, monotonic, 5, "on")

    # Today's behaviour: every recovery restarts the 60 s timer, so nothing fires.
    assert engine.states[rule.rule_id].active is False


def test_recovery_hysteresis_accumulates_consecutive_failures(monotonic):
    rule = _rule(recovery_seconds=30)
    engine = RuleEngine([rule])
    hass = FakeHass({"binary_sensor.a": FakeState("on")})

    _drive(engine, hass, monotonic, 40, "off")
    assert engine.states[rule.rule_id].active is False
    # Healthy for less than recovery_seconds: the elapsed 40 s is kept.
    _drive(engine, hass, monotonic, 5, "on")
    assert engine.states[rule.rule_id].violation_started_at is not None
    _drive(engine, hass, monotonic, 25, "off")

    assert engine.states[rule.rule_id].active is True


def test_recovery_longer_than_hysteresis_clears_the_timer(monotonic):
    rule = _rule(recovery_seconds=30)
    engine = RuleEngine([rule])
    hass = FakeHass({"binary_sensor.a": FakeState("on")})

    _drive(engine, hass, monotonic, 40, "off")
    _drive(engine, hass, monotonic, 35, "on")
    assert engine.states[rule.rule_id].violation_started_at is None

    _drive(engine, hass, monotonic, 40, "off")
    assert engine.states[rule.rule_id].active is False


def test_unavailable_blip_does_not_wipe_elapsed_time(monotonic):
    rule = _rule(recovery_seconds=30)
    engine = RuleEngine([rule])
    hass = FakeHass({"binary_sensor.a": FakeState("off")})

    _drive(engine, hass, monotonic, 40, "off")
    # A bridge reboot: the input disappears for ten seconds.
    _drive(engine, hass, monotonic, 10, "unavailable")
    _drive(engine, hass, monotonic, 25, "off")

    assert engine.states[rule.rule_id].active is True


def test_flap_window_catches_repeated_short_failures(monotonic):
    rule = _rule(flap_window_seconds=3600, flap_budget_seconds=300)
    engine = RuleEngine([rule])
    hass = FakeHass({"binary_sensor.a": FakeState("on")})

    for _ in range(7):
        _drive(engine, hass, monotonic, 45, "off")
        _drive(engine, hass, monotonic, 60, "on")

    state = engine.states[rule.rule_id]
    assert state.flap_seconds >= 300
    assert state.active is True


def test_flap_window_forgets_old_failures(monotonic):
    rule = _rule(flap_window_seconds=300, flap_budget_seconds=200)
    engine = RuleEngine([rule])
    hass = FakeHass({"binary_sensor.a": FakeState("on")})

    _drive(engine, hass, monotonic, 100, "off")
    _drive(engine, hass, monotonic, 400, "on")

    state = engine.states[rule.rule_id]
    assert state.flap_seconds == 0
    assert state.active is False


def test_flap_tracking_is_off_by_default(monotonic):
    rule = _rule()
    engine = RuleEngine([rule])
    hass = FakeHass({"binary_sensor.a": FakeState("off")})

    _drive(engine, hass, monotonic, 30, "off")

    state = engine.states[rule.rule_id]
    assert state.violation_samples == []
    assert state.flap_seconds == 0
