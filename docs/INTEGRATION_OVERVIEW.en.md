# Emergency Stop — Current Integration Overview (EN)

This document describes the **dynamic rule engine** implemented in the `emergency_stop` integration.

The integration is safety-focused. It evaluates user-defined rules over any entities, exposes deterministic outputs, and provides detailed reporting.

## Core Concepts

The coordinator builds a single aggregated state:
- `active`: whether any rule is currently active.
- `level`: the highest active action level.
- `primary_*`: details about the primary (root-cause) rule.
- `active_events`: the full list of active rules.

Action levels are intentionally action-oriented:
- `notify`: informational, notify only.
- `limit`: caution / limit behavior.
- `shutdown`: stop / disconnect.

If multiple rules are active, the highest level wins (`shutdown` > `limit` > `notify`).

## Entities

### Binary Sensors

1. `binary_sensor.emergency_stop_active`
- Purpose: the central “something is wrong” indicator.
- On when: any rule is active.
- Key attributes: `error_level`, `primary_*` details, `active_events`, `active_reasons`,
  `active_levels`, `events_by_reason`, `acknowledged`, `last_update`, `latched_since`.

2. `binary_sensor.emergency_stop_shutdown`
- Purpose: the only signal safe to switch real load from.
- On when: the rules put the level at `shutdown`. A simulation never raises it, and no
  lower level does either — unlike `emergency_stop_active`, which is on from `notify` up.
- Key attributes: `error_level`, `primary_*`, `latched_since`, `simulation_active`, and
  `active_events` filtered to shutdown events.
- Wiring rule: trigger on an explicit `on`. The entity goes `unavailable` whenever the
  coordinator cannot update, so a "not off" condition would read that as an alarm.

3. `binary_sensor.emergency_stop_protection_degraded`
- Purpose: makes a blind protection layer visible.
- On when: a shutdown-capable rule has had fewer trusted inputs than its quorum needs for
  longer than the grace period (stale, out-of-range, non-finite or missing inputs).
- Key attributes: `degraded_rules`, with per-rule `trusted_sources`, `untrusted_inputs`,
  `required_sources` and `blind_for_seconds`.
- Rationale: an untrustworthy input is never treated as a violation — that would shut the
  house down every time an integration drops out — so without this signal the protection
  could stop working silently.

4. `binary_sensor.emergency_stop_<rule_id>`
- Purpose: a direct trigger for a specific rule.
- On when: that rule is active.
- Attributes include the rule config and runtime state (last match/aggregate, timestamps).
- Runtime interpretation:
  - `last_aggregate` / `evaluation.aggregate`: latest aggregated value for this rule.
  - For numeric rules with `aggregate: max`, this is the highest value across configured entities.
  - `last_entity` / `evaluation.entity_id`: entity that produced the aggregate value (for `max`/`min`).
  - `last_match` / `evaluation.match`: boolean in `simple` mode; `null` in `semafor` mode by design.
  - `last_invalid_reason` / `evaluation.invalid_reason`: evaluation problem reason (`unknown`, `no_valid_values`, etc.); `null` means valid inputs.

### Sensors

1. `sensor.emergency_stop_level`
- Purpose: the highest current action level.
- State values: `normal`, `notify`, `limit`, `shutdown`.
- Recommended use: simple automations (e.g., shutdown on `shutdown`).

### Buttons

1. `button.emergency_stop_reset`
- Purpose: clear the latch and all rule timers.

2. `button.emergency_stop_report` (Diagnostic)
- Purpose: generate a JSON report file in `/media/emergency-stop/logs`.
- If email notifications are configured, it also sends the report via email.

## Services

The integration registers these services:
- `emergency_stop.reset`: clears latched state and timers.
- `emergency_stop.acknowledge`: sets `acknowledged = true` without clearing the latch.
- `emergency_stop.generate_report`: writes a timestamped JSON report (and sends email if configured).
- `emergency_stop.export_rules`: writes a JSON export of all rules to `/media/emergency-stop/config`.
- `emergency_stop.test_notification`: sends a test mobile notification for a selected level.
- `emergency_stop.simulate_level`: simulates a level (notify/limit/shutdown/normal) for testing.
- `emergency_stop.clear_simulation`: clears an active simulation.

Settings export/import is provided via the Options UI (not as a service).
Settings export file path:
- `/media/emergency-stop/config/emergency_stop_settings_<entry_id>_<timestamp>.json`

Initial clean installation starts with a setup mode selector:
- `Custom setup`: manual settings + rule wizard.
- `Import settings + rules`: enter settings/rules export file names from `/media/emergency-stop/config`.

## Email Notifications (Optional)

Configure Brevo in options with API key, sender email, and a default recipient email. Select the email levels (notify/limit/shutdown) and optionally set per-level recipients to override the default. Leave the Brevo fields empty to disable email sending.
Global settings are grouped into sections: Report, Email provider (Brevo), Email routing by level, Mobile notifications.

When the emergency stop transitions from inactive to active, the integration writes a report to `/media/emergency-stop/logs` and sends the full JSON report in the email body along with a prompt for ChatGPT. Emails are only sent for the enabled levels and only when a recipient is configured for that level (or the default recipient is set). A new email is sent only after the stop goes inactive and activates again.

Email subject format: `Emergency Stop [level]`. For Brevo, `shutdown` emails are marked high priority.

## Report Detail Mode

You can choose how much data is included in the report and email:
- `basic`: only Emergency Stop configuration + rule inputs.
- `extended`: includes all sensors and binary sensors from the selected integration domains (name, state, attributes).
- Optional: select specific entities (any domain) for the extended snapshot, or combine with domains.

Extended data is stored in the report file and included in the email body.
Optional report retention settings can keep a maximum number of reports or remove reports older than N days (0 disables cleanup).

## Editing Rules

Options navigation:
- Settings → Devices & Services → Emergency Stop → Configure
- Top-level menu:
  - `Settings management`
  - `Rules management`

`Settings management` actions:
- `Edit settings`
- `Import settings`
- `Export settings`

`Rules management` actions:
- `Add`
- `Edit`
- `Delete`
- `Import`
- `Export`
- `Back`

`Back` in Rules management saves options and returns to the top-level menu.
Settings import/export includes Brevo configuration values (including API key), so exported settings JSON should be handled as sensitive.
Imports use file names from `/media/emergency-stop/config` (same directory as export files).

## Mobile Notifications (Optional)

Configure mobile notifications in options:
- Enable/disable globally.
- Per level (notify/limit/shutdown):
  - list of `notify.mobile_app_*` targets
  - urgent flag (default ON for shutdown)

Behavior:
- Sends on **every level change** (including downgrade).
- Downgrade sends to **new level** targets and **previous level** targets.
- Return to `normal` sends to **notify** targets.
- Report button sends a **TEST** notification to all configured targets.
- Notifications and email run detached from the evaluation cycle (bounded by a 3-second
  timeout), so a slow notify service delays neither the next evaluation nor the state
  a physical stop reacts to.

Urgent payload:
- iOS: `push.interruption-level: critical`
- Android: `priority: high`, `ttl: 0`

## Evaluation Logic

Rules are evaluated per-rule interval:
- `interval_seconds`: evaluation frequency for that rule.
- `duration_seconds`: condition must hold continuously for this long to activate.

### Severity Modes

Each rule has a severity mode:
- **Simple**: one condition + `duration_seconds` → rule activates at a single level (`notify` / `limit` / `shutdown`).
- **Semafor**: multiple levels in one rule (notify/limit/shutdown), each with its own threshold + duration.
  - Direction: `higher_is_worse` or `lower_is_worse`.
  - Available only for numeric rules and binary rules with `count`.

### Rule Configuration Structure (Config Entry)

Rules are stored in `config.rules` as a list of dictionaries. Common fields:
- `rule_id`, `rule_name`, `data_type`, `entities`, `aggregate`
- `interval_seconds`, `latched`, `unknown_handling`
- `notify_email`, `notify_mobile`
- `severity_mode` (`simple` or `semafor`)
- Text-only: `text_case_sensitive`, `text_trim`

Simple mode adds:
- `condition`
- `thresholds` (1 value, or 2 values for `between`)
- `duration_seconds`
- `level`

Semafor mode adds:
- `direction` (`higher_is_worse` / `lower_is_worse`)
- `levels`: `notify` / `limit` / `shutdown`, each with `threshold` + `duration_seconds`

Example (simple numeric rule):
```json
{
  "rule_id": "overvoltage",
  "rule_name": "Overvoltage",
  "data_type": "numeric",
  "entities": ["sensor.pack_max"],
  "aggregate": "max",
  "condition": "gt",
  "thresholds": [3.6],
  "duration_seconds": 3,
  "interval_seconds": 1,
  "level": "shutdown",
  "latched": true,
  "unknown_handling": "ignore",
  "notify_email": true,
  "notify_mobile": true,
  "severity_mode": "simple",
  "text_case_sensitive": false,
  "text_trim": true
}
```

Example (semafor numeric rule):
```json
{
  "rule_id": "overvoltage",
  "rule_name": "Overvoltage",
  "data_type": "numeric",
  "entities": ["sensor.pack_max"],
  "aggregate": "max",
  "interval_seconds": 1,
  "latched": true,
  "unknown_handling": "ignore",
  "notify_email": true,
  "notify_mobile": true,
  "severity_mode": "semafor",
  "direction": "higher_is_worse",
  "levels": {
    "notify": { "threshold": 3.5, "duration_seconds": 3 },
    "limit": { "threshold": 3.6, "duration_seconds": 3 },
    "shutdown": { "threshold": 3.8, "duration_seconds": 3 }
  },
  "text_case_sensitive": false,
  "text_trim": true
}
```

### Example (Semafor Smoke Test)

1) Create a helper: `input_number.test_voltage`.
2) Configure Emergency Stop rule:
   - Data type: Numeric
   - Entities: `input_number.test_voltage`
   - Aggregate: Max
   - Severity mode: Semafor
   - Direction: Higher is worse
   - Notify: 3.50 for 3 s, Limit: 3.60 for 3 s, Shutdown: 3.80 for 3 s
   - Interval: 1 s, Latched: ON, Unknown handling: ignore
3) Set the helper value to 3.55, wait 3 s → level `notify`.
4) Set to 3.65, wait 3 s → level `limit`.
5) Set to 3.85, wait 3 s → level `shutdown`.
6) If latched is ON, the highest level stays active until reset.

### Rule Data Types

**Numeric rules**
- Entities with parseable numbers.
- Aggregation: `max`, `min`, `sum`, `avg`.
- Conditions: `gt`, `gte`, `lt`, `lte`, `between` (inclusive), `eq`.

**Binary rules**
- Entities with `on/off` states.
- Aggregation: `any`, `all`, `count`.
- Conditions: `is_on`, `is_off` (for any/all), numeric comparisons for count.

**Text rules**
- Entities with text states.
- Aggregation: `any`, `all`.
- Conditions: `contains`, `equals`.
- Default: case-insensitive + trim whitespace.

### Unknown Handling

For `unknown`, `unavailable`, missing, or invalid values, each rule applies `unknown_handling`:
- `ignore`: resets the timer; rule becomes inactive.
- `treat_ok`: treat as not violated.
- `treat_violation`: treat as violated (fail-safe).

### Latching

If `latched=true`, the rule remains active until reset, even if the condition clears.
In Semafor mode, the highest reached level stays latched until reset.

Latches are persisted across restarts, so the reload that every options save triggers
no longer clears an active alarm. A stored latch is discarded only when the rule's
decisive configuration changed since it was raised (entities, thresholds, duration,
level, quorum, flap settings) - an alarm raised against different thresholds says
nothing about the new ones.

### Input Trust

Per-rule guards, all off by default. A rule that can reach `shutdown` should set them,
because without them it decides on a single unvalidated sensor reading.

| Field | Meaning |
|---|---|
| `max_age_seconds` | Older input counts as `stale` and is dropped. Age comes from `last_reported`, then `last_updated`/`last_changed`; an undeterminable age is treated as stale. |
| `value_min` / `value_max` | Plausible range; outside it the input is `out_of_range`. `nan`/`inf` are always `not_finite`. |
| `max_step` | Largest accepted change between samples; a bigger one is `jump`, but only a few times in a row so a genuinely fast rise is not hidden forever. |
| `min_sources` | Quorum: the condition must hold for that many inputs independently (`max`/`min` aggregates). Fewer trusted inputs than the quorum yields `quorum_not_met` instead of a decision. Per-level override: `levels.<level>.min_sources`. |
| `recovery_seconds` | How long the input must be healthy before elapsed violation time is discarded; otherwise every brief recovery restarts the duration. |
| `flap_window_seconds` + `flap_budget_seconds` | Cumulative failure budget in a trailing window, for inputs that never fail long enough in one go but are unusable overall. Both required together. |

`unknown_handling: treat_violation` is refused on a shutdown-capable rule (options flow,
import and load time): it fires exactly when inputs are missing, which means the layer
is degraded, not that the battery is in trouble. Such situations raise
`binary_sensor.emergency_stop_protection_degraded` instead.
