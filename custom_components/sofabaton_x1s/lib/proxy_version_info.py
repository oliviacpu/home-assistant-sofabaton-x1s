"""Fork: the hub's Wi-Fi module firmware from its version exchange.

``REQ_VERSION`` (0x0058) is answered with ``WIFI_FW`` (0x0359), the Wi-Fi
module's ``major.minor.patch`` (docs/protocol/connection-flow.md). An X1S
on hub firmware 5 answers with that frame alone (live 2026-11-15): the
``INFO_BANNER`` the docs list after it, with the remote's firmware, never
came, so the remote's firmware isn't read. Frames the official app's own
version screen triggers are captured the same way, since the handler reads
every H→A frame. See FORK.md.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from .protocol_const import OP_REQ_VERSION, OP_WIFI_FW

if TYPE_CHECKING:
    from .proxy_host import _ProxyHost


class VersionInfoMixin(_ProxyHost if TYPE_CHECKING else object):
    """Firmware version of the hub's Wi-Fi module (uses the host's
    ``can_issue_commands``, ``enqueue_cmd``, ``_log``)."""

    def _init_version_info(self) -> None:
        self._version_info_lock = threading.Lock()
        self._version_info_event = threading.Event()
        self._version_info: dict[str, Any] = {}

    def record_version_payload(self, opcode: int, payload: bytes) -> None:
        """Keep the Wi-Fi firmware a ``WIFI_FW`` frame reports."""

        raw = bytes(payload)
        if opcode != OP_WIFI_FW or len(raw) < 3:
            return
        version = f"{raw[0]}.{raw[1]}.{raw[2]}"
        with self._version_info_lock:
            changed = self._version_info.get("wifi_firmware") != version
            self._version_info = {**self._version_info, "wifi_firmware": version}
        if changed:
            self._log.info("[HUB] firmware wifi_firmware=%s", version)
        self._version_info_event.set()

    def get_version_info(self) -> dict[str, Any]:
        """The last firmware version seen; empty before any exchange."""

        with self._version_info_lock:
            return dict(self._version_info)

    def fetch_version_info(self, *, timeout: float = 2.0) -> dict[str, Any]:
        """Ask the hub for its version frame and wait for it.

        Returns what is known afterwards: the cached value when the hub
        can't be asked (the app holds it) or doesn't answer in time.
        """

        if not self.can_issue_commands():
            return self.get_version_info()
        self._version_info_event.clear()
        if not self.enqueue_cmd(OP_REQ_VERSION):
            return self.get_version_info()
        self._version_info_event.wait(timeout)
        return self.get_version_info()


__all__ = ["VersionInfoMixin"]
