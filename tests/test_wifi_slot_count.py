"""Fork: configurable Wifi slot counts up to the hub model's ceiling."""

import asyncio
import importlib
from types import SimpleNamespace

import pytest
from homeassistant.exceptions import HomeAssistantError

import custom_components.sofabaton_x1s.wifi_deploy as wifi_deploy_module
from custom_components.sofabaton_x1s.command_config import (
    WIFI_EVENTS_DEVICE_KEY,
    CommandConfigStore,
    _record_slot_count,
)
from custom_components.sofabaton_x1s.hub import SofabatonHub
from custom_components.sofabaton_x1s.lib.hub_versions import HUB_VERSION_X1, HUB_VERSION_X1S, HUB_VERSION_X2
from custom_components.sofabaton_x1s.lib.proxy_wifi_device import (
    MAX_WIFI_RECORDS_VIRTUAL_IP,
    max_wifi_device_records,
    max_wifi_slot_count,
)
from custom_components.sofabaton_x1s.wifi_deploy import WifiSyncError

from tests.hub_fakes import FakeHass

services = importlib.import_module("custom_components.sofabaton_x1s.services")
runtime_module = importlib.import_module("custom_components.sofabaton_x1s.runtime")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _store_with_events(count_used: int) -> CommandConfigStore:
    store = CommandConfigStore(SimpleNamespace())
    _run(store.async_load())
    for n in range(count_used):
        _run(store.async_allocate_wifi_event("hub-1", f"Event {n + 1}"))
    return store


def test_model_ceilings():
    assert MAX_WIFI_RECORDS_VIRTUAL_IP == 255
    assert max_wifi_device_records(HUB_VERSION_X1) == 100
    assert max_wifi_device_records(HUB_VERSION_X1S) == 255
    assert max_wifi_device_records(HUB_VERSION_X2) == 255
    assert max_wifi_device_records(None) == 100
    assert max_wifi_slot_count(HUB_VERSION_X1S, single_record=True) == 255
    assert max_wifi_slot_count(HUB_VERSION_X1S, single_record=False) == 127
    assert max_wifi_slot_count(HUB_VERSION_X1, single_record=True) == 100
    assert max_wifi_slot_count(HUB_VERSION_X1, single_record=False) == 50


def test_persisted_counts_past_100_are_kept():
    # Upstream reset anything past 100 to the default (25), which a sync
    # would then deploy, deleting the rest.
    assert _record_slot_count(WIFI_EVENTS_DEVICE_KEY, 128) == 128
    assert _record_slot_count(WIFI_EVENTS_DEVICE_KEY, 256) == 25


def test_growing_the_events_record_pads_it_and_flags_a_sync():
    store = _store_with_events(3)
    before = _run(store.async_get_hub_config("hub-1", device_key=WIFI_EVENTS_DEVICE_KEY))

    result = _run(store.async_set_record_slot_count("hub-1", WIFI_EVENTS_DEVICE_KEY, 128, max_slot_count=255))

    after = _run(store.async_get_hub_config("hub-1", device_key=WIFI_EVENTS_DEVICE_KEY))
    assert result == {"device_key": WIFI_EVENTS_DEVICE_KEY, "previous_slot_count": 25, "slot_count": 128}
    assert after["slot_count"] == 128
    assert len(after["commands"]) == 128
    assert [c["name"] for c in after["commands"][:3]] == ["Event 1", "Event 2", "Event 3"]
    assert after["commands"][127]["name"] == "Command 128"
    assert after["commands_hash"] and after["commands_hash"] != before["commands_hash"]


def test_shrinking_refuses_to_cut_a_configured_slot():
    store = _store_with_events(5)
    with pytest.raises(ValueError, match="slots 5 are still in use"):
        _run(store.async_set_record_slot_count("hub-1", WIFI_EVENTS_DEVICE_KEY, 4, max_slot_count=255))

    result = _run(store.async_set_record_slot_count("hub-1", WIFI_EVENTS_DEVICE_KEY, 5, max_slot_count=255))
    assert result["slot_count"] == 5


@pytest.mark.parametrize("raw", [0, 256, "x", True, None])
def test_bad_counts_are_rejected(raw):
    store = _store_with_events(1)
    with pytest.raises(ValueError):
        _run(store.async_set_record_slot_count("hub-1", WIFI_EVENTS_DEVICE_KEY, raw, max_slot_count=255))


def test_count_past_the_model_ceiling_is_rejected():
    store = _store_with_events(1)
    with pytest.raises(ValueError, match="between 1 and 100"):
        _run(store.async_set_record_slot_count("hub-1", WIFI_EVENTS_DEVICE_KEY, 101, max_slot_count=100))


class _Hub:
    entry_id = "hub-1"

    def __init__(self, version):
        self.version = version


def _call_service(monkeypatch, store, hub, data):
    async def _resolve(hass, call):
        return hub

    async def _get_store(hass):
        return store

    monkeypatch.setattr(runtime_module, "_async_resolve_hub_from_call", _resolve)
    monkeypatch.setattr(runtime_module, "_async_get_command_config_store", _get_store)
    monkeypatch.setattr(services, "async_dispatcher_send", lambda *a, **k: None)
    return asyncio.run(services._async_handle_set_wifi_slot_count(SimpleNamespace(data=data, hass=SimpleNamespace())))


def test_service_targets_wifi_events_by_default_with_the_hub_ceiling(monkeypatch):
    store = _store_with_events(2)

    result = _call_service(monkeypatch, store, _Hub(HUB_VERSION_X1S), {"device": "hub", "slot_count": 150})

    assert result["slot_count"] == 150
    assert result["max_slot_count"] == 255
    with pytest.raises(ValueError, match="between 1 and 100"):
        _call_service(monkeypatch, store, _Hub(HUB_VERSION_X1), {"device": "hub", "slot_count": 150})


def test_service_without_an_events_record_says_so(monkeypatch):
    store = CommandConfigStore(SimpleNamespace())
    _run(store.async_load())
    with pytest.raises(HomeAssistantError, match="create an event first"):
        _call_service(monkeypatch, store, _Hub(HUB_VERSION_X1S), {"device": "hub", "slot_count": 30})


def _deploy_hub(version):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    hub = SofabatonHub(FakeHass(loop), "entry-id", "hub-name", "127.0.0.1", 1234, {}, 9999, 10000, True, False)
    hub.version = version
    return loop, hub


class _PastTheGuard(Exception):
    pass


def test_deploy_stops_on_a_count_past_the_model_ceiling(monkeypatch):
    loop, hub = _deploy_hub(HUB_VERSION_X1)
    try:
        payload = {"commands": [], "slot_count": 150, "commands_hash": "x"}
        with pytest.raises(WifiSyncError, match="at most 100"):
            loop.run_until_complete(
                hub.async_sync_command_config(command_payload=payload, request_port=8060, device_key="haevents")
            )
    finally:
        loop.close()


def test_deploy_accepts_a_count_past_100_on_x1s(monkeypatch):
    loop, hub = _deploy_hub(HUB_VERSION_X1S)

    def _stop(*_a, **_k):
        raise _PastTheGuard

    monkeypatch.setattr(wifi_deploy_module, "count_configured_command_slots", _stop)
    try:
        payload = {"commands": [], "slot_count": 150, "commands_hash": "x"}
        with pytest.raises(_PastTheGuard):
            loop.run_until_complete(
                hub.async_sync_command_config(command_payload=payload, request_port=8060, device_key="haevents")
            )
    finally:
        loop.close()
