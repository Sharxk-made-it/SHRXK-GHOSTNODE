"""Output primitives shared by the command engine and the UI."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List


@dataclass
class Line:
    """One line of terminal output.

    level: plain | info | ok | warn | err | dim | accent | cmd
    """

    text: str
    level: str = "plain"


@dataclass
class Result:
    """What a command returns: lines to print plus an optional UI action.

    action: None | "clear" | "exit" | "open" | "fx"
    """

    lines: List[Line] = field(default_factory=list)
    action: str = ""
    arg: str = ""

    def add(self, text: str, level: str = "plain") -> "Result":
        self.lines.append(Line(text, level))
        return self

    def extend(self, lines: Iterable[Line]) -> "Result":
        self.lines.extend(lines)
        return self
