# GHOSTNODE
**Portable Digital Operations Toolkit** · creator: **SHRXK**

GHOSTNODE is a Windows-first, offline-friendly toolkit with a cyberpunk/hacktivist-inspired interface. It is a personal hobby project. The visual language is original and does not use franchise logos or assets.

## Included tools

- **System Inspector** — local OS, CPU, RAM and drive snapshot.
- **File Vault** — password-based AES-256-GCM file encryption/decryption using Scrypt; output is written to a user-selected destination and originals are preserved.
- **Hash Generator** — SHA-256 calculation and expected-hash comparison.
- **Password Generator** — cryptographically secure random passwords; generated values are not saved.
- **Network Info** — local IP/adapter details and Windows network settings shortcut.
- **Quick Notes** — JSON notes stored in the portable `data/` folder.
- **File Utilities** — explicit-destination copy/move operations with confirmation before source removal.
- **Wi-Fi Recon** — Windows nearby SSID/security/signal/channel visibility; opens native Wi-Fi settings. It does not crack credentials or bypass protected networks.
- **Packet Analyzer** — offline classic-PCAP summaries (Ethernet IPv4/IPv6); no live capture or injection.
- **Network Mapper** — local host details and the existing ARP cache only; no active probing.
- **Digital Forensics** — local file metadata, signature hints and SHA-256; never executes selected files.
- **Password Audit** — local heuristic strength check only; no account/service testing. Use sample passwords, not current credentials.
- **Hex Viewer** — read-only hex view, capped at 1 MiB per view.
- **ASCII // Earth** — animated local ASCII globe with Earth, Wire, Scan and Glitch modes.
- **Terminal** — integrated command interface with history and Tab completion.

## Architecture

```text
GHOSTNODE_SRC/
├── main.py
├── core/                 # portable paths, config, logs, command engine, diagnostics
├── modules/
│   ├── catalog.py        # module registry
│   ├── implemented.py    # module adapters + terminal commands
│   ├── toolkit_core.py   # Qt-free local helper functions
│   └── tool_widgets.py  # PySide6 tool UIs
├── ui/                   # main window, terminal, theme, CRT effects, boot splash
├── assets/               # icon and optional fonts
├── tests/                # core and helper tests
├── requirements.txt
├── run_dev.bat
└── build.bat
```

## Development on Windows 10/11 x64

Use standard (non-free-threaded) Python 3.12 x64:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
run_dev.bat
```

Run tests:

```bat
.venv\Scripts\python -B -m unittest discover -s tests -t . -v
```

Build the portable directory:

```bat
build.bat
```

Output: `dist\GHOSTNODE\` containing `GHOSTNODE.exe` and `_internal/`. Copy the **entire folder** to the USB. No formatting is required; keep it alongside existing files.

## Portability notes

- PyInstaller **onedir** build: runtime stays beside the executable rather than unpacking into `%TEMP%` at launch.
- All user data/config/logs are stored beside the executable in `data/`, `config/`, and `logs/`.
- No autorun, services, registry changes, admin requirement, or background persistence.
- Some tools are Windows-specific (Wi-Fi scan and adapter details). Other tools are local file operations.
- Close GHOSTNODE before ejecting the USB.

## Terminal commands

Built-ins: `help`, `info`, `scan`, `modules`, `open <id|number>`, `fx`, `clear`, `version`, `about`, `exit`.

Tool commands: `hashfile <path>`, `wifi-scan`, `pcap-summary <file.pcap>`.

Quote paths containing spaces, e.g. `hashfile "D:\\folder\\file.bin"`.

## Roadmap

- ASCII // Earth module; LINKFORGE is not included.
- Future: polish, accessibility settings, optional module/plugin loading, more offline file analysis.
