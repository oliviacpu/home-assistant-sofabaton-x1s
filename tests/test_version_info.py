"""Fork: the hub's Wi-Fi module firmware from the version exchange (FORK.md)."""

from types import SimpleNamespace

from custom_components.sofabaton_x1s.lib.aio import engine_method_triage
from custom_components.sofabaton_x1s.lib.frame_handlers import frame_handler_registry
from custom_components.sofabaton_x1s.lib.hub_versions import HUB_VERSION_X1S
from custom_components.sofabaton_x1s.lib.opcode_handlers import VersionInfoHandler
from custom_components.sofabaton_x1s.lib.protocol_const import OP_INFO_BANNER, OP_REQ_VERSION, OP_WIFI_FW
from custom_components.sofabaton_x1s.lib.x1_proxy import X1Proxy
from custom_components.sofabaton_x1s.sensor import SofabatonFirmwareSensor


def test_wifi_fw_frame_gives_the_wifi_firmware():
    proxy = X1Proxy("127.0.0.1", hub_version=HUB_VERSION_X1S)
    assert proxy.get_version_info() == {}

    # An X1S on hub firmware 5 answered REQ_VERSION with this frame (live 2026-11-15).
    proxy.record_version_payload(OP_WIFI_FW, bytes([2, 1, 5]))

    assert proxy.get_version_info() == {"wifi_firmware": "2.1.5"}
    assert proxy._version_info_event.is_set()


def test_other_and_short_frames_are_ignored():
    proxy = X1Proxy("127.0.0.1", hub_version=HUB_VERSION_X1S)
    proxy.record_version_payload(OP_WIFI_FW, b"\x01")
    proxy.record_version_payload(OP_INFO_BANNER, bytes(17))
    assert proxy.get_version_info() == {}
    assert not proxy._version_info_event.is_set()


def test_version_handler_takes_wifi_fw_from_the_hub_only():
    assert VersionInfoHandler in {type(h) for h in frame_handler_registry.iter_for(OP_WIFI_FW, "H→A")}
    assert VersionInfoHandler not in {type(h) for h in frame_handler_registry.iter_for(OP_WIFI_FW, "A→H")}
    assert VersionInfoHandler not in {type(h) for h in frame_handler_registry.iter_for(OP_INFO_BANNER, "H→A")}


def test_fetch_version_info_asks_once_and_stops_at_wifi_fw(monkeypatch):
    proxy = X1Proxy("127.0.0.1", hub_version=HUB_VERSION_X1S)
    sent = []

    def _enqueue(opcode, payload=b"", **kwargs):
        sent.append(opcode)
        proxy.record_version_payload(OP_WIFI_FW, bytes([2, 1, 5]))
        return True

    monkeypatch.setattr(proxy, "can_issue_commands", lambda: True)
    monkeypatch.setattr(proxy, "enqueue_cmd", _enqueue)

    assert proxy.fetch_version_info(timeout=5.0) == {"wifi_firmware": "2.1.5"}
    assert sent == [OP_REQ_VERSION]


def test_fetch_version_info_does_not_ask_while_the_app_holds_the_hub(monkeypatch):
    proxy = X1Proxy("127.0.0.1", hub_version=HUB_VERSION_X1S)
    proxy.record_version_payload(OP_WIFI_FW, bytes([1, 0, 0]))
    monkeypatch.setattr(proxy, "can_issue_commands", lambda: False)
    monkeypatch.setattr(proxy, "enqueue_cmd", lambda *a, **k: (_ for _ in ()).throw(AssertionError("sent")))

    assert proxy.fetch_version_info(timeout=0.1) == {"wifi_firmware": "1.0.0"}


def test_engine_triage_still_partitions_the_public_methods():
    assert engine_method_triage() == {"untriaged": set(), "overlap": set(), "stale": set()}


def test_wifi_firmware_sensor_reads_the_hub():
    hub = SimpleNamespace(entry_id="entry-id", get_version_info=lambda: {"wifi_firmware": "2.1.5"})
    entry = SimpleNamespace(entry_id="entry-id", data={"mac": "aa:bb:cc:dd:ee:ff"})

    wifi = SofabatonFirmwareSensor(hub, entry, "wifi_firmware")

    assert wifi.native_value == "2.1.5"
    assert wifi._attr_unique_id == "aa:bb:cc:dd:ee:ff_wifi_firmware"
    assert wifi._attr_translation_key == "wifi_firmware"
    assert SofabatonFirmwareSensor(SimpleNamespace(entry_id="e", get_version_info=dict), entry, "wifi_firmware").native_value is None
