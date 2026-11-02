"""Portable path resolution.

Everything GHOSTNODE writes lives next to the executable (or next to the
project in development). Nothing is written to the host's user profile,
%APPDATA%, %TEMP% or the registry.

For tests you can redirect the data root with the GHOSTNODE_HOME variable.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

ENV_HOME = "GHOSTNODE_HOME"


@dataclass(frozen=True)
class Paths:
    root: Path      # folder that holds GHOSTNODE.exe, data/, config/, logs/
    bundle: Path    # where read-only resources live (PyInstaller _internal or project)
    frozen: bool    # True when running as a packaged executable

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def assets(self) -> Path:
        """User-editable assets next to the exe win over bundled ones."""
        external = self.root / "assets"
        return external if external.is_dir() else self.bundle / "assets"

    @property
    def config_file(self) -> Path:
        return self.config_dir / "ghostnode.json"

    @property
    def log_file(self) -> Path:
        return self.logs / "ghostnode.log"

    def ensure(self) -> bool:
        """Create data/config/logs if missing. Returns True when the drive is writable."""
        for folder in (self.data, self.config_dir, self.logs):
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except OSError:
                return False
        return self.is_writable()

    def is_writable(self) -> bool:
        probe = self.data / ".write_probe"
        try:
            probe.write_bytes(b"0")
            probe.unlink()
            return True
        except OSError:
            return False


def resolve() -> Paths:
    frozen = bool(getattr(sys, "frozen", False))
    project_dir = Path(__file__).resolve().parent.parent

    if frozen:
        exe_dir = Path(sys.executable).resolve().parent
        bundle = Path(getattr(sys, "_MEIPASS", exe_dir))
        root = exe_dir
    else:
        bundle = project_dir
        root = project_dir

    override = os.environ.get(ENV_HOME)
    if override:
        root = Path(override).expanduser().resolve()

    return Paths(root=root, bundle=bundle, frozen=frozen)
