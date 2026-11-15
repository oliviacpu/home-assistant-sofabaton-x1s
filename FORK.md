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

<!-- Entry format:
### Short title (YYYY-MM-DD)
- **What it adds or fixes:** the problem.
- **Cause:** what in upstream produced it, when it's a fix.
- **Change:** what changed, with the files.
- **Upstream:** not sent.
-->
