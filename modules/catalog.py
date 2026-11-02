"""GHOSTNODE module catalog."""
from __future__ import annotations
from typing import List
from core.registry import ModuleRegistry
from modules.base import GhostModule
from modules.implemented import ToolModule

def build_catalog() -> List[GhostModule]:
    items = [
        ('inspector','System Inspector','SYS-INSPECT','CPU, RAM, OS and storage diagnostics'),
        ('vault','File Vault','FILE-VAULT','Password-based authenticated file encryption'),
        ('hash','Hash Generator','HASH-GEN','SHA-256 hashing and integrity verification'),
        ('passgen','Password Generator','PASS-GEN','Cryptographically secure password generation'),
        ('netinfo','Network Info','NET-INFO','Local adapter and connection information'),
        ('notes','Quick Notes','QUICK-NOTES','Portable notes saved in GHOSTNODE data'),
        ('files','File Utilities','FILE-UTILS','Safe copy, move and file organization'),
        ('wifi','Wi-Fi Recon','WIFI-RECON','Nearby SSID/security scan and Windows Wi-Fi settings'),
        ('pcap','Packet Analyzer','PCAP-ANALYZER','Offline classic-PCAP inspection only'),
        ('mapper','Network Mapper','NET-MAPPER','Local network info and existing ARP table'),
        ('forensics','Digital Forensics','DIGI-FORENSICS','Local file metadata, signature and hash inspection'),
        ('pwaudit','Password Audit','PASS-AUDIT','Local password-strength heuristic; no account testing'),
        ('hex','Hex Viewer','HEX-VIEW','Read-only hexadecimal file inspection'),
        ('ascii-earth','ASCII // Earth','ASCII-EARTH','Animated 3D-style ASCII globe visualization'),
        ('terminal','Terminal','TERMINAL','Integrated console with GHOSTNODE commands'),
    ]
    return [ToolModule(*item, status='ready') for item in items]

def load_all(registry: ModuleRegistry) -> None:
    for module in build_catalog(): registry.register(module)
