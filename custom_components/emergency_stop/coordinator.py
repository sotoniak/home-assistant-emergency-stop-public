"""Coordinator and evaluation logic for Emergency Stop."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import asyncio
import json
from pathlib import Path
import logging
import time
import zlib
from typing import Any, Awaitable, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from .brevo import async_send_brevo_email
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ACKNOWLEDGED,
    ATTR_ACTIVE_EVENTS,
    ATTR_ACTIVE_LEVELS,
    ATTR_ACTIVE_REASONS,
    ATTR_ERROR_LEVEL,
    ATTR_EVENTS_BY_REASON,
    ATTR_LAST_UPDATE,
    ATTR_LATCHED_SINCE,
    ATTR_PRIMARY_CELL,
    ATTR_PRIMARY_DETAIL,
    ATTR_PRIMARY_INPUT,
    ATTR_PRIMARY_LEVEL,
    ATTR_PRIMARY_PACK,
    ATTR_PRIMARY_REASON,
    ATTR_PRIMARY_SENSOR,
    ATTR_PRIMARY_VALUE,
    CONF_BREVO_API_KEY,
    CONF_BREVO_SENDER,
    CONF_BREVO_RECIPIENT,
    CONF_BREVO_RECIPIENT_LIMIT,
    CONF_BREVO_RECIPIENT_NOTIFY,
    CONF_BREVO_RECIPIENT_SHUTDOWN,
    CONF_EMAIL_LEVELS,
    CONF_MOBILE_NOTIFY_ENABLED,
    CONF_MOBILE_NOTIFY_TARGETS_NOTIFY,
    CONF_MOBILE_NOTIFY_TARGETS_LIMIT,
    CONF_MOBILE_NOTIFY_TARGETS_SHUTDOWN,
    CONF_MOBILE_NOTIFY_URGENT_NOTIFY,
    CONF_MOBILE_NOTIFY_URGENT_LIMIT,
    CONF_MOBILE_NOTIFY_URGENT_SHUTDOWN,
    CONF_REPORT_DOMAINS,
    CONF_REPORT_ENTITY_IDS,
    CONF_REPORT_MODE,
    CONF_REPORT_RETENTION_MAX_AGE_DAYS,
    CONF_REPORT_RETENTION_MAX_FILES,
    CONF_RULES,
    CONF_RULE_AGGREGATE,
    CONF_RULE_CONDITION,
    CONF_RULE_DATA_TYPE,
    CONF_RULE_DURATION,
    CONF_RULE_ENTITIES,
    CONF_RULE_ID,
    CONF_RULE_INTERVAL,
    CONF_RULE_LATCHED,
    CONF_RULE_LEVEL,
    CONF_RULE_SEVERITY_MODE,
    CONF_RULE_DIRECTION,
    CONF_RULE_LEVELS,
    CONF_RULE_NAME,
    CONF_RULE_NOTIFY_EMAIL,
    CONF_RULE_NOTIFY_MOBILE,
    CONF_RULE_TEXT_CASE_SENSITIVE,
    CONF_RULE_TEXT_TRIM,
    CONF_RULE_UNKNOWN_HANDLING,
    CONF_RULE_THRESHOLDS,
    COND_BETWEEN,
    COND_CONTAINS,
    COND_EQUALS,
    COND_EQ,
    COND_GT,
    COND_GTE,
    COND_IS_OFF,
    COND_IS_ON,
    COND_LT,
    COND_LTE,
    DATA_TYPE_BINARY,
    DATA_TYPE_NUMERIC,
    DATA_TYPE_TEXT,
    DEFAULT_RULE_DURATION,
    DEFAULT_RULE_INTERVAL,
    DEFAULT_RULE_LATCHED,
    DEFAULT_RULE_LEVEL,
    DEFAULT_RULE_NOTIFY_EMAIL,
    DEFAULT_RULE_NOTIFY_MOBILE,
    DEFAULT_RULE_UNKNOWN_HANDLING,
    DEFAULT_TEXT_CASE_SENSITIVE,
    DEFAULT_TEXT_TRIM,
    DEFAULT_MOBILE_NOTIFY_ENABLED,
    DEFAULT_MOBILE_NOTIFY_URGENT_NOTIFY,
    DEFAULT_MOBILE_NOTIFY_URGENT_LIMIT,
    DEFAULT_MOBILE_NOTIFY_URGENT_SHUTDOWN,
    DEFAULT_EMAIL_LEVELS,
    DEFAULT_REPORT_RETENTION_MAX_AGE_DAYS,
    DEFAULT_REPORT_RETENTION_MAX_FILES,
    LEVEL_LIMIT,
    LEVEL_NORMAL,
    LEVEL_NOTIFY,
    LEVEL_OPTIONS,
    LEVEL_ORDER,
    LEVEL_SHUTDOWN,
    REPORT_MODE_BASIC,
    REPORT_MODE_EXTENDED,
    SEVERITY_MODE_SEMAFOR,
    SEVERITY_MODE_SIMPLE,
    DIRECTION_HIGHER_IS_WORSE,
    DIRECTION_LOWER_IS_WORSE,
    UNKNOWN_TREAT_OK,
    UNKNOWN_TREAT_VIOLATION,
)

_LOGGER = logging.getLogger(__name__)

_LEVEL_RANK = {LEVEL_NOTIFY: 1, LEVEL_LIMIT: 2, LEVEL_SHUTDOWN: 3}
_NOTIFICATION_TIMEOUT_SECONDS = 3

REPORT_BASE_DIR = Path("/media/emergency-stop")
REPORT_LOG_DIR = REPORT_BASE_DIR / "logs"
REPORT_CONFIG_DIR = REPORT_BASE_DIR / "config"
def _should_notify_on_activation(prev_active: bool, new_active: bool) -> bool:
    return not prev_active and new_active


def _format_notify_message(
    report: dict[str, Any], level: str | None, report_path: Path | None = None
) -> str:
    lines = [
        "You are an expert in Home Assistant troubleshooting.",
        "Analyze the Emergency Stop report below and identify the single most likely root cause.",
        "Answer in English and rely only on the report data.",
        "Use outputs.primary_reason / outputs.primary_sensor_entity / outputs.active_events.",
        "If there are multiple events, pick the highest level; if tied, pick the earliest.",
        "If outputs.active is false or active_events is empty, say: No active violation.",
        "Include relevant thresholds and duration from config when applicable.",
        "Provide the result in this exact format:",
        "Root cause: <one sentence>",
        "Evidence: <primary reason, entity id, value or state, threshold, timestamps>",
        "Recommended action: <1-2 concrete steps>",
    ]
    if level:
        lines.append(f"Current level: {level}")
    if report_path is not None:
        lines.append(f"Report file: {report_path}")
    lines.append("")
    lines.append("Emergency Stop report (JSON):")
    lines.append("```json")
    lines.append(json.dumps(report, indent=2, ensure_ascii=True))
    lines.append("```")
    return "\n".join(lines)


def _deterministic_offset_seconds(rule_id: str, interval_seconds: int) -> int:
    if interval_seconds <= 1:
        return 0
    checksum = zlib.crc32(rule_id.encode("utf-8")) & 0xFFFFFFFF
    return int(checksum % interval_seconds)


@dataclass
class RuleConfig:
    rule_id: str
    name: str
    data_type: str
    entities: list[str]
    aggregate: str
    condition: str | None
    thresholds: list[Any]
    duration_seconds: int
    interval_seconds: int
    level: str
    latched: bool
    unknown_handling: str
    severity_mode: str
    direction: str | None
    levels: dict[str, dict[str, Any]]
    text_case_sensitive: bool
    text_trim: bool
    notify_email: bool = True
    notify_mobile: bool = True


@dataclass
class RuleRuntimeState:
    active: bool = False
    active_since: str | None = None
    last_update: str | None = None
    last_eval_monotonic: float | None = None
    violation_started_at: float | None = None
    last_match: bool | None = None
    last_aggregate: float | int | str | None = None
    last_entity: str | None = None
    last_detail: str | None = None
    last_invalid_reason: str | None = None
    current_level: str | None = None
    latched_level: str | None = None
    level_violation_started_at: dict[str, float | None] = field(default_factory=dict)
    level_active_since: dict[str, str | None] = field(default_factory=dict)
    active_levels: list[str] = field(default_factory=list)

    def reset(self) -> None:
        self.active = False
        self.active_since = None
        self.last_update = None
        self.last_eval_monotonic = None
        self.violation_started_at = None
        self.last_match = None
        self.last_aggregate = None
        self.last_entity = None
        self.last_detail = None
        self.last_invalid_reason = None
        self.current_level = None
        self.latched_level = None
        self.level_violation_started_at = {}
        self.level_active_since = {}
        self.active_levels = []


@dataclass
class SimulationState:
    level: str
    reason: str
    detail: str | None
    entity_id: str | None
    value: float | int | str | None
    started_at: str
    expires_at_monotonic: float | None
    send_notifications: bool


@dataclass
class EmergencyStopState:
    """Aggregated emergency stop state."""

    active: bool = False
    level: str | None = None
    primary_reason: str | None = None
    primary_level: str | None = None
    primary_pack: int | None = None
    primary_input: str | None = None
    primary_cell: int | None = None
    primary_sensor_entity: str | None = None
    primary_value: float | int | str | None = None
    primary_detail: str | None = None
    active_events: list[dict[str, Any]] = field(default_factory=list)
    acknowledged: bool = False
    last_update: str | None = None
    latched_since: str | None = None

    def to_attributes(self) -> dict[str, Any]:
        return {
            ATTR_ERROR_LEVEL: self.level,
            ATTR_PRIMARY_REASON: self.primary_reason,
            ATTR_PRIMARY_LEVEL: self.primary_level,
            ATTR_PRIMARY_PACK: self.primary_pack,
            ATTR_PRIMARY_INPUT: self.primary_input,
            ATTR_PRIMARY_CELL: self.primary_cell,
            ATTR_PRIMARY_SENSOR: self.primary_sensor_entity,
            ATTR_PRIMARY_VALUE: self.primary_value,
            ATTR_PRIMARY_DETAIL: self.primary_detail,
            ATTR_ACTIVE_EVENTS: self.active_events,
            ATTR_ACTIVE_REASONS: self.active_reasons(),
            ATTR_ACTIVE_LEVELS: self.active_levels(),
            ATTR_EVENTS_BY_REASON: self.events_by_reason(),
            ATTR_ACKNOWLEDGED: self.acknowledged,
            ATTR_LAST_UPDATE: self.last_update,
            ATTR_LATCHED_SINCE: self.latched_since,
        }

    def active_reasons(self) -> list[str]:
        reasons: list[str] = []
        seen: set[str] = set()
        for event in self.active_events:
            reason = event.get("reason")
            if not reason or reason in seen:
                continue
            seen.add(reason)
            reasons.append(reason)
        return reasons

    def active_levels(self) -> list[str]:
        levels: list[str] = []
        seen: set[str] = set()
        for event in self.active_events:
            level = event.get("level")
            if not level or level in seen:
                continue
            seen.add(level)
            levels.append(level)
        return levels

    def events_by_reason(self) -> dict[str, dict[str, Any]]:
        by_reason: dict[str, dict[str, Any]] = {}
        for event in self.active_events:
            reason = event.get("reason")
            if not reason:
                continue

            bucket = by_reason.setdefault(
                reason,
                {
                    "count": 0,
                    "highest_level": None,
                    "latest_seen": "",
                    "latest_detail": "",
                    "entity_ids": set(),
                    "rule_ids": set(),
                },
            )
            bucket["count"] += 1
            level = event.get("level")
            if level and (
                bucket["highest_level"] is None
                or _LEVEL_RANK.get(level, 0)
                > _LEVEL_RANK.get(bucket["highest_level"], 0)
            ):
                bucket["highest_level"] = level

            seen_at = event.get("last_seen") or event.get("first_seen") or ""
            if seen_at >= bucket["latest_seen"]:
                bucket["latest_seen"] = seen_at
                bucket["latest_detail"] = event.get("detail") or reason

            entity_id = event.get("entity_id")
            if entity_id:
                bucket["entity_ids"].add(entity_id)
            rule_id = event.get("rule_id")
            if rule_id:
                bucket["rule_ids"].add(rule_id)

        for bucket in by_reason.values():
            bucket["entity_ids"] = sorted(bucket["entity_ids"])
            bucket["rule_ids"] = sorted(bucket["rule_ids"])
        return by_reason


@dataclass
class RuleEvalResult:
    match: bool | None
    aggregate: float | int | str | None
    detail: str
    entity_id: str | None
    invalid_reason: str | None = None


class RuleEngine:
    """Evaluate dynamic rules."""

    def __init__(self, rules: list[RuleConfig]) -> None:
        self._rules = rules
        self._states: dict[str, RuleRuntimeState] = {
            rule.rule_id: RuleRuntimeState() for rule in rules
        }
        self._invalid_logged: set[tuple[str, str, str]] = set()
        self._seed_initial_offsets()

    @property
    def rules(self) -> list[RuleConfig]:
        return self._rules

    @property
    def states(self) -> dict[str, RuleRuntimeState]:
        return self._states

    def reset(self) -> None:
        for state in self._states.values():
            state.reset()

    def _seed_initial_offsets(self) -> None:
        now_monotonic = time.monotonic()
        for rule in self._rules:
            interval = max(1, int(rule.interval_seconds))
            offset = _deterministic_offset_seconds(rule.rule_id, interval)
            state = self._states.get(rule.rule_id)
            if state is None:
                continue
            state.last_eval_monotonic = now_monotonic - (interval - offset)

    def evaluate(self, hass: HomeAssistant) -> None:
        now = dt_util.utcnow()
        now_iso = now.isoformat()
        now_monotonic = time.monotonic()

        for rule in self._rules:
            state = self._states[rule.rule_id]
            if state.last_eval_monotonic is not None and (
                now_monotonic - state.last_eval_monotonic
            ) < rule.interval_seconds:
                continue

            state.last_eval_monotonic = now_monotonic
            if rule.severity_mode == SEVERITY_MODE_SEMAFOR:
                self._evaluate_semafor(rule, hass, state, now_iso, now_monotonic)
            else:
                result = self._evaluate_rule(rule, hass)
                state.last_update = now_iso
                state.last_match = result.match
                state.last_aggregate = result.aggregate
                state.last_entity = result.entity_id
                state.last_detail = result.detail
                state.last_invalid_reason = result.invalid_reason

                if result.match is True:
                    if state.violation_started_at is None:
                        state.violation_started_at = now_monotonic
                    if (now_monotonic - state.violation_started_at) >= rule.duration_seconds:
                        if not state.active:
                            state.active = True
                            state.active_since = now_iso
                else:
                    state.violation_started_at = None
                    if not rule.latched:
                        state.active = False
                        state.active_since = None

    def _evaluate_rule(self, rule: RuleConfig, hass: HomeAssistant) -> RuleEvalResult:
        if rule.data_type == DATA_TYPE_NUMERIC:
            return self._evaluate_numeric(rule, hass)
        if rule.data_type == DATA_TYPE_BINARY:
            return self._evaluate_binary(rule, hass)
        return self._evaluate_text(rule, hass)

    def _evaluate_semafor(
        self,
        rule: RuleConfig,
        hass: HomeAssistant,
        state: RuleRuntimeState,
        now_iso: str,
        now_monotonic: float,
    ) -> None:
        if rule.data_type == DATA_TYPE_NUMERIC:
            value, entity_id, invalid_reason = self._collect_numeric_value(rule, hass)
        elif rule.data_type == DATA_TYPE_BINARY and rule.aggregate == "count":
            value, entity_id, invalid_reason = self._collect_binary_count(rule, hass)
        else:
            _LOGGER.error(
                "Rule %s (%s): semafor mode is not supported for data_type=%s aggregate=%s",
                rule.name,
                rule.rule_id,
                rule.data_type,
                rule.aggregate,
            )
            value, entity_id, invalid_reason = None, None, "unsupported"

        state.last_update = now_iso
        state.last_aggregate = value
        state.last_entity = entity_id
        state.last_invalid_reason = invalid_reason

        matches: dict[str, bool | None] = {}
        if invalid_reason is not None:
            if rule.unknown_handling == UNKNOWN_TREAT_VIOLATION:
                matches = {level: True for level in rule.levels}
            elif rule.unknown_handling == UNKNOWN_TREAT_OK:
                matches = {level: False for level in rule.levels}
            else:
                matches = {level: None for level in rule.levels}
            state.last_detail = f"{rule.name}: {invalid_reason}"
        else:
            for level, cfg in rule.levels.items():
                threshold = cfg["threshold"]
                if rule.direction == DIRECTION_LOWER_IS_WORSE:
                    matches[level] = value <= threshold
                else:
                    matches[level] = value >= threshold

        active_levels: list[str] = []
        for level in LEVEL_ORDER:
            cfg = rule.levels.get(level)
            if not cfg:
                continue
            match = matches.get(level)
            if match is True:
                started_at = state.level_violation_started_at.get(level)
                if started_at is None:
                    state.level_violation_started_at[level] = now_monotonic
                    started_at = now_monotonic
                duration = cfg["duration_seconds"]
                if (now_monotonic - started_at) >= duration:
                    if not state.level_active_since.get(level):
                        state.level_active_since[level] = now_iso
                    active_levels.append(level)
            else:
                state.level_violation_started_at[level] = None
                if not rule.latched:
                    state.level_active_since[level] = None

        state.active_levels = active_levels
        highest_level = _highest_level(active_levels)

        if rule.latched:
            if highest_level:
                state.latched_level = _highest_level(
                    [level for level in [state.latched_level, highest_level] if level]
                )
            state.current_level = state.latched_level
            state.active = state.current_level is not None
            state.active_since = (
                state.level_active_since.get(state.current_level)
                if state.current_level
                else None
            )
        else:
            state.current_level = highest_level
            state.active = state.current_level is not None
            state.active_since = (
                state.level_active_since.get(state.current_level)
                if state.current_level
                else None
            )

        if state.current_level and invalid_reason is None:
            threshold = rule.levels[state.current_level]["threshold"]
            state.last_detail = _format_semafor_detail(
                rule, state.current_level, value, threshold
            )

    def _evaluate_numeric(self, rule: RuleConfig, hass: HomeAssistant) -> RuleEvalResult:
        values: list[tuple[str, float]] = []
        for entity_id in rule.entities:
            state = hass.states.get(entity_id)
            value, reason = _parse_numeric_state(state)
            if reason is not None:
                self._log_invalid(rule, entity_id, reason, state)
                continue
            values.append((entity_id, value))

        if not values:
            return _handle_unknown(rule, "no_valid_values")

        if not _has_required_thresholds(rule):
            _LOGGER.error("Rule %s (%s): missing thresholds", rule.name, rule.rule_id)
            return _handle_unknown(rule, "missing_thresholds")

        aggregate, entity_id = _aggregate_numeric(values, rule.aggregate)
        match = _compare_numeric(aggregate, rule.condition, rule.thresholds)
        detail = _format_numeric_detail(rule, aggregate)
        return RuleEvalResult(match, aggregate, detail, entity_id)

    def _evaluate_binary(self, rule: RuleConfig, hass: HomeAssistant) -> RuleEvalResult:
        values: list[tuple[str, str]] = []
        for entity_id in rule.entities:
            state = hass.states.get(entity_id)
            value, reason = _parse_binary_state(state)
            if reason is not None:
                self._log_invalid(rule, entity_id, reason, state)
                continue
            values.append((entity_id, value))

        if not values:
            return _handle_unknown(rule, "no_valid_values")

        if rule.aggregate == "count":
            if not _has_required_thresholds(rule):
                _LOGGER.error(
                    "Rule %s (%s): missing thresholds for count condition",
                    rule.name,
                    rule.rule_id,
                )
                return _handle_unknown(rule, "missing_thresholds")
            count_on = sum(1 for _, value in values if value == "on")
            match = _compare_numeric(count_on, rule.condition, rule.thresholds)
            detail = _format_binary_count_detail(rule, count_on)
            return RuleEvalResult(match, count_on, detail, None)

        if rule.condition not in (COND_IS_ON, COND_IS_OFF):
            _LOGGER.error(
                "Rule %s (%s): invalid binary condition %s",
                rule.name,
                rule.rule_id,
                rule.condition,
            )
            return _handle_unknown(rule, "invalid_condition")

        target = "on" if rule.condition == COND_IS_ON else "off"
        matching = [entity_id for entity_id, value in values if value == target]
        if rule.aggregate == "any":
            match = bool(matching)
            entity_id = matching[0] if matching else None
        else:
            match = len(matching) == len(values)
            entity_id = values[0][0] if values else None
        detail = _format_binary_state_detail(rule, target)
        return RuleEvalResult(match, None, detail, entity_id)

    def _evaluate_text(self, rule: RuleConfig, hass: HomeAssistant) -> RuleEvalResult:
        values: list[tuple[str, str]] = []
        for entity_id in rule.entities:
            state = hass.states.get(entity_id)
            value, reason = _parse_text_state(state)
            if reason is not None:
                self._log_invalid(rule, entity_id, reason, state)
                continue
            values.append((entity_id, value))

        if not values:
            return _handle_unknown(rule, "no_valid_values")

        if not rule.thresholds:
            _LOGGER.error("Rule %s (%s): missing text match", rule.name, rule.rule_id)
            return _handle_unknown(rule, "missing_thresholds")

        match_value = str(rule.thresholds[0]) if rule.thresholds else ""
        if rule.text_trim:
            match_value = match_value.strip()
        if not rule.text_case_sensitive:
            match_value = match_value.lower()

        matches: list[str] = []
        for entity_id, raw in values:
            normalized = raw
            if rule.text_trim:
                normalized = normalized.strip()
            if not rule.text_case_sensitive:
                normalized = normalized.lower()
            if rule.condition == COND_CONTAINS:
                if match_value and match_value in normalized:
                    matches.append(entity_id)
            else:
                if normalized == match_value:
                    matches.append(entity_id)

        if rule.aggregate == "any":
            match = bool(matches)
            entity_id = matches[0] if matches else None
        else:
            match = len(matches) == len(values)
            entity_id = values[0][0] if values else None

        detail = _format_text_detail(rule, match_value)
        return RuleEvalResult(match, None, detail, entity_id)

    def _collect_numeric_value(
        self, rule: RuleConfig, hass: HomeAssistant
    ) -> tuple[float | None, str | None, str | None]:
        values: list[tuple[str, float]] = []
        for entity_id in rule.entities:
            state = hass.states.get(entity_id)
            value, reason = _parse_numeric_state(state)
            if reason is not None:
                self._log_invalid(rule, entity_id, reason, state)
                continue
            values.append((entity_id, value))

        if not values:
            return None, None, "no_valid_values"

        aggregate, entity_id = _aggregate_numeric(values, rule.aggregate)
        return aggregate, entity_id, None

    def _collect_binary_count(
        self, rule: RuleConfig, hass: HomeAssistant
    ) -> tuple[int | None, str | None, str | None]:
        values: list[tuple[str, str]] = []
        for entity_id in rule.entities:
            state = hass.states.get(entity_id)
            value, reason = _parse_binary_state(state)
            if reason is not None:
                self._log_invalid(rule, entity_id, reason, state)
                continue
            values.append((entity_id, value))

        if not values:
            return None, None, "no_valid_values"

        count_on = sum(1 for _, value in values if value == "on")
        return count_on, None, None

    def _log_invalid(
        self, rule: RuleConfig, entity_id: str, reason: str, state: Any
    ) -> None:
        state_value = state.state if state is not None else None
        key = (rule.rule_id, entity_id, reason)
        if key not in self._invalid_logged:
            _LOGGER.warning(
                "Rule %s (%s): invalid state for %s (%s): %s",
                rule.name,
                rule.rule_id,
                entity_id,
                reason,
                state_value,
            )
            self._invalid_logged.add(key)
        else:
            _LOGGER.debug(
                "Rule %s (%s): invalid state for %s (%s): %s",
                rule.name,
                rule.rule_id,
                entity_id,
                reason,
                state_value,
            )


class EmergencyStopCoordinator(DataUpdateCoordinator[EmergencyStopState]):
    """Coordinator for Emergency Stop integration."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        config = _get_entry_config(entry)
        self._brevo_api_key: str | None = config.get(CONF_BREVO_API_KEY)
        self._brevo_sender: str | None = config.get(CONF_BREVO_SENDER)
        self._brevo_recipient_default: str | None = _normalize_optional_str(
            config.get(CONF_BREVO_RECIPIENT)
        )
        self._brevo_recipients = {
            LEVEL_NOTIFY: _normalize_optional_str(
                config.get(CONF_BREVO_RECIPIENT_NOTIFY)
            ),
            LEVEL_LIMIT: _normalize_optional_str(
                config.get(CONF_BREVO_RECIPIENT_LIMIT)
            ),
            LEVEL_SHUTDOWN: _normalize_optional_str(
                config.get(CONF_BREVO_RECIPIENT_SHUTDOWN)
            ),
        }
        self._email_levels = _normalize_levels(
            config.get(CONF_EMAIL_LEVELS, DEFAULT_EMAIL_LEVELS)
        )
        self._email_levels_set = set(self._email_levels)
        self._report_retention_max_files = _coerce_non_negative_int(
            config.get(
                CONF_REPORT_RETENTION_MAX_FILES, DEFAULT_REPORT_RETENTION_MAX_FILES
            ),
            DEFAULT_REPORT_RETENTION_MAX_FILES,
        )
        self._report_retention_max_age_days = _coerce_non_negative_int(
            config.get(
                CONF_REPORT_RETENTION_MAX_AGE_DAYS, DEFAULT_REPORT_RETENTION_MAX_AGE_DAYS
            ),
            DEFAULT_REPORT_RETENTION_MAX_AGE_DAYS,
        )
        self._acknowledged = False
        self._mobile_notify_enabled = bool(
            config.get(CONF_MOBILE_NOTIFY_ENABLED, DEFAULT_MOBILE_NOTIFY_ENABLED)
        )
        self._mobile_notify_targets = {
            LEVEL_NOTIFY: list(config.get(CONF_MOBILE_NOTIFY_TARGETS_NOTIFY, [])),
            LEVEL_LIMIT: list(config.get(CONF_MOBILE_NOTIFY_TARGETS_LIMIT, [])),
            LEVEL_SHUTDOWN: list(config.get(CONF_MOBILE_NOTIFY_TARGETS_SHUTDOWN, [])),
        }
        self._mobile_notify_urgent = {
            LEVEL_NOTIFY: bool(
                config.get(
                    CONF_MOBILE_NOTIFY_URGENT_NOTIFY,
                    DEFAULT_MOBILE_NOTIFY_URGENT_NOTIFY,
                )
            ),
            LEVEL_LIMIT: bool(
                config.get(
                    CONF_MOBILE_NOTIFY_URGENT_LIMIT,
                    DEFAULT_MOBILE_NOTIFY_URGENT_LIMIT,
                )
            ),
            LEVEL_SHUTDOWN: bool(
                config.get(
                    CONF_MOBILE_NOTIFY_URGENT_SHUTDOWN,
                    DEFAULT_MOBILE_NOTIFY_URGENT_SHUTDOWN,
                )
            ),
        }
        self._last_mobile_level: str | None = None
        self._last_email_active = False
        self._suppress_level_notification = False
        self._simulation: SimulationState | None = None
        self._simulation_cancel: Callable[[], None] | None = None

        rules = _load_rules(config)
        self._rule_engine = RuleEngine(rules)
        self._stop_state = EmergencyStopState(level=LEVEL_NORMAL)

        update_interval = timedelta(seconds=_min_interval(rules))
        super().__init__(
            hass,
            _LOGGER,
            name="emergency_stop",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> EmergencyStopState:
        now_monotonic = time.monotonic()
        if self._simulation:
            if (
                self._simulation.expires_at_monotonic is not None
                and now_monotonic >= self._simulation.expires_at_monotonic
            ):
                send_notifications = self._simulation.send_notifications
                self._simulation = None
                if self._simulation_cancel:
                    self._simulation_cancel()
                    self._simulation_cancel = None
                if not send_notifications:
                    self._suppress_level_notification = True
            else:
                self._stop_state = self._build_simulation_state()
                return self._stop_state

        prev_mobile_level = self._last_mobile_level
        prev_email_active = self._last_email_active
        self._rule_engine.evaluate(self.hass)
        self._stop_state = _build_stop_state(
            self._rule_engine.rules,
            self._rule_engine.states,
            self._acknowledged,
        )
        email_rules = [rule for rule in self._rule_engine.rules if rule.notify_email]
        mobile_rules = [rule for rule in self._rule_engine.rules if rule.notify_mobile]
        email_state = _build_stop_state(
            email_rules, self._rule_engine.states, self._acknowledged
        )
        mobile_state = _build_stop_state(
            mobile_rules, self._rule_engine.states, self._acknowledged
        )
        if not self._stop_state.active:
            self._acknowledged = False
        side_effects: list[asyncio.Future] = []
        side_effects.append(
            self._maybe_send_activation_email(prev_email_active, email_state)
        )
        self._last_email_active = email_state.active
        if prev_mobile_level is None:
            self._last_mobile_level = mobile_state.level
        elif self._suppress_level_notification:
            self._suppress_level_notification = False
            self._last_mobile_level = mobile_state.level
        else:
            side_effects.append(
                self._maybe_send_level_notifications(
                    prev_mobile_level, mobile_state.level, mobile_state
                )
            )
            self._last_mobile_level = mobile_state.level
        await self._run_side_effects(side_effects, "notifications/email")
        return self._stop_state

    @property
    def rules(self) -> list[RuleConfig]:
        return self._rule_engine.rules

    @property
    def rule_states(self) -> dict[str, RuleRuntimeState]:
        return self._rule_engine.states

    def reset(self) -> None:
        now_iso = dt_util.utcnow().isoformat()
        self._acknowledged = False
        self._rule_engine.reset()
        self._stop_state = EmergencyStopState(last_update=now_iso, level=LEVEL_NORMAL)

    def acknowledge(self) -> None:
        now_iso = dt_util.utcnow().isoformat()
        self._acknowledged = True
        self._stop_state.acknowledged = True
        self._stop_state.last_update = now_iso

    @property
    def stop_state(self) -> EmergencyStopState:
        return self._stop_state

    def _effective_email_level(self, level: str | None) -> str:
        if level in LEVEL_OPTIONS:
            return level
        return LEVEL_NOTIFY

    def _recipient_for_level(self, level: str | None) -> str | None:
        effective = self._effective_email_level(level)
        recipient = self._brevo_recipients.get(effective)
        if recipient:
            return recipient
        return self._brevo_recipient_default

    def _email_should_send(self, level: str | None) -> bool:
        if not self._brevo_api_key or not self._brevo_sender:
            return False
        if not self._email_levels_set:
            return False
        effective = self._effective_email_level(level)
        if effective not in self._email_levels_set:
            return False
        return self._recipient_for_level(level) is not None

    async def async_write_report(
        self, send_email: bool = False, send_mobile_notification: bool = False
    ) -> Path:
        report, report_path = await self._async_write_report_file()
        if send_email:
            await self._send_report_email(report, report_path)
        if send_mobile_notification:
            await self._send_report_mobile_notification(report_path, self._stop_state.level)
        return report_path

    async def async_export_rules(self) -> Path:
        export = self._build_rules_export()
        filename = export["file_name"]
        export_path = REPORT_CONFIG_DIR / filename
        await self.hass.async_add_executor_job(
            self._write_report_file, export_path, export
        )
        _LOGGER.info("Emergency Stop rules exported to %s", export_path)
        return export_path

    async def async_send_test_notification(
        self,
        level: str,
        message: str | None = None,
        urgent: bool | None = None,
        targets: list[str] | None = None,
    ) -> None:
        if level not in LEVEL_OPTIONS and level != LEVEL_NORMAL:
            _LOGGER.warning("Invalid test notification level: %s", level)
            return
        if targets is None:
            targets = self._targets_for_level(level)
        if urgent is None:
            urgent = self._urgent_for_level(level)
        if not targets:
            _LOGGER.debug("No mobile notification targets configured for %s", level)
            return
        title = f"Emergency Stop [{level}]"
        body = message or f"Test notification for level {level}"
        await self._send_mobile_notifications(targets, title, body, urgent)

    async def async_simulate_level(
        self,
        level: str,
        duration_seconds: int | None = None,
        reason: str | None = None,
        detail: str | None = None,
        entity_id: str | None = None,
        value: float | int | str | None = None,
        send_notifications: bool = True,
        send_email: bool = False,
    ) -> None:
        if level not in LEVEL_OPTIONS and level != LEVEL_NORMAL:
            _LOGGER.warning("Invalid simulation level: %s", level)
            return
        if duration_seconds is not None and duration_seconds < 1:
            _LOGGER.warning("Simulation duration must be >= 1 second.")
            duration_seconds = None
        prev_level = getattr(self, "_last_mobile_level", None) or LEVEL_NORMAL
        if level == LEVEL_NORMAL:
            await self._clear_simulation(send_notifications=send_notifications)
            return

        now_iso = dt_util.utcnow().isoformat()
        expires_at = None
        if duration_seconds and duration_seconds > 0:
            expires_at = time.monotonic() + duration_seconds
        self._simulation = SimulationState(
            level=level,
            reason=reason or "Simulation",
            detail=detail,
            entity_id=entity_id,
            value=value,
            started_at=now_iso,
            expires_at_monotonic=expires_at,
            send_notifications=send_notifications,
        )
        if self._simulation_cancel:
            self._simulation_cancel()
            self._simulation_cancel = None
        if duration_seconds and duration_seconds > 0:
            self._simulation_cancel = async_call_later(
                self.hass, duration_seconds, self._handle_simulation_timeout
            )
        self._stop_state = self._build_simulation_state()
        self._last_mobile_level = level
        self.async_set_updated_data(self._stop_state)
        if send_notifications:
            await self._maybe_send_level_notifications(prev_level, level, self._stop_state)
        if send_email:
            try:
                report, report_path = await self._async_write_report_file()
                await self._send_report_email(report, report_path)
            except Exception:
                _LOGGER.exception("Failed to send Emergency Stop simulation email.")

    async def async_clear_simulation(self, send_notifications: bool = True) -> None:
        await self._clear_simulation(send_notifications=send_notifications)

    async def _clear_simulation(self, send_notifications: bool = True) -> None:
        if not self._simulation:
            return
        self._simulation = None
        if self._simulation_cancel:
            self._simulation_cancel()
            self._simulation_cancel = None
        if not send_notifications:
            self._suppress_level_notification = True
        await self.async_request_refresh()

    async def _async_end_simulation(self) -> None:
        if not self._simulation:
            return
        send_notifications = self._simulation.send_notifications
        self._simulation = None
        if self._simulation_cancel:
            self._simulation_cancel()
            self._simulation_cancel = None
        if not send_notifications:
            self._suppress_level_notification = True
        await self.async_request_refresh()

    def _handle_simulation_timeout(self, _now: Any) -> None:
        self.hass.async_create_task(self._async_end_simulation())

    async def _async_write_report_file(
        self, report: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any], Path]:
        if report is None:
            report = self._build_report()
        filename = report["file_name"]
        report_path = REPORT_LOG_DIR / filename
        await self.hass.async_add_executor_job(
            self._write_report_file, report_path, report
        )
        await self.hass.async_add_executor_job(self._cleanup_reports)
        _LOGGER.info("Emergency Stop report written to %s", report_path)
        return report, report_path

    def _write_report_file(self, path: Path, report: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=True))

    def _cleanup_reports(self) -> None:
        max_files = self._report_retention_max_files
        max_age_days = self._report_retention_max_age_days
        if max_files <= 0 and max_age_days <= 0:
            return
        try:
            if not REPORT_LOG_DIR.exists():
                return
            reports = [
                path for path in REPORT_LOG_DIR.glob("emergency_stop_report_*.json")
            ]
        except Exception:
            _LOGGER.exception("Failed to list Emergency Stop report files.")
            return

        now_ts = time.time()
        if max_age_days > 0:
            cutoff = now_ts - (max_age_days * 86400)
            remaining: list[Path] = []
            for path in reports:
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                        continue
                except Exception:
                    _LOGGER.exception("Failed to remove report %s", path)
                else:
                    remaining.append(path)
            reports = remaining

        if max_files > 0 and reports:
            try:
                reports.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            except Exception:
                _LOGGER.exception("Failed to sort Emergency Stop reports for cleanup.")
                return
            for path in reports[max_files:]:
                try:
                    path.unlink()
                except Exception:
                    _LOGGER.exception("Failed to remove report %s", path)

    async def _maybe_send_activation_email(
        self, prev_active: bool, email_state: EmergencyStopState
    ) -> None:
        if not _should_notify_on_activation(prev_active, email_state.active):
            return
        if not email_state.active:
            return
        if not self._email_should_send(email_state.level):
            _LOGGER.debug(
                "Emergency Stop email disabled or missing recipient for level %s.",
                email_state.level,
            )
            return
        try:
            report, report_path = await self._async_write_report_file()
            await self._send_report_email(report, report_path, level=email_state.level)
        except Exception:
            _LOGGER.exception("Failed to send Emergency Stop activation email.")

    async def _send_brevo_email(self, message: str, level: str | None) -> None:
        if not self._brevo_api_key or not self._brevo_sender:
            _LOGGER.warning("Brevo configuration incomplete; cannot send email.")
            return
        effective_level = self._effective_email_level(level)
        if effective_level not in self._email_levels_set:
            _LOGGER.debug("Email for level %s disabled; skipping email.", effective_level)
            return
        recipient = self._recipient_for_level(level)
        if not recipient:
            _LOGGER.debug("No email recipient configured for level %s.", effective_level)
            return
        await async_send_brevo_email(
            self.hass,
            self._brevo_api_key,
            self._brevo_sender,
            recipient,
            message,
            level,
        )

    async def _send_report_email(
        self,
        report: dict[str, Any],
        report_path: Path,
        level: str | None = None,
    ) -> None:
        level = level or self._stop_state.level
        if not self._email_should_send(level):
            _LOGGER.debug(
                "Email disabled for level %s; skipping report email.",
                level,
            )
            return
        message = _format_notify_message(report, level, report_path)
        await self._send_brevo_email(message, level)

    async def _send_report_mobile_notification(
        self, report_path: Path, level: str | None
    ) -> None:
        if not self._mobile_notify_enabled:
            _LOGGER.debug("Mobile notifications disabled; skipping report notification.")
            return
        targets = self._all_mobile_targets()
        if not targets:
            _LOGGER.debug("No mobile notification targets configured; skipping.")
            return
        title = f"Emergency Stop [{level or LEVEL_NORMAL}]"
        message = (
            "TEST: Emergency Stop report generated\n"
            f"Level: {level or LEVEL_NORMAL}\n"
            f"Report: {report_path.name}"
        )
        await self._send_mobile_notifications(targets, title, message, urgent=False)

    async def _run_side_effects(
        self, coros: list[Awaitable[Any]], label: str
    ) -> None:
        if not coros:
            return
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*coros, return_exceptions=True),
                timeout=_NOTIFICATION_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Emergency Stop %s timed out after %ss",
                label,
                _NOTIFICATION_TIMEOUT_SECONDS,
            )
            return
        for result in results:
            if isinstance(result, Exception):
                _LOGGER.warning(
                    "Emergency Stop %s failed: %s",
                    label,
                    result,
                )

    def _build_report(self) -> dict[str, Any]:
        now = dt_util.utcnow()
        timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        file_name = f"emergency_stop_report_{timestamp}.json"
        config = _get_entry_config(self.entry)
        rules_config = config.get(CONF_RULES, [])
        state_rows: list[dict[str, Any]] = []
        for rule in self._rule_engine.rules:
            for entity_id in rule.entities:
                state = self.hass.states.get(entity_id)
                attributes: dict[str, Any] = {}
                name = entity_id
                state_value: str | None = None
                if state is not None:
                    attributes = dict(state.attributes)
                    state_value = state.state
                    name = attributes.get("friendly_name") or entity_id
                state_rows.append(
                    {
                        "rule_id": rule.rule_id,
                        "rule_name": rule.name,
                        "entity_id": entity_id,
                        "name": name,
                        "state": state_value,
                        "attributes": attributes,
                    }
                )

        rule_states: list[dict[str, Any]] = []
        for rule in self._rule_engine.rules:
            runtime = self._rule_engine.states.get(rule.rule_id)
            if runtime is None:
                continue
            rule_states.append(
                {
                    "rule_id": rule.rule_id,
                    "rule_name": rule.name,
                    "active": runtime.active,
                    "active_since": runtime.active_since,
                    "last_match": runtime.last_match,
                    "last_aggregate": runtime.last_aggregate,
                    "last_entity": runtime.last_entity,
                    "last_detail": runtime.last_detail,
                    "last_update": runtime.last_update,
                    "latched": rule.latched,
                    "notify_email": rule.notify_email,
                    "notify_mobile": rule.notify_mobile,
                    "unknown_handling": rule.unknown_handling,
                    "severity_mode": rule.severity_mode,
                    "direction": rule.direction,
                    "current_level": runtime.current_level,
                    "latched_level": runtime.latched_level,
                    "active_levels": list(runtime.active_levels),
                }
            )

        extended_snapshot = self._build_extended_snapshot(config)
        email_levels = _normalize_levels(
            config.get(CONF_EMAIL_LEVELS, DEFAULT_EMAIL_LEVELS)
        )
        email_recipients = {
            "default": _normalize_optional_str(config.get(CONF_BREVO_RECIPIENT)),
            LEVEL_NOTIFY: _normalize_optional_str(
                config.get(CONF_BREVO_RECIPIENT_NOTIFY)
            ),
            LEVEL_LIMIT: _normalize_optional_str(
                config.get(CONF_BREVO_RECIPIENT_LIMIT)
            ),
            LEVEL_SHUTDOWN: _normalize_optional_str(
                config.get(CONF_BREVO_RECIPIENT_SHUTDOWN)
            ),
        }
        has_email_recipient = bool(
            email_recipients["default"]
            or email_recipients[LEVEL_NOTIFY]
            or email_recipients[LEVEL_LIMIT]
            or email_recipients[LEVEL_SHUTDOWN]
        )

        return {
            "generated_at": now.isoformat(),
            "file_name": file_name,
            "config": {
                "rules": rules_config,
                CONF_REPORT_MODE: config.get(CONF_REPORT_MODE, REPORT_MODE_BASIC),
                CONF_REPORT_DOMAINS: config.get(CONF_REPORT_DOMAINS, []),
                CONF_REPORT_ENTITY_IDS: config.get(CONF_REPORT_ENTITY_IDS, []),
                "mobile_notifications": {
                    "enabled": bool(
                        config.get(
                            CONF_MOBILE_NOTIFY_ENABLED,
                            DEFAULT_MOBILE_NOTIFY_ENABLED,
                        )
                    ),
                    "targets": {
                        LEVEL_NOTIFY: list(
                            config.get(CONF_MOBILE_NOTIFY_TARGETS_NOTIFY, [])
                        ),
                        LEVEL_LIMIT: list(
                            config.get(CONF_MOBILE_NOTIFY_TARGETS_LIMIT, [])
                        ),
                        LEVEL_SHUTDOWN: list(
                            config.get(CONF_MOBILE_NOTIFY_TARGETS_SHUTDOWN, [])
                        ),
                    },
                    "urgent": {
                        LEVEL_NOTIFY: bool(
                            config.get(
                                CONF_MOBILE_NOTIFY_URGENT_NOTIFY,
                                DEFAULT_MOBILE_NOTIFY_URGENT_NOTIFY,
                            )
                        ),
                        LEVEL_LIMIT: bool(
                            config.get(
                                CONF_MOBILE_NOTIFY_URGENT_LIMIT,
                                DEFAULT_MOBILE_NOTIFY_URGENT_LIMIT,
                            )
                        ),
                        LEVEL_SHUTDOWN: bool(
                            config.get(
                                CONF_MOBILE_NOTIFY_URGENT_SHUTDOWN,
                                DEFAULT_MOBILE_NOTIFY_URGENT_SHUTDOWN,
                            )
                        ),
                    },
                },
                "email": {
                    "enabled": bool(
                        config.get(CONF_BREVO_API_KEY)
                        and config.get(CONF_BREVO_SENDER)
                        and email_levels
                        and has_email_recipient
                    ),
                    CONF_BREVO_SENDER: config.get(CONF_BREVO_SENDER),
                    CONF_BREVO_RECIPIENT: email_recipients["default"],
                    CONF_BREVO_RECIPIENT_NOTIFY: email_recipients[LEVEL_NOTIFY],
                    CONF_BREVO_RECIPIENT_LIMIT: email_recipients[LEVEL_LIMIT],
                    CONF_BREVO_RECIPIENT_SHUTDOWN: email_recipients[LEVEL_SHUTDOWN],
                    CONF_EMAIL_LEVELS: list(email_levels),
                },
                "report_retention": {
                    CONF_REPORT_RETENTION_MAX_FILES: config.get(
                        CONF_REPORT_RETENTION_MAX_FILES,
                        DEFAULT_REPORT_RETENTION_MAX_FILES,
                    ),
                    CONF_REPORT_RETENTION_MAX_AGE_DAYS: config.get(
                        CONF_REPORT_RETENTION_MAX_AGE_DAYS,
                        DEFAULT_REPORT_RETENTION_MAX_AGE_DAYS,
                    ),
                },
            },
            "states": state_rows,
            "rule_states": rule_states,
            "extended_snapshot": extended_snapshot,
            "outputs": {
                "active": self._stop_state.active,
                "level": self._stop_state.level,
                "primary_reason": self._stop_state.primary_reason,
                "primary_level": self._stop_state.primary_level,
                "primary_pack": self._stop_state.primary_pack,
                "primary_input": self._stop_state.primary_input,
                "primary_cell": self._stop_state.primary_cell,
                "primary_sensor_entity": self._stop_state.primary_sensor_entity,
                "primary_value": self._stop_state.primary_value,
                "active_events": list(self._stop_state.active_events),
                "active_reasons": self._stop_state.active_reasons(),
                "active_levels": self._stop_state.active_levels(),
                "events_by_reason": self._stop_state.events_by_reason(),
                "acknowledged": self._stop_state.acknowledged,
                "last_update": self._stop_state.last_update,
                "latched_since": self._stop_state.latched_since,
            },
        }

    def _build_rules_export(self) -> dict[str, Any]:
        now = dt_util.utcnow()
        timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        file_name = f"emergency_stop_rules_{self.entry.entry_id}_{timestamp}.json"
        config = _get_entry_config(self.entry)
        rules_config = config.get(CONF_RULES, [])
        return {
            "generated_at": now.isoformat(),
            "file_name": file_name,
            "version": 1,
            "rules": rules_config,
        }

    def _build_simulation_state(self) -> EmergencyStopState:
        now_iso = dt_util.utcnow().isoformat()
        if not self._simulation:
            return EmergencyStopState(
                active=False,
                level=LEVEL_NORMAL,
                acknowledged=False,
                last_update=now_iso,
            )
        level = self._simulation.level
        if level == LEVEL_NORMAL:
            return EmergencyStopState(
                active=False,
                level=LEVEL_NORMAL,
                acknowledged=False,
                last_update=now_iso,
            )
        detail = self._simulation.detail or f"Simulation: {self._simulation.reason}"
        event = {
            "rule_id": "simulation",
            "reason": self._simulation.reason,
            "level": level,
            "entity_id": self._simulation.entity_id,
            "value": self._simulation.value,
            "detail": detail,
            "latched": False,
            "first_seen": self._simulation.started_at,
            "last_seen": now_iso,
            "data_type": "simulation",
        }
        return EmergencyStopState(
            active=True,
            level=level,
            primary_reason=self._simulation.reason,
            primary_level=level,
            primary_sensor_entity=self._simulation.entity_id,
            primary_value=self._simulation.value,
            primary_detail=detail,
            active_events=[event],
            acknowledged=False,
            last_update=now_iso,
            latched_since=self._simulation.started_at,
        )

    def _build_extended_snapshot(self, config: dict[str, Any]) -> dict[str, Any] | None:
        mode = config.get(CONF_REPORT_MODE, REPORT_MODE_BASIC)
        if mode != REPORT_MODE_EXTENDED:
            return None
        domains = config.get(CONF_REPORT_DOMAINS) or []
        selected_entity_ids = config.get(CONF_REPORT_ENTITY_IDS) or []
        if not domains and not selected_entity_ids:
            return None
        entities = self._collect_domain_entities(set(domains))
        selected_entities = self._collect_selected_entities(selected_entity_ids)
        by_entity_id = {row["entity_id"]: row for row in entities}
        for row in selected_entities:
            by_entity_id.setdefault(row["entity_id"], row)
        combined = list(by_entity_id.values())
        combined.sort(key=lambda item: (item.get("platform", ""), item.get("entity_id", "")))
        return {
            "domains": sorted(domains),
            "entity_ids": sorted(set(selected_entity_ids)),
            "entities": combined,
        }

    def _collect_domain_entities(self, domains: set[str]) -> list[dict[str, Any]]:
        if not domains:
            return []
        registry = er.async_get(self.hass)
        rows: list[dict[str, Any]] = []
        for entry in registry.entities.values():
            if entry.platform not in domains:
                continue
            if entry.domain not in ("sensor", "binary_sensor"):
                continue
            state = self.hass.states.get(entry.entity_id)
            attributes: dict[str, Any] = {}
            name = entry.name or entry.original_name or entry.entity_id
            state_value: str | None = None
            if state is not None:
                attributes = dict(state.attributes)
                state_value = state.state
                friendly = attributes.get("friendly_name")
                if friendly:
                    name = friendly
            rows.append(
                {
                    "platform": entry.platform,
                    "entity_id": entry.entity_id,
                    "name": name,
                    "state": state_value,
                    "attributes": attributes,
                }
            )
        rows.sort(key=lambda item: (item.get("platform", ""), item.get("entity_id", "")))
        return rows

    def _collect_selected_entities(self, entity_ids: list[str]) -> list[dict[str, Any]]:
        if not entity_ids:
            return []
        registry = er.async_get(self.hass)
        rows: list[dict[str, Any]] = []
        for entity_id in entity_ids:
            if not entity_id:
                continue
            entry = registry.entities.get(entity_id)
            platform = entry.platform if entry else entity_id.split(".", 1)[0]
            name = entity_id
            if entry:
                name = entry.name or entry.original_name or entity_id
            state = self.hass.states.get(entity_id)
            attributes: dict[str, Any] = {}
            state_value: str | None = None
            if state is not None:
                attributes = dict(state.attributes)
                state_value = state.state
                friendly = attributes.get("friendly_name")
                if friendly:
                    name = friendly
            rows.append(
                {
                    "platform": platform,
                    "entity_id": entity_id,
                    "name": name,
                    "state": state_value,
                    "attributes": attributes,
                }
            )
        rows.sort(key=lambda item: (item.get("platform", ""), item.get("entity_id", "")))
        return rows

    async def _maybe_send_level_notifications(
        self,
        prev_level: str | None,
        new_level: str | None,
        state: EmergencyStopState | None = None,
    ) -> None:
        if not self._mobile_notify_enabled:
            return
        if prev_level == new_level:
            return
        if new_level is None:
            new_level = LEVEL_NORMAL
        if prev_level is None:
            return

        if state is None:
            state = self._stop_state
        message = _format_level_change_message(
            prev_level,
            new_level,
            state,
        )

        if new_level == LEVEL_NORMAL:
            targets = self._targets_for_level(LEVEL_NOTIFY)
            await self._send_mobile_notifications(
                targets,
                f"Emergency Stop [{new_level}]",
                message,
                self._urgent_for_level(LEVEL_NOTIFY),
            )
            return

        await self._send_mobile_notifications(
            self._targets_for_level(new_level),
            f"Emergency Stop [{new_level}]",
            message,
            self._urgent_for_level(new_level),
        )

        if _is_downgrade(prev_level, new_level):
            await self._send_mobile_notifications(
                self._targets_for_level(prev_level),
                f"Emergency Stop [{new_level}]",
                message,
                self._urgent_for_level(prev_level),
            )

    def _targets_for_level(self, level: str) -> list[str]:
        if level == LEVEL_NORMAL:
            level = LEVEL_NOTIFY
        return list(self._mobile_notify_targets.get(level, []))

    def _all_mobile_targets(self) -> list[str]:
        targets: set[str] = set()
        for level in LEVEL_OPTIONS:
            targets.update(self._targets_for_level(level))
        return sorted(targets)

    def _urgent_for_level(self, level: str) -> bool:
        if level == LEVEL_NORMAL:
            level = LEVEL_NOTIFY
        return bool(self._mobile_notify_urgent.get(level, False))

    async def _send_mobile_notifications(
        self, targets: list[str], title: str, message: str, urgent: bool
    ) -> None:
        if not targets:
            return
        data: dict[str, Any] = {}
        if urgent:
            data = {
                "ttl": 0,
                "priority": "high",
                "push": {"interruption-level": "critical"},
            }
        for target in targets:
            domain, service = _split_notify_service(target)
            if domain != "notify":
                _LOGGER.warning("Invalid notify target: %s", target)
                continue
            if not self.hass.services.has_service(domain, service):
                _LOGGER.warning("Notify service not found: %s.%s", domain, service)
                continue
            payload = {"title": title, "message": message}
            if data:
                payload["data"] = data
            try:
                await self.hass.services.async_call(
                    domain, service, payload, blocking=True
                )
                _LOGGER.info("Mobile notification sent via %s.%s", domain, service)
            except Exception:
                _LOGGER.exception(
                    "Failed to send mobile notification via %s.%s", domain, service
                )


def _load_rules(config: dict[str, Any]) -> list[RuleConfig]:
    rules: list[RuleConfig] = []
    for raw in config.get(CONF_RULES, []) or []:
        try:
            rule_id = str(raw.get(CONF_RULE_ID))
            name = str(raw.get(CONF_RULE_NAME))
        except (TypeError, ValueError):
            _LOGGER.error("Invalid rule definition; missing id/name: %s", raw)
            continue
        if not rule_id or not name:
            _LOGGER.error("Invalid rule definition; missing id/name: %s", raw)
            continue

        thresholds = list(raw.get(CONF_RULE_THRESHOLDS, []))
        severity_mode = raw.get(CONF_RULE_SEVERITY_MODE, SEVERITY_MODE_SIMPLE)
        levels: dict[str, dict[str, Any]] = {}
        raw_levels = raw.get(CONF_RULE_LEVELS, {}) or {}
        if isinstance(raw_levels, dict):
            for level in LEVEL_ORDER:
                cfg = raw_levels.get(level)
                if not isinstance(cfg, dict):
                    continue
                try:
                    threshold = cfg.get("threshold")
                    duration = cfg.get("duration_seconds")
                    if threshold is None or duration is None:
                        continue
                    levels[level] = {
                        "threshold": float(threshold),
                        "duration_seconds": int(duration),
                    }
                except (TypeError, ValueError):
                    continue
        rule = RuleConfig(
            rule_id=rule_id,
            name=name,
            data_type=raw.get(CONF_RULE_DATA_TYPE, DATA_TYPE_NUMERIC),
            entities=list(raw.get(CONF_RULE_ENTITIES, [])),
            aggregate=raw.get(CONF_RULE_AGGREGATE, ""),
            condition=raw.get(CONF_RULE_CONDITION, ""),
            thresholds=thresholds,
            duration_seconds=max(
                1, int(raw.get(CONF_RULE_DURATION, DEFAULT_RULE_DURATION))
            ),
            interval_seconds=max(
                1, int(raw.get(CONF_RULE_INTERVAL, DEFAULT_RULE_INTERVAL))
            ),
            level=raw.get(CONF_RULE_LEVEL, DEFAULT_RULE_LEVEL),
            latched=bool(raw.get(CONF_RULE_LATCHED, DEFAULT_RULE_LATCHED)),
            unknown_handling=raw.get(
                CONF_RULE_UNKNOWN_HANDLING, DEFAULT_RULE_UNKNOWN_HANDLING
            ),
            severity_mode=severity_mode,
            direction=raw.get(CONF_RULE_DIRECTION),
            levels=levels,
            text_case_sensitive=bool(
                raw.get(CONF_RULE_TEXT_CASE_SENSITIVE, DEFAULT_TEXT_CASE_SENSITIVE)
            ),
            text_trim=bool(raw.get(CONF_RULE_TEXT_TRIM, DEFAULT_TEXT_TRIM)),
            notify_email=bool(
                raw.get(CONF_RULE_NOTIFY_EMAIL, DEFAULT_RULE_NOTIFY_EMAIL)
            ),
            notify_mobile=bool(
                raw.get(CONF_RULE_NOTIFY_MOBILE, DEFAULT_RULE_NOTIFY_MOBILE)
            ),
        )
        rules.append(rule)
    return rules


def _min_interval(rules: list[RuleConfig]) -> int:
    if not rules:
        return 1
    return max(1, min(rule.interval_seconds for rule in rules))


def _rule_active_level(
    rule: RuleConfig, runtime: RuleRuntimeState | None
) -> str | None:
    if runtime is None or not runtime.active:
        return None
    if rule.severity_mode == SEVERITY_MODE_SEMAFOR:
        return runtime.current_level
    return rule.level


def _build_stop_state(
    rules: list[RuleConfig],
    states: dict[str, RuleRuntimeState],
    acknowledged: bool,
) -> EmergencyStopState:
    active_events: list[dict[str, Any]] = []
    for rule in rules:
        runtime = states.get(rule.rule_id)
        level = _rule_active_level(rule, runtime)
        if not level:
            continue
        active_events.append(
            {
                "rule_id": rule.rule_id,
                "reason": rule.name,
                "level": level,
                "entity_id": runtime.last_entity,
                "value": runtime.last_aggregate,
                "detail": runtime.last_detail or rule.name,
                "latched": rule.latched,
                "notify_email": rule.notify_email,
                "notify_mobile": rule.notify_mobile,
                "first_seen": runtime.active_since,
                "last_seen": runtime.last_update or runtime.active_since,
                "data_type": rule.data_type,
            }
        )

    active_events.sort(
        key=lambda event: (event.get("first_seen") or "", event.get("rule_id") or "")
    )

    if not active_events:
        return EmergencyStopState(
            active=False,
            level=LEVEL_NORMAL,
            acknowledged=False,
            last_update=dt_util.utcnow().isoformat(),
        )

    def primary_sort_key(event: dict[str, Any]) -> tuple[int, str, str]:
        rank = _LEVEL_RANK.get(event.get("level", ""), 0)
        first_seen = event.get("first_seen") or ""
        rule_id = event.get("rule_id") or ""
        return (-rank, first_seen, rule_id)

    primary = min(active_events, key=primary_sort_key)
    level = _highest_level([event.get("level", "") for event in active_events])
    now_iso = dt_util.utcnow().isoformat()
    return EmergencyStopState(
        active=True,
        level=level,
        primary_reason=primary.get("reason"),
        primary_level=primary.get("level"),
        primary_pack=None,
        primary_input=None,
        primary_cell=None,
        primary_sensor_entity=primary.get("entity_id"),
        primary_value=primary.get("value"),
        primary_detail=primary.get("detail"),
        active_events=active_events,
        acknowledged=acknowledged,
        last_update=now_iso,
        latched_since=primary.get("first_seen"),
    )


def _parse_numeric_state(state: Any) -> tuple[float | None, str | None]:
    if state is None:
        return None, "missing"
    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None, "unknown"
    try:
        return float(state.state), None
    except (TypeError, ValueError):
        return None, "invalid"


def _parse_binary_state(state: Any) -> tuple[str | None, str | None]:
    if state is None:
        return None, "missing"
    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None, "unknown"
    value = str(state.state).lower()
    if value in ("on", "off"):
        return value, None
    return None, "invalid"


def _parse_text_state(state: Any) -> tuple[str | None, str | None]:
    if state is None:
        return None, "missing"
    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None, "unknown"
    return str(state.state), None


def _aggregate_numeric(
    values: list[tuple[str, float]], aggregate: str
) -> tuple[float, str | None]:
    if aggregate == "min":
        entity_id, value = min(values, key=lambda item: item[1])
        return value, entity_id
    if aggregate == "sum":
        return sum(value for _, value in values), None
    if aggregate == "avg":
        return sum(value for _, value in values) / len(values), None
    entity_id, value = max(values, key=lambda item: item[1])
    return value, entity_id


def _compare_numeric(value: float | int, condition: str, thresholds: list[Any]) -> bool:
    if condition == COND_GT:
        return value > float(thresholds[0])
    if condition == COND_GTE:
        return value >= float(thresholds[0])
    if condition == COND_LT:
        return value < float(thresholds[0])
    if condition == COND_LTE:
        return value <= float(thresholds[0])
    if condition == COND_EQ:
        return value == float(thresholds[0])
    low = float(thresholds[0])
    high = float(thresholds[1])
    return low <= value <= high


def _has_required_thresholds(rule: RuleConfig) -> bool:
    if rule.condition == COND_BETWEEN:
        return len(rule.thresholds) >= 2
    return len(rule.thresholds) >= 1


def _highest_level(levels: list[str] | None) -> str | None:
    if not levels:
        return None
    return max(levels, key=lambda level: _LEVEL_RANK.get(level, 0))


def _handle_unknown(rule: RuleConfig, reason: str) -> RuleEvalResult:
    detail = f"{rule.name}: {reason}"
    if rule.unknown_handling == UNKNOWN_TREAT_VIOLATION:
        return RuleEvalResult(True, None, detail, None, reason)
    if rule.unknown_handling == UNKNOWN_TREAT_OK:
        return RuleEvalResult(False, None, detail, None, reason)
    return RuleEvalResult(None, None, detail, None, reason)


def _format_numeric_detail(rule: RuleConfig, value: float) -> str:
    if rule.condition == COND_BETWEEN and len(rule.thresholds) >= 2:
        return (
            f"{rule.name}: {rule.aggregate}={value:.3f} between "
            f"{rule.thresholds[0]}..{rule.thresholds[1]}"
        )
    threshold = rule.thresholds[0] if rule.thresholds else ""
    return f"{rule.name}: {rule.aggregate}={value:.3f} {rule.condition} {threshold}"


def _format_binary_state_detail(rule: RuleConfig, target: str) -> str:
    return f"{rule.name}: {rule.aggregate} is {target}"


def _format_binary_count_detail(rule: RuleConfig, count_on: int) -> str:
    if rule.condition == COND_BETWEEN and len(rule.thresholds) >= 2:
        return (
            f"{rule.name}: count={count_on} between "
            f"{rule.thresholds[0]}..{rule.thresholds[1]}"
        )
    threshold = rule.thresholds[0] if rule.thresholds else ""
    return f"{rule.name}: count={count_on} {rule.condition} {threshold}"


def _format_text_detail(rule: RuleConfig, match_value: str) -> str:
    return f"{rule.name}: {rule.condition} '{match_value}'"


def _format_semafor_detail(
    rule: RuleConfig, level: str, value: float | int | None, threshold: float | int
) -> str:
    if value is None:
        return f"{rule.name}: {level} threshold {threshold}"
    comparator = ">=" if rule.direction != DIRECTION_LOWER_IS_WORSE else "<="
    return f"{rule.name}: {level} {value} {comparator} {threshold}"


def _get_entry_config(entry: ConfigEntry) -> dict[str, Any]:
    return {**entry.data, **entry.options}


def _split_notify_service(service: str) -> tuple[str, str]:
    if "." in service:
        domain, name = service.split(".", 1)
        return domain, name
    return "notify", service


def _is_downgrade(prev_level: str, new_level: str) -> bool:
    prev_rank = _LEVEL_RANK.get(prev_level, 0)
    new_rank = _LEVEL_RANK.get(new_level, 0)
    return new_rank < prev_rank


def _format_level_change_message(
    prev_level: str,
    new_level: str,
    state: EmergencyStopState,
) -> str:
    lines = [f"LEVEL CHANGED: {prev_level} -> {new_level}"]
    if state.primary_reason:
        lines.append(f"Reason: {state.primary_reason}")
    if state.primary_sensor_entity:
        lines.append(f"Entity: {state.primary_sensor_entity}")
    if state.primary_value is not None:
        lines.append(f"Value: {state.primary_value}")
    return "\n".join(lines)


def _normalize_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return str(value)


def _normalize_levels(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_levels = [value]
    else:
        raw_levels = list(value)
    normalized = {level for level in raw_levels if level in LEVEL_OPTIONS}
    return [level for level in LEVEL_ORDER if level in normalized]


def _coerce_non_negative_int(value: Any, default: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, numeric)
