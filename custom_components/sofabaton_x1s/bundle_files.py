"""Hub bundle files on disk (fork: ``backup_bundle`` with ``save``).

Plain file handling with no Home Assistant imports, run in the executor.
Files are ``<mac>-<UTC stamp>.json`` in one folder; pruning only ever
touches files of that exact shape for the same hub.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: Folder under the Home Assistant config directory.
BUNDLE_SUBDIR = ("sofabaton-backups", "hub")
#: Most bundles ``keep`` may ask to retain.
MAX_KEEP = 1000

_STAMP_FORMAT = "%Y%m%dT%H%M%SZ"


def _mac_slug(mac: str) -> str:
    slug = re.sub(r"[^0-9a-f]", "", str(mac or "").lower())
    if not slug:
        raise ValueError("the hub has no MAC address to name its bundle files")
    return slug


def _bundle_pattern(slug: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(slug)}-\d{{8}}T\d{{6}}Z(?:-\d+)?\.json$")


def validate_keep(raw: Any) -> int | None:
    """``keep`` as an int in 1..MAX_KEEP, or None when omitted."""

    if raw is None:
        return None
    if isinstance(raw, bool):
        raise ValueError("keep must be a whole number of bundles")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("keep must be a whole number of bundles") from exc
    if value < 1 or value > MAX_KEEP:
        raise ValueError(f"keep must be between 1 and {MAX_KEEP}")
    return value


def save_bundle(
    directory: Path,
    mac: str,
    bundle: dict[str, Any],
    *,
    keep: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Write ``bundle`` as a new file and prune this hub's oldest files.

    Returns ``{"saved_path": str, "pruned": [str, ...]}``. The file is
    written to a temporary name first and renamed, so a crash never leaves
    a truncated bundle under a real name; it is readable by the owner only.
    """

    slug = _mac_slug(mac)
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime(_STAMP_FORMAT)
    directory.mkdir(parents=True, exist_ok=True)

    target = directory / f"{slug}-{stamp}.json"
    suffix = 2
    while target.exists():
        target = directory / f"{slug}-{stamp}-{suffix}.json"
        suffix += 1

    tmp = target.with_name(f".{target.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(bundle, handle, ensure_ascii=False, indent=1)
            handle.write("\n")
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    pruned: list[str] = []
    if keep is not None:
        pattern = _bundle_pattern(slug)
        mine = sorted(p for p in directory.iterdir() if p.is_file() and pattern.match(p.name))
        for old in mine[: max(0, len(mine) - keep)]:
            old.unlink()
            pruned.append(str(old))
    return {"saved_path": str(target), "pruned": pruned}
