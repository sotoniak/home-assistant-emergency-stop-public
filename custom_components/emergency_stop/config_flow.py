"""Config flow for Emergency Stop."""
from __future__ import annotations

from typing import Any
import json

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_BREVO_API_KEY,
    CONF_BREVO_RECIPIENT,
    CONF_BREVO_RECIPIENT_LIMIT,
    CONF_BREVO_RECIPIENT_NOTIFY,
    CONF_BREVO_RECIPIENT_SHUTDOWN,
    CONF_BREVO_SENDER,
    CONF_EMAIL_LEVELS,
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
    CONF_RULE_NAME,
    CONF_RULE_SEVERITY_MODE,
    CONF_RULE_DIRECTION,
    CONF_RULE_LEVELS,
    CONF_RULE_TEXT_CASE_SENSITIVE,
    CONF_RULE_TEXT_MATCH,
    CONF_RULE_TEXT_TRIM,
    CONF_RULE_NOTIFY_EMAIL,
    CONF_RULE_NOTIFY_MOBILE,
    CONF_RULE_THRESHOLD,
    CONF_RULE_THRESHOLD_HIGH,
    CONF_RULE_THRESHOLD_LOW,
    CONF_MOBILE_NOTIFY_ENABLED,
    CONF_MOBILE_NOTIFY_TARGETS_NOTIFY,
    CONF_MOBILE_NOTIFY_TARGETS_LIMIT,
    CONF_MOBILE_NOTIFY_TARGETS_SHUTDOWN,
    CONF_MOBILE_NOTIFY_URGENT_NOTIFY,
    CONF_MOBILE_NOTIFY_URGENT_LIMIT,
    CONF_MOBILE_NOTIFY_URGENT_SHUTDOWN,
    CONF_RULE_NOTIFY_THRESHOLD,
    CONF_RULE_NOTIFY_DURATION,
    CONF_RULE_LIMIT_THRESHOLD,
    CONF_RULE_LIMIT_DURATION,
    CONF_RULE_SHUTDOWN_THRESHOLD,
    CONF_RULE_SHUTDOWN_DURATION,
    CONF_RULE_UNKNOWN_HANDLING,
    CONF_RULE_THRESHOLDS,
    CONF_IMPORT_MODE,
    CONF_IMPORT_RULES_JSON,
    IMPORT_MODE_MERGE,
    IMPORT_MODE_OPTIONS,
    IMPORT_MODE_REPLACE,
    DATA_TYPE_BINARY,
    DATA_TYPE_NUMERIC,
    DATA_TYPE_OPTIONS,
    DATA_TYPE_TEXT,
    DEFAULT_RULE_DURATION,
    DEFAULT_RULE_INTERVAL,
    DEFAULT_RULE_LATCHED,
    DEFAULT_RULE_LEVEL,
    DEFAULT_RULE_UNKNOWN_HANDLING,
    DEFAULT_RULE_NOTIFY_EMAIL,
    DEFAULT_RULE_NOTIFY_MOBILE,
    DEFAULT_TEXT_CASE_SENSITIVE,
    DEFAULT_TEXT_TRIM,
    DEFAULT_MOBILE_NOTIFY_ENABLED,
    DEFAULT_MOBILE_NOTIFY_URGENT_NOTIFY,
    DEFAULT_MOBILE_NOTIFY_URGENT_LIMIT,
    DEFAULT_MOBILE_NOTIFY_URGENT_SHUTDOWN,
    DEFAULT_EMAIL_LEVELS,
    DEFAULT_REPORT_RETENTION_MAX_AGE_DAYS,
    DEFAULT_REPORT_RETENTION_MAX_FILES,
    DIRECTION_OPTIONS,
    DIRECTION_HIGHER_IS_WORSE,
    DIRECTION_LOWER_IS_WORSE,
    LEVEL_OPTIONS,
    LEVEL_ORDER,
    NAME,
    NUMERIC_AGGREGATES,
    BINARY_AGGREGATES,
    TEXT_AGGREGATES,
    NUMERIC_CONDITIONS,
    BINARY_STATE_CONDITIONS,
    TEXT_CONDITIONS,
    REPORT_MODE_BASIC,
    REPORT_MODE_EXTENDED,
    SEVERITY_MODE_OPTIONS,
    SEVERITY_MODE_SEMAFOR,
    SEVERITY_MODE_SIMPLE,
    UNKNOWN_HANDLING_OPTIONS,
    COND_BETWEEN,
    AGGREGATE_COUNT,
    DOMAIN,
)

_SECTION_PREFIX = "section_"
_SECTION_SELECTOR = getattr(selector, "SectionSelector", None)
_SECTION_SELECTOR_CONFIG = getattr(selector, "SectionSelectorConfig", None)
_CONSTANT_SELECTOR = getattr(selector, "ConstantSelector", None)
_CONSTANT_SELECTOR_CONFIG = getattr(selector, "ConstantSelectorConfig", None)


def _section_label(text: str) -> dict[vol.Optional, Any]:
    if not _SECTION_SELECTOR or not _SECTION_SELECTOR_CONFIG:
        if not _CONSTANT_SELECTOR or not _CONSTANT_SELECTOR_CONFIG:
            return {}
        key = f"{_SECTION_PREFIX}{slugify(text)}"
        return {
            vol.Optional(key, default=""): _CONSTANT_SELECTOR(
                _CONSTANT_SELECTOR_CONFIG(label=text, value="")
            )
        }
    try:
        key = f"{_SECTION_PREFIX}{slugify(text)}"
        return {
            vol.Optional(key): _SECTION_SELECTOR(
                _SECTION_SELECTOR_CONFIG(label=text)
            )
        }
    except Exception:
        return {}


class EmergencyStopConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Emergency Stop."""

    VERSION = 3

    def __init__(self) -> None:
        self._global_config: dict[str, Any] = {}
        self._rules: list[dict[str, Any]] = []
        self._rule_context: dict[str, Any] = {}
        self._edit_index: int | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle global settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = _clean_email_config(user_input)
            errors = _validate_globals(user_input)
            if not errors:
                self._global_config = user_input
                self._rules = []
                return await self.async_step_rule()

        schema = _global_schema(self.hass)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_rule(self, user_input: dict[str, Any] | None = None):
        """Define rule name and data type."""
        errors: dict[str, str] = {}
        if user_input is not None:
            rule_name = _normalize_optional_str(user_input.get(CONF_RULE_NAME))
            data_type = user_input.get(CONF_RULE_DATA_TYPE)
            if not rule_name:
                errors[CONF_RULE_NAME] = "required"
            if data_type not in DATA_TYPE_OPTIONS:
                errors[CONF_RULE_DATA_TYPE] = "invalid_data_type"
            if not errors:
                if self._rule_context:
                    self._rule_context[CONF_RULE_NAME] = rule_name
                    self._rule_context[CONF_RULE_DATA_TYPE] = data_type
                else:
                    self._rule_context = {
                        CONF_RULE_NAME: rule_name,
                        CONF_RULE_DATA_TYPE: data_type,
                    }
                if data_type == DATA_TYPE_NUMERIC:
                    return await self.async_step_rule_numeric()
                if data_type == DATA_TYPE_BINARY:
                    return await self.async_step_rule_binary()
                return await self.async_step_rule_text()

        schema = _rule_schema(self._rule_context)
        return self.async_show_form(step_id="rule", data_schema=schema, errors=errors)

    async def async_step_rule_numeric(self, user_input: dict[str, Any] | None = None):
        """Select numeric rule mode and inputs."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors.update(_validate_entities(user_input))
            aggregate = user_input.get(CONF_RULE_AGGREGATE)
            if aggregate not in NUMERIC_AGGREGATES:
                errors[CONF_RULE_AGGREGATE] = "invalid_aggregate"
            severity_mode = user_input.get(CONF_RULE_SEVERITY_MODE, SEVERITY_MODE_SIMPLE)
            if severity_mode not in SEVERITY_MODE_OPTIONS:
                errors[CONF_RULE_SEVERITY_MODE] = "invalid_severity_mode"
            if not errors:
                self._rule_context.update(
                    {
                        CONF_RULE_ENTITIES: user_input.get(CONF_RULE_ENTITIES, []),
                        CONF_RULE_AGGREGATE: user_input.get(CONF_RULE_AGGREGATE),
                        CONF_RULE_SEVERITY_MODE: severity_mode,
                    }
                )
                if severity_mode == SEVERITY_MODE_SEMAFOR:
                    return await self.async_step_rule_numeric_semafor()
                return await self.async_step_rule_numeric_simple()

        schema = _numeric_rule_select_schema(self._rule_context)
        return self.async_show_form(
            step_id="rule_numeric",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rule_numeric_simple(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_rule_common(user_input)
            merged_input = {**self._rule_context, **user_input}
            errors.update(_validate_numeric_rule(merged_input))
            if not errors:
                merged = dict(self._rule_context)
                merged.update(user_input)
                rule = _build_rule_config(
                    merged,
                    {},
                    self._rules,
                )
                self._rules.append(rule)
                return await self.async_step_add_rule()

        schema = _numeric_rule_simple_schema(self._rule_context)
        return self.async_show_form(
            step_id="rule_numeric_simple",
            data_schema=schema,
            errors=errors,
        )
    async def async_step_rule_numeric_semafor(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_semafor_rule(user_input, numeric=True)
            if not errors:
                merged = dict(self._rule_context)
                merged.update(user_input)
                merged[CONF_RULE_SEVERITY_MODE] = SEVERITY_MODE_SEMAFOR
                rule = _build_rule_config(merged, {}, self._rules)
                self._rules.append(rule)
                return await self.async_step_add_rule()

        schema = _semafor_rule_schema(numeric=True, defaults=self._rule_context)
        return self.async_show_form(
            step_id="rule_numeric_semafor",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rule_binary(self, user_input: dict[str, Any] | None = None):
        """Configure a binary rule (select aggregation first)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors.update(_validate_entities(user_input))
            aggregate = user_input.get(CONF_RULE_AGGREGATE)
            if aggregate not in BINARY_AGGREGATES:
                errors[CONF_RULE_AGGREGATE] = "invalid_aggregate"
            if not errors:
                self._rule_context.update(
                    {
                        CONF_RULE_ENTITIES: user_input.get(CONF_RULE_ENTITIES, []),
                        CONF_RULE_AGGREGATE: aggregate,
                    }
                )
                if aggregate == AGGREGATE_COUNT:
                    return await self.async_step_rule_binary_count()
                return await self.async_step_rule_binary_state()

        schema = _binary_rule_select_schema(self._rule_context)
        return self.async_show_form(
            step_id="rule_binary",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rule_binary_state(
        self, user_input: dict[str, Any] | None = None
    ):
        """Configure binary any/all rule."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_rule_common(user_input)
            condition = user_input.get(CONF_RULE_CONDITION)
            if condition not in BINARY_STATE_CONDITIONS:
                errors[CONF_RULE_CONDITION] = "invalid_condition"
            if not errors:
                merged = dict(self._rule_context)
                merged.update(user_input)
                merged[CONF_RULE_THRESHOLDS] = []
                rule = _build_rule_config(merged, {}, self._rules)
                self._rules.append(rule)
                return await self.async_step_add_rule()

        schema = _binary_rule_state_schema(self._rule_context)
        return self.async_show_form(
            step_id="rule_binary_state",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rule_binary_count(
        self, user_input: dict[str, Any] | None = None
    ):
        """Configure binary count rule."""
        errors: dict[str, str] = {}
        if user_input is not None:
            severity_mode = user_input.get(CONF_RULE_SEVERITY_MODE, SEVERITY_MODE_SIMPLE)
            if severity_mode not in SEVERITY_MODE_OPTIONS:
                errors[CONF_RULE_SEVERITY_MODE] = "invalid_severity_mode"
            if not errors:
                self._rule_context[CONF_RULE_SEVERITY_MODE] = severity_mode
                if severity_mode == SEVERITY_MODE_SEMAFOR:
                    return await self.async_step_rule_binary_count_semafor()
                return await self.async_step_rule_binary_count_simple()

        schema = _binary_rule_count_select_schema(self._rule_context)
        return self.async_show_form(
            step_id="rule_binary_count",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rule_binary_count_simple(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_rule_common(user_input)
            errors.update(_validate_numeric_thresholds(user_input))
            condition = user_input.get(CONF_RULE_CONDITION)
            if condition not in NUMERIC_CONDITIONS:
                errors[CONF_RULE_CONDITION] = "invalid_condition"
            if not errors:
                merged = dict(self._rule_context)
                merged.update(user_input)
                merged[CONF_RULE_THRESHOLDS] = _extract_thresholds(user_input)
                rule = _build_rule_config(merged, {}, self._rules)
                self._rules.append(rule)
                return await self.async_step_add_rule()

        schema = _binary_rule_count_simple_schema(self._rule_context)
        return self.async_show_form(
            step_id="rule_binary_count_simple",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rule_binary_count_semafor(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_semafor_rule(user_input, numeric=False)
            if not errors:
                merged = dict(self._rule_context)
                merged.update(user_input)
                merged[CONF_RULE_SEVERITY_MODE] = SEVERITY_MODE_SEMAFOR
                rule = _build_rule_config(merged, {}, self._rules)
                self._rules.append(rule)
                return await self.async_step_add_rule()

        schema = _semafor_rule_schema(numeric=False, defaults=self._rule_context)
        return self.async_show_form(
            step_id="rule_binary_count_semafor",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rule_text(self, user_input: dict[str, Any] | None = None):
        """Configure a text rule."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_rule_common(user_input)
            errors.update(_validate_entities(user_input))
            condition = user_input.get(CONF_RULE_CONDITION)
            if condition not in TEXT_CONDITIONS:
                errors[CONF_RULE_CONDITION] = "invalid_condition"
            raw_match = user_input.get(CONF_RULE_TEXT_MATCH)
            text_trim = bool(user_input.get(CONF_RULE_TEXT_TRIM, DEFAULT_TEXT_TRIM))
            if raw_match is None:
                errors[CONF_RULE_TEXT_MATCH] = "required"
                match = None
            else:
                match_value = str(raw_match)
                normalized = match_value.strip() if text_trim else match_value
                if not normalized:
                    errors[CONF_RULE_TEXT_MATCH] = "required"
                    match = None
                else:
                    match = normalized if text_trim else match_value
            if not errors:
                merged = dict(user_input)
                merged[CONF_RULE_TEXT_MATCH] = match
                merged[CONF_RULE_SEVERITY_MODE] = SEVERITY_MODE_SIMPLE
                rule = _build_rule_config(self._rule_context, merged, self._rules)
                self._rules.append(rule)
                return await self.async_step_add_rule()

        schema = _text_rule_schema(self._rule_context)
        return self.async_show_form(
            step_id="rule_text",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_add_rule(self, user_input: dict[str, Any] | None = None):
        """Ask whether to add another rule."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get("add_another"):
                return await self.async_step_rule()
            if not self._rules:
                errors["base"] = "rules_required"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                data = {**self._global_config, CONF_RULES: list(self._rules)}
                return self.async_create_entry(title=NAME, data=data)

        schema = vol.Schema(
            {
                vol.Required("add_another", default=True): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="add_rule",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]):
        """Handle import flow."""
        return await self.async_step_user(user_input)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return EmergencyStopOptionsFlow(config_entry)


class EmergencyStopOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Emergency Stop."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry
        self._global_config: dict[str, Any] = {}
        self._rules: list[dict[str, Any]] = []
        self._rule_context: dict[str, Any] = {}
        self._edit_index: int | None = None
        self._rules_action: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        current = {**self._entry.data, **self._entry.options}

        if user_input is not None:
            user_input = _clean_email_config(user_input)
            errors = _validate_globals(user_input)
            if not errors:
                self._global_config = user_input
                self._rules = [
                    dict(rule) for rule in current.get(CONF_RULES, []) or []
                ]
                return await self.async_step_rules_action()

        schema = _global_schema(self.hass, current)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_rules_action(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        if user_input is not None:
            action = user_input.get("rules_action")
            if action == "add":
                self._edit_index = None
                self._rule_context = {}
                return await self.async_step_rule()
            if action in ("edit", "delete"):
                if not self._rules:
                    errors["base"] = "rules_required"
                else:
                    self._rules_action = action
                    return await self.async_step_rule_select()
            if action == "import":
                return await self.async_step_rule_import()
            if action == "export":
                return await self.async_step_rule_export()
            if action == "finish":
                data = {**self._global_config, CONF_RULES: list(self._rules)}
                return self.async_create_entry(title=NAME, data=data)

        schema = vol.Schema(
            {
                vol.Required("rules_action"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=_rules_action_options())
                )
            }
        )
        return self.async_show_form(
            step_id="rules_action",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rule_export(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        if user_input is not None:
            return await self.async_step_rules_action()

        export_path = None
        try:
            coordinator = self.hass.data[DOMAIN][self._entry.entry_id]
            export_path = await coordinator.async_export_rules()
        except Exception:
            errors["base"] = "export_failed"

        schema = vol.Schema({})
        return self.async_show_form(
            step_id="rule_export",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "path": str(export_path) if export_path else "",
            },
        )

    async def async_step_rule_select(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            rule_id = user_input.get("rule_id")
            index = _rule_index_for_id(self._rules, rule_id)
            if index is None:
                errors["rule_id"] = "invalid_rule"
            elif self._rules_action == "delete":
                self._rules.pop(index)
                self._rules_action = None
                return await self.async_step_rules_action()
            elif self._rules_action == "edit":
                self._edit_index = index
                self._rule_context = _seed_rule_context(self._rules[index])
                self._rules_action = None
                return await self.async_step_rule()
            else:
                errors["rule_id"] = "invalid_rule"

        schema = _rule_select_schema(self._rules)
        return self.async_show_form(
            step_id="rule_select",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rule_import(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        if user_input is not None:
            mode = user_input.get(CONF_IMPORT_MODE, IMPORT_MODE_MERGE)
            payload = user_input.get(CONF_IMPORT_RULES_JSON)
            rules, error = _parse_import_payload(payload)
            if error:
                errors["base"] = error
            elif mode not in IMPORT_MODE_OPTIONS:
                errors[CONF_IMPORT_MODE] = "invalid_import_mode"
            else:
                normalized, error = _normalize_import_rules(rules)
                if error:
                    errors["base"] = error
                else:
                    conflicts = _find_rule_id_conflicts(self._rules, normalized)
                    if conflicts and mode == IMPORT_MODE_MERGE:
                        errors["base"] = "import_conflict"
                    else:
                        if mode == IMPORT_MODE_REPLACE:
                            self._rules = normalized
                        else:
                            self._rules.extend(normalized)
                        return await self.async_step_rules_action()

        schema = _rule_import_schema()
        return self.async_show_form(
            step_id="rule_import",
            data_schema=schema,
            errors=errors,
        )
    async def async_step_rule(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            rule_name = _normalize_optional_str(user_input.get(CONF_RULE_NAME))
            data_type = user_input.get(CONF_RULE_DATA_TYPE)
            if not rule_name:
                errors[CONF_RULE_NAME] = "required"
            if data_type not in DATA_TYPE_OPTIONS:
                errors[CONF_RULE_DATA_TYPE] = "invalid_data_type"
            if not errors:
                if self._rule_context:
                    self._rule_context[CONF_RULE_NAME] = rule_name
                    self._rule_context[CONF_RULE_DATA_TYPE] = data_type
                else:
                    self._rule_context = {
                        CONF_RULE_NAME: rule_name,
                        CONF_RULE_DATA_TYPE: data_type,
                    }
                if data_type == DATA_TYPE_NUMERIC:
                    return await self.async_step_rule_numeric()
                if data_type == DATA_TYPE_BINARY:
                    return await self.async_step_rule_binary()
                return await self.async_step_rule_text()

        schema = _rule_schema(self._rule_context)
        return self.async_show_form(step_id="rule", data_schema=schema, errors=errors)

    async def async_step_rule_numeric(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            errors.update(_validate_entities(user_input))
            aggregate = user_input.get(CONF_RULE_AGGREGATE)
            if aggregate not in NUMERIC_AGGREGATES:
                errors[CONF_RULE_AGGREGATE] = "invalid_aggregate"
            severity_mode = user_input.get(CONF_RULE_SEVERITY_MODE, SEVERITY_MODE_SIMPLE)
            if severity_mode not in SEVERITY_MODE_OPTIONS:
                errors[CONF_RULE_SEVERITY_MODE] = "invalid_severity_mode"
            if not errors:
                self._rule_context.update(
                    {
                        CONF_RULE_ENTITIES: user_input.get(CONF_RULE_ENTITIES, []),
                        CONF_RULE_AGGREGATE: user_input.get(CONF_RULE_AGGREGATE),
                        CONF_RULE_SEVERITY_MODE: severity_mode,
                    }
                )
                if severity_mode == SEVERITY_MODE_SEMAFOR:
                    return await self.async_step_rule_numeric_semafor()
                return await self.async_step_rule_numeric_simple()

        schema = _numeric_rule_select_schema(self._rule_context)
        return self.async_show_form(
            step_id="rule_numeric",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rule_numeric_simple(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_rule_common(user_input)
            merged_input = {**self._rule_context, **user_input}
            errors.update(_validate_numeric_rule(merged_input))
            if not errors:
                merged = dict(self._rule_context)
                merged.update(user_input)
                existing_rules = _rules_excluding_index(self._rules, self._edit_index)
                rule = _build_rule_config(merged, {}, existing_rules)
                _store_rule(self._rules, rule, self._edit_index)
                if self._edit_index is not None:
                    self._edit_index = None
                    return await self.async_step_rules_action()
                return await self.async_step_add_rule()

        schema = _numeric_rule_simple_schema(self._rule_context)
        return self.async_show_form(
            step_id="rule_numeric_simple",
            data_schema=schema,
            errors=errors,
        )
    async def async_step_rule_numeric_semafor(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_semafor_rule(user_input, numeric=True)
            if not errors:
                merged = dict(self._rule_context)
                merged.update(user_input)
                merged[CONF_RULE_SEVERITY_MODE] = SEVERITY_MODE_SEMAFOR
                existing_rules = _rules_excluding_index(self._rules, self._edit_index)
                rule = _build_rule_config(merged, {}, existing_rules)
                _store_rule(self._rules, rule, self._edit_index)
                if self._edit_index is not None:
                    self._edit_index = None
                    return await self.async_step_rules_action()
                return await self.async_step_add_rule()

        schema = _semafor_rule_schema(numeric=True, defaults=self._rule_context)
        return self.async_show_form(
            step_id="rule_numeric_semafor",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rule_binary(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            errors.update(_validate_entities(user_input))
            aggregate = user_input.get(CONF_RULE_AGGREGATE)
            if aggregate not in BINARY_AGGREGATES:
                errors[CONF_RULE_AGGREGATE] = "invalid_aggregate"
            if not errors:
                self._rule_context.update(
                    {
                        CONF_RULE_ENTITIES: user_input.get(CONF_RULE_ENTITIES, []),
                        CONF_RULE_AGGREGATE: aggregate,
                    }
                )
                if aggregate == AGGREGATE_COUNT:
                    return await self.async_step_rule_binary_count()
                return await self.async_step_rule_binary_state()

        schema = _binary_rule_select_schema(self._rule_context)
        return self.async_show_form(
            step_id="rule_binary",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rule_binary_state(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_rule_common(user_input)
            condition = user_input.get(CONF_RULE_CONDITION)
            if condition not in BINARY_STATE_CONDITIONS:
                errors[CONF_RULE_CONDITION] = "invalid_condition"
            if not errors:
                merged = dict(self._rule_context)
                merged.update(user_input)
                merged[CONF_RULE_THRESHOLDS] = []
                existing_rules = _rules_excluding_index(self._rules, self._edit_index)
                rule = _build_rule_config(merged, {}, existing_rules)
                _store_rule(self._rules, rule, self._edit_index)
                if self._edit_index is not None:
                    self._edit_index = None
                    return await self.async_step_rules_action()
                return await self.async_step_add_rule()

        schema = _binary_rule_state_schema(self._rule_context)
        return self.async_show_form(
            step_id="rule_binary_state",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rule_binary_count(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        if user_input is not None:
            severity_mode = user_input.get(CONF_RULE_SEVERITY_MODE, SEVERITY_MODE_SIMPLE)
            if severity_mode not in SEVERITY_MODE_OPTIONS:
                errors[CONF_RULE_SEVERITY_MODE] = "invalid_severity_mode"
            if not errors:
                self._rule_context[CONF_RULE_SEVERITY_MODE] = severity_mode
                if severity_mode == SEVERITY_MODE_SEMAFOR:
                    return await self.async_step_rule_binary_count_semafor()
                return await self.async_step_rule_binary_count_simple()

        schema = _binary_rule_count_select_schema(self._rule_context)
        return self.async_show_form(
            step_id="rule_binary_count",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rule_binary_count_simple(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_rule_common(user_input)
            errors.update(_validate_numeric_thresholds(user_input))
            condition = user_input.get(CONF_RULE_CONDITION)
            if condition not in NUMERIC_CONDITIONS:
                errors[CONF_RULE_CONDITION] = "invalid_condition"
            if not errors:
                merged = dict(self._rule_context)
                merged.update(user_input)
                merged[CONF_RULE_THRESHOLDS] = _extract_thresholds(user_input)
                existing_rules = _rules_excluding_index(self._rules, self._edit_index)
                rule = _build_rule_config(merged, {}, existing_rules)
                _store_rule(self._rules, rule, self._edit_index)
                if self._edit_index is not None:
                    self._edit_index = None
                    return await self.async_step_rules_action()
                return await self.async_step_add_rule()

        schema = _binary_rule_count_simple_schema(self._rule_context)
        return self.async_show_form(
            step_id="rule_binary_count_simple",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rule_binary_count_semafor(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_semafor_rule(user_input, numeric=False)
            if not errors:
                merged = dict(self._rule_context)
                merged.update(user_input)
                merged[CONF_RULE_SEVERITY_MODE] = SEVERITY_MODE_SEMAFOR
                existing_rules = _rules_excluding_index(self._rules, self._edit_index)
                rule = _build_rule_config(merged, {}, existing_rules)
                _store_rule(self._rules, rule, self._edit_index)
                if self._edit_index is not None:
                    self._edit_index = None
                    return await self.async_step_rules_action()
                return await self.async_step_add_rule()

        schema = _semafor_rule_schema(numeric=False, defaults=self._rule_context)
        return self.async_show_form(
            step_id="rule_binary_count_semafor",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rule_text(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_rule_common(user_input)
            errors.update(_validate_entities(user_input))
            condition = user_input.get(CONF_RULE_CONDITION)
            if condition not in TEXT_CONDITIONS:
                errors[CONF_RULE_CONDITION] = "invalid_condition"
            raw_match = user_input.get(CONF_RULE_TEXT_MATCH)
            text_trim = bool(user_input.get(CONF_RULE_TEXT_TRIM, DEFAULT_TEXT_TRIM))
            if raw_match is None:
                errors[CONF_RULE_TEXT_MATCH] = "required"
                match = None
            else:
                match_value = str(raw_match)
                normalized = match_value.strip() if text_trim else match_value
                if not normalized:
                    errors[CONF_RULE_TEXT_MATCH] = "required"
                    match = None
                else:
                    match = normalized if text_trim else match_value
            if not errors:
                merged = dict(user_input)
                merged[CONF_RULE_TEXT_MATCH] = match
                merged[CONF_RULE_SEVERITY_MODE] = SEVERITY_MODE_SIMPLE
                existing_rules = _rules_excluding_index(self._rules, self._edit_index)
                rule = _build_rule_config(self._rule_context, merged, existing_rules)
                _store_rule(self._rules, rule, self._edit_index)
                if self._edit_index is not None:
                    self._edit_index = None
                    return await self.async_step_rules_action()
                return await self.async_step_add_rule()

        schema = _text_rule_schema(self._rule_context)
        return self.async_show_form(
            step_id="rule_text",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_add_rule(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get("add_another"):
                self._rule_context = {}
                self._edit_index = None
                return await self.async_step_rule()
            if not self._rules:
                errors["base"] = "rules_required"
            else:
                data = {**self._global_config, CONF_RULES: list(self._rules)}
                return self.async_create_entry(title=NAME, data=data)

        schema = vol.Schema(
            {
                vol.Required("add_another", default=True): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="add_rule",
            data_schema=schema,
            errors=errors,
        )


def _global_schema(
    hass: HomeAssistant, defaults: dict[str, Any] | None = None
) -> vol.Schema:
    defaults = defaults or {}
    domain_options = _domain_options(hass)
    notify_options = _notify_service_options(hass)
    report_entity_selector = selector.EntitySelector(
        selector.EntitySelectorConfig(multiple=True)
    )
    schema_fields: dict[Any, Any] = {}
    schema_fields.update(_section_label("Report"))
    schema_fields.update(
        {
            vol.Optional(
                CONF_REPORT_MODE,
                default=defaults.get(CONF_REPORT_MODE, REPORT_MODE_BASIC),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[REPORT_MODE_BASIC, REPORT_MODE_EXTENDED]
                )
            ),
            vol.Optional(
                CONF_REPORT_DOMAINS,
                default=defaults.get(CONF_REPORT_DOMAINS, []),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=domain_options,
                    multiple=True,
                )
            ),
            vol.Optional(
                CONF_REPORT_ENTITY_IDS,
                default=defaults.get(CONF_REPORT_ENTITY_IDS, []),
            ): report_entity_selector,
            vol.Optional(
                CONF_REPORT_RETENTION_MAX_FILES,
                default=defaults.get(
                    CONF_REPORT_RETENTION_MAX_FILES,
                    DEFAULT_REPORT_RETENTION_MAX_FILES,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX, min=0, step=1
                )
            ),
            vol.Optional(
                CONF_REPORT_RETENTION_MAX_AGE_DAYS,
                default=defaults.get(
                    CONF_REPORT_RETENTION_MAX_AGE_DAYS,
                    DEFAULT_REPORT_RETENTION_MAX_AGE_DAYS,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX, min=0, step=1
                )
            ),
        }
    )
    schema_fields.update(_section_label("Email provider (Brevo)"))
    schema_fields.update(
        {
            vol.Optional(
                CONF_BREVO_API_KEY,
                default=defaults.get(CONF_BREVO_API_KEY, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Optional(
                CONF_BREVO_SENDER,
                default=defaults.get(CONF_BREVO_SENDER, ""),
            ): selector.TextSelector(),
            vol.Optional(
                CONF_BREVO_RECIPIENT,
                default=defaults.get(CONF_BREVO_RECIPIENT, ""),
            ): selector.TextSelector(),
        }
    )
    schema_fields.update(_section_label("Email routing by level"))
    schema_fields.update(
        {
            vol.Optional(
                CONF_EMAIL_LEVELS,
                default=defaults.get(CONF_EMAIL_LEVELS, DEFAULT_EMAIL_LEVELS),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_level_options(),
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Optional(
                CONF_BREVO_RECIPIENT_NOTIFY,
                default=defaults.get(CONF_BREVO_RECIPIENT_NOTIFY, ""),
            ): selector.TextSelector(),
            vol.Optional(
                CONF_BREVO_RECIPIENT_LIMIT,
                default=defaults.get(CONF_BREVO_RECIPIENT_LIMIT, ""),
            ): selector.TextSelector(),
            vol.Optional(
                CONF_BREVO_RECIPIENT_SHUTDOWN,
                default=defaults.get(CONF_BREVO_RECIPIENT_SHUTDOWN, ""),
            ): selector.TextSelector(),
        }
    )
    schema_fields.update(_section_label("Mobile notifications"))
    schema_fields.update(
        {
            vol.Optional(
                CONF_MOBILE_NOTIFY_ENABLED,
                default=defaults.get(
                    CONF_MOBILE_NOTIFY_ENABLED, DEFAULT_MOBILE_NOTIFY_ENABLED
                ),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_MOBILE_NOTIFY_TARGETS_NOTIFY,
                default=defaults.get(CONF_MOBILE_NOTIFY_TARGETS_NOTIFY, []),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=notify_options, multiple=True)
            ),
            vol.Optional(
                CONF_MOBILE_NOTIFY_TARGETS_LIMIT,
                default=defaults.get(CONF_MOBILE_NOTIFY_TARGETS_LIMIT, []),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=notify_options, multiple=True)
            ),
            vol.Optional(
                CONF_MOBILE_NOTIFY_TARGETS_SHUTDOWN,
                default=defaults.get(CONF_MOBILE_NOTIFY_TARGETS_SHUTDOWN, []),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=notify_options, multiple=True)
            ),
            vol.Optional(
                CONF_MOBILE_NOTIFY_URGENT_NOTIFY,
                default=defaults.get(
                    CONF_MOBILE_NOTIFY_URGENT_NOTIFY,
                    DEFAULT_MOBILE_NOTIFY_URGENT_NOTIFY,
                ),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_MOBILE_NOTIFY_URGENT_LIMIT,
                default=defaults.get(
                    CONF_MOBILE_NOTIFY_URGENT_LIMIT,
                    DEFAULT_MOBILE_NOTIFY_URGENT_LIMIT,
                ),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_MOBILE_NOTIFY_URGENT_SHUTDOWN,
                default=defaults.get(
                    CONF_MOBILE_NOTIFY_URGENT_SHUTDOWN,
                    DEFAULT_MOBILE_NOTIFY_URGENT_SHUTDOWN,
                ),
            ): selector.BooleanSelector(),
        }
    )
    return vol.Schema(schema_fields)


def _rule_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    return vol.Schema(
        {
            _required_key(CONF_RULE_NAME, defaults): selector.TextSelector(),
            _required_key(CONF_RULE_DATA_TYPE, defaults): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_data_type_options())
            ),
        }
    )


def _rule_notification_schema(
    defaults: dict[str, Any] | None = None,
) -> dict[vol.Optional, Any]:
    return {
        _required_key(
            CONF_RULE_NOTIFY_EMAIL,
            defaults,
            fallback=DEFAULT_RULE_NOTIFY_EMAIL,
        ): selector.BooleanSelector(),
        _required_key(
            CONF_RULE_NOTIFY_MOBILE,
            defaults,
            fallback=DEFAULT_RULE_NOTIFY_MOBILE,
        ): selector.BooleanSelector(),
    }


def _numeric_rule_select_schema(
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    entity_selector = selector.EntitySelector(
        selector.EntitySelectorConfig(multiple=True)
    )
    return vol.Schema(
        {
            _required_key(CONF_RULE_ENTITIES, defaults): entity_selector,
            _required_key(CONF_RULE_AGGREGATE, defaults): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_aggregate_options(NUMERIC_AGGREGATES))
            ),
            _required_key(
                CONF_RULE_SEVERITY_MODE,
                defaults,
                fallback=SEVERITY_MODE_SIMPLE,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_severity_mode_options())
            ),
        }
    )


def _numeric_rule_simple_schema(
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    return vol.Schema(
        {
            _required_key(CONF_RULE_CONDITION, defaults): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_numeric_condition_options())
            ),
            _optional_key(CONF_RULE_THRESHOLD, defaults): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX, step=0.001
                )
            ),
            _optional_key(CONF_RULE_THRESHOLD_LOW, defaults): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX, step=0.001
                )
            ),
            _optional_key(CONF_RULE_THRESHOLD_HIGH, defaults): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX, step=0.001
                )
            ),
            _required_key(
                CONF_RULE_DURATION,
                defaults,
                fallback=DEFAULT_RULE_DURATION,
            ): vol.Coerce(int),
            _required_key(
                CONF_RULE_INTERVAL,
                defaults,
                fallback=DEFAULT_RULE_INTERVAL,
            ): vol.Coerce(int),
            _required_key(
                CONF_RULE_LEVEL,
                defaults,
                fallback=DEFAULT_RULE_LEVEL,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_level_options())
            ),
            _required_key(
                CONF_RULE_LATCHED,
                defaults,
                fallback=DEFAULT_RULE_LATCHED,
            ): selector.BooleanSelector(),
            _required_key(
                CONF_RULE_UNKNOWN_HANDLING,
                defaults,
                fallback=DEFAULT_RULE_UNKNOWN_HANDLING,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_unknown_options())
            ),
            **_rule_notification_schema(defaults),
        }
    )


def _binary_rule_select_schema(
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    entity_selector = selector.EntitySelector(
        selector.EntitySelectorConfig(multiple=True)
    )
    return vol.Schema(
        {
            _required_key(CONF_RULE_ENTITIES, defaults): entity_selector,
            _required_key(CONF_RULE_AGGREGATE, defaults): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_aggregate_options(BINARY_AGGREGATES))
            ),
        }
    )


def _binary_rule_state_schema(
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    return vol.Schema(
        {
            _required_key(CONF_RULE_CONDITION, defaults): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_binary_state_condition_options())
            ),
            _required_key(
                CONF_RULE_DURATION,
                defaults,
                fallback=DEFAULT_RULE_DURATION,
            ): vol.Coerce(int),
            _required_key(
                CONF_RULE_INTERVAL,
                defaults,
                fallback=DEFAULT_RULE_INTERVAL,
            ): vol.Coerce(int),
            _required_key(
                CONF_RULE_LEVEL,
                defaults,
                fallback=DEFAULT_RULE_LEVEL,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_level_options())
            ),
            _required_key(
                CONF_RULE_LATCHED,
                defaults,
                fallback=DEFAULT_RULE_LATCHED,
            ): selector.BooleanSelector(),
            _required_key(
                CONF_RULE_UNKNOWN_HANDLING,
                defaults,
                fallback=DEFAULT_RULE_UNKNOWN_HANDLING,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_unknown_options())
            ),
            **_rule_notification_schema(defaults),
        }
    )


def _binary_rule_count_select_schema(
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    return vol.Schema(
        {
            _required_key(
                CONF_RULE_SEVERITY_MODE,
                defaults,
                fallback=SEVERITY_MODE_SIMPLE,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_severity_mode_options())
            ),
        }
    )


def _binary_rule_count_simple_schema(
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    return vol.Schema(
        {
            _required_key(CONF_RULE_CONDITION, defaults): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_numeric_condition_options())
            ),
            _optional_key(CONF_RULE_THRESHOLD, defaults): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX, step=1
                )
            ),
            _optional_key(CONF_RULE_THRESHOLD_LOW, defaults): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX, step=1
                )
            ),
            _optional_key(CONF_RULE_THRESHOLD_HIGH, defaults): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX, step=1
                )
            ),
            _required_key(
                CONF_RULE_DURATION,
                defaults,
                fallback=DEFAULT_RULE_DURATION,
            ): vol.Coerce(int),
            _required_key(
                CONF_RULE_INTERVAL,
                defaults,
                fallback=DEFAULT_RULE_INTERVAL,
            ): vol.Coerce(int),
            _required_key(
                CONF_RULE_LEVEL,
                defaults,
                fallback=DEFAULT_RULE_LEVEL,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_level_options())
            ),
            _required_key(
                CONF_RULE_LATCHED,
                defaults,
                fallback=DEFAULT_RULE_LATCHED,
            ): selector.BooleanSelector(),
            _required_key(
                CONF_RULE_UNKNOWN_HANDLING,
                defaults,
                fallback=DEFAULT_RULE_UNKNOWN_HANDLING,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_unknown_options())
            ),
            **_rule_notification_schema(defaults),
        }
    )


def _semafor_rule_schema(
    numeric: bool, defaults: dict[str, Any] | None = None
) -> vol.Schema:
    step = 0.001 if numeric else 1
    return vol.Schema(
        {
            _required_key(CONF_RULE_DIRECTION, defaults): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_direction_options())
            ),
            _optional_key(CONF_RULE_NOTIFY_THRESHOLD, defaults): selector.NumberSelector(
                selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX, step=step)
            ),
            _optional_key(CONF_RULE_NOTIFY_DURATION, defaults): vol.Coerce(int),
            _optional_key(CONF_RULE_LIMIT_THRESHOLD, defaults): selector.NumberSelector(
                selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX, step=step)
            ),
            _optional_key(CONF_RULE_LIMIT_DURATION, defaults): vol.Coerce(int),
            _optional_key(CONF_RULE_SHUTDOWN_THRESHOLD, defaults): selector.NumberSelector(
                selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX, step=step)
            ),
            _optional_key(CONF_RULE_SHUTDOWN_DURATION, defaults): vol.Coerce(int),
            _required_key(
                CONF_RULE_INTERVAL,
                defaults,
                fallback=DEFAULT_RULE_INTERVAL,
            ): vol.Coerce(int),
            _required_key(
                CONF_RULE_LATCHED,
                defaults,
                fallback=DEFAULT_RULE_LATCHED,
            ): selector.BooleanSelector(),
            _required_key(
                CONF_RULE_UNKNOWN_HANDLING,
                defaults,
                fallback=DEFAULT_RULE_UNKNOWN_HANDLING,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_unknown_options())
            ),
            **_rule_notification_schema(defaults),
        }
    )


def _text_rule_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    entity_selector = selector.EntitySelector(
        selector.EntitySelectorConfig(multiple=True)
    )
    return vol.Schema(
        {
            _required_key(CONF_RULE_ENTITIES, defaults): entity_selector,
            _required_key(CONF_RULE_AGGREGATE, defaults): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_aggregate_options(TEXT_AGGREGATES))
            ),
            _required_key(CONF_RULE_CONDITION, defaults): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_text_condition_options())
            ),
            _required_key(CONF_RULE_TEXT_MATCH, defaults): selector.TextSelector(),
            _required_key(
                CONF_RULE_DURATION,
                defaults,
                fallback=DEFAULT_RULE_DURATION,
            ): vol.Coerce(int),
            _required_key(
                CONF_RULE_INTERVAL,
                defaults,
                fallback=DEFAULT_RULE_INTERVAL,
            ): vol.Coerce(int),
            _required_key(
                CONF_RULE_LEVEL,
                defaults,
                fallback=DEFAULT_RULE_LEVEL,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_level_options())
            ),
            _required_key(
                CONF_RULE_LATCHED,
                defaults,
                fallback=DEFAULT_RULE_LATCHED,
            ): selector.BooleanSelector(),
            _required_key(
                CONF_RULE_UNKNOWN_HANDLING,
                defaults,
                fallback=DEFAULT_RULE_UNKNOWN_HANDLING,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_unknown_options())
            ),
            _required_key(
                CONF_RULE_TEXT_CASE_SENSITIVE,
                defaults,
                fallback=DEFAULT_TEXT_CASE_SENSITIVE,
            ): selector.BooleanSelector(),
            _required_key(
                CONF_RULE_TEXT_TRIM,
                defaults,
                fallback=DEFAULT_TEXT_TRIM,
            ): selector.BooleanSelector(),
            **_rule_notification_schema(defaults),
        }
    )


def _validate_globals(data: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    mode = data.get(CONF_REPORT_MODE, REPORT_MODE_BASIC)
    if mode not in (REPORT_MODE_BASIC, REPORT_MODE_EXTENDED):
        errors[CONF_REPORT_MODE] = "invalid_report_mode"
    levels = data.get(CONF_EMAIL_LEVELS, DEFAULT_EMAIL_LEVELS)
    if not isinstance(levels, list):
        errors[CONF_EMAIL_LEVELS] = "invalid_email_levels"
    elif any(level not in LEVEL_OPTIONS for level in levels):
        errors[CONF_EMAIL_LEVELS] = "invalid_email_levels"

    for key in (
        CONF_REPORT_RETENTION_MAX_FILES,
        CONF_REPORT_RETENTION_MAX_AGE_DAYS,
    ):
        raw = data.get(key, 0)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            errors[key] = "invalid_number"
            continue
        if value < 0:
            errors[key] = "min_0"
    return errors


def _validate_rule_common(data: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    try:
        duration = int(data[CONF_RULE_DURATION])
        interval = int(data[CONF_RULE_INTERVAL])
    except (TypeError, ValueError, KeyError):
        return {"base": "invalid_number"}

    if duration < 1:
        errors[CONF_RULE_DURATION] = "min_1"
    if interval < 1:
        errors[CONF_RULE_INTERVAL] = "min_1"
    if interval > duration:
        errors[CONF_RULE_INTERVAL] = "interval_gt_duration"

    level = data.get(CONF_RULE_LEVEL)
    if level not in LEVEL_OPTIONS:
        errors[CONF_RULE_LEVEL] = "invalid_level"

    unknown_handling = data.get(CONF_RULE_UNKNOWN_HANDLING)
    if unknown_handling not in UNKNOWN_HANDLING_OPTIONS:
        errors[CONF_RULE_UNKNOWN_HANDLING] = "invalid_unknown"

    return errors


def _validate_entities(data: dict[str, Any]) -> dict[str, str]:
    entities = data.get(CONF_RULE_ENTITIES) or []
    if not entities:
        return {CONF_RULE_ENTITIES: "entities_required"}
    return {}


def _validate_numeric_rule(data: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if data.get(CONF_RULE_SEVERITY_MODE) == SEVERITY_MODE_SEMAFOR:
        return errors
    aggregate = data.get(CONF_RULE_AGGREGATE)
    if aggregate not in NUMERIC_AGGREGATES:
        errors[CONF_RULE_AGGREGATE] = "invalid_aggregate"
    condition = data.get(CONF_RULE_CONDITION)
    if condition not in NUMERIC_CONDITIONS:
        errors[CONF_RULE_CONDITION] = "invalid_condition"
    errors.update(_validate_numeric_thresholds(data))
    return errors


def _validate_numeric_thresholds(data: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if data.get(CONF_RULE_SEVERITY_MODE) == SEVERITY_MODE_SEMAFOR:
        return errors
    condition = data.get(CONF_RULE_CONDITION)
    if condition == COND_BETWEEN:
        low = data.get(CONF_RULE_THRESHOLD_LOW)
        high = data.get(CONF_RULE_THRESHOLD_HIGH)
        if low is None or high is None:
            errors[CONF_RULE_THRESHOLD_LOW] = "thresholds_required"
            errors[CONF_RULE_THRESHOLD_HIGH] = "thresholds_required"
        else:
            try:
                low_val = float(low)
                high_val = float(high)
            except (TypeError, ValueError):
                errors[CONF_RULE_THRESHOLD_LOW] = "invalid_number"
                errors[CONF_RULE_THRESHOLD_HIGH] = "invalid_number"
            else:
                if low_val > high_val:
                    errors[CONF_RULE_THRESHOLD_LOW] = "thresholds_order"
    else:
        threshold = data.get(CONF_RULE_THRESHOLD)
        if threshold is None:
            errors[CONF_RULE_THRESHOLD] = "thresholds_required"
        else:
            try:
                float(threshold)
            except (TypeError, ValueError):
                errors[CONF_RULE_THRESHOLD] = "invalid_number"
    return errors


def _validate_semafor_rule(data: dict[str, Any], numeric: bool) -> dict[str, str]:
    errors: dict[str, str] = {}
    direction = data.get(CONF_RULE_DIRECTION)
    if direction not in DIRECTION_OPTIONS:
        errors[CONF_RULE_DIRECTION] = "invalid_direction"

    interval: int | None
    try:
        interval = int(data.get(CONF_RULE_INTERVAL, DEFAULT_RULE_INTERVAL))
    except (TypeError, ValueError):
        errors[CONF_RULE_INTERVAL] = "invalid_number"
        interval = None
    else:
        if interval < 1:
            errors[CONF_RULE_INTERVAL] = "min_1"

    unknown_handling = data.get(CONF_RULE_UNKNOWN_HANDLING)
    if unknown_handling not in UNKNOWN_HANDLING_OPTIONS:
        errors[CONF_RULE_UNKNOWN_HANDLING] = "invalid_unknown"

    for level in LEVEL_ORDER:
        threshold_key = _threshold_key(level)
        duration_key = _duration_key(level)
        threshold = data.get(threshold_key)
        duration = data.get(duration_key)
        if threshold is None and duration is None:
            continue
        if threshold is None:
            errors[threshold_key] = "thresholds_required"
        if duration is None:
            errors[duration_key] = "duration_required"

    levels = _extract_semafor_levels(data, numeric)
    if not levels:
        errors["base"] = "semafor_levels_required"
        return errors

    for level, cfg in levels.items():
        duration = cfg.get("duration_seconds")
        if duration is None:
            errors[_duration_key(level)] = "duration_required"
        elif duration < 1:
            errors[_duration_key(level)] = "min_1"
        if interval is not None and duration is not None and interval > duration:
            errors[CONF_RULE_INTERVAL] = "interval_gt_duration"

    thresholds = [cfg["threshold"] for cfg in levels.values()]
    if direction == "higher_is_worse" and thresholds != sorted(thresholds):
        errors["base"] = "semafor_order"
    if direction == "lower_is_worse" and thresholds != sorted(thresholds, reverse=True):
        errors["base"] = "semafor_order"
    return errors


def _extract_semafor_levels(data: dict[str, Any], numeric: bool) -> dict[str, dict[str, Any]]:
    levels: dict[str, dict[str, Any]] = {}
    for level in LEVEL_ORDER:
        threshold_key = _threshold_key(level)
        duration_key = _duration_key(level)
        threshold = data.get(threshold_key)
        duration = data.get(duration_key)
        if threshold is None and duration is None:
            continue
        try:
            value = float(threshold) if numeric else int(threshold)
        except (TypeError, ValueError):
            continue
        levels[level] = {
            "threshold": value,
            "duration_seconds": int(duration) if duration is not None else None,
        }
    return levels


def _threshold_key(level: str) -> str:
    if level == "notify":
        return CONF_RULE_NOTIFY_THRESHOLD
    if level == "limit":
        return CONF_RULE_LIMIT_THRESHOLD
    return CONF_RULE_SHUTDOWN_THRESHOLD


def _duration_key(level: str) -> str:
    if level == "notify":
        return CONF_RULE_NOTIFY_DURATION
    if level == "limit":
        return CONF_RULE_LIMIT_DURATION
    return CONF_RULE_SHUTDOWN_DURATION


def _extract_thresholds(data: dict[str, Any]) -> list[float]:
    condition = data.get(CONF_RULE_CONDITION)
    if condition == COND_BETWEEN:
        return [
            float(data.get(CONF_RULE_THRESHOLD_LOW)),
            float(data.get(CONF_RULE_THRESHOLD_HIGH)),
        ]
    return [float(data.get(CONF_RULE_THRESHOLD))]


def _build_rule_config(
    base_context: dict[str, Any],
    data: dict[str, Any],
    existing_rules: list[dict[str, Any]],
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base_context)
    merged.update(data)
    rule_name = merged[CONF_RULE_NAME]
    rule_id = merged.get(CONF_RULE_ID)
    if not rule_id:
        rule_id = _generate_rule_id(rule_name, existing_rules)
    rule: dict[str, Any] = {
        CONF_RULE_ID: rule_id,
        CONF_RULE_NAME: rule_name,
        CONF_RULE_DATA_TYPE: merged.get(CONF_RULE_DATA_TYPE),
        CONF_RULE_ENTITIES: list(merged.get(CONF_RULE_ENTITIES, [])),
        CONF_RULE_AGGREGATE: merged.get(CONF_RULE_AGGREGATE),
        CONF_RULE_CONDITION: merged.get(CONF_RULE_CONDITION),
        CONF_RULE_DURATION: int(
            merged.get(CONF_RULE_DURATION, DEFAULT_RULE_DURATION)
        ),
        CONF_RULE_INTERVAL: int(
            merged.get(CONF_RULE_INTERVAL, DEFAULT_RULE_INTERVAL)
        ),
        CONF_RULE_LEVEL: merged.get(CONF_RULE_LEVEL, DEFAULT_RULE_LEVEL),
        CONF_RULE_LATCHED: bool(merged.get(CONF_RULE_LATCHED, DEFAULT_RULE_LATCHED)),
        CONF_RULE_UNKNOWN_HANDLING: merged.get(
            CONF_RULE_UNKNOWN_HANDLING, DEFAULT_RULE_UNKNOWN_HANDLING
        ),
        CONF_RULE_SEVERITY_MODE: merged.get(
            CONF_RULE_SEVERITY_MODE, SEVERITY_MODE_SIMPLE
        ),
        CONF_RULE_DIRECTION: merged.get(CONF_RULE_DIRECTION),
        CONF_RULE_TEXT_CASE_SENSITIVE: bool(
            merged.get(CONF_RULE_TEXT_CASE_SENSITIVE, DEFAULT_TEXT_CASE_SENSITIVE)
        ),
        CONF_RULE_TEXT_TRIM: bool(
            merged.get(CONF_RULE_TEXT_TRIM, DEFAULT_TEXT_TRIM)
        ),
        CONF_RULE_NOTIFY_EMAIL: bool(
            merged.get(CONF_RULE_NOTIFY_EMAIL, DEFAULT_RULE_NOTIFY_EMAIL)
        ),
        CONF_RULE_NOTIFY_MOBILE: bool(
            merged.get(CONF_RULE_NOTIFY_MOBILE, DEFAULT_RULE_NOTIFY_MOBILE)
        ),
    }
    if rule[CONF_RULE_SEVERITY_MODE] == SEVERITY_MODE_SEMAFOR:
        numeric = rule.get(CONF_RULE_DATA_TYPE) == DATA_TYPE_NUMERIC
        rule[CONF_RULE_LEVELS] = _extract_semafor_levels(merged, numeric)
    else:
        if CONF_RULE_THRESHOLDS in merged:
            rule[CONF_RULE_THRESHOLDS] = list(merged[CONF_RULE_THRESHOLDS])
        elif merged.get(CONF_RULE_TEXT_MATCH) is not None:
            rule[CONF_RULE_THRESHOLDS] = [merged[CONF_RULE_TEXT_MATCH]]
        else:
            rule[CONF_RULE_THRESHOLDS] = _extract_thresholds(merged)
    return rule


def _generate_rule_id(
    name: str, existing_rules: list[dict[str, Any]]
) -> str:
    existing = {rule.get(CONF_RULE_ID) for rule in existing_rules}
    base = slugify(name)
    if not base:
        base = "rule"
    candidate = base
    counter = 2
    while candidate in existing:
        candidate = f"{base}_{counter}"
        counter += 1
    return candidate


def _required_key(
    key: str,
    defaults: dict[str, Any] | None,
    fallback: Any | None = None,
) -> vol.Required:
    if defaults and key in defaults:
        return vol.Required(key, default=defaults.get(key))
    if fallback is not None:
        return vol.Required(key, default=fallback)
    return vol.Required(key)


def _optional_key(key: str, defaults: dict[str, Any] | None) -> vol.Optional:
    if defaults and key in defaults:
        return vol.Optional(key, default=defaults.get(key))
    return vol.Optional(key)


def _rules_action_options() -> list[selector.SelectOptionDict]:
    options = {
        "add": "Add new rule",
        "edit": "Edit existing rule",
        "delete": "Delete existing rule",
        "import": "Import rules",
        "export": "Export rules",
        "finish": "Finish",
    }
    return [
        selector.SelectOptionDict(value=value, label=label)
        for value, label in options.items()
    ]


def _rule_select_schema(rules: list[dict[str, Any]]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("rule_id"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_rule_select_options(rules))
            )
        }
    )


def _import_mode_options() -> list[selector.SelectOptionDict]:
    options = {
        IMPORT_MODE_MERGE: "Merge (add new rules)",
        IMPORT_MODE_REPLACE: "Replace (overwrite existing rules)",
    }
    return [
        selector.SelectOptionDict(value=value, label=label)
        for value, label in options.items()
    ]


def _rule_import_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_IMPORT_MODE, default=IMPORT_MODE_MERGE
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_import_mode_options())
            ),
            vol.Required(CONF_IMPORT_RULES_JSON): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)
            ),
        }
    )


def _rule_select_options(
    rules: list[dict[str, Any]]
) -> list[selector.SelectOptionDict]:
    options: list[selector.SelectOptionDict] = []
    for rule in rules:
        rule_id = str(rule.get(CONF_RULE_ID, ""))
        rule_name = str(rule.get(CONF_RULE_NAME, rule_id))
        if not rule_id:
            continue
        label = f"{rule_name} ({rule_id})"
        options.append(selector.SelectOptionDict(value=rule_id, label=label))
    return options


def _rule_index_for_id(rules: list[dict[str, Any]], rule_id: str | None) -> int | None:
    if not rule_id:
        return None
    for idx, rule in enumerate(rules):
        if str(rule.get(CONF_RULE_ID)) == rule_id:
            return idx
    return None


def _parse_import_payload(raw: Any) -> tuple[list[dict[str, Any]] | None, str | None]:
    if raw is None:
        return None, "import_invalid_json"
    if not isinstance(raw, str):
        raw = str(raw)
    if not raw.strip():
        return None, "import_invalid_json"
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None, "import_invalid_json"

    rules = payload.get(CONF_RULES) if isinstance(payload, dict) else payload
    if not isinstance(rules, list):
        return None, "import_invalid_rules"
    if not rules:
        return None, "import_rules_required"
    return rules, None


def _find_rule_id_conflicts(
    existing: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> list[str]:
    existing_ids = {
        str(rule.get(CONF_RULE_ID)) for rule in existing if rule.get(CONF_RULE_ID)
    }
    return [
        str(rule.get(CONF_RULE_ID))
        for rule in incoming
        if rule.get(CONF_RULE_ID) in existing_ids
    ]


def _normalize_import_rules(
    rules: list[Any],
) -> tuple[list[dict[str, Any]] | None, str | None]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rules:
        rule, error = _normalize_import_rule(raw)
        if error:
            return None, error
        rule_id = str(rule[CONF_RULE_ID])
        if rule_id in seen:
            return None, "import_duplicate_rule_id"
        seen.add(rule_id)
        normalized.append(rule)
    return normalized, None


def _normalize_import_rule(raw: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(raw, dict):
        return None, "import_invalid_rules"
    rule_id = _normalize_optional_str(raw.get(CONF_RULE_ID))
    name = _normalize_optional_str(raw.get(CONF_RULE_NAME))
    if not rule_id or not name:
        return None, "import_invalid_rule"
    data_type = raw.get(CONF_RULE_DATA_TYPE)
    if data_type not in DATA_TYPE_OPTIONS:
        return None, "import_invalid_rule"
    entities = list(raw.get(CONF_RULE_ENTITIES, []))
    if not entities:
        return None, "import_invalid_rule"
    aggregate = raw.get(CONF_RULE_AGGREGATE)
    severity_mode = raw.get(CONF_RULE_SEVERITY_MODE, SEVERITY_MODE_SIMPLE)
    if severity_mode not in SEVERITY_MODE_OPTIONS:
        return None, "import_invalid_rule"

    try:
        duration = int(raw.get(CONF_RULE_DURATION, DEFAULT_RULE_DURATION))
        interval = int(raw.get(CONF_RULE_INTERVAL, DEFAULT_RULE_INTERVAL))
    except (TypeError, ValueError):
        return None, "import_invalid_rule"
    if duration < 1 or interval < 1:
        return None, "import_invalid_rule"
    if severity_mode == SEVERITY_MODE_SIMPLE and interval > duration:
        return None, "import_invalid_rule"

    level = raw.get(CONF_RULE_LEVEL, DEFAULT_RULE_LEVEL)
    if level not in LEVEL_OPTIONS:
        return None, "import_invalid_rule"
    unknown_handling = raw.get(CONF_RULE_UNKNOWN_HANDLING, DEFAULT_RULE_UNKNOWN_HANDLING)
    if unknown_handling not in UNKNOWN_HANDLING_OPTIONS:
        return None, "import_invalid_rule"
    latched = bool(raw.get(CONF_RULE_LATCHED, DEFAULT_RULE_LATCHED))
    text_case_sensitive = bool(
        raw.get(CONF_RULE_TEXT_CASE_SENSITIVE, DEFAULT_TEXT_CASE_SENSITIVE)
    )
    text_trim = bool(raw.get(CONF_RULE_TEXT_TRIM, DEFAULT_TEXT_TRIM))
    notify_email = bool(raw.get(CONF_RULE_NOTIFY_EMAIL, DEFAULT_RULE_NOTIFY_EMAIL))
    notify_mobile = bool(raw.get(CONF_RULE_NOTIFY_MOBILE, DEFAULT_RULE_NOTIFY_MOBILE))

    condition = raw.get(CONF_RULE_CONDITION)
    thresholds = list(raw.get(CONF_RULE_THRESHOLDS, []))
    direction = raw.get(CONF_RULE_DIRECTION)
    levels: dict[str, dict[str, Any]] = {}

    if data_type == DATA_TYPE_NUMERIC:
        if aggregate not in NUMERIC_AGGREGATES:
            return None, "import_invalid_rule"
        if severity_mode == SEVERITY_MODE_SIMPLE:
            if condition not in NUMERIC_CONDITIONS:
                return None, "import_invalid_rule"
            thresholds, error = _normalize_numeric_thresholds(condition, thresholds)
            if error:
                return None, "import_invalid_rule"
        else:
            condition = None
            thresholds = []
            levels, error = _normalize_semafor_levels(
                raw, numeric=True, interval=interval
            )
            if error:
                return None, "import_invalid_rule"
            if direction not in DIRECTION_OPTIONS:
                return None, "import_invalid_rule"
            if not _validate_semafor_order(direction, levels):
                return None, "import_invalid_rule"
    elif data_type == DATA_TYPE_BINARY:
        if aggregate not in BINARY_AGGREGATES:
            return None, "import_invalid_rule"
        if aggregate == AGGREGATE_COUNT:
            if severity_mode == SEVERITY_MODE_SIMPLE:
                if condition not in NUMERIC_CONDITIONS:
                    return None, "import_invalid_rule"
                thresholds, error = _normalize_numeric_thresholds(
                    condition, thresholds, numeric=False
                )
                if error:
                    return None, "import_invalid_rule"
            else:
                condition = None
                thresholds = []
                levels, error = _normalize_semafor_levels(
                    raw, numeric=False, interval=interval
                )
                if error:
                    return None, "import_invalid_rule"
                if direction not in DIRECTION_OPTIONS:
                    return None, "import_invalid_rule"
                if not _validate_semafor_order(direction, levels):
                    return None, "import_invalid_rule"
        else:
            if severity_mode != SEVERITY_MODE_SIMPLE:
                return None, "import_invalid_rule"
            if condition not in BINARY_STATE_CONDITIONS:
                return None, "import_invalid_rule"
            thresholds = []
    else:
        if aggregate not in TEXT_AGGREGATES:
            return None, "import_invalid_rule"
        if severity_mode != SEVERITY_MODE_SIMPLE:
            return None, "import_invalid_rule"
        if condition not in TEXT_CONDITIONS:
            return None, "import_invalid_rule"
        if not thresholds:
            return None, "import_invalid_rule"
        match_value = str(thresholds[0])
        if text_trim:
            match_value = match_value.strip()
        if not match_value:
            return None, "import_invalid_rule"
        thresholds = [match_value]

    rule = {
        CONF_RULE_ID: rule_id,
        CONF_RULE_NAME: name,
        CONF_RULE_DATA_TYPE: data_type,
        CONF_RULE_ENTITIES: entities,
        CONF_RULE_AGGREGATE: aggregate,
        CONF_RULE_CONDITION: condition,
        CONF_RULE_DURATION: duration,
        CONF_RULE_INTERVAL: interval,
        CONF_RULE_LEVEL: level,
        CONF_RULE_LATCHED: latched,
        CONF_RULE_UNKNOWN_HANDLING: unknown_handling,
        CONF_RULE_SEVERITY_MODE: severity_mode,
        CONF_RULE_DIRECTION: direction,
        CONF_RULE_TEXT_CASE_SENSITIVE: text_case_sensitive,
        CONF_RULE_TEXT_TRIM: text_trim,
        CONF_RULE_NOTIFY_EMAIL: notify_email,
        CONF_RULE_NOTIFY_MOBILE: notify_mobile,
    }
    if severity_mode == SEVERITY_MODE_SEMAFOR:
        rule[CONF_RULE_LEVELS] = levels
    else:
        rule[CONF_RULE_THRESHOLDS] = thresholds
    return rule, None


def _normalize_numeric_thresholds(
    condition: str, thresholds: list[Any], numeric: bool = True
) -> tuple[list[float], str | None]:
    if condition == COND_BETWEEN:
        if len(thresholds) < 2:
            return [], "invalid"
        try:
            low = float(thresholds[0])
            high = float(thresholds[1])
        except (TypeError, ValueError):
            return [], "invalid"
        if not numeric:
            low = int(low)
            high = int(high)
        if low > high:
            return [], "invalid"
        return [low, high], None
    if not thresholds:
        return [], "invalid"
    try:
        value = float(thresholds[0])
    except (TypeError, ValueError):
        return [], "invalid"
    if not numeric:
        value = int(value)
    return [value], None


def _normalize_semafor_levels(
    raw: dict[str, Any], numeric: bool, interval: int
) -> tuple[dict[str, dict[str, Any]], str | None]:
    raw_levels = raw.get(CONF_RULE_LEVELS, {}) or {}
    if not isinstance(raw_levels, dict):
        return {}, "invalid"
    levels: dict[str, dict[str, Any]] = {}
    for level in LEVEL_ORDER:
        cfg = raw_levels.get(level)
        if not isinstance(cfg, dict):
            continue
        threshold = cfg.get("threshold")
        duration = cfg.get("duration_seconds")
        if threshold is None or duration is None:
            continue
        try:
            value = float(threshold)
            dur_val = int(duration)
        except (TypeError, ValueError):
            return {}, "invalid"
        if not numeric:
            value = int(value)
        if dur_val < 1:
            return {}, "invalid"
        if interval > dur_val:
            return {}, "invalid"
        levels[level] = {"threshold": value, "duration_seconds": dur_val}
    if not levels:
        return {}, "invalid"
    return levels, None


def _validate_semafor_order(direction: str, levels: dict[str, dict[str, Any]]) -> bool:
    thresholds = [cfg["threshold"] for cfg in levels.values()]
    if not thresholds:
        return False
    if direction == DIRECTION_HIGHER_IS_WORSE:
        return thresholds == sorted(thresholds)
    if direction == DIRECTION_LOWER_IS_WORSE:
        return thresholds == sorted(thresholds, reverse=True)
    return False


def _rules_excluding_index(
    rules: list[dict[str, Any]], index: int | None
) -> list[dict[str, Any]]:
    if index is None:
        return list(rules)
    return [rule for idx, rule in enumerate(rules) if idx != index]


def _store_rule(
    rules: list[dict[str, Any]], rule: dict[str, Any], edit_index: int | None
) -> None:
    if edit_index is None:
        rules.append(rule)
    elif 0 <= edit_index < len(rules):
        rules[edit_index] = rule


def _seed_rule_context(rule: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {
        CONF_RULE_ID: rule.get(CONF_RULE_ID),
        CONF_RULE_NAME: rule.get(CONF_RULE_NAME),
        CONF_RULE_DATA_TYPE: rule.get(CONF_RULE_DATA_TYPE),
        CONF_RULE_ENTITIES: list(rule.get(CONF_RULE_ENTITIES, [])),
        CONF_RULE_AGGREGATE: rule.get(CONF_RULE_AGGREGATE),
        CONF_RULE_DURATION: rule.get(CONF_RULE_DURATION, DEFAULT_RULE_DURATION),
        CONF_RULE_INTERVAL: rule.get(CONF_RULE_INTERVAL, DEFAULT_RULE_INTERVAL),
        CONF_RULE_LEVEL: rule.get(CONF_RULE_LEVEL, DEFAULT_RULE_LEVEL),
        CONF_RULE_LATCHED: rule.get(CONF_RULE_LATCHED, DEFAULT_RULE_LATCHED),
        CONF_RULE_UNKNOWN_HANDLING: rule.get(
            CONF_RULE_UNKNOWN_HANDLING, DEFAULT_RULE_UNKNOWN_HANDLING
        ),
        CONF_RULE_SEVERITY_MODE: rule.get(
            CONF_RULE_SEVERITY_MODE, SEVERITY_MODE_SIMPLE
        ),
        CONF_RULE_TEXT_CASE_SENSITIVE: rule.get(
            CONF_RULE_TEXT_CASE_SENSITIVE, DEFAULT_TEXT_CASE_SENSITIVE
        ),
        CONF_RULE_TEXT_TRIM: rule.get(CONF_RULE_TEXT_TRIM, DEFAULT_TEXT_TRIM),
    }
    severity_mode = context[CONF_RULE_SEVERITY_MODE]
    if severity_mode == SEVERITY_MODE_SEMAFOR:
        context[CONF_RULE_DIRECTION] = rule.get(CONF_RULE_DIRECTION)
        levels = rule.get(CONF_RULE_LEVELS, {}) or {}
        notify_cfg = levels.get("notify")
        if isinstance(notify_cfg, dict):
            context[CONF_RULE_NOTIFY_THRESHOLD] = notify_cfg.get("threshold")
            context[CONF_RULE_NOTIFY_DURATION] = notify_cfg.get("duration_seconds")
        limit_cfg = levels.get("limit")
        if isinstance(limit_cfg, dict):
            context[CONF_RULE_LIMIT_THRESHOLD] = limit_cfg.get("threshold")
            context[CONF_RULE_LIMIT_DURATION] = limit_cfg.get("duration_seconds")
        shutdown_cfg = levels.get("shutdown")
        if isinstance(shutdown_cfg, dict):
            context[CONF_RULE_SHUTDOWN_THRESHOLD] = shutdown_cfg.get("threshold")
            context[CONF_RULE_SHUTDOWN_DURATION] = shutdown_cfg.get("duration_seconds")
    else:
        condition = rule.get(CONF_RULE_CONDITION)
        context[CONF_RULE_CONDITION] = condition
        thresholds = list(rule.get(CONF_RULE_THRESHOLDS, []))
        if condition == COND_BETWEEN and len(thresholds) >= 2:
            context[CONF_RULE_THRESHOLD_LOW] = thresholds[0]
            context[CONF_RULE_THRESHOLD_HIGH] = thresholds[1]
        elif thresholds:
            context[CONF_RULE_THRESHOLD] = thresholds[0]
        if rule.get(CONF_RULE_DATA_TYPE) == DATA_TYPE_TEXT and thresholds:
            context[CONF_RULE_TEXT_MATCH] = thresholds[0]
    return context


def _level_options() -> list[selector.SelectOptionDict]:
    return [
        selector.SelectOptionDict(value=level, label=level.capitalize())
        for level in LEVEL_OPTIONS
    ]


def _data_type_options() -> list[selector.SelectOptionDict]:
    labels = {
        DATA_TYPE_NUMERIC: "Numeric",
        DATA_TYPE_BINARY: "Binary",
        DATA_TYPE_TEXT: "Text",
    }
    return [
        selector.SelectOptionDict(value=value, label=labels.get(value, value))
        for value in DATA_TYPE_OPTIONS
    ]


def _aggregate_options(options: list[str]) -> list[selector.SelectOptionDict]:
    labels = {
        "max": "Max",
        "min": "Min",
        "sum": "Sum",
        "avg": "Average",
        "any": "Any",
        "all": "All",
        "count": "Count",
    }
    return [
        selector.SelectOptionDict(value=value, label=labels.get(value, value))
        for value in options
    ]


def _numeric_condition_options() -> list[selector.SelectOptionDict]:
    labels = {
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
        "between": "Between (inclusive)",
        "eq": "Equals",
    }
    return [
        selector.SelectOptionDict(value=value, label=labels.get(value, value))
        for value in NUMERIC_CONDITIONS
    ]


def _binary_state_condition_options() -> list[selector.SelectOptionDict]:
    labels = {
        "is_on": "Is on",
        "is_off": "Is off",
    }
    return [
        selector.SelectOptionDict(value=value, label=labels.get(value, value))
        for value in BINARY_STATE_CONDITIONS
    ]


def _text_condition_options() -> list[selector.SelectOptionDict]:
    labels = {
        "contains": "Contains",
        "equals": "Equals",
    }
    return [
        selector.SelectOptionDict(value=value, label=labels.get(value, value))
        for value in TEXT_CONDITIONS
    ]


def _unknown_options() -> list[selector.SelectOptionDict]:
    labels = {
        "ignore": "Ignore",
        "treat_ok": "Treat as OK",
        "treat_violation": "Treat as violation",
    }
    return [
        selector.SelectOptionDict(value=value, label=labels.get(value, value))
        for value in UNKNOWN_HANDLING_OPTIONS
    ]


def _severity_mode_options() -> list[selector.SelectOptionDict]:
    labels = {
        SEVERITY_MODE_SIMPLE: "Simple",
        SEVERITY_MODE_SEMAFOR: "Semafor",
    }
    return [
        selector.SelectOptionDict(value=value, label=labels.get(value, value))
        for value in SEVERITY_MODE_OPTIONS
    ]


def _direction_options() -> list[selector.SelectOptionDict]:
    labels = {
        "higher_is_worse": "Higher is worse",
        "lower_is_worse": "Lower is worse",
    }
    return [
        selector.SelectOptionDict(value=value, label=labels.get(value, value))
        for value in DIRECTION_OPTIONS
    ]


def _domain_options(hass: HomeAssistant) -> list[str]:
    domains: set[str] = set()
    for entry in hass.config_entries.async_entries():
        domains.add(entry.domain)
    return sorted(domains)


def _notify_service_options(hass: HomeAssistant) -> list[str]:
    services = hass.services.async_services().get("notify", {})
    return sorted([f"notify.{service}" for service in services])


def _normalize_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return str(value)


def _clean_email_config(data: dict[str, Any]) -> dict[str, Any]:
    cleaned = {
        key: value
        for key, value in data.items()
        if not (isinstance(key, str) and key.startswith(_SECTION_PREFIX))
    }
    for key in (
        CONF_BREVO_API_KEY,
        CONF_BREVO_SENDER,
        CONF_BREVO_RECIPIENT,
        CONF_BREVO_RECIPIENT_NOTIFY,
        CONF_BREVO_RECIPIENT_LIMIT,
        CONF_BREVO_RECIPIENT_SHUTDOWN,
    ):
        if key in cleaned:
            value = _normalize_optional_str(cleaned.get(key))
            if value is None:
                cleaned.pop(key, None)
            else:
                cleaned[key] = value
    return cleaned
