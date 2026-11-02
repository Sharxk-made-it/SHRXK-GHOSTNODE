"""AppContext: the shared state handed to commands, modules and the UI."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.config import Config
from core.paths import Paths
from core.registry import ModuleRegistry


@dataclass
class AppContext:
    paths: Paths
    config: Config
    registry: ModuleRegistry
    writable: bool
    log: Optional[logging.Logger] = None
    engine: Any = None  # CommandEngine, assigned after construction
    started: float = field(default_factory=time.monotonic)

    def uptime(self) -> float:
        return time.monotonic() - self.started
