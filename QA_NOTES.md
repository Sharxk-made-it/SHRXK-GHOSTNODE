# GHOSTNODE QA notes

- `python -m compileall -q .`: passed.
- `python -B -m unittest discover -s tests -t . -v`: 39 tests passed.
- Includes tests for portable core, module catalog/commands, SHA-256, password generation/heuristic, metadata and classic-PCAP parsing.
- GUI and PyInstaller build still need to be exercised on the target Windows machine with Python 3.12 x64 and the dependencies in `requirements.txt`; this environment does not have PySide6 installed, so no claim is made that the actual Qt window or `.exe` was run here.
