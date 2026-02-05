from custom_components.emergency_stop.coordinator import RuleConfig, RuleRuntimeState, _build_stop_state
from custom_components.emergency_stop.const import DATA_TYPE_NUMERIC, LEVEL_NOTIFY, LEVEL_SHUTDOWN


def _rule(
    rule_id: str,
    name: str,
    level: str,
    notify_email: bool = True,
    notify_mobile: bool = True,
) -> RuleConfig:
    return RuleConfig(
        rule_id=rule_id,
        name=name,
        data_type=DATA_TYPE_NUMERIC,
        entities=["sensor.test"],
        aggregate="max",
        condition="gt",
        thresholds=[1.0],
        duration_seconds=1,
        interval_seconds=1,
        level=level,
        latched=False,
        unknown_handling="ignore",
        severity_mode="simple",
        direction=None,
        levels={},
        text_case_sensitive=False,
        text_trim=True,
        notify_email=notify_email,
        notify_mobile=notify_mobile,
    )


def test_stop_state_unaffected_by_notification_flags():
    rule = _rule("silent_rule", "Silent rule", LEVEL_SHUTDOWN, False, False)
    runtime = RuleRuntimeState(active=True)
    stop_state = _build_stop_state([rule], {rule.rule_id: runtime}, acknowledged=False)
    assert stop_state.active is True
    assert stop_state.level == LEVEL_SHUTDOWN


def test_notification_filtering_ignores_silent_rules():
    silent = _rule("silent_rule", "Silent rule", LEVEL_SHUTDOWN, False, False)
    loud = _rule("loud_rule", "Loud rule", LEVEL_NOTIFY, True, True)
    states = {
        silent.rule_id: RuleRuntimeState(active=True),
        loud.rule_id: RuleRuntimeState(active=True),
    }
    stop_state = _build_stop_state([silent, loud], states, acknowledged=False)
    email_state = _build_stop_state(
        [rule for rule in (silent, loud) if rule.notify_email],
        states,
        acknowledged=False,
    )
    assert stop_state.level == LEVEL_SHUTDOWN
    assert email_state.level == LEVEL_NOTIFY
    assert email_state.primary_reason == "Loud rule"
