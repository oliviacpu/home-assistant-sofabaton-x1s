"""Fork: Wi-Fi and remote firmware from the hub's version exchange.

``REQ_VERSION`` (0x0058) is answered with ``WIFI_FW`` (0x0359, the Wi-Fi
module's ``major.minor.patch``) and ``INFO_BANNER`` (0x112F, which on
X1/X1S carries the remote's firmware in ``payload[12]``), per
docs/protocol/connection-flow.md and opcodes.md. Frames the official app's
own version screen triggers are captured the same way, since the handler
reads every H→A frame. See FORK.md.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from .hub_versions import HUB_VERSION_X2
from .protocol_const import OP_INFO_BANNER, OP_REQ_VERSION, OP_WIFI_FW

if TYPE_CHECKING:
    from .proxy_host import _ProxyHost


class VersionInfoMixin(_ProxyHost if TYPE_CHECKING else object):
    """Firmware versions of the hub's Wi-Fi module and remote (uses the
    host's ``hub_version``, ``can_issue_commands``, ``enqueue_cmd``, ``_log``)."""

    def _init_version_info(self) -> None:
        self._version_info_lock = threading.Lock()
        self._version_info_event = threading.Event()
        self._version_info: dict[str, Any] = {}

    def record_version_payload(self, opcode: int, payload: bytes) -> None:
        """Keep the firmware versions one version-exchange frame reports."""

        raw = bytes(payload)
        update: dict[str, Any] = {}
        if opcode == OP_WIFI_FW and len(raw) >= 3:
            update["wifi_firmware"] = f"{raw[0]}.{raw[1]}.{raw[2]}"
        elif opcode == OP_INFO_BANNER and self.hub_version != HUB_VERSION_X2 and len(raw) > 12:
            update["remote_firmware"] = int(raw[12])
        if update:
            with self._version_info_lock:
                changed = any(self._version_info.get(key) != value for key, value in update.items())
                self._version_info = {**self._version_info, **update}
            if changed:
                self._log.info("[HUB] firmware %s", ", ".join(f"{k}={v}" for k, v in update.items()))
        if opcode == OP_INFO_BANNER:
            self._version_info_event.set()

    def get_version_info(self) -> dict[str, Any]:
        """The last firmware versions seen; empty before any exchange."""

        with self._version_info_lock:
            return dict(self._version_info)

    def fetch_version_info(self, *, timeout: float = 2.0) -> dict[str, Any]:
        """Ask the hub for its version frames and wait for them.

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
