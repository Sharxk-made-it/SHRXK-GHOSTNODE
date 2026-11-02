"""Real host/drive diagnostics using only the standard library (+ ctypes on Windows).

No network calls, no registry access, nothing written outside the app folder.
"""
from __future__ import annotations

import ctypes
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import version
from core.result import Line

_TAGS = {"ok": " OK ", "warn": "WARN", "err": "FAIL", "info": " -- "}
_LEVELS = {"ok": "ok", "warn": "warn", "err": "err", "info": "info"}


# --------------------------------------------------------------------------
# formatting helpers
# --------------------------------------------------------------------------
def human_bytes(n: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(n)
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    return "%d B" % value if idx == 0 else "%.1f %s" % (value, units[idx])


def fmt_duration(seconds: float) -> str:
    s = int(seconds)
    return "%02d:%02d:%02d" % (s // 3600, (s % 3600) // 60, s % 60)


def row(level: str, key: str, value: str) -> Line:
    return Line("[%s] %-14s%s" % (_TAGS[level], key, value), _LEVELS[level])


# --------------------------------------------------------------------------
# host probes
# --------------------------------------------------------------------------
def os_name() -> str:
    system = platform.system()
    if system == "Windows":
        release = platform.release()
        try:
            build = int(platform.version().split(".")[2])
        except (IndexError, ValueError):
            build = 0
        if release == "10" and build >= 22000:
            release = "11"
        return "Windows %s" % release
    return ("%s %s" % (system, platform.release())).strip()


def is_admin() -> bool:
    try:
        if sys.platform == "win32":
            return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
        return os.geteuid() == 0
    except Exception:
        return False


def drive_kind(path: Path) -> str:
    """removable | fixed | network | optical | ram | unknown | n/a (non-Windows)."""
    if sys.platform != "win32":
        return "n/a"
    try:
        anchor = Path(path).anchor
        code = ctypes.windll.kernel32.GetDriveTypeW(anchor)  # type: ignore[attr-defined]
    except Exception:
        return "unknown"
    return {2: "removable", 3: "fixed", 4: "network", 5: "optical", 6: "ram"}.get(code, "unknown")


def disk_usage(path: Path) -> Optional[Tuple[int, int, int]]:
    try:
        usage = shutil.disk_usage(str(path))
        return usage.total, usage.used, usage.free
    except OSError:
        return None


class _MemStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def ram_info() -> Optional[Tuple[int, int]]:
    """(total, available) physical memory in bytes, or None if unknown."""
    try:
        if sys.platform == "win32":
            status = _MemStatus()
            status.dwLength = ctypes.sizeof(status)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
                return None
            return int(status.ullTotalPhys), int(status.ullAvailPhys)
        page = os.sysconf("SC_PAGE_SIZE")
        return page * os.sysconf("SC_PHYS_PAGES"), page * os.sysconf("SC_AVPHYS_PAGES")
    except (OSError, ValueError, AttributeError):
        return None


def folder_size(path: Path, max_files: int = 20000) -> int:
    total = 0
    seen = 0
    for dirpath, _dirs, files in os.walk(str(path)):
        for name in files:
            seen += 1
            if seen > max_files:
                return total
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                pass
    return total


def host_summary() -> Dict[str, Any]:
    return {
        "os": os_name(),
        "build": platform.version(),
        "arch": platform.machine() or "unknown",
        "cpus": os.cpu_count() or 0,
        "python": platform.python_version(),
    }


# --------------------------------------------------------------------------
# reports used by the terminal
# --------------------------------------------------------------------------
def boot_report(ctx: Any) -> List[Line]:
    p = ctx.paths
    mods = ctx.registry
    lines: List[Line] = [
        Line(">> %s" % version.APP_NAME, "accent"),
        Line(version.SUBTITLE, "dim"),
        Line("-" * 56, "dim"),
        row("ok", "portable root", str(p.root)),
        row("ok" if ctx.writable else "warn", "storage",
            "read/write" if ctx.writable
            else "READ-ONLY - settings and logs will not persist"),
        row("ok" if ctx.config.status in ("loaded", "defaults") else "warn",
            "config", ctx.config.status),
        row("ok", "modules", "%d registered (%d ready, %d planned)"
            % (len(mods), mods.ready_count(), len(mods) - mods.ready_count())),
        row("info", "network", "not used by the core (offline-first)"),
        Line("", "plain"),
        Line("type 'help' for the command list.", "dim"),
    ]
    return lines


def info_report(ctx: Any) -> List[Line]:
    p = ctx.paths
    host = host_summary()
    usage = disk_usage(p.root)
    ram = ram_info()
    kv: List[Tuple[str, str]] = [
        ("app", version.APP_NAME),
        ("mode", "packaged executable" if p.frozen else "development (python)"),
        ("root", str(p.root)),
        ("drive", drive_kind(p.root)),
    ]
    if usage:
        kv.append(("space", "%s free of %s" % (human_bytes(usage[2]), human_bytes(usage[0]))))
    kv += [
        ("host", "%s %s" % (host["os"], host["arch"])),
        ("cpu", "%d logical cores" % host["cpus"]),
    ]
    if ram:
        kv.append(("ram", "%s free of %s" % (human_bytes(ram[1]), human_bytes(ram[0]))))
    kv += [
        ("python", host["python"]),
        ("uptime", fmt_duration(ctx.uptime())),
    ]
    lines = [Line(version.SUBTITLE, "dim")]
    lines += [Line("  %-8s %s" % (k, v), "info") for k, v in kv]
    return lines


def scan_report(ctx: Any) -> List[Line]:
    """Self-diagnostic of the portable environment. Every check is real."""
    p = ctx.paths
    counts = {"ok": 0, "warn": 0, "err": 0, "info": 0}
    lines: List[Line] = [Line("scanning environment...", "dim")]

    def add(level: str, key: str, value: str) -> None:
        counts[level] += 1
        lines.append(row(level, key, value))

    add("info", "mode", "packaged executable" if p.frozen
        else "development (python %s)" % platform.python_version())
    add("ok", "root", str(p.root))

    kind = drive_kind(p.root)
    if kind == "removable":
        add("ok", "drive", "removable drive (%s)" % (Path(p.root).anchor or "?"))
    elif kind in ("n/a", "unknown"):
        add("info", "drive", "type not detectable on this platform")
    else:
        add("info", "drive", "%s disk (not a removable USB)" % kind)

    if p.is_writable():
        add("ok", "write test", "data/ read/write check passed")
    else:
        add("err", "write test", "cannot write to data/ - drive locked or read-only")

    usage = disk_usage(p.root)
    if usage is None:
        add("warn", "free space", "could not read drive capacity")
    else:
        total, _used, free = usage
        text = "%s free of %s" % (human_bytes(free), human_bytes(total))
        if free < 10 * 1024 * 1024:
            add("err", "free space", text + " - critically low")
        elif free < 100 * 1024 * 1024:
            add("warn", "free space", text + " - low")
        else:
            add("ok", "free space", text)

    missing = [name for name, folder in (
        ("data", p.data), ("config", p.config_dir), ("logs", p.logs), ("assets", p.assets))
        if not folder.is_dir()]
    if missing:
        add("warn", "layout", "missing: " + ", ".join(missing))
    else:
        add("ok", "layout", "data/ config/ logs/ assets/ present")

    add("info", "footprint", "data %s | config %s | logs %s" % (
        human_bytes(folder_size(p.data)),
        human_bytes(folder_size(p.config_dir)),
        human_bytes(folder_size(p.logs))))

    if is_admin():
        add("warn", "privileges", "elevated session (GHOSTNODE does not need it)")
    else:
        add("ok", "privileges", "standard user - no elevation needed")

    host = host_summary()
    add("info", "host", "%s %s, %d cores" % (host["os"], host["arch"], host["cpus"]))
    ram = ram_info()
    if ram:
        add("info", "ram", "%s free of %s" % (human_bytes(ram[1]), human_bytes(ram[0])))

    status = ctx.config.status
    add("ok" if status in ("loaded", "defaults") else "warn", "config", status)
    add("ok", "modules", "%d registered, %d ready, %d planned" % (
        len(ctx.registry), ctx.registry.ready_count(),
        len(ctx.registry) - ctx.registry.ready_count()))
    add("info", "network", "not used by the core (offline-first)")

    summary = "scan complete: %d ok, %d warn, %d fail" % (
        counts["ok"], counts["warn"], counts["err"])
    level = "err" if counts["err"] else ("warn" if counts["warn"] else "ok")
    lines.append(Line(summary, level))
    return lines
