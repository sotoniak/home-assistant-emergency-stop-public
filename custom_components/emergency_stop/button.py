"""Button platform for Emergency Stop."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import EmergencyStopCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    coordinator: EmergencyStopCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            EmergencyStopResetButton(coordinator),
            EmergencyStopReportButton(coordinator),
        ]
    )


class EmergencyStopResetButton(
    CoordinatorEntity[EmergencyStopCoordinator], ButtonEntity
):
    """Button to reset the latched Emergency Stop state."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:restart-alert"

    def __init__(self, coordinator: EmergencyStopCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_reset"
        self._attr_name = "Emergency Stop Reset"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "emergency_stop")},
            name=NAME,
        )

    async def async_press(self) -> None:
        self.coordinator.reset()
        self.coordinator.async_set_updated_data(self.coordinator.stop_state)


class EmergencyStopReportButton(
    CoordinatorEntity[EmergencyStopCoordinator], ButtonEntity
):
    """Button to generate a JSON report for the integration."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:file-document-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: EmergencyStopCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_report"
        self._attr_name = "Emergency Stop Report"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "emergency_stop")},
            name=NAME,
        )

    async def async_press(self) -> None:
        await self.coordinator.async_write_report(
            send_email=True, send_mobile_notification=True
        )
