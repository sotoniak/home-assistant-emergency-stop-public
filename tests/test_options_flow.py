import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import custom_components.emergency_stop.config_flow as config_flow_module
from custom_components.emergency_stop.config_flow import EmergencyStopOptionsFlow
from custom_components.emergency_stop.const import (
    AGGREGATE_MAX,
    CONF_BREVO_API_KEY,
    CONF_IMPORT_MODE,
    CONF_IMPORT_RULES_JSON,
    CONF_IMPORT_SETTINGS_JSON,
    CONF_REPORT_MODE,
    CONF_RULE_AGGREGATE,
    CONF_RULE_CONDITION,
    CONF_RULE_DATA_TYPE,
    CONF_RULE_DURATION,
    CONF_RULE_ENTITIES,
    CONF_RULE_INTERVAL,
    CONF_RULE_LATCHED,
    CONF_RULE_LEVEL,
    CONF_RULE_NAME,
    CONF_RULES,
    CONF_RULE_THRESHOLD,
    CONF_RULE_UNKNOWN_HANDLING,
    COND_GT,
    DATA_TYPE_NUMERIC,
    DOMAIN,
    IMPORT_MODE_REPLACE,
    LEVEL_NOTIFY,
    REPORT_MODE_BASIC,
    UNKNOWN_IGNORE,
)


class FakeConfigEntries:
    def __init__(self) -> None:
        self.update_calls: list[dict] = []

    def async_update_entry(self, entry, *, options):
        entry.options = options
        self.update_calls.append(options)

    def async_entries(self):
        return [SimpleNamespace(domain="esphome"), SimpleNamespace(domain="ibms")]


class FakeServices:
    def async_services(self):
        return {"notify": {"mobile_app_phone": object()}}


class FakeCoordinator:
    def __init__(self, path: Path | None = None, fail: bool = False) -> None:
        self.path = path or Path("/tmp/settings.json")
        self.fail = fail

    async def async_export_settings(self) -> Path:
        if self.fail:
            raise RuntimeError("export failed")
        return self.path


def _make_hass(coordinator=None):
    data = {}
    if coordinator is not None:
        data[DOMAIN] = {"entry_1": coordinator}

    async def _async_add_executor_job(func, *args):
        return func(*args)

    return SimpleNamespace(
        config_entries=FakeConfigEntries(),
        services=FakeServices(),
        data=data,
        async_add_executor_job=_async_add_executor_job,
    )


def _make_entry():
    return SimpleNamespace(
        entry_id="entry_1",
        data={CONF_REPORT_MODE: REPORT_MODE_BASIC, CONF_RULES: [{"rule_id": "r1"}]},
        options={},
    )


def test_options_flow_menu_to_settings_action():
    flow = EmergencyStopOptionsFlow(_make_entry())
    flow.hass = _make_hass()

    init_result = asyncio.run(flow.async_step_init())
    assert init_result["step_id"] == "menu"

    settings_result = asyncio.run(flow.async_step_menu({"menu_action": "settings"}))
    assert settings_result["step_id"] == "settings_action"


def test_options_flow_edit_settings_saves_and_returns_menu():
    entry = _make_entry()
    flow = EmergencyStopOptionsFlow(entry)
    flow.hass = _make_hass()

    result = asyncio.run(flow.async_step_user({CONF_REPORT_MODE: REPORT_MODE_BASIC}))

    assert result["step_id"] == "menu"
    assert flow.hass.config_entries.update_calls
    saved = flow.hass.config_entries.update_calls[-1]
    assert saved[CONF_REPORT_MODE] == REPORT_MODE_BASIC
    assert saved[CONF_RULES] == [{"rule_id": "r1"}]


def test_options_flow_rules_back_saves_and_returns_menu():
    entry = _make_entry()
    flow = EmergencyStopOptionsFlow(entry)
    flow.hass = _make_hass()

    result = asyncio.run(flow.async_step_rules_action({"rules_action": "back"}))

    assert result["step_id"] == "menu"
    assert flow.hass.config_entries.update_calls
    saved = flow.hass.config_entries.update_calls[-1]
    assert saved[CONF_RULES] == [{"rule_id": "r1"}]


def test_options_flow_settings_import_saves_and_returns_menu(tmp_path, monkeypatch):
    entry = _make_entry()
    flow = EmergencyStopOptionsFlow(entry)
    flow.hass = _make_hass()
    monkeypatch.setattr(config_flow_module, "IMPORT_CONFIG_DIR", tmp_path)

    payload = json.dumps(
        {
            "settings": {
                CONF_REPORT_MODE: REPORT_MODE_BASIC,
                CONF_BREVO_API_KEY: "secret-token",
            }
        }
    )
    (tmp_path / "settings.json").write_text(payload, encoding="utf-8")
    result = asyncio.run(
        flow.async_step_settings_import({CONF_IMPORT_SETTINGS_JSON: "settings.json"})
    )

    assert result["step_id"] == "menu"
    saved = flow.hass.config_entries.update_calls[-1]
    assert saved[CONF_BREVO_API_KEY] == "secret-token"
    assert saved[CONF_RULES] == [{"rule_id": "r1"}]


def test_options_flow_settings_export_success():
    flow = EmergencyStopOptionsFlow(_make_entry())
    flow.hass = _make_hass(FakeCoordinator(path=Path("/tmp/exported.json")))

    result = asyncio.run(flow.async_step_settings_export())

    assert result["step_id"] == "settings_export"
    assert result["description_placeholders"]["path"] == "/tmp/exported.json"


def test_options_flow_settings_export_failure():
    flow = EmergencyStopOptionsFlow(_make_entry())
    flow.hass = _make_hass(FakeCoordinator(fail=True))

    result = asyncio.run(flow.async_step_settings_export())

    assert result["step_id"] == "settings_export"
    assert result["errors"]["base"] == "export_failed"


def test_options_flow_add_rule_saves_immediately():
    entry = SimpleNamespace(
        entry_id="entry_1",
        data={CONF_REPORT_MODE: REPORT_MODE_BASIC, CONF_RULES: []},
        options={},
    )
    flow = EmergencyStopOptionsFlow(entry)
    flow.hass = _make_hass()
    flow._rule_context = {
        CONF_RULE_NAME: "Voltage high",
        CONF_RULE_DATA_TYPE: DATA_TYPE_NUMERIC,
        CONF_RULE_ENTITIES: ["sensor.voltage"],
        CONF_RULE_AGGREGATE: AGGREGATE_MAX,
    }

    result = asyncio.run(
        flow.async_step_rule_numeric_simple(
            {
                CONF_RULE_CONDITION: COND_GT,
                CONF_RULE_THRESHOLD: 3.5,
                CONF_RULE_DURATION: 5,
                CONF_RULE_INTERVAL: 1,
                CONF_RULE_LEVEL: LEVEL_NOTIFY,
                CONF_RULE_LATCHED: True,
                CONF_RULE_UNKNOWN_HANDLING: UNKNOWN_IGNORE,
            }
        )
    )

    assert result["step_id"] == "add_rule"
    saved = flow.hass.config_entries.update_calls[-1]
    assert len(saved[CONF_RULES]) == 1
    assert saved[CONF_RULES][0][CONF_RULE_NAME] == "Voltage high"


def test_options_flow_delete_rule_saves_immediately():
    entry = _make_entry()
    flow = EmergencyStopOptionsFlow(entry)
    flow.hass = _make_hass()

    select_result = asyncio.run(flow.async_step_rules_action({"rules_action": "delete"}))
    assert select_result["step_id"] == "rule_select"

    result = asyncio.run(flow.async_step_rule_select({"rule_id": "r1"}))

    assert result["step_id"] == "rules_action"
    saved = flow.hass.config_entries.update_calls[-1]
    assert saved[CONF_RULES] == []


def test_options_flow_import_rule_saves_immediately(tmp_path, monkeypatch):
    entry = _make_entry()
    flow = EmergencyStopOptionsFlow(entry)
    flow.hass = _make_hass()
    monkeypatch.setattr(config_flow_module, "IMPORT_CONFIG_DIR", tmp_path)

    payload = json.dumps(
        [
            {
                "rule_id": "imported_rule",
                CONF_RULE_NAME: "Imported Rule",
                CONF_RULE_DATA_TYPE: DATA_TYPE_NUMERIC,
                CONF_RULE_ENTITIES: ["sensor.imported"],
                CONF_RULE_AGGREGATE: AGGREGATE_MAX,
                CONF_RULE_CONDITION: COND_GT,
                "thresholds": [3.2],
                CONF_RULE_DURATION: 5,
                CONF_RULE_INTERVAL: 1,
                CONF_RULE_LEVEL: LEVEL_NOTIFY,
                CONF_RULE_LATCHED: True,
                CONF_RULE_UNKNOWN_HANDLING: UNKNOWN_IGNORE,
                "severity_mode": "simple",
            }
        ]
    )
    (tmp_path / "rules.json").write_text(payload, encoding="utf-8")
    result = asyncio.run(
        flow.async_step_rule_import(
            {
                CONF_IMPORT_MODE: IMPORT_MODE_REPLACE,
                CONF_IMPORT_RULES_JSON: "rules.json",
            }
        )
    )

    assert result["step_id"] == "rules_action"
    saved = flow.hass.config_entries.update_calls[-1]
    assert [rule["rule_id"] for rule in saved[CONF_RULES]] == ["imported_rule"]


def test_trust_fields_round_trip_through_the_rule_form():
    """Editing a rule must preserve its trust settings, not silently reset them."""
    from custom_components.emergency_stop.config_flow import (
        _build_rule_config,
        _seed_rule_context,
        _validate_trust_fields,
    )

    stored = {
        "rule_id": "ov",
        "rule_name": "OV",
        "data_type": "numeric",
        "entities": ["sensor.a", "sensor.b"],
        "aggregate": "max",
        "condition": "gte",
        "thresholds": [3.6],
        "duration_seconds": 5,
        "interval_seconds": 1,
        "level": "shutdown",
        "max_age_seconds": 120,
        "min_sources": 2,
        "recovery_seconds": 30,
        "flap_window_seconds": 3600,
        "flap_budget_seconds": 600,
        "value_min": 2.0,
        "value_max": 4.2,
        "max_step": 0.15,
    }

    context = _seed_rule_context(stored)
    rebuilt = _build_rule_config(context, {}, [])

    for field in (
        "max_age_seconds",
        "min_sources",
        "recovery_seconds",
        "flap_window_seconds",
        "flap_budget_seconds",
        "value_min",
        "value_max",
        "max_step",
    ):
        assert rebuilt[field] == stored[field], field


def test_trust_field_validation_rejects_nonsense():
    from custom_components.emergency_stop.config_flow import _validate_trust_fields

    assert _validate_trust_fields({"min_sources": 0}) == {"min_sources": "min_1"}
    assert _validate_trust_fields({"max_age_seconds": -1}) == {
        "max_age_seconds": "min_0"
    }
    assert _validate_trust_fields({"value_min": 4, "value_max": 2}) == {
        "value_min": "thresholds_order"
    }
    assert _validate_trust_fields({"max_step": 0}) == {"max_step": "min_1"}
    assert _validate_trust_fields({"flap_window_seconds": 600}) == {
        "flap_budget_seconds": "flap_pair_required"
    }
    assert _validate_trust_fields(
        {"flap_window_seconds": 60, "flap_budget_seconds": 600}
    ) == {"flap_budget_seconds": "flap_budget_too_large"}
    assert _validate_trust_fields({}) == {}
