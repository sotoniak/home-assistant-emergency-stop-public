# Playbook - Working With Codex

## Resume quickly after a break
Ask:
- "Load context recovery skill and summarize the state."

Codex should:
1) Read `docs/original_prompt.md`
2) Read `docs/SESSION_NOTES.md`
3) Run `git status --short`
4) Summarize the current state

## Normal workflow
1) Describe the change you want.
2) Codex edits files.
3) If you want tests, explicitly say: "Run tests".
4) If you want git actions, explicitly say: "Commit" or "Push".

## Where to look
- Project notes: `docs/SESSION_NOTES.md`
- Original spec: `docs/original_prompt.md`
- Integration code: `custom_components/emergency_stop/`
- Tests: `tests/`

## Install to Home Assistant (manual)
1) Copy `custom_components/emergency_stop/` to `/config/custom_components/emergency_stop/`.
2) Restart Home Assistant.
3) Add integration: Settings → Devices & Services → Add Integration → Emergency Stop.

## Integration icon (brand tile)
- The integration tile icon comes from the Home Assistant Brands repository.
- Local `icon.svg`/`logo.svg` files in `custom_components` are not enough for the tile icon.
- To show a custom tile icon, submit a PR to `home-assistant/brands` with `custom_integrations/emergency_stop/icon.png` and `logo.png` (follow brands repo guidelines).
