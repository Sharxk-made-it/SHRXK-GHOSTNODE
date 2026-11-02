"""Implemented GHOSTNODE module adapters. Qt is imported lazily in create_widget."""
from __future__ import annotations
from typing import Any
from modules.base import GhostModule
from core.commands import Command
from core.result import Result

class ToolModule(GhostModule):
    def __init__(self, module_id: str, name: str, code: str, summary: str, status: str='ready'):
        self.id=module_id; self.name=name; self.code=code; self.summary=summary; self.status=status
    def create_widget(self, ctx: Any) -> Any:
        from modules.tool_widgets import build_tool_widget
        return build_tool_widget(self.id, ctx)
    def register_commands(self, engine: Any) -> None:
        if self.id == 'hash':
            def handler(args, ctx):
                if not args: return Result().add('usage: hashfile <path>', 'err')
                from pathlib import Path
                from modules.toolkit_core import sha256_file
                p=Path(' '.join(args)).expanduser()
                if not p.is_file(): return Result().add('file not found: %s' % p,'err')
                return Result().add(sha256_file(p),'ok').add(str(p),'dim')
            engine.register(Command('hashfile',handler,'calculate SHA-256 for a local file','hashfile <path>'))
        elif self.id == 'wifi':
            def handler(args, ctx):
                if args and args[0].lower() not in ('scan','list'): return Result().add('usage: wifi-scan','err')
                try:
                    from modules.toolkit_core import wifi_scan_windows
                    rows=wifi_scan_windows(); r=Result().add('NEARBY WI-FI NETWORKS','accent')
                    for n in rows: r.add('%s | %s | signal %s | channel %s | open=%s' % (n['ssid'],n['security'],n['signal'],n['channel'],n['open']),'info')
                    if not rows:r.add('No SSIDs returned. Ensure Wi-Fi is enabled.','warn')
                    r.add('Protected networks require owner-provided credentials.','dim'); return r
                except Exception as exc: return Result().add(str(exc),'err')
            engine.register(Command('wifi-scan',handler,'list nearby Wi-Fi SSIDs and security types','wifi-scan'))
        elif self.id == 'pcap':
            def handler(args, ctx):
                if not args:return Result().add('usage: pcap-summary <file.pcap>','err')
                from pathlib import Path
                from modules.toolkit_core import parse_classic_pcap
                try:
                    d=parse_classic_pcap(Path(' '.join(args)).expanduser())
                    r=Result().add('OFFLINE PCAP SUMMARY','accent').add('Packets: %s | Bytes: %s' % (d['packets'],d['bytes']),'ok')
                    for k,v in d['protocols'].items():r.add('%s: %s' % (k,v),'info')
                    return r
                except Exception as exc:return Result().add(str(exc),'err')
            engine.register(Command('pcap-summary',handler,'summarize a classic PCAP file offline','pcap-summary <file>'))
