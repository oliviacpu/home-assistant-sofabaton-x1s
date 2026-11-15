# About this fork

A personal fork of [m3tac0de/home-assistant-sofabaton-x1s](https://github.com/m3tac0de/home-assistant-sofabaton-x1s),
installed through HACS on one Home Assistant instance that drives a Sofabaton X1S hub. Its `main` is an upstream release
tag plus the changes listed below. Upstream's README, `CONTRIBUTING.md` and `docs/` still apply.

## Rules for changes

- **Nothing is sent upstream.** Changes still stay upstream-shaped: one change and its tests per commit, so any one of
  them could be cherry-picked onto a branch from an upstream tag later.
- **Upstream behaviour stays the default.** A new option does nothing until it's set; new entities only add to what
  upstream creates; existing entity ids, stores and wire behaviour don't change.
- **Tests:** `uv venv .venv-py313 --python 3.13 && uv pip install --python .venv-py313 pytest`, `npm ci`, then
  `.venv-py313/bin/python -m pytest -q tests`. On a macOS workstation two tests that open real sockets with a chosen
  source address fail before any fork change (`test_call_me_packet_source_matches_callback_over_real_udp`,
  `test_app_session_uses_the_selected_source_over_real_tcp`); the release workflow runs the whole suite on Linux.
- **Tags** start with `oliviacpu-` and name the day: `oliviacpu-2026.11.15`, with `.2` for a second one that day.
  Upstream's tags are bare versions (`0.7.2`), so the two never collide.

## Releases and HACS

- **Base:** upstream `0.7.2`. To take a newer upstream release: `git fetch upstream --tags`, branch from `main`,
  `git merge <tag>`, open a pull request in this repository, merge it, then release. The merge keeps the fork's commits.
- **Release:** pushing an `oliviacpu-*` tag runs `.github/workflows/fork-release.yml`. It runs the Python suite, builds
  the frontend bundles, zips `custom_components/sofabaton_x1s` the way upstream's `release.yml` does, and creates a
  GitHub Release with `sofabaton_x1s.zip` attached. HACS needs that asset (`hacs.json` has `zip_release: true`), so
  pushing a tag is releasing it.
- **Version:** `manifest.json` carries `<upstream version>-oliviacpu.<YYYYMMDD>` (`.N` appended for a second tag that
  day); the release workflow refuses a tag whose date doesn't match. Bump it in the commit before tagging.
- **Install:** HACS → custom repository `oliviacpu/home-assistant-sofabaton-x1s` (Integration). The domain is still
  `sofabaton_x1s`, so the config entry, entities and stores carry over from an upstream install. Remove the upstream
  repository from HACS first: two HACS repositories writing one folder overwrite each other.
- **Rollback:** download an older release of this repository in HACS, or remove it and add upstream back.
- **Upstream's workflows are disabled here** (`gh workflow disable <name> --repo oliviacpu/home-assistant-sofabaton-x1s`).
  Their release jobs publish to PyPI, npm and GHCR with secrets this fork doesn't have, and `release.yml` would attach a
  second zip to every fork release. After merging upstream, check `gh workflow list --all` for new ones and disable
  them too.

## Changes in this fork

Newest first.

### Wifi slot counts are a setting, up to the hub's protocol ceiling (2026-11-15)
- **What it adds:** `sofabaton_x1s.set_wifi_slot_count` sets the slot count of the Wifi Events device (default) or a
  named Wifi Device through the store. Upstream fixes it at record creation (25 events, 10 per device), so raising it
  meant hand-editing `.storage/sofabaton_x1s.command_config` (this install went 25 → 27 → 50 → 100 that way).
- **Cause (two caps):** upstream clamps persisted counts at the benched 100 (`_MAX_RECORD_SLOT_COUNT`) and **resets**
  anything past it to the default, so a hand-set 128 would have synced back down to 25 and deleted the rest; the
  X1S/X2 create path also truncated every device to the X1 key-id table's 100 entries.
- **Change:** `lib/proxy_wifi_device.py` gains `max_wifi_device_records` / `max_wifi_slot_count`: X1 keeps its 100-entry
  table; X1S/X2 (virtual-IP flow, one-byte command id) go to 255, halved for devices with long records. The persisted
  clamp is 255; the deploy guard in `wifi_deploy.py` uses the model's ceiling and now stops a sync with a count past
  it instead of falling back to 10 (which deployed, so deleted, all but ten slots). Shrinking is refused while a cut
  slot is in use. `command_config.py` (`async_set_record_slot_count`), `services.py`, `services.yaml`,
  `translations/en.json`, `docs/actions.md`, `docs/wifi_commands.md`. Tests: `tests/test_wifi_slot_count.py`.
- **Live check:** an X1S accepting more than 100 records is not benched yet (upstream validated 1..100).
- **Upstream:** not sent.

### Remote and Wi-Fi firmware sensors (2026-11-15)
- **What it adds:** diagnostic `sensor.<hub>_remote_firmware` (X1/X1S) and `sensor.<hub>_wifi_firmware`. Upstream
  documents the version exchange (`REQ_VERSION` 0x0058 → `WIFI_FW` 0x0359 + `INFO_BANNER` 0x112F) but never sends or
  decodes it, so neither version was visible; the device registry only shows the hub firmware from the banner.
- **Change:** `lib/proxy_version_info.py` (new mixin; `x1_proxy.py` stays under its 2000-line budget) decodes both
  frames, `VersionInfoHandler` in `lib/opcode_handlers.py` feeds it from every H→A frame (so the official app's version
  screen is captured too), and `_async_initial_sync` in `hub.py` asks once, before the catalog bursts. The engine
  methods are triaged as engine-only in `lib/aio.py`. Sensors in `sensor.py`, names in `translations/en.json`,
  `docs/entities.md`. Tests: `tests/test_version_info.py`.
- **Upstream:** not sent.

### `backup_bundle` can save the bundle to disk (2026-11-15)
- **What it adds:** `save: true` writes the bundle to `<config>/sofabaton-backups/hub/<hub MAC>-<UTC time>.json`
  (mode 0600, written to a temporary name and renamed) and `keep: N` deletes that hub's older files there. Upstream
  only returns the bundle, and an automation has no built-in way to write a response to a file, so scheduled backups
  weren't possible. A bundle that isn't `complete` (the Sofabaton app holding the hub, for one) is refused with an
  error instead of being saved as a backup. Without `save` the action behaves exactly as upstream's.
- **Change:** `bundle_files.py` (new, no Home Assistant imports), `_async_handle_backup_bundle` in `services.py`,
  `services.yaml`, `translations/en.json`, `docs/actions.md`. Tests: `tests/test_backup_bundle_save.py`.
- **Upstream:** not sent.

### Event entities for remote presses and hub transitions (2026-11-15)
- **What it adds:** `event.<hub>_button_press` fires on every Wifi Command or Wifi Event press (`short`/`long`, with
  device, command and transport). `event.<hub>_hub_event` fires on `activity_start`, `activity_stop`, `power_off` and
  `redundant_off` (OFF pressed while already off). Upstream exposes presses only through a sensor that pulses for 0.3 s,
  and hub events only to the Control Panel and its configured Actions, so neither was a dependable automation trigger.
- **Change:** `event.py` (new), `"event"` in `PLATFORMS` (`const.py`), names in `translations/en.json`,
  `docs/entities.md`. Both entities subscribe to dispatcher signals upstream already sends (`signal_ip_commands`,
  `signal_hub_events`); the sensor, Actions and hooks are untouched. The press record's raw HTTP path, headers and body
  are not copied into the state machine. Tests: `tests/test_event_platform.py`, plus the pinned key list in
  `tests/test_backend_translations.py` and an `event` stub in `tests/conftest.py`.
- **Upstream:** not sent.

<!-- Entry format:
### Short title (YYYY-MM-DD)
- **What it adds or fixes:** the problem.
- **Cause:** what in upstream produced it, when it's a fix.
- **Change:** what changed, with the files.
- **Upstream:** not sent.
-->
