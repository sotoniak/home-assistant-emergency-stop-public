"""Latch persistence: a raised latched alarm must outlive a restart.

Recovery is manual by design, so a restart or an options reload must not be a way
to clear an active alarm - but a retuned rule must not inherit the old one either.
"""
import pytest

from custom_components.emergency_stop.const import (
    DIRECTION_HIGHER_IS_WORSE,
    LEVEL_SHUTDOWN,
)
from custom_components.emergency_stop.coordinator import (
    RuleConfig,
    RuleEngine,
    _rule_fingerprint,
)


class FakeState:
    def __init__(self, state):
        self.state = state
        self.attributes = {}


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


def _rule(**overrides):
    kwargs = dict(
        rule_id="ov",
        name="OV",
        data_type="numeric",
        entities=["sensor.a"],
        aggregate="max",
        condition="gte",
        thresholds=[3.6],
        duration_seconds=1,
        interval_seconds=1,
        level=LEVEL_SHUTDOWN,
        latched=True,
        unknown_handling="ignore",
        severity_mode="simple",
        direction=DIRECTION_HIGHER_IS_WORSE,
        levels={},
        text_case_sensitive=False,
        text_trim=True,
    )
    kwargs.update(overrides)
    return RuleConfig(**kwargs)


def _latched_engine(monotonic, rule):
    engine = RuleEngine([rule])
    hass = FakeHass({"sensor.a": FakeState("3.99")})
    engine.evaluate(hass)
    monotonic.append(monotonic[-1] + 5.0)
    engine.evaluate(hass)
    assert engine.states[rule.rule_id].active is True
    return engine


def test_latch_survives_a_restart(monotonic):
    rule = _rule()
    snapshot = _latched_engine(monotonic, rule).latch_snapshot()
    assert rule.rule_id in snapshot

    # Fresh engine == what a restart or an options reload builds.
    fresh = RuleEngine([_rule()])
    assert fresh.states[rule.rule_id].active is False
    restored = fresh.restore_latches(snapshot)

    assert restored == [rule.rule_id]
    assert fresh.states[rule.rule_id].active is True


def test_healthy_input_does_not_clear_a_restored_latch(monotonic):
    snapshot = _latched_engine(monotonic, _rule()).latch_snapshot()
    rule = _rule()
    fresh = RuleEngine([rule])
    fresh.restore_latches(snapshot)

    # Value back to normal: a latch is only cleared by reset, never by recovery.
    monotonic.append(monotonic[-1] + 10.0)
    fresh.evaluate(FakeHass({"sensor.a": FakeState("3.29")}))
    assert fresh.states[rule.rule_id].active is True


def test_reset_clears_the_persisted_latch(monotonic):
    engine = _latched_engine(monotonic, _rule())
    engine.reset()
    assert engine.latch_snapshot() == {}


def test_retuned_rule_does_not_inherit_the_latch(monotonic):
    snapshot = _latched_engine(monotonic, _rule()).latch_snapshot()

    retuned = _rule(thresholds=[3.9])
    fresh = RuleEngine([retuned])
    assert fresh.restore_latches(snapshot) == []
    assert fresh.states[retuned.rule_id].active is False


def test_non_latched_rule_is_not_persisted(monotonic):
    engine = _latched_engine(monotonic, _rule(latched=False))
    assert engine.latch_snapshot() == {}


def test_fingerprint_is_stable_and_sensitive():
    assert _rule_fingerprint(_rule()) == _rule_fingerprint(_rule())
    assert _rule_fingerprint(_rule()) != _rule_fingerprint(_rule(thresholds=[3.9]))
    assert _rule_fingerprint(_rule()) != _rule_fingerprint(_rule(duration_seconds=99))
    assert _rule_fingerprint(_rule()) != _rule_fingerprint(_rule(min_sources=2))
    # Cosmetics must not invalidate a latch.
    assert _rule_fingerprint(_rule()) == _rule_fingerprint(_rule(name="Renamed"))


def test_garbage_snapshot_is_ignored():
    fresh = RuleEngine([_rule()])
    assert fresh.restore_latches(None) == []
    assert fresh.restore_latches({}) == []
    assert fresh.restore_latches({"ov": "not-a-dict"}) == []
    assert fresh.states["ov"].active is False
