# Emergency Stop — Aktuální přehled integrace (CS)

Tento dokument popisuje **dynamický rule engine** v integraci `emergency_stop`.

Integrace je bezpečnostně orientovaná. Vyhodnocuje uživatelsky definovaná pravidla nad libovolnými entitami, poskytuje deterministické výstupy a detailní report.

## Základní koncepty

Koordinátor buduje jeden agregovaný stav:
- `active`: zda je aktivní alespoň jedno pravidlo.
- `level`: nejvyšší aktivní úroveň.
- `primary_*`: detail primárního (root-cause) pravidla.
- `active_events`: seznam aktivních pravidel.

Úrovně:
- `notify`: informativní.
- `limit`: omezení / varování.
- `shutdown`: zastavení / odpojení.

Pokud je aktivních více pravidel, platí nejvyšší úroveň (`shutdown` > `limit` > `notify`).

## Entity

### Binary senzory

1. `binary_sensor.emergency_stop_active`
- Centrální indikátor „něco je špatně“.
- On, pokud je aktivní jakékoli pravidlo.
- Klíčové atributy: `error_level`, `primary_*`, `active_events`, `active_reasons`,
  `active_levels`, `events_by_reason`, `acknowledged`, `last_update`, `latched_since`.

2. `binary_sensor.emergency_stop_shutdown`
- Jediný signál, ze kterého se smí spínat reálná zátěž.
- On, pokud pravidla vyhodnotí úroveň `shutdown`. Simulace ho nikdy nezvedne a nižší
  úroveň také ne — na rozdíl od `emergency_stop_active`, který svítí už od `notify`.
- Klíčové atributy: `error_level`, `primary_*`, `latched_since`, `simulation_active`
  a `active_events` filtrované na shutdown události.
- Pravidlo pro zapojení: spouštěj na explicitní `on`. Entita je `unavailable`, kdykoli
  koordinátor nemůže aktualizovat, takže podmínka „není off“ by to čtla jako poplach.

3. `binary_sensor.emergency_stop_protection_degraded`
- Zviditelňuje stav, kdy ochrana neslyší.
- On, pokud shutdown pravidlo delší dobu než grace nemá dost důvěryhodných vstupů na
  rozhodnutí (zastaralé, mimo rozsah, nekonečné nebo chybějící hodnoty).
- Klíčové atributy: `degraded_rules` s `trusted_sources`, `untrusted_inputs`,
  `required_sources` a `blind_for_seconds` pro každé pravidlo.
- Důvod: nedůvěryhodný vstup se záměrně nikdy nebere jako porušení — to by vypnulo dům
  při každém výpadku integrace — takže bez tohoto signálu by ochrana mohla tiše přestat
  fungovat.

4. `binary_sensor.emergency_stop_<rule_id>`
- Přímý trigger pro konkrétní pravidlo.
- On, pokud je dané pravidlo aktivní.
- Atributy obsahují konfiguraci pravidla i runtime stav.
- Interpretace runtime hodnot:
  - `last_aggregate` / `evaluation.aggregate`: poslední agregovaná hodnota pravidla.
  - U numerického pravidla s `aggregate: max` jde o nejvyšší hodnotu ze všech vybraných entit.
  - `last_entity` / `evaluation.entity_id`: entita, která agregovanou hodnotu dala (pro `max`/`min`).
  - `last_match` / `evaluation.match`: v režimu `simple` boolean; v režimu `semafor` je záměrně `null`.
  - `last_invalid_reason` / `evaluation.invalid_reason`: důvod nevalidního vyhodnocení (`unknown`, `no_valid_values` atd.); `null` znamená validní vstupy.

### Senzory

1. `sensor.emergency_stop_level`
- Nejvyšší aktuální úroveň.
- Stavy: `normal`, `notify`, `limit`, `shutdown`.

### Tlačítka

1. `button.emergency_stop_reset`
- Resetuje latched stav a timery.

2. `button.emergency_stop_report` (diagnostické)
- Vytvoří report do `/media/emergency-stop/logs`.
- Pokud je nastaven e-mail, report odešle.

## Služby

- `emergency_stop.reset`: reset latched stavu a timerů.
- `emergency_stop.acknowledge`: nastaví `acknowledged = true` bez resetu.
- `emergency_stop.generate_report`: vytvoří JSON report (a případně odešle e‑mail).
- `emergency_stop.export_rules`: uloží JSON export pravidel do `/media/emergency-stop/config`.
- `emergency_stop.test_notification`: odešle test mobilní notifikace pro vybraný level.
- `emergency_stop.simulate_level`: simuluje level (notify/limit/shutdown/normal) pro testy.
- `emergency_stop.clear_simulation`: zruší aktivní simulaci.

Export/import nastavení je dostupný v Options UI (není jako service).
Cesta exportu nastavení:
- `/media/emergency-stop/config/emergency_stop_settings_<entry_id>_<timestamp>.json`

Čistá instalace začíná volbou režimu nastavení:
- `Custom setup`: ruční nastavení + průvodce pravidly.
- `Import settings + rules`: zadání názvů exportovaných souborů nastavení/pravidel z `/media/emergency-stop/config`.

## E‑mail (volitelně)

Nastavuje se přes Brevo (API key, sender, výchozí recipient). Vyberte úrovně e‑mailu (notify/limit/shutdown) a volitelně nastavte recipienty per level, které přepíší výchozí. Prázdné Brevo hodnoty znamenají vypnuto.
Globální nastavení jsou v UI rozdělená do sekcí: Report, Poskytovatel e‑mailu (Brevo), Směrování e‑mailu podle úrovně, Mobilní notifikace.

Při přechodu `off -> on` se vytvoří report a odešle e‑mail s JSON reportem v těle. E‑maily se posílají jen pro povolené úrovně a pouze pokud je pro danou úroveň nastaven recipient (nebo existuje výchozí). Další e‑mail se pošle až po návratu do neaktivního stavu a opětovné aktivaci.

Subject: `Emergency Stop [level]`. `shutdown` má high priority.

## Úprava pravidel

Navigace v Options:
- Settings → Devices & Services → Emergency Stop → Configure
- Hlavní rozcestník:
  - `Settings management`
  - `Rules management`

Akce v `Settings management`:
- `Edit settings`
- `Import settings`
- `Export settings`

Akce v `Rules management`:
- `Add`
- `Edit`
- `Delete`
- `Import`
- `Export`
- `Back`

`Back` v Rules management uloží options a vrátí vás na hlavní rozcestník.
Import/export nastavení obsahuje i Brevo konfiguraci (včetně API key), proto exportovaný JSON považujte za citlivý.
Import používá názvy souborů z `/media/emergency-stop/config` (stejný adresář jako export).

## Report detail

- `basic`: pouze konfigurace + rule inputs.
- `extended`: všechny `sensor` a `binary_sensor` entity vybraných domén (stav + atributy).
- Volitelně: konkrétní entity (libovolná doména).
- Volitelná retence reportů: max počet souborů nebo max stáří v dnech (0 = vypnuto).

## Mobilní notifikace (volitelné)

Nastavují se v options:
- zapnutí/vypnutí globálně,
- per level (notify/limit/shutdown):
  - seznam `notify.mobile_app_*` cílů
  - urgent flag (default ON pro shutdown)

Chování:
- posílá se při **každé změně levelu** (včetně poklesu),
- při poklesu se posílá na cíle **nového levelu** i **původního levelu**,
- návrat na `normal` posílá na cíle `notify`,
- report button posílá **TEST** notifikaci na všechna zařízení.
- notifikace i e‑mail běží mimo evaluační cyklus (s timeoutem 3 s), takže pomalá notify
  služba nezdrží ani další vyhodnocení, ani publikaci stavu, na který reaguje fyzický stop.

Urgent payload:
- iOS: `push.interruption-level: critical`
- Android: `priority: high`, `ttl: 0`

## Vyhodnocování pravidel

Každé pravidlo se vyhodnocuje podle:
- `interval_seconds`: jak často se vyhodnocuje.
- `duration_seconds`: jak dlouho musí podmínka trvat.

### Režim závažnosti

Každé pravidlo má režim závažnosti:
- **Simple**: jedna podmínka + `duration_seconds` → pravidlo aktivuje jednu úroveň (`notify` / `limit` / `shutdown`).
- **Semafor**: více úrovní v jednom pravidle (notify/limit/shutdown), každá má vlastní threshold + duration.
  - Směr: `higher_is_worse` nebo `lower_is_worse`.
  - Pouze pro numerická pravidla a binární pravidla s agregací `count`.

### Struktura konfigurace pravidel (config entry)

Pravidla jsou uložená v `config.rules` jako seznam slovníků. Společná pole:
- `rule_id`, `rule_name`, `data_type`, `entities`, `aggregate`
- `interval_seconds`, `latched`, `unknown_handling`
- `notify_email`, `notify_mobile`
- `severity_mode` (`simple` nebo `semafor`)
- pouze text: `text_case_sensitive`, `text_trim`

Simple režim přidává:
- `condition`
- `thresholds` (1 hodnota, nebo 2 hodnoty pro `between`)
- `duration_seconds`
- `level`

Semafor režim přidává:
- `direction` (`higher_is_worse` / `lower_is_worse`)
- `levels`: `notify` / `limit` / `shutdown`, každá má `threshold` + `duration_seconds`

Příklad (simple numerické pravidlo):
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

Příklad (semafor numerické pravidlo):
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

### Příklad (rychlý smoke test Semaforu)

1) Vytvoř helper: `input_number.test_voltage`.
2) Nastav pravidlo Emergency Stop:
   - Data type: Numeric
   - Entities: `input_number.test_voltage`
   - Aggregate: Max
   - Severity mode: Semafor
   - Direction: Higher is worse
   - Notify: 3.50 po 3 s, Limit: 3.60 po 3 s, Shutdown: 3.80 po 3 s
   - Interval: 1 s, Latched: ON, Unknown handling: ignore
3) Nastav hodnotu na 3.55, počkej 3 s → level `notify`.
4) Nastav na 3.65, počkej 3 s → level `limit`.
5) Nastav na 3.85, počkej 3 s → level `shutdown`.
6) Pokud je latched ON, nejvyšší dosažený level drží až do resetu.

### Typy pravidel

**Numerická pravidla**
- Entity s parsovatelným číslem.
- Agregace: `max`, `min`, `sum`, `avg`.
- Podmínky: `gt`, `gte`, `lt`, `lte`, `between` (inkluzivně), `eq`.

**Binární pravidla**
- Entity se stavem `on/off`.
- Agregace: `any`, `all`, `count`.
- Podmínky: `is_on`, `is_off` (pro any/all), numerické porovnání pro count.

**Textová pravidla**
- Entity se stavem textu.
- Agregace: `any`, `all`.
- Podmínky: `contains`, `equals`.
- Defaultně case‑insensitive + trim whitespace.

### Unknown handling

Pro `unknown`, `unavailable`, chybějící nebo neplatné hodnoty:
- `ignore`: resetuje timer; pravidlo je neaktivní.
- `treat_ok`: bere jako neporušení.
- `treat_violation`: bere jako porušení (fail‑safe).

### Latched

Pokud `latched=true`, pravidlo zůstává aktivní až do resetu, i když podmínka zmizí.
V režimu semafor zůstává latchnutá nejvyšší dosažená úroveň.

Latch se ukládá a přežije restart, takže reload, který spouští každé uložení options,
už aktivní poplach nesmaže. Uložený latch se zahodí jen tehdy, když se od jeho vyhlášení
změnila rozhodující konfigurace pravidla (entity, prahy, doba, úroveň, kvórum, flap
nastavení) - poplach vyhlášený proti jiným prahům o těch nových nic neříká.

### Důvěryhodnost vstupů

Pojistky na úrovni pravidla, ve výchozím stavu vypnuté. Pravidlo, které může dosáhnout
`shutdown`, by je mít mělo - bez nich rozhoduje podle jednoho neověřeného čtení senzoru.

| Pole | Význam |
|---|---|
| `max_age_seconds` | Starší vstup je `stale` a zahodí se. Věk se bere z `last_reported`, pak `last_updated`/`last_changed`; nezjistitelný věk se považuje za zastaralý. |
| `value_min` / `value_max` | Plausibilní rozsah; mimo něj je vstup `out_of_range`. `nan`/`inf` jsou vždy `not_finite`. |
| `max_step` | Největší přijatá změna mezi vzorky; větší je `jump`, ale jen několikrát po sobě, aby reálný rychlý růst nezůstal navěky skrytý. |
| `min_sources` | Kvórum: podmínka musí platit pro tolik vstupů nezávisle (agregace `max`/`min`). Méně důvěryhodných vstupů než kvórum dá `quorum_not_met` místo rozhodnutí. Per-úroveň: `levels.<level>.min_sources`. |
| `recovery_seconds` | Jak dlouho musí být vstup zdravý, než se zahodí naběhlá doba porušení; jinak každé krátké zotavení začíná od nuly. |
| `flap_window_seconds` + `flap_budget_seconds` | Kumulativní rozpočet poruchy v klouzavém okně, pro vstupy, které nikdy nespadnou na dost dlouho v jednom kuse, ale celkově jsou nepoužitelné. Nutné nastavit oba. |

`unknown_handling: treat_violation` je na shutdown pravidle odmítnuto (options flow,
import i načtení): vyhlásí se přesně tehdy, když vstupy chybí, tedy když je degradovaná
vrstva, ne když má baterie problém. Takové situace zvedají
`binary_sensor.emergency_stop_protection_degraded`.