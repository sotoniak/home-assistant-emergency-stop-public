# Emergency Stop (Home Assistant)

[![HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=sotoniak&repository=home-assistant-emergency-stop-public)

[![Release](https://img.shields.io/github/v/release/sotoniak/home-assistant-emergency-stop-public?display_name=tag)](https://github.com/sotoniak/home-assistant-emergency-stop-public/releases)
[![Validate](https://github.com/sotoniak/home-assistant-emergency-stop-public/actions/workflows/validate.yaml/badge.svg)](https://github.com/sotoniak/home-assistant-emergency-stop-public/actions/workflows/validate.yaml)
[![Hassfest](https://github.com/sotoniak/home-assistant-emergency-stop-public/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/sotoniak/home-assistant-emergency-stop-public/actions/workflows/hassfest.yaml)

Custom integration for Home Assistant that evaluates **dynamic, user-defined rules** over any entities and latches a central "Emergency Stop" when configured conditions are violated.

## Pitch
Emergency Stop is a safety-first rule engine for Home Assistant: define numeric/binary/text rules with aggregations and time-based conditions, then latch a central stop with clear levels (`notify`/`limit`/`shutdown`) and full reports. It focuses on correctness and debuggability over convenience.

## Features
- Config Flow UI setup (no YAML required)
- Options UI with a top-level menu:
  - `Settings management`
  - `Rules management`
- Fully dynamic rules:
  - numeric, binary, or text inputs
  - aggregation (max/min/sum/avg, any/all/count)
  - conditions (>, <, between, equals, contains)
  - per-rule duration + interval
  - Simple mode (single level) or Semafor mode (notify/limit/shutdown)
  - per-level thresholds + durations in Semafor mode
  - per-rule level (notify/limit/shutdown) and latching
  - per-rule unknown handling
- Per-rule binary sensors + shared level sensor (`normal`/`notify`/`limit`/`shutdown`)
- Latched emergency stop with reset/acknowledge services
- Optional email notification on activation with full JSON report
- Optional mobile notifications per level (notify/limit/shutdown), including urgent flag
- Report snapshots with optional extended domains/entities
- Settings export/import in options (including Brevo configuration)
- Reset and report button entities

## Installation (manual / HACS custom repository)
1. Copy `custom_components/emergency_stop` into `/config/custom_components/emergency_stop/`.
2. Restart Home Assistant.
3. Add the integration: **Settings → Devices & Services → Add Integration → Emergency Stop**.

## Configuration
During setup:
- Choose setup mode first:
  - `Custom setup`: continue with manual settings + rule wizard.
  - `Import settings + rules`: enter `Settings` and `Rules` export file names (`.json`) from `/media/emergency-stop/config`.
- Configure global reporting + optional email (Brevo)
- Add one or more **rules**, each with:
  - name and data type (numeric/binary/text)
  - entity list
  - aggregation + condition + thresholds
  - duration + evaluation interval
  - severity mode: Simple or Semafor (notify/limit/shutdown thresholds + durations)
  - direction (Semafor only): higher is worse / lower is worse
  - Semafor is available for numeric rules and binary count rules
  - level (Notify/Limit/Shutdown)
  - latched on/off
  - unknown handling
  - per-rule notification toggles (email/mobile)
- If multiple rules are active, the highest level wins (`shutdown` > `limit` > `notify`)
- Options navigation after setup:
  - **Settings → Devices & Services → Emergency Stop → Configure**
  - `Settings management`:
    - `Edit settings`
    - `Import settings`
    - `Export settings`
  - `Rules management`:
    - `Add`, `Edit`, `Delete`, `Import`, `Export`, `Back`
  - `Back` in Rules management saves current options and returns to the top menu.
- Settings import/export includes Brevo fields (including API key). Treat exported settings JSON as sensitive.
- Import in setup/options uses file names from `/media/emergency-stop/config` (same directory as exports).
- Global settings are grouped into sections: Report, Email provider (Brevo), Email routing by level, Mobile notifications.
- Optionally configure email notifications:
  - Brevo: enter API key, sender email, and recipient email
  - Email levels: choose which levels send email (Notify/Limit/Shutdown)
  - Optional per-level recipients override the default recipient
  - When the emergency stop activates, a report is written to `/media/emergency-stop/logs` and the full JSON is sent in the email body.
  - The email body contains a prompt plus the full JSON report (ready to paste into ChatGPT).
  - Subject format is `Emergency Stop [level]`. `shutdown` emails are marked high priority.
  - Leave the Brevo fields empty to disable email sending. The API key is stored in the config entry (.storage).
- Report detail:
  - `basic`: only Emergency Stop data + rule inputs.
  - `extended`: include all sensors and binary sensors from selected integration domains (name, state, attributes).
  - Optional: select specific entities to include in the extended snapshot (any domain), or combine with domains.
  - Extended data is included in the report file and email.
  - Optional report retention: keep a max number of files or remove files older than N days (0 disables cleanup).
  - Example (extended):
    - Domains: `ibms`, `esphome`
    - Entities: `sensor.inverter_power`, `switch.backup_relay`

### Rule configuration structure (config entry)
Rules are stored in `config.rules` as a list of dictionaries.

Simple mode example:
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
  "severity_mode": "simple",
  "notify_email": true,
  "notify_mobile": true
}
```

Semafor mode example:
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
  "severity_mode": "semafor",
  "direction": "higher_is_worse",
  "notify_email": true,
  "notify_mobile": true,
  "levels": {
    "notify": { "threshold": 3.5, "duration_seconds": 3 },
    "limit": { "threshold": 3.6, "duration_seconds": 3 },
    "shutdown": { "threshold": 3.8, "duration_seconds": 3 }
  }
}
```

### Services
- `emergency_stop.reset`: Clears the latched stop and all active events.
- `emergency_stop.acknowledge`: Marks the stop as acknowledged without clearing it.
- `emergency_stop.generate_report`: Writes a JSON report to `/media/emergency-stop/logs/emergency_stop_report_<timestamp>.json` and sends email if configured.
- `emergency_stop.export_rules`: Writes a JSON export of all rules to `/media/emergency-stop/config/emergency_stop_rules_<timestamp>.json`.
- `emergency_stop.test_notification`: Sends a test mobile notification for a selected level.
- `emergency_stop.simulate_level`: Simulates a level (notify/limit/shutdown/normal) for testing.
- `emergency_stop.clear_simulation`: Clears an active simulation.

Settings export/import is available in the options UI (not as a service):
- Settings export file: `/media/emergency-stop/config/emergency_stop_settings_<entry_id>_<timestamp>.json`

### Entities
- `binary_sensor.emergency_stop_active` — on from `notify` upwards. **Do not switch load from this**: it cannot tell an informational rule from a shutdown.
- `binary_sensor.emergency_stop_shutdown` — on only for a rule-derived `shutdown` level, and a simulation cannot raise it. This is the one signal safe to drive a contactor or stop circuit from.
- `binary_sensor.emergency_stop_protection_degraded` — on when a shutdown-capable rule cannot decide on its inputs for longer than the grace period (stale, implausible or missing inputs). Untrustworthy inputs deliberately never raise an alarm, so this is how a blind protection layer becomes visible.
- `binary_sensor.emergency_stop_<rule_id>` (one per rule)
- `sensor.emergency_stop_level` (returns `normal` when no violations are active)
- `button.emergency_stop_reset`
- `button.emergency_stop_report`

### Wiring a physical stop

If a level of this integration is allowed to switch real load, treat the following
as requirements rather than suggestions:

- Trigger on `binary_sensor.emergency_stop_shutdown` being explicitly `on`. Never
  write the condition as "not off" — the entity becomes `unavailable` whenever the
  coordinator cannot update, and "not off" reads that as an alarm.
- Keep the hardware protection layer independent. This integration reacts to
  published entity states, i.e. seconds; a BMS reacts in milliseconds.
- Give every shutdown-capable rule `max_age_seconds`, `value_min`/`value_max` and
  `min_sources` (below). Without them a rule decides on a single unvalidated reading.
- Alert on `binary_sensor.emergency_stop_protection_degraded` too, otherwise a
  silently blind rule looks exactly like a healthy one.

### Input trust (per rule)

All of these default to off, so existing rules keep behaving as before. A rule that
can reach `shutdown` should set them.

| Field | Meaning |
|---|---|
| `max_age_seconds` | An input older than this counts as `stale` and is dropped. Freshness comes from `last_reported`, falling back to `last_updated`/`last_changed`; an input whose age cannot be determined is treated as stale. |
| `value_min` / `value_max` | Plausible range. Outside it the input is `out_of_range` and dropped. `nan`/`inf` are always rejected as `not_finite`. |
| `max_step` | Largest change accepted between two samples; a bigger one is dropped as `jump` — but only a few times in a row, after which the new level is believed, so a genuinely fast rise cannot stay hidden. |
| `min_sources` | Quorum: the condition must hold for this many inputs independently (`max`/`min` aggregates), and a rule with fewer trusted inputs than its quorum reports `quorum_not_met` instead of deciding. A per-level override lives in `levels.<level>.min_sources`, so `shutdown` can demand two sources while `notify` still fires on one. |
| `recovery_seconds` | How long the input must be healthy before elapsed violation time is discarded. Without it every brief recovery — including a momentary `unavailable` — restarts the duration from zero. |
| `flap_window_seconds` + `flap_budget_seconds` | Cumulative failure budget in a trailing window: fires when the input has been failing for `flap_budget_seconds` in total within `flap_window_seconds`, even if never long enough in one go. Both must be set together. |

`unknown_handling: treat_violation` is rejected on a shutdown-capable rule — in the
options flow, in rule import and at load time. It fires precisely when the inputs
are missing, which means the layer is degraded rather than the battery being in
trouble.

### Latching and recovery

A latched rule stays active until `emergency_stop.reset` (or the reset button).
Latches are persisted, so a restart — including the reload every options save
triggers — no longer clears an active alarm. A latch is dropped only when the
rule's decisive configuration (entities, thresholds, duration, level, quorum, flap
settings) changed since it was raised.

### Simulation safety

`emergency_stop.simulate_level` drives the display and notification surfaces only.
It never raises `binary_sensor.emergency_stop_shutdown`, it no longer stops rules
from being evaluated, and it always expires on its own (default 300 s, capped at
3600 s).

### Rule Runtime Attributes (per-rule binary sensor)
On `binary_sensor.emergency_stop_<rule_id>`, runtime attributes describe the latest evaluation snapshot:
- `last_aggregate` and `evaluation.aggregate`: latest aggregated value for the rule.
- For numeric rules with `aggregate: max`, this is the current highest value across selected entities.
- `last_entity` and `evaluation.entity_id`: entity that produced the aggregate value (for `max`/`min`).
- `last_match` and `evaluation.match`:
  - `simple` mode: boolean (`true`/`false`).
  - `semafor` mode: `null` by design, because each level is evaluated independently.
- `last_invalid_reason` and `evaluation.invalid_reason`: why evaluation was invalid (`unknown`, `no_valid_values`, etc.); `null` means valid evaluation.

### Mobile notifications (optional)
Configure in UI (options):
- Enable mobile notifications (global on/off)
- Per level (notify/limit/shutdown):
  - List of `notify.mobile_app_*` targets
  - Urgent flag (default ON for shutdown)

Behavior:
- Notifies on **every level change** (including downgrade).
- Return to normal sends to **notify** targets.
- Downgrade sends to **new level** targets and **previous level** targets.
- Report button sends a **TEST** notification to all configured targets.

## Context recovery
- Original specification: `docs/original_prompt.md`
- Session notes / change log: `docs/SESSION_NOTES.md`
- Quick workflow: `docs/PLAYBOOK.md`

## Example automation
```yaml
automation:
  - alias: "Emergency stop notification"
    trigger:
      - platform: state
        entity_id: binary_sensor.emergency_stop_active
        to: "on"
    action:
      - service: notify.notify
        data:
          title: "Emergency Stop"
          message: >-
            {{ state_attr('binary_sensor.emergency_stop_active', 'primary_reason') }}
            sensor {{ state_attr('binary_sensor.emergency_stop_active', 'primary_sensor_entity') }}
```
