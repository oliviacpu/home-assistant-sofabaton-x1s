# custom_components/sofabaton_x1s/event.py
"""Event entities for remote presses and hub transitions.

Both feed off dispatcher signals the integration already sends: Wifi
presses (``signal_ip_commands``, the record behind the Wifi commands
sensor) and hub events (``signal_hub_events``, the feed of the Control
Panel's Hub Events tab). They only add a stable automation surface; the
sensor, the configured Actions and the hooks behave as before.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MAC, DOMAIN, signal_hub_events, signal_ip_commands
from .hub import SofabatonHub, hub_device_info

PRESS_EVENT_TYPES = ["short", "long"]
HUB_EVENT_TYPES = ["activity_start", "activity_stop", "power_off", "redundant_off"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub: SofabatonHub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SofabatonButtonPressEvent(hub, entry),
            SofabatonHubEvent(hub, entry),
        ]
    )


def press_event(record: dict[str, Any] | None) -> tuple[str, dict[str, Any]] | None:
    """The ``(event_type, attributes)`` for one Wifi press record.

    Only the press itself is exposed: the record's raw HTTP path, headers
    and body stay out of the state machine.
    """

    if not record:
        return None
    press_type = "long" if record.get("press_type") == "long" else "short"
    device_id = record.get("entity_id")
    return press_type, {
        "device": record.get("entity_name"),
        "device_id": device_id if isinstance(device_id, int) and device_id >= 0 else None,
        "command": record.get("command_label"),
        "command_index": record.get("command_index"),
        "transport": record.get("transport") or "http",
    }


def hub_events(event: dict[str, Any] | None, activity_name) -> list[tuple[str, dict[str, Any]]]:
    """Split one hub-event record into the event entity's event types.

    An ``activity_change`` becomes the stop of the old activity (when one
    ran and it differs from the new one), then the start of the new one or,
    with no new activity, ``power_off``: the order the configured hooks run
    in (``SofabatonHub._on_activity_change``).
    """

    if not event:
        return []
    kind = event.get("type")
    if kind == "redundant_off":
        return [("redundant_off", {})]
    if kind != "activity_change":
        return []

    old_id = event.get("from_activity_id")
    new_id = event.get("to_activity_id")
    base = {
        "from_activity_id": old_id,
        "from_activity": activity_name(old_id) if old_id is not None else None,
        "to_activity_id": new_id,
        "to_activity": activity_name(new_id) if new_id is not None else None,
    }
    out: list[tuple[str, dict[str, Any]]] = []
    if old_id is not None and old_id != new_id:
        out.append(("activity_stop", {**base, "activity_id": old_id, "activity": base["from_activity"]}))
    if new_id is not None:
        out.append(("activity_start", {**base, "activity_id": new_id, "activity": base["to_activity"]}))
    elif old_id is not None:
        out.append(("power_off", {**base, "activity_id": old_id, "activity": base["from_activity"]}))
    return out


class _SofabatonEvent(EventEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hub: SofabatonHub, entry: ConfigEntry, key: str) -> None:
        self._hub = hub
        self._entry = entry
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.data[CONF_MAC]}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        return hub_device_info(self._hub, self._entry)


class SofabatonButtonPressEvent(_SofabatonEvent):
    """A press of a Wifi Event or Wifi Device command reached Home Assistant."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = PRESS_EVENT_TYPES

    def __init__(self, hub: SofabatonHub, entry: ConfigEntry) -> None:
        super().__init__(hub, entry, "button_press")

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal_ip_commands(self._hub.entry_id), self._handle_press)
        )

    @callback
    def _handle_press(self) -> None:
        fired = press_event(self._hub.get_last_ip_command())
        if fired is None:
            return
        self._trigger_event(*fired)
        self.async_write_ha_state()


class SofabatonHubEvent(_SofabatonEvent):
    """The hub started or stopped an activity, powered off, or saw OFF while off."""

    _attr_event_types = HUB_EVENT_TYPES

    def __init__(self, hub: SofabatonHub, entry: ConfigEntry) -> None:
        super().__init__(hub, entry, "hub_event")

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal_hub_events(self._hub.entry_id), self._handle_hub_event)
        )

    @callback
    def _handle_hub_event(self) -> None:
        for event_type, attributes in hub_events(self._hub.get_last_hub_event(), self._activity_name):
            self._trigger_event(event_type, attributes)
            self.async_write_ha_state()

    def _activity_name(self, activity_id: Any) -> str | None:
        try:
            return self._hub.get_activity_name_by_id(int(activity_id))
        except (TypeError, ValueError):
            return None
