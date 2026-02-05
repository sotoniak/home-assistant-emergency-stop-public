from types import SimpleNamespace

from custom_components.emergency_stop.coordinator import EmergencyStopCoordinator
from custom_components.emergency_stop.const import (
    CONF_REPORT_DOMAINS,
    CONF_REPORT_ENTITY_IDS,
    CONF_REPORT_MODE,
    REPORT_MODE_EXTENDED,
)


class FakeRegistry:
    def __init__(self, entities):
        self.entities = entities


class FakeStates:
    def __init__(self, mapping):
        self._mapping = mapping

    def get(self, entity_id):
        return self._mapping.get(entity_id)


class FakeHass:
    def __init__(self, mapping):
        self.states = FakeStates(mapping)


def test_extended_snapshot_collects_selected_domains(monkeypatch):
    entries = {
        "sensor.ibms_voltage": SimpleNamespace(
            entity_id="sensor.ibms_voltage",
            domain="sensor",
            platform="ibms",
            name="",
            original_name="IBMS Voltage",
        ),
        "binary_sensor.jablotron_alarm": SimpleNamespace(
            entity_id="binary_sensor.jablotron_alarm",
            domain="binary_sensor",
            platform="jablotron100",
            name="Alarm",
            original_name="Alarm",
        ),
        "switch.jablotron_switch": SimpleNamespace(
            entity_id="switch.jablotron_switch",
            domain="switch",
            platform="jablotron100",
            name="Switch",
            original_name="Switch",
        ),
        "sensor.other": SimpleNamespace(
            entity_id="sensor.other",
            domain="sensor",
            platform="other",
            name="Other",
            original_name="Other",
        ),
    }

    def fake_async_get(_hass):
        return FakeRegistry(entries)

    monkeypatch.setattr("custom_components.emergency_stop.coordinator.er.async_get", fake_async_get)

    hass = FakeHass(
        {
            "sensor.ibms_voltage": SimpleNamespace(
                state="54.3",
                attributes={"friendly_name": "BMS Voltage", "unit": "V"},
            ),
            "binary_sensor.jablotron_alarm": SimpleNamespace(
                state="on",
                attributes={"friendly_name": "Jablotron Alarm"},
            ),
        }
    )

    coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
    coordinator.hass = hass

    config = {
        CONF_REPORT_MODE: REPORT_MODE_EXTENDED,
        CONF_REPORT_DOMAINS: ["ibms", "jablotron100"],
    }

    snapshot = coordinator._build_extended_snapshot(config)
    assert snapshot["domains"] == ["ibms", "jablotron100"]
    entities = snapshot["entities"]
    assert len(entities) == 2
    by_platform = {row["platform"]: row for row in entities}
    assert by_platform["ibms"]["name"] == "BMS Voltage"
    assert by_platform["ibms"]["state"] == "54.3"
    assert by_platform["jablotron100"]["name"] == "Jablotron Alarm"


def test_extended_snapshot_includes_selected_entities(monkeypatch):
    entries = {
        "sensor.ibms_voltage": SimpleNamespace(
            entity_id="sensor.ibms_voltage",
            domain="sensor",
            platform="ibms",
            name="",
            original_name="IBMS Voltage",
        ),
        "binary_sensor.jablotron_alarm": SimpleNamespace(
            entity_id="binary_sensor.jablotron_alarm",
            domain="binary_sensor",
            platform="jablotron100",
            name="Alarm",
            original_name="Alarm",
        ),
        "switch.jablotron_switch": SimpleNamespace(
            entity_id="switch.jablotron_switch",
            domain="switch",
            platform="jablotron100",
            name="Switch",
            original_name="Switch",
        ),
    }

    def fake_async_get(_hass):
        return FakeRegistry(entries)

    monkeypatch.setattr("custom_components.emergency_stop.coordinator.er.async_get", fake_async_get)

    hass = FakeHass(
        {
            "sensor.ibms_voltage": SimpleNamespace(
                state="54.3",
                attributes={"friendly_name": "BMS Voltage", "unit": "V"},
            ),
            "binary_sensor.jablotron_alarm": SimpleNamespace(
                state="on",
                attributes={"friendly_name": "Jablotron Alarm"},
            ),
            "switch.jablotron_switch": SimpleNamespace(
                state="on",
                attributes={"friendly_name": "Jablotron Switch"},
            ),
        }
    )

    coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
    coordinator.hass = hass

    config = {
        CONF_REPORT_MODE: REPORT_MODE_EXTENDED,
        CONF_REPORT_DOMAINS: ["ibms"],
        CONF_REPORT_ENTITY_IDS: [
            "binary_sensor.jablotron_alarm",
            "switch.jablotron_switch",
        ],
    }

    snapshot = coordinator._build_extended_snapshot(config)
    assert snapshot["domains"] == ["ibms"]
    assert snapshot["entity_ids"] == [
        "binary_sensor.jablotron_alarm",
        "switch.jablotron_switch",
    ]
    entities = snapshot["entities"]
    assert len(entities) == 3
    by_entity_id = {row["entity_id"]: row for row in entities}
    assert by_entity_id["sensor.ibms_voltage"]["name"] == "BMS Voltage"
    assert by_entity_id["binary_sensor.jablotron_alarm"]["name"] == "Jablotron Alarm"
    assert by_entity_id["switch.jablotron_switch"]["name"] == "Jablotron Switch"


def test_extended_snapshot_entity_only(monkeypatch):
    entries = {
        "switch.jablotron_switch": SimpleNamespace(
            entity_id="switch.jablotron_switch",
            domain="switch",
            platform="jablotron100",
            name="Switch",
            original_name="Switch",
        ),
    }

    def fake_async_get(_hass):
        return FakeRegistry(entries)

    monkeypatch.setattr("custom_components.emergency_stop.coordinator.er.async_get", fake_async_get)

    hass = FakeHass(
        {
            "switch.jablotron_switch": SimpleNamespace(
                state="on",
                attributes={"friendly_name": "Jablotron Switch"},
            ),
        }
    )

    coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
    coordinator.hass = hass

    config = {
        CONF_REPORT_MODE: REPORT_MODE_EXTENDED,
        CONF_REPORT_DOMAINS: [],
        CONF_REPORT_ENTITY_IDS: ["switch.jablotron_switch"],
    }

    snapshot = coordinator._build_extended_snapshot(config)
    assert snapshot["domains"] == []
    assert snapshot["entity_ids"] == ["switch.jablotron_switch"]
    entities = snapshot["entities"]
    assert len(entities) == 1
    assert entities[0]["platform"] == "jablotron100"
    assert entities[0]["name"] == "Jablotron Switch"
