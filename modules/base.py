"""Base class every GHOSTNODE module implements.

Adding a tool later = one new file in modules/ + one line in catalog.py:
  - set id / name / code / summary and status = "ready"
  - register_commands(engine) to expose terminal commands
  - create_widget(ctx) to return a QWidget shown in the main area
"""
from __future__ import annotations

from typing import Any


class GhostModule:
    id: str = ""
    name: str = ""
    code: str = ""
    summary: str = ""
    status: str = "planned"   # "ready" | "planned"
    order: int = 0            # assigned by the registry

    def is_ready(self) -> bool:
        return self.status == "ready"

    def register_commands(self, engine: Any) -> None:
        """Hook: add terminal commands via engine.register(Command(...))."""
        return None

    def create_widget(self, ctx: Any) -> Any:
        """Hook: return a QWidget for the main area, or None if there is none."""
        return None


class StubModule(GhostModule):
    """Placeholder for a module that is planned but not built yet."""

    def __init__(self, module_id: str, name: str, code: str, summary: str,
                 status: str = "planned") -> None:
        self.id = module_id
        self.name = name
        self.code = code
        self.summary = summary
        self.status = status
