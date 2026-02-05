import asyncio
from pathlib import Path

from custom_components.emergency_stop.coordinator import EmergencyStopCoordinator, EmergencyStopState
from custom_components.emergency_stop.const import LEVEL_LIMIT, LEVEL_NORMAL, LEVEL_NOTIFY, LEVEL_SHUTDOWN


class FakeServices:
    def __init__(self):
        self.calls = []

    def has_service(self, domain, service):
        return True

    async def async_call(self, domain, service, data, blocking=True):
        self.calls.append((domain, service, data, blocking))


class FakeHass:
    def __init__(self):
        self.services = FakeServices()

    def async_create_task(self, coro):
        return coro


def test_mobile_notifications_on_downgrade():
    async def run():
        coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
        coordinator.hass = FakeHass()
        coordinator._mobile_notify_enabled = True
        coordinator._mobile_notify_targets = {
            LEVEL_NOTIFY: ["notify.mobile_app_notify"],
            LEVEL_LIMIT: ["notify.mobile_app_limit"],
            LEVEL_SHUTDOWN: [],
        }
        coordinator._mobile_notify_urgent = {
            LEVEL_NOTIFY: False,
            LEVEL_LIMIT: True,
            LEVEL_SHUTDOWN: True,
        }
        coordinator._stop_state = EmergencyStopState(
            level=LEVEL_NOTIFY,
            primary_reason="Overvoltage",
            primary_sensor_entity="sensor.pack_max",
            primary_value=3.7,
        )

        await coordinator._maybe_send_level_notifications(LEVEL_LIMIT, LEVEL_NOTIFY)

        calls = coordinator.hass.services.calls
        assert len(calls) == 2
        assert calls[0][0] == "notify"
        assert calls[0][1] == "mobile_app_notify"
        assert "LEVEL CHANGED: limit -> notify" in calls[0][2]["message"]
        assert "data" not in calls[0][2]
        assert calls[1][0] == "notify"
        assert calls[1][1] == "mobile_app_limit"
        assert "LEVEL CHANGED: limit -> notify" in calls[1][2]["message"]
        assert calls[1][2]["data"]["priority"] == "high"

    asyncio.run(run())


def test_mobile_notifications_on_upgrade_only_new_level():
    async def run():
        coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
        coordinator.hass = FakeHass()
        coordinator._mobile_notify_enabled = True
        coordinator._mobile_notify_targets = {
            LEVEL_NOTIFY: ["notify.mobile_app_notify"],
            LEVEL_LIMIT: ["notify.mobile_app_limit"],
            LEVEL_SHUTDOWN: [],
        }
        coordinator._mobile_notify_urgent = {
            LEVEL_NOTIFY: False,
            LEVEL_LIMIT: False,
            LEVEL_SHUTDOWN: True,
        }
        coordinator._stop_state = EmergencyStopState(level=LEVEL_LIMIT)

        await coordinator._maybe_send_level_notifications(LEVEL_NOTIFY, LEVEL_LIMIT)

        calls = coordinator.hass.services.calls
        assert len(calls) == 1
        assert calls[0][1] == "mobile_app_limit"
        assert "LEVEL CHANGED: notify -> limit" in calls[0][2]["message"]

    asyncio.run(run())


def test_mobile_notifications_no_change():
    async def run():
        coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
        coordinator.hass = FakeHass()
        coordinator._mobile_notify_enabled = True
        coordinator._mobile_notify_targets = {
            LEVEL_NOTIFY: ["notify.mobile_app_notify"],
            LEVEL_LIMIT: ["notify.mobile_app_limit"],
            LEVEL_SHUTDOWN: [],
        }
        coordinator._mobile_notify_urgent = {
            LEVEL_NOTIFY: False,
            LEVEL_LIMIT: False,
            LEVEL_SHUTDOWN: True,
        }
        coordinator._stop_state = EmergencyStopState(level=LEVEL_LIMIT)

        await coordinator._maybe_send_level_notifications(LEVEL_LIMIT, LEVEL_LIMIT)

        calls = coordinator.hass.services.calls
        assert calls == []

    asyncio.run(run())


def test_mobile_notifications_to_normal_go_to_notify():
    async def run():
        coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
        coordinator.hass = FakeHass()
        coordinator._mobile_notify_enabled = True
        coordinator._mobile_notify_targets = {
            LEVEL_NOTIFY: ["notify.mobile_app_notify"],
            LEVEL_LIMIT: ["notify.mobile_app_limit"],
            LEVEL_SHUTDOWN: [],
        }
        coordinator._mobile_notify_urgent = {
            LEVEL_NOTIFY: False,
            LEVEL_LIMIT: False,
            LEVEL_SHUTDOWN: True,
        }
        coordinator._stop_state = EmergencyStopState(level=LEVEL_NORMAL)

        await coordinator._maybe_send_level_notifications(LEVEL_NOTIFY, LEVEL_NORMAL)

        calls = coordinator.hass.services.calls
        assert len(calls) == 1
        assert calls[0][1] == "mobile_app_notify"
        assert "LEVEL CHANGED: notify -> normal" in calls[0][2]["message"]

    asyncio.run(run())


def test_report_button_sends_test_notification():
    async def run():
        coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
        coordinator.hass = FakeHass()
        coordinator._mobile_notify_enabled = True
        coordinator._mobile_notify_targets = {
            LEVEL_NOTIFY: ["notify.mobile_app_notify"],
            LEVEL_LIMIT: ["notify.mobile_app_limit"],
            LEVEL_SHUTDOWN: ["notify.mobile_app_shutdown"],
        }
        coordinator._mobile_notify_urgent = {
            LEVEL_NOTIFY: False,
            LEVEL_LIMIT: False,
            LEVEL_SHUTDOWN: True,
        }

        await coordinator._send_report_mobile_notification(
            Path("/tmp/report.json"), LEVEL_LIMIT
        )

        calls = coordinator.hass.services.calls
        assert len(calls) == 3
        assert all("TEST" in call[2]["message"] for call in calls)

    asyncio.run(run())


def test_mobile_notifications_urgent_payload():
    async def run():
        coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
        coordinator.hass = FakeHass()
        coordinator._mobile_notify_enabled = True
        coordinator._mobile_notify_targets = {
            LEVEL_NOTIFY: ["notify.mobile_app_notify"],
            LEVEL_LIMIT: [],
            LEVEL_SHUTDOWN: ["notify.mobile_app_shutdown"],
        }
        coordinator._mobile_notify_urgent = {
            LEVEL_NOTIFY: False,
            LEVEL_LIMIT: False,
            LEVEL_SHUTDOWN: True,
        }
        coordinator._stop_state = EmergencyStopState(level=LEVEL_SHUTDOWN)

        await coordinator._maybe_send_level_notifications(LEVEL_LIMIT, LEVEL_SHUTDOWN)

        calls = coordinator.hass.services.calls
        assert len(calls) == 1
        assert calls[0][1] == "mobile_app_shutdown"
        assert calls[0][2]["data"]["priority"] == "high"
        assert calls[0][2]["data"]["push"]["interruption-level"] == "critical"

    asyncio.run(run())


def test_run_side_effects_timeout(monkeypatch):
    async def run():
        coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)

        async def dummy():
            return None

        async def fake_wait_for(*args, **kwargs):
            raise asyncio.TimeoutError

        monkeypatch.setattr(
            "custom_components.emergency_stop.coordinator.asyncio.wait_for", fake_wait_for
        )
        await coordinator._run_side_effects([dummy()], "test")

    asyncio.run(run())


def test_run_side_effects_exception_is_caught():
    async def run():
        coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)

        async def bad():
            raise RuntimeError("boom")

        await coordinator._run_side_effects([bad()], "test")

    asyncio.run(run())


def test_simulate_level_no_notifications():
    async def run():
        coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
        coordinator.hass = FakeHass()
        coordinator._mobile_notify_enabled = True
        coordinator._mobile_notify_targets = {
            LEVEL_NOTIFY: ["notify.mobile_app_notify"],
            LEVEL_LIMIT: ["notify.mobile_app_limit"],
            LEVEL_SHUTDOWN: ["notify.mobile_app_shutdown"],
        }
        coordinator._mobile_notify_urgent = {
            LEVEL_NOTIFY: False,
            LEVEL_LIMIT: False,
            LEVEL_SHUTDOWN: True,
        }
        coordinator._stop_state = EmergencyStopState(level=LEVEL_NORMAL)
        coordinator._simulation = None
        coordinator._simulation_cancel = None
        coordinator._suppress_level_notification = False
        coordinator.async_set_updated_data = lambda _data: None

        await coordinator.async_simulate_level(
            level=LEVEL_LIMIT, duration_seconds=None, send_notifications=False
        )

        assert coordinator.hass.services.calls == []

    asyncio.run(run())
