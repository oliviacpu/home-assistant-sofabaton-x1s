"""Fork: event entities for Wifi presses and hub transitions (FORK.md)."""

import asyncio
from types import SimpleNamespace

import custom_components.sofabaton_x1s.event as event_platform
from custom_components.sofabaton_x1s.const import (
    CONF_MAC,
    DOMAIN,
    PLATFORMS,
    signal_hub_events,
    signal_ip_commands,
)
from custom_components.sofabaton_x1s.event import (
    HUB_EVENT_TYPES,
    PRESS_EVENT_TYPES,
    SofabatonButtonPressEvent,
    SofabatonHubEvent,
    hub_events,
    press_event,
)
from custom_components.sofabaton_x1s.hub import SofabatonHub, hub_device_info

from tests.hub_fakes import FakeHass

ENTRY = SimpleNamespace(entry_id="entry-id", data={CONF_MAC: "aa:bb:cc:dd:ee:ff", "mdns_txt": {"HVER": "2"}}, title="Hub")


def _hub(loop):
    hass = FakeHass(loop)
    hub = SofabatonHub(hass, "entry-id", "hub-name", "127.0.0.1", 1234, {}, 9999, 10000, True, False)
    hass.data = {DOMAIN: {"entry-id": hub}}
    hub.activities = {101: {"name": "Apple TV"}, 104: {"name": "NTS"}}
    return hub


def _connect(monkeypatch, entity, hass):
    handlers: dict[str, object] = {}
    monkeypatch.setattr(
        event_platform,
        "async_dispatcher_connect",
        lambda _hass, sig, target: handlers.__setitem__(sig, target) or (lambda: None),
    )
    entity.hass = hass
    asyncio.run(entity.async_added_to_hass())
    return handlers


HTTP_RECORD = {
    "entity_id": 8,
    "entity_kind": "device",
    "entity_name": "Wifi Events",
    "command_id": "Lights dim",
    "command_index": 31,
    "command_label": "Lights dim",
    "button_label": "Lights dim",
    "press_type": "short",
    "timestamp": 1.0,
    "iso_time": "2026-11-15T00:00:00+00:00",
    "source_ip": "192.168.1.13",
    "path": "/launch/8/31",
    "body": "secret-ish body",
    "headers": {"Authorization": "x"},
    "transport": "http",
}


def test_event_is_a_registered_platform():
    assert "event" in PLATFORMS


def test_press_event_exposes_the_press_but_not_the_request():
    event_type, attrs = press_event(HTTP_RECORD)

    assert event_type == "short"
    assert attrs == {
        "device": "Wifi Events",
        "device_id": 8,
        "command": "Lights dim",
        "command_index": 31,
        "transport": "http",
    }
    assert press_event({**HTTP_RECORD, "press_type": "long"})[0] == "long"
    assert press_event(None) is None
    assert press_event({**HTTP_RECORD, "entity_id": -1})[1]["device_id"] is None


def test_hub_events_split_an_activity_switch_into_stop_then_start():
    names = {101: "Apple TV", 104: "NTS"}.get

    switch = hub_events({"type": "activity_change", "from_activity_id": 101, "to_activity_id": 104}, names)
    assert [kind for kind, _ in switch] == ["activity_stop", "activity_start"]
    assert switch[0][1]["activity"] == "Apple TV"
    assert switch[1][1]["activity"] == "NTS"
    assert switch[1][1]["from_activity"] == "Apple TV"

    start = hub_events({"type": "activity_change", "from_activity_id": None, "to_activity_id": 101}, names)
    assert [kind for kind, _ in start] == ["activity_start"]

    off = hub_events({"type": "activity_change", "from_activity_id": 104, "to_activity_id": None}, names)
    assert [kind for kind, _ in off] == ["activity_stop", "power_off"]
    assert off[1][1]["activity_id"] == 104

    assert hub_events({"type": "redundant_off"}, names) == [("redundant_off", {})]
    assert hub_events({"type": "something_else"}, names) == []
    assert hub_events(None, names) == []
    for kind, _ in switch + start + off:
        assert kind in HUB_EVENT_TYPES


def test_button_press_entity_fires_on_each_wifi_press(monkeypatch):
    loop = asyncio.new_event_loop()
    try:
        hub = _hub(loop)
        entity = SofabatonButtonPressEvent(hub, ENTRY)
        handlers = _connect(monkeypatch, entity, hub.hass)

        assert list(handlers) == [signal_ip_commands("entry-id")]
        assert entity._attr_unique_id == "aa:bb:cc:dd:ee:ff_button_press"
        assert entity.device_info == hub_device_info(hub, ENTRY)
        assert entity._attr_event_types == PRESS_EVENT_TYPES

        hub._last_ip_command = dict(HTTP_RECORD)
        handlers[signal_ip_commands("entry-id")]()
        hub._last_ip_command = {**HTTP_RECORD, "press_type": "long", "command_label": "Back hold"}
        handlers[signal_ip_commands("entry-id")]()

        assert [kind for kind, _ in entity.fired] == ["short", "long"]
        assert entity.fired[1][1]["command"] == "Back hold"
    finally:
        loop.close()


def test_hub_event_entity_fires_redundant_off_and_transitions(monkeypatch):
    loop = asyncio.new_event_loop()
    try:
        hub = _hub(loop)
        entity = SofabatonHubEvent(hub, ENTRY)
        handlers = _connect(monkeypatch, entity, hub.hass)

        assert list(handlers) == [signal_hub_events("entry-id")]
        assert entity._attr_unique_id == "aa:bb:cc:dd:ee:ff_hub_event"

        hub._last_hub_event = {"type": "redundant_off", "timestamp": 1.0}
        handlers[signal_hub_events("entry-id")]()
        hub._last_hub_event = {
            "type": "activity_change",
            "from_activity_id": 101,
            "to_activity_id": None,
            "timestamp": 2.0,
        }
        handlers[signal_hub_events("entry-id")]()

        assert [kind for kind, _ in entity.fired] == ["redundant_off", "activity_stop", "power_off"]
        assert entity.fired[2][1]["activity"] == "Apple TV"
    finally:
        loop.close()
