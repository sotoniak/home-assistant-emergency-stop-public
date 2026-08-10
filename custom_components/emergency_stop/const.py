"""Constants for Emergency Stop integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "emergency_stop"
NAME = "Emergency Stop"

PLATFORMS = ["binary_sensor", "sensor", "button"]

CONF_RULES = "rules"
CONF_RULE_ID = "rule_id"
CONF_RULE_NAME = "rule_name"
CONF_RULE_DATA_TYPE = "data_type"
CONF_RULE_ENTITIES = "entities"
CONF_RULE_AGGREGATE = "aggregate"
CONF_RULE_CONDITION = "condition"
CONF_RULE_THRESHOLDS = "thresholds"
CONF_RULE_DURATION = "duration_seconds"
CONF_RULE_INTERVAL = "interval_seconds"
CONF_RULE_LEVEL = "level"
CONF_RULE_LATCHED = "latched"
CONF_RULE_UNKNOWN_HANDLING = "unknown_handling"
CONF_RULE_SEVERITY_MODE = "severity_mode"
CONF_RULE_DIRECTION = "direction"
CONF_RULE_LEVELS = "levels"
CONF_RULE_TEXT_CASE_SENSITIVE = "text_case_sensitive"
CONF_RULE_TEXT_TRIM = "text_trim"
CONF_RULE_NOTIFY_EMAIL = "notify_email"
CONF_RULE_NOTIFY_MOBILE = "notify_mobile"

# Input-trust fields. All default to "off" so existing rules keep their behaviour,
# but a rule that can reach `shutdown` should set them: an input that is stale,
# implausible or physically impossible must never be able to switch load.
CONF_RULE_MAX_AGE = "max_age_seconds"
CONF_RULE_VALUE_MIN = "value_min"
CONF_RULE_VALUE_MAX = "value_max"
CONF_RULE_MAX_STEP = "max_step"
CONF_RULE_MIN_SOURCES = "min_sources"
# Flap/hysteresis fields. `recovery_seconds` keeps a violation timer running while
# the input is briefly healthy again; the flap pair catches inputs that never fail
# long enough in one go but are unusable overall.
CONF_RULE_RECOVERY = "recovery_seconds"
CONF_RULE_FLAP_WINDOW = "flap_window_seconds"
CONF_RULE_FLAP_BUDGET = "flap_budget_seconds"

# Config-flow helper fields (not persisted in entry data)
CONF_RULE_THRESHOLD = "threshold"
CONF_RULE_THRESHOLD_LOW = "threshold_low"
CONF_RULE_THRESHOLD_HIGH = "threshold_high"
CONF_RULE_TEXT_MATCH = "text_match"
CONF_RULE_NOTIFY_THRESHOLD = "notify_threshold"
CONF_RULE_NOTIFY_DURATION = "notify_duration_seconds"
CONF_RULE_LIMIT_THRESHOLD = "limit_threshold"
CONF_RULE_LIMIT_DURATION = "limit_duration_seconds"
CONF_RULE_SHUTDOWN_THRESHOLD = "shutdown_threshold"
CONF_RULE_SHUTDOWN_DURATION = "shutdown_duration_seconds"

CONF_BREVO_API_KEY = "brevo_api_key"
CONF_BREVO_SENDER = "brevo_sender_email"
CONF_BREVO_RECIPIENT = "brevo_recipient_email"
CONF_BREVO_RECIPIENT_NOTIFY = "brevo_recipient_email_notify"
CONF_BREVO_RECIPIENT_LIMIT = "brevo_recipient_email_limit"
CONF_BREVO_RECIPIENT_SHUTDOWN = "brevo_recipient_email_shutdown"
CONF_EMAIL_LEVELS = "email_levels"
CONF_REPORT_MODE = "report_mode"
CONF_REPORT_DOMAINS = "report_domains"
CONF_REPORT_ENTITY_IDS = "report_entity_ids"
CONF_REPORT_RETENTION_MAX_FILES = "report_retention_max_files"
CONF_REPORT_RETENTION_MAX_AGE_DAYS = "report_retention_max_age_days"
CONF_MOBILE_NOTIFY_ENABLED = "mobile_notify_enabled"
CONF_MOBILE_NOTIFY_TARGETS_NOTIFY = "mobile_notify_targets_notify"
CONF_MOBILE_NOTIFY_TARGETS_LIMIT = "mobile_notify_targets_limit"
CONF_MOBILE_NOTIFY_TARGETS_SHUTDOWN = "mobile_notify_targets_shutdown"
CONF_MOBILE_NOTIFY_URGENT_NOTIFY = "mobile_notify_urgent_notify"
CONF_MOBILE_NOTIFY_URGENT_LIMIT = "mobile_notify_urgent_limit"
CONF_MOBILE_NOTIFY_URGENT_SHUTDOWN = "mobile_notify_urgent_shutdown"
CONF_NOTIFICATION_LEVEL = "level"
CONF_NOTIFICATION_MESSAGE = "message"
CONF_NOTIFICATION_TARGETS = "targets"
CONF_NOTIFICATION_URGENT = "urgent"
CONF_SIMULATION_LEVEL = "level"
CONF_SIMULATION_DURATION = "duration_seconds"
CONF_SIMULATION_REASON = "reason"
CONF_SIMULATION_DETAIL = "detail"
CONF_SIMULATION_ENTITY_ID = "entity_id"
CONF_SIMULATION_VALUE = "value"
CONF_SIMULATION_SEND_NOTIFICATIONS = "send_notifications"
CONF_SIMULATION_SEND_EMAIL = "send_email"
CONF_IMPORT_MODE = "import_mode"
CONF_IMPORT_RULES_JSON = "import_rules_json"
CONF_IMPORT_SETTINGS_JSON = "import_settings_json"

IMPORT_MODE_MERGE = "merge"
IMPORT_MODE_REPLACE = "replace"
IMPORT_MODE_OPTIONS = [IMPORT_MODE_MERGE, IMPORT_MODE_REPLACE]

ATTR_PRIMARY_REASON = "primary_reason"
ATTR_PRIMARY_PACK = "primary_pack"
ATTR_PRIMARY_INPUT = "primary_input"
ATTR_PRIMARY_CELL = "primary_cell"
ATTR_PRIMARY_SENSOR = "primary_sensor_entity"
ATTR_PRIMARY_VALUE = "primary_value"
ATTR_PRIMARY_DETAIL = "primary_detail"
ATTR_ACTIVE_EVENTS = "active_events"
ATTR_ACTIVE_REASONS = "active_reasons"
ATTR_ACTIVE_LEVELS = "active_levels"
ATTR_EVENTS_BY_REASON = "events_by_reason"
ATTR_ACKNOWLEDGED = "acknowledged"
ATTR_LAST_UPDATE = "last_update"
ATTR_LATCHED_SINCE = "latched_since"
ATTR_ERROR_LEVEL = "error_level"
ATTR_PRIMARY_LEVEL = "primary_level"
ATTR_SIMULATION_ACTIVE = "simulation_active"
ATTR_TRUSTED_SOURCES = "trusted_sources"
ATTR_UNTRUSTED_INPUTS = "untrusted_inputs"
ATTR_DEGRADED_RULES = "degraded_rules"
ATTR_PROTECTION_DEGRADED = "protection_degraded"

SERVICE_RESET = "reset"
SERVICE_ACK = "acknowledge"
SERVICE_REPORT = "generate_report"
SERVICE_TEST_NOTIFICATION = "test_notification"
SERVICE_SIMULATE_LEVEL = "simulate_level"
SERVICE_CLEAR_SIMULATION = "clear_simulation"
SERVICE_EXPORT_RULES = "export_rules"

# Action-oriented severity levels for direct use in automations.
LEVEL_NOTIFY = "notify"
LEVEL_LIMIT = "limit"
LEVEL_SHUTDOWN = "shutdown"
LEVEL_NORMAL = "normal"

REPORT_MODE_BASIC = "basic"
REPORT_MODE_EXTENDED = "extended"

LEVEL_OPTIONS = [LEVEL_NOTIFY, LEVEL_LIMIT, LEVEL_SHUTDOWN]
LEVEL_ORDER = [LEVEL_NOTIFY, LEVEL_LIMIT, LEVEL_SHUTDOWN]

DATA_TYPE_NUMERIC = "numeric"
DATA_TYPE_BINARY = "binary"
DATA_TYPE_TEXT = "text"
DATA_TYPE_OPTIONS = [DATA_TYPE_NUMERIC, DATA_TYPE_BINARY, DATA_TYPE_TEXT]

AGGREGATE_MAX = "max"
AGGREGATE_MIN = "min"
AGGREGATE_SUM = "sum"
AGGREGATE_AVG = "avg"
AGGREGATE_ANY = "any"
AGGREGATE_ALL = "all"
AGGREGATE_COUNT = "count"

NUMERIC_AGGREGATES = [AGGREGATE_MAX, AGGREGATE_MIN, AGGREGATE_SUM, AGGREGATE_AVG]
BINARY_AGGREGATES = [AGGREGATE_ANY, AGGREGATE_ALL, AGGREGATE_COUNT]
TEXT_AGGREGATES = [AGGREGATE_ANY, AGGREGATE_ALL]

COND_GT = "gt"
COND_GTE = "gte"
COND_LT = "lt"
COND_LTE = "lte"
COND_BETWEEN = "between"
COND_EQ = "eq"
COND_IS_ON = "is_on"
COND_IS_OFF = "is_off"
COND_CONTAINS = "contains"
COND_EQUALS = "equals"

NUMERIC_CONDITIONS = [COND_GT, COND_GTE, COND_LT, COND_LTE, COND_BETWEEN, COND_EQ]
BINARY_STATE_CONDITIONS = [COND_IS_ON, COND_IS_OFF]
TEXT_CONDITIONS = [COND_CONTAINS, COND_EQUALS]

UNKNOWN_IGNORE = "ignore"
UNKNOWN_TREAT_OK = "treat_ok"
UNKNOWN_TREAT_VIOLATION = "treat_violation"
UNKNOWN_HANDLING_OPTIONS = [UNKNOWN_IGNORE, UNKNOWN_TREAT_OK, UNKNOWN_TREAT_VIOLATION]

DEFAULT_RULE_DURATION = 10
DEFAULT_RULE_INTERVAL = 1
DEFAULT_RULE_LEVEL = LEVEL_NOTIFY
DEFAULT_RULE_LATCHED = True
DEFAULT_RULE_UNKNOWN_HANDLING = UNKNOWN_IGNORE
DEFAULT_RULE_NOTIFY_EMAIL = True
DEFAULT_RULE_NOTIFY_MOBILE = True
DEFAULT_RULE_MAX_AGE = 0
DEFAULT_RULE_MIN_SOURCES = 1
DEFAULT_RULE_RECOVERY = 0
DEFAULT_RULE_FLAP_WINDOW = 0
DEFAULT_RULE_FLAP_BUDGET = 0
# A rejected jump must not blind the rule forever: after this many consecutive
# rejects the new value is accepted as the sensor's real level.
MAX_CONSECUTIVE_JUMP_REJECTS = 3
# Invalid inputs are only logged at debug for this long after setup: rules are
# evaluated seconds after startup, before the source integrations exist.
STARTUP_GRACE_SECONDS = 120
# How long an undecidable shutdown-capable rule must stay undecidable before the
# protection is reported as degraded (restarts and short blips must not fire it).
PROTECTION_DEGRADED_GRACE_SECONDS = 60
DEFAULT_TEXT_CASE_SENSITIVE = False
DEFAULT_TEXT_TRIM = True
DEFAULT_MOBILE_NOTIFY_ENABLED = False
DEFAULT_MOBILE_NOTIFY_URGENT_NOTIFY = False
DEFAULT_MOBILE_NOTIFY_URGENT_LIMIT = False
DEFAULT_MOBILE_NOTIFY_URGENT_SHUTDOWN = True
DEFAULT_EMAIL_LEVELS = [LEVEL_NOTIFY, LEVEL_LIMIT, LEVEL_SHUTDOWN]
DEFAULT_REPORT_RETENTION_MAX_FILES = 0
DEFAULT_REPORT_RETENTION_MAX_AGE_DAYS = 0

# A simulation always expires on its own. An open-ended one used to mask the real
# rule state for as long as it ran, which is not acceptable for a safety layer.
DEFAULT_SIMULATION_DURATION_SECONDS = 300
MAX_SIMULATION_DURATION_SECONDS = 3600

SEVERITY_MODE_SIMPLE = "simple"
SEVERITY_MODE_SEMAFOR = "semafor"
SEVERITY_MODE_OPTIONS = [SEVERITY_MODE_SIMPLE, SEVERITY_MODE_SEMAFOR]

DIRECTION_HIGHER_IS_WORSE = "higher_is_worse"
DIRECTION_LOWER_IS_WORSE = "lower_is_worse"
DIRECTION_OPTIONS = [DIRECTION_HIGHER_IS_WORSE, DIRECTION_LOWER_IS_WORSE]

MIN_EVAL_INTERVAL = timedelta(seconds=1)
