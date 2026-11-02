"""Module registry: the single list of tools GHOSTNODE knows about."""
from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from modules.base import GhostModule


class ModuleRegistry:
    def __init__(self) -> None:
        self._mods: Dict[str, "GhostModule"] = {}

    def register(self, module: "GhostModule") -> None:
        if not module.id:
            raise ValueError("module has no id")
        if module.id in self._mods:
            raise ValueError("duplicate module id: %s" % module.id)
        if not module.order:
            module.order = len(self._mods) + 1
        self._mods[module.id] = module

    def get(self, module_id: str) -> Optional["GhostModule"]:
        return self._mods.get(module_id)

    def all(self) -> List["GhostModule"]:
        return sorted(self._mods.values(), key=lambda m: m.order)

    def ids(self) -> List[str]:
        return [m.id for m in self.all()]

    def ready_count(self) -> int:
        return sum(1 for m in self._mods.values() if m.is_ready())

    def __len__(self) -> int:
        return len(self._mods)

    def find(self, token: str) -> Optional["GhostModule"]:
        """Resolve 'vault', '2' or a unique prefix like 'pass' to a module."""
        t = token.strip().lower()
        if not t:
            return None
        if t in self._mods:
            return self._mods[t]
        if t.isdigit():
            number = int(t)
            for module in self.all():
                if module.order == number:
                    return module
            return None
        matches = [m for m in self.all()
                   if m.id.startswith(t) or m.name.lower().startswith(t)]
        return matches[0] if len(matches) == 1 else None
