# Positioning: Emergency Stop

## One-line value prop
A safety-first, UI-configurable rule engine for Home Assistant that turns complex, multi-sensor logic into a single, auditable Emergency Stop with clear levels and reports.

## Target users
- People building safety-related automations (batteries, pumps, HVAC, lab equipment, water leaks, etc.)
- Users who want complex logic without writing Python or maintaining large template chains
- Installations where clear auditability and consistent behavior matter more than flexibility hacks

## Core promise
Define rules once, evaluate them consistently, and get a single source of truth for the current safety level plus a report you can act on.

## Differentiators
- Structured rule types (numeric/binary/text) with aggregations and durations
- Semafor mode: explicit notify/limit/shutdown thresholds with per-level timing
- Latched stop with explicit reset and acknowledge flows
- Built-in reporting (basic/extended snapshot) and optional notifications
- Safety-oriented defaults and explicit unknown handling

## What it is not
- Not a general automation framework
- Not a replacement for hardware-level safety controls
- Not a free-form scripting environment

## Comparisons (high level)
- Alert/Alert2: great for alerting, but Emergency Stop focuses on safety levels, latching, and reporting.
- Node-RED / Pyscript / AppDaemon: powerful, but require building and maintaining logic flows or code.
- External rule engines: flexible, but add another runtime and separate UI.

## Messaging ideas
- "Make safety rules explicit and testable."
- "One stop, one level, one report."
- "From scattered automations to a single safety signal."
