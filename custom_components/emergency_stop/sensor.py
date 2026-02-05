"""Sensor platform for Emergency Stop."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    LEVEL_LIMIT,
    LEVEL_NORMAL,
    LEVEL_NOTIFY,
    LEVEL_SHUTDOWN,
    NAME,
)
from .coordinator import EmergencyStopCoordinator

_LEVEL_ICON_MAP = {
    LEVEL_NORMAL: "mdi:checkbox-blank-circle-outline",
    LEVEL_NOTIFY: "mdi:alpha-i-circle-outline",
    LEVEL_LIMIT: "mdi:alert-circle",
    LEVEL_SHUTDOWN: "mdi:alert-octagon",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    coordinator: EmergencyStopCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        EmergencyStopLevelSensor(coordinator),
    ]
    async_add_entities(entities)


class EmergencyStopLevelSensor(
    CoordinatorEntity[EmergencyStopCoordinator], SensorEntity
):
    """Sensor reporting the highest active severity level."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EmergencyStopCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_level"
        self._attr_name = "Emergency Stop Level"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "emergency_stop")},
            name=NAME,
        )

    @property
    def native_value(self) -> str:
        return self.coordinator.stop_state.level or LEVEL_NORMAL

    @property
    def icon(self) -> str | None:
        level = self.coordinator.stop_state.level or LEVEL_NORMAL
        return _LEVEL_ICON_MAP.get(level, "mdi:alert-octagon")
