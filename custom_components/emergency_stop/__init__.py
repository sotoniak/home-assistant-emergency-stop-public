"""Emergency Stop integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import (
    CONF_RULES,
    CONF_NOTIFICATION_LEVEL,
    CONF_NOTIFICATION_MESSAGE,
    CONF_NOTIFICATION_TARGETS,
    CONF_NOTIFICATION_URGENT,
    CONF_SIMULATION_LEVEL,
    CONF_SIMULATION_DURATION,
    CONF_SIMULATION_REASON,
    CONF_SIMULATION_DETAIL,
    CONF_SIMULATION_ENTITY_ID,
    CONF_SIMULATION_VALUE,
    CONF_SIMULATION_SEND_NOTIFICATIONS,
    CONF_SIMULATION_SEND_EMAIL,
    DOMAIN,
    PLATFORMS,
    SERVICE_ACK,
    SERVICE_CLEAR_SIMULATION,
    SERVICE_EXPORT_RULES,
    SERVICE_REPORT,
    SERVICE_RESET,
    SERVICE_SIMULATE_LEVEL,
    SERVICE_TEST_NOTIFICATION,
    LEVEL_NORMAL,
    LEVEL_OPTIONS,
)
from .coordinator import EmergencyStopCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_SCHEMA = vol.Schema({})
SERVICE_TEST_NOTIFICATION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NOTIFICATION_LEVEL): vol.In(LEVEL_OPTIONS + [LEVEL_NORMAL]),
        vol.Optional(CONF_NOTIFICATION_MESSAGE): cv.string,
        vol.Optional(CONF_NOTIFICATION_TARGETS): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_NOTIFICATION_URGENT): cv.boolean,
    }
)
SERVICE_SIMULATE_LEVEL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SIMULATION_LEVEL): vol.In(LEVEL_OPTIONS + [LEVEL_NORMAL]),
        vol.Optional(CONF_SIMULATION_DURATION): vol.Coerce(int),
        vol.Optional(CONF_SIMULATION_REASON): cv.string,
        vol.Optional(CONF_SIMULATION_DETAIL): cv.string,
        vol.Optional(CONF_SIMULATION_ENTITY_ID): cv.string,
        vol.Optional(CONF_SIMULATION_VALUE): object,
        vol.Optional(CONF_SIMULATION_SEND_NOTIFICATIONS, default=True): cv.boolean,
        vol.Optional(CONF_SIMULATION_SEND_EMAIL, default=False): cv.boolean,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Emergency Stop from a config entry."""
    config = {**entry.data, **entry.options}
    if not config.get(CONF_RULES):
        _LOGGER.error(
            "Emergency Stop rule engine requires rules. Remove the old entry and add a new one."
        )
        return False
    coordinator = EmergencyStopCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    if not hass.services.has_service(DOMAIN, SERVICE_RESET):
        hass.services.async_register(
            DOMAIN,
            SERVICE_RESET,
            _handle_reset,
            schema=SERVICE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_ACK):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ACK,
            _handle_ack,
            schema=SERVICE_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_REPORT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REPORT,
            _handle_report,
            schema=SERVICE_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_TEST_NOTIFICATION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_TEST_NOTIFICATION,
            _handle_test_notification,
            schema=SERVICE_TEST_NOTIFICATION_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_SIMULATE_LEVEL):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SIMULATE_LEVEL,
            _handle_simulate_level,
            schema=SERVICE_SIMULATE_LEVEL_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_SIMULATION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_SIMULATION,
            _handle_clear_simulation,
            schema=SERVICE_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_EXPORT_RULES):
        hass.services.async_register(
            DOMAIN,
            SERVICE_EXPORT_RULES,
            _handle_export_rules,
            schema=SERVICE_SCHEMA,
        )

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry to the latest version."""
    if entry.version >= 3:
        return True

    _LOGGER.error(
        "Emergency Stop rule engine does not support migration from older versions. "
        "Remove the existing entry and configure a new one."
    )
    return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    if not hass.data.get(DOMAIN):
        if hass.services.has_service(DOMAIN, SERVICE_RESET):
            hass.services.async_remove(DOMAIN, SERVICE_RESET)
        if hass.services.has_service(DOMAIN, SERVICE_ACK):
            hass.services.async_remove(DOMAIN, SERVICE_ACK)
        if hass.services.has_service(DOMAIN, SERVICE_REPORT):
            hass.services.async_remove(DOMAIN, SERVICE_REPORT)
        if hass.services.has_service(DOMAIN, SERVICE_TEST_NOTIFICATION):
            hass.services.async_remove(DOMAIN, SERVICE_TEST_NOTIFICATION)
        if hass.services.has_service(DOMAIN, SERVICE_SIMULATE_LEVEL):
            hass.services.async_remove(DOMAIN, SERVICE_SIMULATE_LEVEL)
        if hass.services.has_service(DOMAIN, SERVICE_CLEAR_SIMULATION):
            hass.services.async_remove(DOMAIN, SERVICE_CLEAR_SIMULATION)
        if hass.services.has_service(DOMAIN, SERVICE_EXPORT_RULES):
            hass.services.async_remove(DOMAIN, SERVICE_EXPORT_RULES)

    return unload_ok


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def _handle_reset(call: ServiceCall) -> None:
    hass: HomeAssistant = call.hass
    for coordinator in hass.data.get(DOMAIN, {}).values():
        coordinator.reset()
        coordinator.async_set_updated_data(coordinator.stop_state)


async def _handle_ack(call: ServiceCall) -> None:
    hass: HomeAssistant = call.hass
    for coordinator in hass.data.get(DOMAIN, {}).values():
        coordinator.acknowledge()
        coordinator.async_set_updated_data(coordinator.stop_state)


async def _handle_report(call: ServiceCall) -> None:
    hass: HomeAssistant = call.hass
    for coordinator in hass.data.get(DOMAIN, {}).values():
        await coordinator.async_write_report(send_email=True)


async def _handle_test_notification(call: ServiceCall) -> None:
    hass: HomeAssistant = call.hass
    level = call.data.get(CONF_NOTIFICATION_LEVEL, LEVEL_NORMAL)
    message = call.data.get(CONF_NOTIFICATION_MESSAGE)
    targets = call.data.get(CONF_NOTIFICATION_TARGETS)
    urgent = call.data.get(CONF_NOTIFICATION_URGENT)
    for coordinator in hass.data.get(DOMAIN, {}).values():
        await coordinator.async_send_test_notification(
            level=level, message=message, urgent=urgent, targets=targets
        )


async def _handle_simulate_level(call: ServiceCall) -> None:
    hass: HomeAssistant = call.hass
    level = call.data.get(CONF_SIMULATION_LEVEL, LEVEL_NORMAL)
    duration = call.data.get(CONF_SIMULATION_DURATION)
    reason = call.data.get(CONF_SIMULATION_REASON)
    detail = call.data.get(CONF_SIMULATION_DETAIL)
    entity_id = call.data.get(CONF_SIMULATION_ENTITY_ID)
    value = call.data.get(CONF_SIMULATION_VALUE)
    send_notifications = call.data.get(CONF_SIMULATION_SEND_NOTIFICATIONS, True)
    send_email = call.data.get(CONF_SIMULATION_SEND_EMAIL, False)
    for coordinator in hass.data.get(DOMAIN, {}).values():
        await coordinator.async_simulate_level(
            level=level,
            duration_seconds=duration,
            reason=reason,
            detail=detail,
            entity_id=entity_id,
            value=value,
            send_notifications=send_notifications,
            send_email=send_email,
        )


async def _handle_clear_simulation(call: ServiceCall) -> None:
    hass: HomeAssistant = call.hass
    for coordinator in hass.data.get(DOMAIN, {}).values():
        await coordinator.async_clear_simulation(send_notifications=True)


async def _handle_export_rules(call: ServiceCall) -> None:
    hass: HomeAssistant = call.hass
    for coordinator in hass.data.get(DOMAIN, {}).values():
        path = await coordinator.async_export_rules()
        _LOGGER.info("Emergency Stop rules exported to %s", path)
