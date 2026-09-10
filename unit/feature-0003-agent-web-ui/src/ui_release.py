"""Expose only a completed deployment matching this replica; no database access."""
from __future__ import annotations

import json
import re
from pathlib import Path

from static_cache import read_build_stamp

RELEASE_PATH = Path("/srv/ui-release/current.json")


def read_release(path: Path, static_dir: Path, commit: str) -> dict:
    pending = {"status": "pending"}
    try:
        with path.open("rb") as source:
            raw = source.read(4097)
        if len(raw) > 4096:
            return pending
        value = json.loads(raw)
        if not isinstance(value, dict) or value.get("status") != "complete":
            return pending
        stamp = value.get("asset_stamp")
        generation = value.get("generation")
        release = value.get("release")
        if (not isinstance(stamp, str) or not re.fullmatch(r"[a-f0-9]{12}", stamp)
                or not isinstance(release, str) or not re.fullmatch(r"[a-f0-9]{7,40}", release)
                or type(generation) is not int or not 0 < generation < 2**53
                or release != commit or stamp != read_build_stamp(static_dir)):
            return pending
        return {"status": "complete", "release": release,
                "asset_stamp": stamp, "generation": generation}
    except (OSError, ValueError, TypeError):
        return pending
