"""Binary sensor platform for Emergency Stop."""
from __future__ import annotations

from typing import Any
import time

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, NAME
from .coordinator import EmergencyStopCoordinator, RuleConfig


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    coordinator: EmergencyStopCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = [
        EmergencyStopActiveBinarySensor(coordinator),
    ]
    entities.extend(
        EmergencyStopRuleBinarySensor(coordinator, rule)
        for rule in coordinator.rules
    )
    async_add_entities(entities)


class EmergencyStopActiveBinarySensor(
    CoordinatorEntity[EmergencyStopCoordinator], BinarySensorEntity
):
    """Binary sensor indicating if emergency stop is active."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EmergencyStopCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_active"
        self._attr_name = "Emergency Stop Active"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "emergency_stop")},
            name=NAME,
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.stop_state.active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.stop_state.to_attributes()


class EmergencyStopRuleBinarySensor(
    CoordinatorEntity[EmergencyStopCoordinator], BinarySensorEntity
):
    """Binary sensor indicating if a rule is active."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EmergencyStopCoordinator, rule: RuleConfig) -> None:
        super().__init__(coordinator)
        self._rule = rule
        self._attr_unique_id = f"{DOMAIN}_rule_{rule.rule_id}"
        self._attr_name = rule.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "emergency_stop")},
            name=NAME,
        )

    @property
    def is_on(self) -> bool:
        state = self.coordinator.rule_states.get(self._rule.rule_id)
        return bool(state and state.active)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.coordinator.rule_states.get(self._rule.rule_id)
        now = dt_util.utcnow()
        active_for_seconds: float | None = None
        violation_for_seconds: float | None = None
        next_evaluation_in_seconds: float | None = None
        evaluation: dict[str, Any] = {
            "evaluated_at": None,
            "aggregate": None,
            "match": None,
            "entity_id": None,
            "detail": None,
            "invalid_reason": None,
        }
        if state is not None:
            if state.active_since:
                active_since = dt_util.parse_datetime(state.active_since)
                if active_since:
                    active_for_seconds = max(
                        0.0, (now - active_since).total_seconds()
                    )
            violation_started_at = None
            if state.current_level and state.level_violation_started_at:
                violation_started_at = state.level_violation_started_at.get(
                    state.current_level
                )
            if violation_started_at is None:
                violation_started_at = state.violation_started_at
            if violation_started_at is not None:
                violation_for_seconds = max(
                    0.0, time.monotonic() - violation_started_at
                )
            if state.last_eval_monotonic is not None:
                elapsed = time.monotonic() - state.last_eval_monotonic
                next_evaluation_in_seconds = max(
                    0.0, self._rule.interval_seconds - elapsed
                )
            evaluation = {
                "evaluated_at": state.last_update,
                "aggregate": state.last_aggregate,
                "match": state.last_match,
                "entity_id": state.last_entity,
                "detail": state.last_detail,
                "invalid_reason": state.last_invalid_reason,
            }
        return {
            "rule_id": self._rule.rule_id,
            "rule_name": self._rule.name,
            "data_type": self._rule.data_type,
            "entities": list(self._rule.entities),
            "aggregate": self._rule.aggregate,
            "condition": self._rule.condition,
            "thresholds": list(self._rule.thresholds),
            "severity_mode": self._rule.severity_mode,
            "direction": self._rule.direction,
            "levels": dict(self._rule.levels),
            "duration_seconds": self._rule.duration_seconds,
            "interval_seconds": self._rule.interval_seconds,
            "level": self._rule.level,
            "latched": self._rule.latched,
            "notify_email": self._rule.notify_email,
            "notify_mobile": self._rule.notify_mobile,
            "unknown_handling": self._rule.unknown_handling,
            "text_case_sensitive": self._rule.text_case_sensitive,
            "text_trim": self._rule.text_trim,
            "active_since": state.active_since if state else None,
            "last_match": state.last_match if state else None,
            "last_aggregate": state.last_aggregate if state else None,
            "last_entity": state.last_entity if state else None,
            "last_detail": state.last_detail if state else None,
            "last_update": state.last_update if state else None,
            "last_invalid_reason": state.last_invalid_reason if state else None,
            "current_level": state.current_level if state else None,
            "latched_level": state.latched_level if state else None,
            "active_levels": list(state.active_levels) if state else [],
            "active_for_seconds": active_for_seconds,
            "violation_for_seconds": violation_for_seconds,
            "next_evaluation_in_seconds": next_evaluation_in_seconds,
            "evaluation": evaluation,
        }
