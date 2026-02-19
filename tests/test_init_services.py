import asyncio
from types import SimpleNamespace

import custom_components.emergency_stop as integration
from custom_components.emergency_stop.const import (
    CONF_NOTIFICATION_LEVEL,
    CONF_SIMULATION_DETAIL,
    CONF_SIMULATION_DURATION,
    CONF_SIMULATION_ENTITY_ID,
    CONF_SIMULATION_LEVEL,
    CONF_SIMULATION_REASON,
    CONF_SIMULATION_SEND_EMAIL,
    CONF_SIMULATION_SEND_NOTIFICATIONS,
    CONF_SIMULATION_VALUE,
    DOMAIN,
    LEVEL_LIMIT,
    LEVEL_NORMAL,
    SERVICE_ACK,
    SERVICE_CLEAR_SIMULATION,
    SERVICE_EXPORT_RULES,
    SERVICE_REPORT,
    SERVICE_RESET,
    SERVICE_SIMULATE_LEVEL,
    SERVICE_TEST_NOTIFICATION,
    CONF_RULES,
)


class FakeServices:
    def __init__(self) -> None:
        self._registered: dict[str, dict[str, object]] = {}

    def has_service(self, domain: str, service: str) -> bool:
        return service in self._registered.get(domain, {})

    def async_register(self, domain: str, service: str, handler, schema=None) -> None:
        self._registered.setdefault(domain, {})[service] = {
            "handler": handler,
            "schema": schema,
        }

    def async_remove(self, domain: str, service: str) -> None:
        self._registered.get(domain, {}).pop(service, None)


class FakeConfigEntries:
    def __init__(self, unload_ok: bool = True) -> None:
        self.forward_calls: list[tuple[str, list[str]]] = []
        self.unload_calls: list[tuple[str, list[str]]] = []
        self.reload_calls: list[str] = []
        self.unload_ok = unload_ok

    async def async_forward_entry_setups(self, entry, platforms):
        self.forward_calls.append((entry.entry_id, list(platforms)))

    async def async_unload_platforms(self, entry, platforms):
        self.unload_calls.append((entry.entry_id, list(platforms)))
        return self.unload_ok

    async def async_reload(self, entry_id: str):
        self.reload_calls.append(entry_id)


class FakeEntry:
    def __init__(self, entry_id: str, data: dict, options: dict | None = None) -> None:
        self.entry_id = entry_id
        self.data = data
        self.options = options or {}
        self._listener = None
        self._unload = None

    def add_update_listener(self, listener):
        self._listener = listener
        return lambda: None

    def async_on_unload(self, callback):
        self._unload = callback


class FakeCoordinator:
    def __init__(self, hass, entry) -> None:
        self.hass = hass
        self.entry = entry
        self.stop_state = {"state": "ok"}
        self.calls: list[tuple[str, tuple, dict]] = []

    async def async_config_entry_first_refresh(self):
        self.calls.append(("first_refresh", (), {}))

    def reset(self):
        self.calls.append(("reset", (), {}))

    def acknowledge(self):
        self.calls.append(("acknowledge", (), {}))

    async def async_write_report(self, send_email=False):
        self.calls.append(("write_report", (), {"send_email": send_email}))

    async def async_send_test_notification(
        self, level, message=None, urgent=None, targets=None
    ):
        self.calls.append(
            (
                "test_notification",
                (),
                {
                    "level": level,
                    "message": message,
                    "urgent": urgent,
                    "targets": targets,
                },
            )
        )

    async def async_simulate_level(self, **kwargs):
        self.calls.append(("simulate_level", (), kwargs))

    async def async_clear_simulation(self, send_notifications=True):
        self.calls.append(
            ("clear_simulation", (), {"send_notifications": send_notifications})
        )

    async def async_export_rules(self):
        self.calls.append(("export_rules", (), {}))
        return "/tmp/rules.json"

    def async_set_updated_data(self, data):
        self.calls.append(("set_updated_data", (data,), {}))


def _make_hass() -> SimpleNamespace:
    return SimpleNamespace(
        data={},
        services=FakeServices(),
        config_entries=FakeConfigEntries(),
    )


def test_async_setup_entry_registers_services(monkeypatch):
    hass = _make_hass()
    entry = FakeEntry("entry_1", {CONF_RULES: [{"rule_id": "r1"}]})

    monkeypatch.setattr(
        integration, "EmergencyStopCoordinator", FakeCoordinator, raising=True
    )

    result = asyncio.run(integration.async_setup_entry(hass, entry))

    assert result is True
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]
    assert hass.config_entries.forward_calls
    assert entry._listener is integration._async_update_options
    registered = hass.services._registered.get(DOMAIN, {})
    assert SERVICE_RESET in registered
    assert SERVICE_ACK in registered
    assert SERVICE_REPORT in registered
    assert SERVICE_TEST_NOTIFICATION in registered
    assert SERVICE_SIMULATE_LEVEL in registered
    assert SERVICE_CLEAR_SIMULATION in registered
    assert SERVICE_EXPORT_RULES in registered


def test_async_setup_entry_fails_without_rules():
    hass = _make_hass()
    entry = FakeEntry("entry_1", {})

    result = asyncio.run(integration.async_setup_entry(hass, entry))

    assert result is False
    assert DOMAIN not in hass.data


def test_async_unload_entry_removes_services_when_last_entry():
    hass = _make_hass()
    entry = FakeEntry("entry_1", {CONF_RULES: [{"rule_id": "r1"}]})
    hass.data[DOMAIN] = {entry.entry_id: object()}
    for service in (
        SERVICE_RESET,
        SERVICE_ACK,
        SERVICE_REPORT,
        SERVICE_TEST_NOTIFICATION,
        SERVICE_SIMULATE_LEVEL,
        SERVICE_CLEAR_SIMULATION,
        SERVICE_EXPORT_RULES,
    ):
        hass.services.async_register(DOMAIN, service, lambda *_args, **_kwargs: None)

    result = asyncio.run(integration.async_unload_entry(hass, entry))

    assert result is True
    assert hass.services._registered.get(DOMAIN, {}) == {}


def test_async_update_options_reloads_entry():
    hass = _make_hass()
    entry = FakeEntry("entry_1", {CONF_RULES: [{"rule_id": "r1"}]})

    asyncio.run(integration._async_update_options(hass, entry))

    assert hass.config_entries.reload_calls == ["entry_1"]


def test_service_handlers_dispatch_to_coordinators():
    hass = _make_hass()
    c1 = FakeCoordinator(hass, None)
    c2 = FakeCoordinator(hass, None)
    hass.data[DOMAIN] = {"a": c1, "b": c2}

    asyncio.run(integration._handle_reset(SimpleNamespace(hass=hass, data={})))
    asyncio.run(integration._handle_ack(SimpleNamespace(hass=hass, data={})))
    asyncio.run(integration._handle_report(SimpleNamespace(hass=hass, data={})))
    asyncio.run(
        integration._handle_test_notification(
            SimpleNamespace(hass=hass, data={CONF_NOTIFICATION_LEVEL: LEVEL_NORMAL})
        )
    )
    asyncio.run(
        integration._handle_simulate_level(
            SimpleNamespace(
                hass=hass,
                data={
                    CONF_SIMULATION_LEVEL: LEVEL_LIMIT,
                    CONF_SIMULATION_DURATION: 5,
                    CONF_SIMULATION_REASON: "reason",
                    CONF_SIMULATION_DETAIL: "detail",
                    CONF_SIMULATION_ENTITY_ID: "sensor.x",
                    CONF_SIMULATION_VALUE: 12.3,
                    CONF_SIMULATION_SEND_NOTIFICATIONS: False,
                    CONF_SIMULATION_SEND_EMAIL: True,
                },
            )
        )
    )
    asyncio.run(integration._handle_clear_simulation(SimpleNamespace(hass=hass, data={})))
    asyncio.run(integration._handle_export_rules(SimpleNamespace(hass=hass, data={})))

    for coordinator in (c1, c2):
        methods = [name for name, _args, _kwargs in coordinator.calls]
        assert "reset" in methods
        assert "acknowledge" in methods
        assert "write_report" in methods
        assert "test_notification" in methods
        assert "simulate_level" in methods
        assert "clear_simulation" in methods
        assert "export_rules" in methods
        assert "set_updated_data" in methods
