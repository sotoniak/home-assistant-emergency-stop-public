import json
import pytest

import voluptuous as vol

from custom_components.emergency_stop.config_flow import (
    _build_rule_config,
    _binary_rule_count_simple_schema,
    _binary_rule_state_schema,
    _numeric_rule_simple_schema,
    _semafor_rule_schema,
    _store_rule,
    _text_rule_schema,
    _validate_globals,
    _validate_semafor_rule,
    _parse_import_payload,
    _normalize_import_rules,
    _find_rule_id_conflicts,
)
from custom_components.emergency_stop.const import (
    CONF_EMAIL_LEVELS,
    CONF_REPORT_RETENTION_MAX_AGE_DAYS,
    CONF_REPORT_RETENTION_MAX_FILES,
    CONF_REPORT_MODE,
    CONF_RULES,
    CONF_RULE_ID,
    CONF_RULE_NAME,
    CONF_RULE_DATA_TYPE,
    CONF_RULE_ENTITIES,
    CONF_RULE_AGGREGATE,
    CONF_RULE_CONDITION,
    CONF_RULE_LEVEL,
    CONF_RULE_LATCHED,
    CONF_RULE_UNKNOWN_HANDLING,
    CONF_RULE_THRESHOLDS,
    CONF_RULE_SEVERITY_MODE,
    CONF_RULE_THRESHOLD,
    CONF_RULE_THRESHOLD_HIGH,
    CONF_RULE_THRESHOLD_LOW,
    CONF_RULE_DURATION,
    CONF_RULE_INTERVAL,
    CONF_RULE_NOTIFY_THRESHOLD,
    CONF_RULE_LIMIT_THRESHOLD,
    CONF_RULE_SHUTDOWN_THRESHOLD,
    CONF_RULE_NOTIFY_DURATION,
    CONF_RULE_LIMIT_DURATION,
    CONF_RULE_SHUTDOWN_DURATION,
    CONF_RULE_DIRECTION,
    DEFAULT_EMAIL_LEVELS,
    SEVERITY_MODE_SIMPLE,
    DATA_TYPE_NUMERIC,
    NUMERIC_AGGREGATES,
    COND_GT,
    REPORT_MODE_BASIC,
)


def test_numeric_threshold_step_allows_three_decimals():
    schema = _numeric_rule_simple_schema()
    for key in (
        CONF_RULE_THRESHOLD,
        CONF_RULE_THRESHOLD_LOW,
        CONF_RULE_THRESHOLD_HIGH,
    ):
        selector = schema.schema[key]
        assert selector.config["step"] == pytest.approx(0.001)


def test_binary_count_threshold_step_is_integer():
    schema = _binary_rule_count_simple_schema()
    for key in (
        CONF_RULE_THRESHOLD,
        CONF_RULE_THRESHOLD_LOW,
        CONF_RULE_THRESHOLD_HIGH,
    ):
        selector = schema.schema[key]
        assert selector.config["step"] == 1


@pytest.mark.parametrize(
    "schema_fn",
    [
        _numeric_rule_simple_schema,
        _binary_rule_state_schema,
        _binary_rule_count_simple_schema,
        _text_rule_schema,
    ],
)
def test_duration_interval_use_integers(schema_fn):
    schema = schema_fn()
    for key in (CONF_RULE_DURATION, CONF_RULE_INTERVAL):
        assert isinstance(schema.schema[key], vol.Coerce)


def test_semafor_numeric_threshold_step_allows_three_decimals():
    schema = _semafor_rule_schema(numeric=True)
    for key in (
        CONF_RULE_THRESHOLD,
        CONF_RULE_THRESHOLD_LOW,
        CONF_RULE_THRESHOLD_HIGH,
    ):
        assert key not in schema.schema
    for key in (
        CONF_RULE_NOTIFY_THRESHOLD,
        CONF_RULE_LIMIT_THRESHOLD,
        CONF_RULE_SHUTDOWN_THRESHOLD,
    ):
        selector = schema.schema[key]
        assert selector.config["step"] == pytest.approx(0.001)


def test_semafor_count_threshold_step_is_integer():
    schema = _semafor_rule_schema(numeric=False)
    for key in (
        CONF_RULE_NOTIFY_THRESHOLD,
        CONF_RULE_LIMIT_THRESHOLD,
        CONF_RULE_SHUTDOWN_THRESHOLD,
    ):
        selector = schema.schema[key]
        assert selector.config["step"] == 1


def test_build_rule_config_preserves_rule_id():
    base = {
        CONF_RULE_ID: "fixed_id",
        CONF_RULE_NAME: "Rule A",
        CONF_RULE_DATA_TYPE: "numeric",
        CONF_RULE_ENTITIES: ["sensor.x"],
        CONF_RULE_AGGREGATE: "max",
        CONF_RULE_CONDITION: "gt",
        CONF_RULE_DURATION: 5,
        CONF_RULE_INTERVAL: 1,
        CONF_RULE_LEVEL: "notify",
        CONF_RULE_LATCHED: True,
        CONF_RULE_UNKNOWN_HANDLING: "ignore",
        CONF_RULE_THRESHOLD: 3.5,
    }
    rule = _build_rule_config(base, {}, [])
    assert rule[CONF_RULE_ID] == "fixed_id"


def test_store_rule_replaces_at_index():
    rules = [{"rule_id": "a"}, {"rule_id": "b"}]
    _store_rule(rules, {"rule_id": "b2"}, 1)
    assert rules[1]["rule_id"] == "b2"


def test_validate_semafor_interval_gt_duration():
    data = {
        CONF_RULE_DIRECTION: "higher_is_worse",
        CONF_RULE_UNKNOWN_HANDLING: "ignore",
        CONF_RULE_INTERVAL: 10,
        CONF_RULE_NOTIFY_THRESHOLD: 3.5,
        CONF_RULE_NOTIFY_DURATION: 5,
    }
    errors = _validate_semafor_rule(data, numeric=True)
    assert errors[CONF_RULE_INTERVAL] == "interval_gt_duration"


def test_validate_globals_rejects_negative_retention():
    data = {
        CONF_REPORT_RETENTION_MAX_FILES: -1,
        CONF_REPORT_RETENTION_MAX_AGE_DAYS: -5,
        CONF_EMAIL_LEVELS: DEFAULT_EMAIL_LEVELS,
        CONF_REPORT_MODE: REPORT_MODE_BASIC,
    }
    errors = _validate_globals(data)
    assert errors[CONF_REPORT_RETENTION_MAX_FILES] == "min_0"
    assert errors[CONF_REPORT_RETENTION_MAX_AGE_DAYS] == "min_0"


def test_parse_import_payload_accepts_rules_list():
    payload = json.dumps(
        [
            {
                CONF_RULE_ID: "rule_1",
                CONF_RULE_NAME: "Rule 1",
            }
        ]
    )
    rules, error = _parse_import_payload(payload)
    assert error is None
    assert rules[0][CONF_RULE_ID] == "rule_1"


def test_parse_import_payload_accepts_wrapped_rules():
    payload = json.dumps(
        {
            CONF_RULES: [
                {
                    CONF_RULE_ID: "rule_1",
                    CONF_RULE_NAME: "Rule 1",
                }
            ]
        }
    )
    rules, error = _parse_import_payload(payload)
    assert error is None
    assert rules[0][CONF_RULE_ID] == "rule_1"


def test_normalize_import_rules_detects_duplicates():
    rules = [
        {
            CONF_RULE_ID: "rule_1",
            CONF_RULE_NAME: "Rule 1",
            CONF_RULE_DATA_TYPE: DATA_TYPE_NUMERIC,
            CONF_RULE_ENTITIES: ["sensor.value"],
            CONF_RULE_AGGREGATE: NUMERIC_AGGREGATES[0],
            CONF_RULE_CONDITION: COND_GT,
            CONF_RULE_THRESHOLDS: [3.5],
            CONF_RULE_DURATION: 5,
            CONF_RULE_INTERVAL: 1,
            CONF_RULE_LEVEL: "notify",
            CONF_RULE_LATCHED: True,
            CONF_RULE_UNKNOWN_HANDLING: "ignore",
            CONF_RULE_SEVERITY_MODE: SEVERITY_MODE_SIMPLE,
        },
        {
            CONF_RULE_ID: "rule_1",
            CONF_RULE_NAME: "Rule 1b",
            CONF_RULE_DATA_TYPE: DATA_TYPE_NUMERIC,
            CONF_RULE_ENTITIES: ["sensor.value"],
            CONF_RULE_AGGREGATE: NUMERIC_AGGREGATES[0],
            CONF_RULE_CONDITION: COND_GT,
            CONF_RULE_THRESHOLDS: [3.5],
            CONF_RULE_DURATION: 5,
            CONF_RULE_INTERVAL: 1,
            CONF_RULE_LEVEL: "notify",
            CONF_RULE_LATCHED: True,
            CONF_RULE_UNKNOWN_HANDLING: "ignore",
            CONF_RULE_SEVERITY_MODE: SEVERITY_MODE_SIMPLE,
        },
    ]
    normalized, error = _normalize_import_rules(rules)
    assert normalized is None
    assert error == "import_duplicate_rule_id"


def test_find_rule_id_conflicts():
    existing = [{CONF_RULE_ID: "rule_1"}]
    incoming = [
        {CONF_RULE_ID: "rule_1"},
        {CONF_RULE_ID: "rule_2"},
    ]
    conflicts = _find_rule_id_conflicts(existing, incoming)
    assert conflicts == ["rule_1"]
