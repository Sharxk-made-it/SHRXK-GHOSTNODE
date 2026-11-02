"""JSON configuration stored in config/ghostnode.json (on the USB).

Writes are atomic (temp file + replace) so pulling the drive mid-save does not
corrupt the existing config. A corrupt file is set aside and defaults are used.
"""
from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger("ghostnode.config")

DEFAULTS: Dict[str, Any] = {
    "schema": 1,
    "ui": {
        "scanlines": True,
        "glitch": True,
        "window": {"width": 1280, "height": 780},
    },
}


def _merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


class Config:
    def __init__(self, path: Optional[Path]):
        """path=None means memory-only (read-only drive)."""
        self.path = path
        self.data: Dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.status = "defaults"  # defaults | loaded | recovered | memory-only

    def load(self) -> None:
        if self.path is None:
            self.status = "memory-only"
            return
        if not self.path.is_file():
            self.status = "defaults"
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("config root is not an object")
            _merge(self.data, raw)
            self.status = "loaded"
        except (OSError, ValueError) as exc:
            log.warning("config unreadable (%s) - using defaults", exc)
            self.status = "recovered"
            try:
                self.path.replace(self.path.with_suffix(".json.corrupt"))
            except OSError:
                pass

    def get(self, key: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, key: str, value: Any, save: bool = True) -> None:
        parts = key.split(".")
        node = self.data
        for part in parts[:-1]:
            if not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value
        if save:
            self.save()

    def save(self) -> bool:
        if self.path is None:
            return False
        tmp = self.path.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
            return True
        except OSError as exc:
            log.warning("could not save config: %s", exc)
            return False
