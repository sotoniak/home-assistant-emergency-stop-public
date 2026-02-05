# Emergency Stop (Home Assistant)

Custom integration for Home Assistant that evaluates **dynamic, user-defined rules** over any entities and latches a central "Emergency Stop" when configured conditions are violated.

## Pitch
Emergency Stop is a safety-first rule engine for Home Assistant: define numeric/binary/text rules with aggregations and time-based conditions, then latch a central stop with clear levels (`notify`/`limit`/`shutdown`) and full reports. It focuses on correctness and debuggability over convenience.

## Features
- Config Flow UI setup (no YAML required)
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
- Reset and report button entities

## Installation (manual / HACS custom repository)
1. Copy `custom_components/emergency_stop` into `/config/custom_components/emergency_stop/`.
2. Restart Home Assistant.
3. Add the integration: **Settings → Devices & Services → Add Integration → Emergency Stop**.

## Configuration
During setup:
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
- To edit, delete, or import rules later: **Settings → Devices & Services → Emergency Stop → Configure**, then choose **Edit**, **Delete**, or **Import** in the rules step.
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

### Entities
- `binary_sensor.emergency_stop_active`
- `binary_sensor.emergency_stop_<rule_id>` (one per rule)
- `sensor.emergency_stop_level` (returns `normal` when no violations are active)
- `button.emergency_stop_reset`
- `button.emergency_stop_report`

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

## Documentation
- Quick workflow: `docs/PLAYBOOK.md`
- Integration overview (EN): `docs/INTEGRATION_OVERVIEW.en.md`
- Integration overview (CS): `docs/INTEGRATION_OVERVIEW.cs.md`

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
