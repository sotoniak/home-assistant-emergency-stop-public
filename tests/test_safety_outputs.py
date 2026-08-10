"""Safety-output contracts: what a physical stop is allowed to be wired to.

These cover the guarantees that make the integration safe to drive load with:
a shutdown signal that no lower level and no simulation can raise, and a
simulation that can neither run forever nor stop the rules from being evaluated.
"""
import asyncio

from custom_components.emergency_stop.const import (
    DEFAULT_SIMULATION_DURATION_SECONDS,
    LEVEL_LIMIT,
    LEVEL_NORMAL,
    LEVEL_NOTIFY,
    LEVEL_SHUTDOWN,
    MAX_SIMULATION_DURATION_SECONDS,
)
from custom_components.emergency_stop.coordinator import (
    EmergencyStopCoordinator,
    EmergencyStopState,
    _coerce_simulation_duration,
)


class FakeServices:
    def __init__(self):
        self.calls = []

    def has_service(self, domain, service):
        return True

    async def async_call(self, domain, service, payload, blocking=False):
        self.calls.append((domain, service, payload))


class FakeHass:
    def __init__(self):
        self.services = FakeServices()


def _coordinator(monkeypatch):
    monkeypatch.setattr(
        "custom_components.emergency_stop.coordinator.async_call_later",
        lambda *args, **kwargs: (lambda: None),
    )
    coordinator = EmergencyStopCoordinator.__new__(EmergencyStopCoordinator)
    coordinator.hass = FakeHass()
    coordinator._mobile_notify_enabled = False
    coordinator._mobile_notify_targets = {}
    coordinator._mobile_notify_urgent = {}
    coordinator._stop_state = EmergencyStopState(level=LEVEL_NORMAL)
    coordinator._real_stop_state = EmergencyStopState(level=LEVEL_NORMAL)
    coordinator._simulation = None
    coordinator._simulation_cancel = None
    coordinator._suppress_level_notification = False
    coordinator._last_mobile_level = None
    coordinator.async_set_updated_data = lambda _data: None
    return coordinator


def test_notifications_are_detached_from_the_update_cycle(monkeypatch):
    coordinator = _coordinator(monkeypatch)
    started = []
    finished = []

    async def slow_notification():
        started.append(True)
        await asyncio.sleep(0.05)
        finished.append(True)

    async def run():
        created = []

        def async_create_task(coro):
            created.append(coro)
            return asyncio.ensure_future(coro)

        coordinator.hass.async_create_task = async_create_task
        coordinator._schedule_side_effects([slow_notification()], "test")
        # The update cycle returns without waiting for the notification.
        assert finished == []
        await coordinator.async_wait_for_notifications()
        assert finished == [True]
        assert len(created) == 1

    asyncio.run(run())


def test_shutdown_active_only_for_shutdown_level(monkeypatch):
    coordinator = _coordinator(monkeypatch)
    for level in (LEVEL_NORMAL, LEVEL_NOTIFY, LEVEL_LIMIT):
        coordinator._real_stop_state = EmergencyStopState(active=True, level=level)
        assert coordinator.shutdown_active is False
    coordinator._real_stop_state = EmergencyStopState(
        active=True, level=LEVEL_SHUTDOWN
    )
    assert coordinator.shutdown_active is True


def test_simulated_shutdown_does_not_raise_shutdown_active(monkeypatch):
    coordinator = _coordinator(monkeypatch)

    async def run():
        await coordinator.async_simulate_level(
            level=LEVEL_SHUTDOWN, duration_seconds=60, send_notifications=False
        )

    asyncio.run(run())

    assert coordinator.simulation_active is True
    assert coordinator.stop_state.level == LEVEL_SHUTDOWN
    # The rule-derived state is untouched, so nothing that switches load reacts.
    assert coordinator.real_stop_state.level == LEVEL_NORMAL
    assert coordinator.shutdown_active is False


def test_simulation_always_expires(monkeypatch):
    coordinator = _coordinator(monkeypatch)

    async def run():
        await coordinator.async_simulate_level(
            level=LEVEL_LIMIT, duration_seconds=None, send_notifications=False
        )

    asyncio.run(run())

    assert coordinator._simulation is not None
    assert coordinator._simulation.expires_at_monotonic is not None


def test_simulation_duration_is_bounded():
    assert _coerce_simulation_duration(None) == DEFAULT_SIMULATION_DURATION_SECONDS
    assert _coerce_simulation_duration(0) == DEFAULT_SIMULATION_DURATION_SECONDS
    assert _coerce_simulation_duration(-5) == DEFAULT_SIMULATION_DURATION_SECONDS
    assert _coerce_simulation_duration("nonsense") == (
        DEFAULT_SIMULATION_DURATION_SECONDS
    )
    assert _coerce_simulation_duration(30) == 30
    assert (
        _coerce_simulation_duration(MAX_SIMULATION_DURATION_SECONDS * 10)
        == MAX_SIMULATION_DURATION_SECONDS
    )


def test_coordinator_constructor_runs(monkeypatch, tmp_path):
    """The real __init__ must be exercised at least once.

    Every other test builds the coordinator with __new__, so a NameError in the
    constructor shipped undetected: only the deployed instance found it.
    """
    import custom_components.emergency_stop.coordinator as coordinator_module

    class FakeStore:
        def __init__(self, *args, **kwargs):
            self.args = args

        async def async_load(self):
            return None

        def async_delay_save(self, *args, **kwargs):
            return None

    class FakeEntry:
        entry_id = "entry123"
        data = {
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
                }
            ]
        }
        options: dict = {}

    monkeypatch.setattr(coordinator_module, "Store", FakeStore)

    class LoopHass(FakeHass):
        pass

    coordinator = coordinator_module.EmergencyStopCoordinator(LoopHass(), FakeEntry())

    assert [rule.rule_id for rule in coordinator.rules] == ["ov"]
    assert coordinator.shutdown_active is False
    assert coordinator.protection_degraded is False
    assert coordinator.update_interval is not None
