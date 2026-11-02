"""Command engine for the integrated terminal.

Qt-free on purpose: handlers return a Result (lines + optional UI action), so
every command can be unit-tested without a display. Modules can register their
own commands later through GhostModule.register_commands(engine).
"""
from __future__ import annotations

import difflib
import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from core import diagnostics, version
from core.result import Result

log = logging.getLogger("ghostnode.commands")

Handler = Callable[[List[str], Any], Result]
Completer = Callable[[Any, List[str]], List[str]]

FX_KEYS = {"scanlines": "ui.scanlines", "glitch": "ui.glitch"}


@dataclass
class Command:
    name: str
    handler: Handler
    summary: str
    usage: str = ""
    aliases: Tuple[str, ...] = ()
    completer: Optional[Completer] = None


def tokenize(line: str) -> List[str]:
    """Split on whitespace; single/double quotes group words; backslashes stay
    literal so Windows paths like E:\\GHOSTNODE\\data work unquoted."""
    tokens: List[str] = []
    buf: List[str] = []
    quote = ""
    in_token = False
    for ch in line:
        if quote:
            if ch == quote:
                quote = ""
            else:
                buf.append(ch)
        elif ch in "\"'":
            quote = ch
            in_token = True
        elif ch.isspace():
            if in_token:
                tokens.append("".join(buf))
                buf = []
                in_token = False
        else:
            buf.append(ch)
            in_token = True
    if quote:
        raise ValueError("unbalanced quote")
    if in_token:
        tokens.append("".join(buf))
    return tokens


class CommandEngine:
    def __init__(self, ctx: Any) -> None:
        self.ctx = ctx
        self._cmds: Dict[str, Command] = {}
        self._aliases: Dict[str, str] = {}

    # ---- registration ---------------------------------------------------
    def register(self, cmd: Command) -> None:
        self._cmds[cmd.name] = cmd
        for alias in cmd.aliases:
            self._aliases[alias] = cmd.name

    def commands(self) -> List[Command]:
        return [self._cmds[n] for n in sorted(self._cmds)]

    def names(self) -> List[str]:
        return sorted(self._cmds)

    def lookup(self, name: str) -> Optional[Command]:
        name = name.lower()
        return self._cmds.get(self._aliases.get(name, name))

    # ---- execution ------------------------------------------------------
    def execute(self, line: str) -> Result:
        line = line.strip()
        if not line:
            return Result()
        try:
            tokens = tokenize(line)
        except ValueError as exc:
            return Result().add("parse error: %s" % exc, "err")
        if not tokens:
            return Result()

        name, args = tokens[0], tokens[1:]
        cmd = self.lookup(name)
        if cmd is None:
            result = Result().add("unknown command: %s" % name, "err")
            close = difflib.get_close_matches(
                name.lower(), self.names() + list(self._aliases), n=1)
            if close:
                result.add("did you mean '%s'?" % close[0], "dim")
            else:
                result.add("type 'help' for the command list.", "dim")
            return result
        try:
            return cmd.handler(args, self.ctx)
        except Exception as exc:  # a broken command must never kill the UI
            log.exception("command '%s' failed", cmd.name)
            return Result().add("command '%s' failed: %s" % (cmd.name, exc), "err")

    # ---- tab completion -------------------------------------------------
    def complete(self, line: str) -> Tuple[str, List[str]]:
        """Return (new_line, candidates_to_show). candidates is empty when the
        completion was unambiguous or nothing matched."""
        head, sep, last = line.rpartition(" ")
        prefix = head + sep
        needle = last.lower()

        if not sep:
            options = self.names() + list(self._aliases)
        else:
            words = head.split()
            if not words:
                return line, []
            cmd = self.lookup(words[0])
            if cmd is None or cmd.completer is None:
                return line, []
            options = cmd.completer(self.ctx, words[1:])

        candidates = sorted(o for o in options if o.lower().startswith(needle))
        if not candidates:
            return line, []
        if len(candidates) == 1:
            return prefix + candidates[0] + " ", []
        common = os.path.commonprefix(candidates)
        return prefix + (common if len(common) > len(last) else last), candidates


# --------------------------------------------------------------------------
# built-in commands
# --------------------------------------------------------------------------
def _cmd_help(args: List[str], ctx: Any) -> Result:
    engine: CommandEngine = ctx.engine
    r = Result()
    if args:
        cmd = engine.lookup(args[0])
        if cmd is None:
            return r.add("no such command: %s" % args[0], "err")
        r.add("%s - %s" % (cmd.name, cmd.summary), "accent")
        r.add("  usage: %s" % (cmd.usage or cmd.name), "info")
        if cmd.aliases:
            r.add("  aliases: %s" % ", ".join(cmd.aliases), "dim")
        return r
    r.add("GHOSTNODE COMMANDS", "accent")
    for cmd in engine.commands():
        label = cmd.usage or cmd.name
        r.add("  %-22s %s" % (label, cmd.summary), "info")
    r.add("tab = autocomplete | up/down = history | ctrl+L = clear", "dim")
    return r


def _cmd_info(args: List[str], ctx: Any) -> Result:
    return Result().extend(diagnostics.info_report(ctx))


def _cmd_scan(args: List[str], ctx: Any) -> Result:
    if ctx.log:
        ctx.log.info("environment scan requested")
    return Result().extend(diagnostics.scan_report(ctx))


def _cmd_modules(args: List[str], ctx: Any) -> Result:
    r = Result().add(" #  %-10s %-20s STATUS" % ("ID", "NAME"), "accent")
    for m in ctx.registry.all():
        level = "ok" if m.is_ready() else "dim"
        r.add("%02d  %-10s %-20s %s" % (m.order, m.id, m.name, m.status.upper()), level)
    r.add("use: open <id | number>", "dim")
    return r


def _complete_modules(ctx: Any, done: List[str]) -> List[str]:
    return ctx.registry.ids() if not done else []


def _cmd_open(args: List[str], ctx: Any) -> Result:
    if not args:
        return Result().add("usage: open <module id | number>", "err")
    module = ctx.registry.find(args[0])
    if module is None:
        r = Result().add("no module matches '%s'" % args[0], "err")
        return r.add("known: %s" % ", ".join(ctx.registry.ids()), "dim")
    if not module.is_ready():
        return Result().add(
            "[%s] %s is planned for a later stage - not available yet."
            % (module.id, module.name), "warn")
    r = Result().add("[%s] %s online" % (module.id, module.name), "ok")
    r.action, r.arg = "open", module.id
    return r


def _parse_state(token: str) -> Optional[bool]:
    t = token.lower()
    if t in ("on", "1", "true", "yes"):
        return True
    if t in ("off", "0", "false", "no"):
        return False
    return None


def _cmd_fx(args: List[str], ctx: Any) -> Result:
    r = Result()
    cfg = ctx.config
    if not args:
        for name, key in FX_KEYS.items():
            r.add("  %-10s %s" % (name, "ON" if cfg.get(key, True) else "OFF"), "info")
        return r.add("usage: fx <scanlines|glitch|all> [on|off]", "dim")

    target = args[0].lower()
    if target != "all" and target not in FX_KEYS:
        return r.add("unknown effect '%s' (scanlines, glitch, all)" % args[0], "err")

    if len(args) > 1:
        state = _parse_state(args[1])
        if state is None:
            return r.add("state must be on or off", "err")
    elif target == "all":
        return r.add("usage: fx all <on|off>", "err")
    else:
        state = not bool(cfg.get(FX_KEYS[target], True))

    keys = list(FX_KEYS.values()) if target == "all" else [FX_KEYS[target]]
    for key in keys:
        cfg.set(key, state, save=False)
    cfg.save()
    r.add("fx %s -> %s" % (target, "ON" if state else "OFF"), "ok")
    if not ctx.writable:
        r.add("drive is read-only: change applies to this session only", "warn")
    r.action = "fx"
    return r


def _complete_fx(ctx: Any, done: List[str]) -> List[str]:
    if not done:
        return list(FX_KEYS) + ["all"]
    if len(done) == 1:
        return ["on", "off"]
    return []


def _cmd_clear(args: List[str], ctx: Any) -> Result:
    r = Result()
    r.action = "clear"
    return r


def _cmd_version(args: List[str], ctx: Any) -> Result:
    return Result().add(version.APP_NAME, "accent")


def _cmd_about(args: List[str], ctx: Any) -> Result:
    r = Result()
    r.add(version.APP_NAME, "accent")
    r.add(version.SUBTITLE, "dim")
    r.add("", "plain")
    r.add("offline-first | no install | no registry | nothing leaves this machine", "info")
    r.add(version.CREDIT, "dim")
    return r


def _cmd_exit(args: List[str], ctx: Any) -> Result:
    r = Result().add("closing GHOSTNODE - safe to eject the drive afterwards.", "ok")
    r.action = "exit"
    return r


def _complete_help(ctx: Any, done: List[str]) -> List[str]:
    return ctx.engine.names() if not done else []


def register_builtin(engine: CommandEngine) -> None:
    engine.register(Command("help", _cmd_help, "list commands or show usage",
                            "help [command]", ("?",), _complete_help))
    engine.register(Command("info", _cmd_info, "application and host summary"))
    engine.register(Command("scan", _cmd_scan, "run the environment self-diagnostic"))
    engine.register(Command("modules", _cmd_modules, "list modules and their status"))
    engine.register(Command("open", _cmd_open, "open a module",
                            "open <module>", (), _complete_modules))
    engine.register(Command("fx", _cmd_fx, "toggle visual effects",
                            "fx [name] [on|off]", (), _complete_fx))
    engine.register(Command("clear", _cmd_clear, "clear the terminal", "clear", ("cls",)))
    engine.register(Command("version", _cmd_version, "show version"))
    engine.register(Command("about", _cmd_about, "credits"))
    engine.register(Command("exit", _cmd_exit, "close GHOSTNODE", "exit", ("quit",)))
