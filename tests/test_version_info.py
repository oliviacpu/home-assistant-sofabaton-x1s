"""Fork: Wi-Fi and remote firmware from the version exchange (FORK.md)."""

from types import SimpleNamespace

from custom_components.sofabaton_x1s.lib.aio import engine_method_triage
from custom_components.sofabaton_x1s.lib.frame_handlers import frame_handler_registry
from custom_components.sofabaton_x1s.lib.hub_versions import HUB_VERSION_X1S, HUB_VERSION_X2
from custom_components.sofabaton_x1s.lib.opcode_handlers import (
    RemoteStatusReplyHandler,
    VersionInfoHandler,
    X2RemoteListRowHandler,
)
from custom_components.sofabaton_x1s.lib.protocol_const import OP_INFO_BANNER, OP_REQ_VERSION, OP_WIFI_FW
from custom_components.sofabaton_x1s.lib.x1_proxy import X1Proxy
from custom_components.sofabaton_x1s.sensor import SofabatonFirmwareSensor

# INFO_BANNER (17 bytes): model and batch bytes repeated, remote firmware at payload[12].
INFO_BANNER = bytes(6) + bytes([0x02]) + bytes.fromhex("20221120") + bytes([0x00, 0x11]) + bytes(4)
assert len(INFO_BANNER) == 17 and INFO_BANNER[12] == 0x11


def test_x1s_version_frames_give_wifi_and_remote_firmware():
    proxy = X1Proxy("127.0.0.1", hub_version=HUB_VERSION_X1S)
    assert proxy.get_version_info() == {}

    proxy.record_version_payload(OP_WIFI_FW, bytes([1, 4, 2]))
    proxy.record_version_payload(OP_INFO_BANNER, INFO_BANNER)

    assert proxy.get_version_info() == {"wifi_firmware": "1.4.2", "remote_firmware": 0x11}
    assert proxy._version_info_event.is_set()


def test_x2_info_banner_is_not_read_as_remote_firmware():
    proxy = X1Proxy("127.0.0.1", hub_version=HUB_VERSION_X2)
    proxy.record_version_payload(OP_INFO_BANNER, INFO_BANNER)
    assert "remote_firmware" not in proxy.get_version_info()


def test_short_frames_are_ignored():
    proxy = X1Proxy("127.0.0.1", hub_version=HUB_VERSION_X1S)
    proxy.record_version_payload(OP_WIFI_FW, b"\x01")
    proxy.record_version_payload(OP_INFO_BANNER, bytes(5))
    assert proxy.get_version_info() == {}


def test_version_handler_runs_beside_the_family_0x2f_handlers():
    banner = {type(h) for h in frame_handler_registry.iter_for(OP_INFO_BANNER, "H→A")}
    assert {VersionInfoHandler, RemoteStatusReplyHandler, X2RemoteListRowHandler} <= banner
    assert VersionInfoHandler in {type(h) for h in frame_handler_registry.iter_for(OP_WIFI_FW, "H→A")}
    assert VersionInfoHandler not in {type(h) for h in frame_handler_registry.iter_for(OP_WIFI_FW, "A→H")}


def test_fetch_version_info_asks_once_and_waits_for_the_banner(monkeypatch):
    proxy = X1Proxy("127.0.0.1", hub_version=HUB_VERSION_X1S)
    sent = []

    def _enqueue(opcode, payload=b"", **kwargs):
        sent.append(opcode)
        proxy.record_version_payload(OP_WIFI_FW, bytes([2, 0, 1]))
        proxy.record_version_payload(OP_INFO_BANNER, INFO_BANNER)
        return True

    monkeypatch.setattr(proxy, "can_issue_commands", lambda: True)
    monkeypatch.setattr(proxy, "enqueue_cmd", _enqueue)

    assert proxy.fetch_version_info(timeout=0.5) == {"wifi_firmware": "2.0.1", "remote_firmware": 0x11}
    assert sent == [OP_REQ_VERSION]


def test_fetch_version_info_does_not_ask_while_the_app_holds_the_hub(monkeypatch):
    proxy = X1Proxy("127.0.0.1", hub_version=HUB_VERSION_X1S)
    proxy.record_version_payload(OP_WIFI_FW, bytes([1, 0, 0]))
    monkeypatch.setattr(proxy, "can_issue_commands", lambda: False)
    monkeypatch.setattr(proxy, "enqueue_cmd", lambda *a, **k: (_ for _ in ()).throw(AssertionError("sent")))

    assert proxy.fetch_version_info(timeout=0.1) == {"wifi_firmware": "1.0.0"}


def test_engine_triage_still_partitions_the_public_methods():
    assert engine_method_triage() == {"untriaged": set(), "overlap": set(), "stale": set()}


def test_firmware_sensors_read_the_hub():
    hub = SimpleNamespace(entry_id="entry-id", get_version_info=lambda: {"remote_firmware": 17})
    entry = SimpleNamespace(entry_id="entry-id", data={"mac": "aa:bb:cc:dd:ee:ff"})

    remote = SofabatonFirmwareSensor(hub, entry, "remote_firmware")
    wifi = SofabatonFirmwareSensor(hub, entry, "wifi_firmware")

    assert remote.native_value == "17"
    assert wifi.native_value is None
    assert remote._attr_unique_id == "aa:bb:cc:dd:ee:ff_remote_firmware"
    assert remote._attr_translation_key == "remote_firmware"
