"""Fork: backup_bundle can write the bundle to disk and prune old ones."""

import asyncio
import importlib
import json
import os
import stat
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.sofabaton_x1s import bundle_files

services = importlib.import_module("custom_components.sofabaton_x1s.services")
runtime_module = importlib.import_module("custom_components.sofabaton_x1s.runtime")

T0 = datetime(2026, 11, 15, 11, 0, 0, tzinfo=timezone.utc)
BUNDLE = {"kind": "hub_bundle", "schema_version": 5, "complete": True, "devices": [], "activities": []}


def test_save_bundle_writes_an_owner_only_file(tmp_path):
    result = bundle_files.save_bundle(tmp_path / "hub", "D7:01:84:06:45:88", BUNDLE, now=T0)

    path = tmp_path / "hub" / "d70184064588-20261115T110000Z.json"
    assert result == {"saved_path": str(path), "pruned": []}
    assert json.loads(path.read_text(encoding="utf-8")) == BUNDLE
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert not [p for p in path.parent.iterdir() if p.name.endswith(".tmp")]


def test_save_bundle_never_overwrites_a_same_second_file(tmp_path):
    first = bundle_files.save_bundle(tmp_path, "d70184064588", BUNDLE, now=T0)
    second = bundle_files.save_bundle(tmp_path, "d70184064588", {**BUNDLE, "n": 2}, now=T0)

    assert first["saved_path"] != second["saved_path"]
    assert second["saved_path"].endswith("d70184064588-20261115T110000Z-2.json")


def test_keep_prunes_only_this_hubs_oldest_bundles(tmp_path):
    for day in range(4):
        bundle_files.save_bundle(tmp_path, "d70184064588", BUNDLE, now=T0 + timedelta(days=day))
    other_hub = bundle_files.save_bundle(tmp_path, "aabbccddeeff", BUNDLE, now=T0)["saved_path"]
    (tmp_path / "notes.json").write_text("{}", encoding="utf-8")
    (tmp_path / "d70184064588-manual.json").write_text("{}", encoding="utf-8")

    result = bundle_files.save_bundle(tmp_path, "d70184064588", BUNDLE, now=T0 + timedelta(days=9), keep=2)

    kept = sorted(p.name for p in tmp_path.iterdir() if p.name.startswith("d70184064588-2"))
    assert kept == ["d70184064588-20261118T110000Z.json", "d70184064588-20261124T110000Z.json"]
    assert len(result["pruned"]) == 3
    assert os.path.exists(other_hub)
    assert (tmp_path / "notes.json").exists()
    assert (tmp_path / "d70184064588-manual.json").exists()


@pytest.mark.parametrize("raw", [0, -1, 1001, "x", True, 1.5j])
def test_validate_keep_rejects_bad_values(raw):
    with pytest.raises(ValueError):
        bundle_files.validate_keep(raw)


def test_validate_keep_accepts_omitted_and_whole_numbers():
    assert bundle_files.validate_keep(None) is None
    assert bundle_files.validate_keep("8") == 8


def test_save_bundle_needs_a_mac(tmp_path):
    with pytest.raises(ValueError, match="MAC"):
        bundle_files.save_bundle(tmp_path, "", BUNDLE, now=T0)


class _Hub:
    def __init__(self, bundle):
        self.entry_id = "entry-1"
        self.mac = None
        self._bundle = bundle

    async def async_backup_hub(self, device_ids=None):
        return dict(self._bundle)


def _call(monkeypatch, tmp_path, data, bundle=BUNDLE):
    hub = _Hub(bundle)

    async def _resolve(hass, call):
        return hub

    async def _executor(func, *args):
        return func(*args)

    monkeypatch.setattr(runtime_module, "_async_resolve_hub_from_call", _resolve)
    entry = SimpleNamespace(entry_id="entry-1", data={"mac": "d70184064588"})
    hass = SimpleNamespace(
        config=SimpleNamespace(path=lambda *parts: str(tmp_path.joinpath(*parts))),
        config_entries=SimpleNamespace(async_get_entry=lambda entry_id: entry),
        async_add_executor_job=_executor,
    )
    return asyncio.run(services._async_handle_backup_bundle(SimpleNamespace(data=data, hass=hass)))


def test_plain_backup_bundle_is_unchanged(monkeypatch, tmp_path):
    assert _call(monkeypatch, tmp_path, {"device": "hub"}) == BUNDLE
    assert not (tmp_path / "sofabaton-backups").exists()


def test_backup_bundle_save_writes_and_reports_the_path(monkeypatch, tmp_path):
    result = _call(monkeypatch, tmp_path, {"device": "hub", "save": True, "keep": 8})

    assert result["saved_path"].startswith(str(tmp_path / "sofabaton-backups" / "hub" / "d70184064588-"))
    assert result["pruned"] == []
    assert result["schema_version"] == 5
    assert json.loads(open(result["saved_path"], encoding="utf-8").read()) == BUNDLE


def test_backup_bundle_refuses_to_save_an_incomplete_bundle(monkeypatch, tmp_path):
    with pytest.raises(HomeAssistantError, match="incomplete"):
        _call(monkeypatch, tmp_path, {"device": "hub", "save": True}, bundle={**BUNDLE, "complete": False})
    assert not (tmp_path / "sofabaton-backups" / "hub").exists()


def test_keep_without_save_is_rejected(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="save"):
        _call(monkeypatch, tmp_path, {"device": "hub", "keep": 3})
