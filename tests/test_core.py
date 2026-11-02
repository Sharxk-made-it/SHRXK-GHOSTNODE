"""Qt-free tests for the GHOSTNODE core.

Run from the project root:
    python -m unittest discover -s tests -t . -v
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from core import logger
from core.commands import CommandEngine, register_builtin, tokenize
from core.config import Config
from core.context import AppContext
from core.paths import Paths, resolve
from core.registry import ModuleRegistry
from modules.catalog import load_all


def make_ctx(root: Path) -> AppContext:
    paths = Paths(root=root, bundle=Path(__file__).resolve().parent.parent, frozen=False)
    writable = paths.ensure()
    cfg = Config(paths.config_file if writable else None)
    cfg.load()
    registry = ModuleRegistry()
    load_all(registry)
    ctx = AppContext(paths=paths, config=cfg, registry=registry, writable=writable,
                     log=logger.setup(paths, writable))
    engine = CommandEngine(ctx)
    register_builtin(engine)
    for module in registry.all():
        module.register_commands(engine)
    ctx.engine = engine
    return ctx


class CoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.ctx = make_ctx(self.root)

    def tearDown(self) -> None:
        import logging
        logging.shutdown()
        for h in list(logging.getLogger("ghostnode").handlers):
            logging.getLogger("ghostnode").removeHandler(h)
            h.close()
        self._tmp.cleanup()

    def run_cmd(self, line: str):
        return self.ctx.engine.execute(line)

    def text(self, result) -> str:
        return "\n".join(l.text for l in result.lines)


class TestTokenize(unittest.TestCase):
    def test_plain_and_quotes(self):
        self.assertEqual(tokenize("open vault"), ["open", "vault"])
        self.assertEqual(tokenize('x "a b" c'), ["x", "a b", "c"])

    def test_windows_path_kept(self):
        self.assertEqual(tokenize(r"x E:\GHOSTNODE\data"), ["x", r"E:\GHOSTNODE\data"])

    def test_unbalanced_quote(self):
        with self.assertRaises(ValueError):
            tokenize('x "oops')


class TestPaths(unittest.TestCase):
    def test_ensure_creates_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Paths(root=Path(tmp), bundle=Path(tmp), frozen=False)
            self.assertTrue(p.ensure())
            for d in (p.data, p.config_dir, p.logs):
                self.assertTrue(d.is_dir())
            self.assertFalse((p.data / ".write_probe").exists())

    def test_env_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["GHOSTNODE_HOME"] = tmp
            try:
                self.assertEqual(resolve().root, Path(tmp).resolve())
            finally:
                del os.environ["GHOSTNODE_HOME"]


class TestConfig(unittest.TestCase):
    def test_roundtrip_and_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            cfg = Config(path)
            cfg.load()
            cfg.set("ui.glitch", False)
            again = Config(path)
            again.load()
            self.assertEqual(again.status, "loaded")
            self.assertFalse(again.get("ui.glitch"))
            self.assertTrue(again.get("ui.scanlines"))  # default preserved
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_corrupt_file_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text("{ not json", encoding="utf-8")
            cfg = Config(path)
            cfg.load()
            self.assertEqual(cfg.status, "recovered")
            self.assertTrue(cfg.get("ui.scanlines"))
            self.assertTrue((Path(tmp) / "c.json.corrupt").exists())

    def test_wrong_types_do_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps({"ui": 5}), encoding="utf-8")
            cfg = Config(path)
            cfg.load()
            self.assertEqual(cfg.get("ui.scanlines", "fallback"), "fallback")

    def test_memory_only(self):
        cfg = Config(None)
        cfg.load()
        cfg.set("ui.glitch", False)
        self.assertEqual(cfg.status, "memory-only")
        self.assertFalse(cfg.get("ui.glitch"))


class TestRegistry(CoreTestCase):
    def test_catalog(self):
        reg = self.ctx.registry
        self.assertEqual(len(reg), 15)
        self.assertEqual(reg.ready_count(), 15)
        self.assertEqual(reg.ids()[0], "inspector")
        self.assertEqual(reg.ids()[-1], "terminal")

    def test_find(self):
        reg = self.ctx.registry
        self.assertEqual(reg.find("vault").id, "vault")
        self.assertEqual(reg.find("2").id, "vault")
        self.assertEqual(reg.find("passgen").id, "passgen")
        self.assertIsNone(reg.find("zzz"))
        self.assertIsNone(reg.find("0"))

    def test_duplicate_rejected(self):
        from modules.base import StubModule
        with self.assertRaises(ValueError):
            self.ctx.registry.register(StubModule("vault", "x", "x", "x"))


class TestCommands(CoreTestCase):
    def test_empty_line(self):
        self.assertEqual(self.run_cmd("   ").lines, [])

    def test_help_lists_required_commands(self):
        out = self.text(self.run_cmd("help"))
        for name in ("help", "info", "scan", "clear", "open", "modules"):
            self.assertIn(name, out)

    def test_help_for_command_and_alias(self):
        self.assertIn("usage", self.text(self.run_cmd("help open")))
        self.assertEqual(self.run_cmd("?").lines[0].text, "GHOSTNODE COMMANDS")

    def test_unknown_suggests(self):
        out = self.text(self.run_cmd("scn"))
        self.assertIn("unknown command", out)
        self.assertIn("scan", out)

    def test_clear_and_alias(self):
        self.assertEqual(self.run_cmd("clear").action, "clear")
        self.assertEqual(self.run_cmd("cls").action, "clear")

    def test_exit(self):
        self.assertEqual(self.run_cmd("exit").action, "exit")
        self.assertEqual(self.run_cmd("quit").action, "exit")

    def test_open_ready_and_planned(self):
        r = self.run_cmd("open terminal")
        self.assertEqual((r.action, r.arg), ("open", "terminal"))
        r = self.run_cmd("open vault")
        self.assertEqual((r.action, r.arg), ("open", "vault"))
        self.assertIn("online", self.text(r))
        self.assertIn("no module matches", self.text(self.run_cmd("open nope")))
        self.assertIn("usage", self.text(self.run_cmd("open")))

    def test_open_by_number(self):
        self.assertEqual(self.run_cmd("open 15").arg, "terminal")

    def test_modules_table(self):
        out = self.text(self.run_cmd("modules"))
        self.assertIn("System Inspector", out)
        self.assertIn("READY", out)
        self.assertIn("READY", out)
        self.assertIn("Wi-Fi Recon", out)

    def test_info(self):
        out = self.text(self.run_cmd("info"))
        self.assertIn("GHOSTNODE", out)
        self.assertIn(str(self.root), out)

    def test_scan_is_clean_on_writable_dir(self):
        r = self.run_cmd("scan")
        out = self.text(r)
        self.assertIn("write test", out)
        self.assertNotIn("FAIL", out)
        self.assertIn("scan complete", out)

    def test_scan_detects_readonly(self):
        # Replace data/ with a plain file so the write probe must fail.
        data = self.ctx.paths.data
        data.rmdir()
        data.write_text("not a directory")
        out = self.text(self.run_cmd("scan"))
        self.assertIn("FAIL", out)

    def test_fx_toggle_persists(self):
        r = self.run_cmd("fx glitch off")
        self.assertEqual(r.action, "fx")
        self.assertFalse(self.ctx.config.get("ui.glitch"))
        saved = json.loads(self.ctx.paths.config_file.read_text(encoding="utf-8"))
        self.assertFalse(saved["ui"]["glitch"])
        self.run_cmd("fx glitch")  # toggle back
        self.assertTrue(self.ctx.config.get("ui.glitch"))

    def test_fx_all_and_errors(self):
        self.run_cmd("fx all off")
        self.assertFalse(self.ctx.config.get("ui.scanlines"))
        self.assertFalse(self.ctx.config.get("ui.glitch"))
        self.assertEqual(self.run_cmd("fx bogus on").action, "")
        self.assertEqual(self.run_cmd("fx glitch maybe").action, "")
        self.assertEqual(self.run_cmd("fx all").action, "")

    def test_broken_handler_is_contained(self):
        from core.commands import Command

        def boom(args, ctx):
            raise RuntimeError("kaput")

        self.ctx.engine.register(Command("boom", boom, "explodes"))
        self.assertIn("failed", self.text(self.run_cmd("boom")))

    def test_parse_error(self):
        self.assertIn("parse error", self.text(self.run_cmd('open "x')))


    def test_module_commands_registered(self):
        self.assertIn("hashfile", self.ctx.engine.names())
        self.assertIn("wifi-scan", self.ctx.engine.names())
        self.assertIn("pcap-summary", self.ctx.engine.names())

    def test_hashfile_command(self):
        p=self.root/"hash sample.txt"; p.write_text("hello",encoding="utf-8")
        result=self.run_cmd('hashfile "%s"' % p)
        self.assertIn("2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",self.text(result))


class TestCompletion(CoreTestCase):
    def test_command_completion(self):
        self.assertEqual(self.ctx.engine.complete("sc"), ("scan ", []))
        line, cands = self.ctx.engine.complete("c")
        self.assertIn("clear", cands)
        self.assertEqual(self.ctx.engine.complete("zzz"), ("zzz", []))

    def test_argument_completion(self):
        self.assertEqual(self.ctx.engine.complete("open vau"), ("open vault ", []))
        line, cands = self.ctx.engine.complete("fx ")
        self.assertEqual(sorted(cands), ["all", "glitch", "scanlines"])
        self.assertEqual(self.ctx.engine.complete("fx glitch o")[1], ["off", "on"])


class TestLogging(CoreTestCase):
    def test_file_and_bus(self):
        seen = []
        logger.bus.subscribe(lambda lvl, txt: seen.append((lvl, txt)), replay=False)
        self.ctx.log.info("hello ghost")
        for h in self.ctx.log.handlers:
            h.flush()
        self.assertTrue(any("hello ghost" in t for _l, t in seen))
        self.assertIn("hello ghost", self.ctx.paths.log_file.read_text(encoding="utf-8"))


class TestToolkitHelpers(unittest.TestCase):
    def test_sha256(self):
        from modules.toolkit_core import sha256_file
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"sample.txt"; p.write_bytes(b"hello")
            self.assertEqual(sha256_file(p), "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")

    def test_password_generator(self):
        from modules.toolkit_core import secure_password
        pw=secure_password(24,True,True,True,True)
        self.assertEqual(len(pw),24)
        self.assertTrue(any(c.isupper() for c in pw))
        self.assertTrue(any(c.islower() for c in pw))
        self.assertTrue(any(c.isdigit() for c in pw))
        with self.assertRaises(ValueError): secure_password(8,False,False,False,False)

    def test_password_strength(self):
        from modules.toolkit_core import password_strength
        self.assertEqual(password_strength("")["score"],0)
        self.assertIn("label",password_strength("sample-not-real-Password-92!"))

    def test_file_metadata(self):
        from modules.toolkit_core import file_metadata
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"a.pdf"; p.write_bytes(b"%PDF-1.4 sample")
            d=file_metadata(p)
            self.assertEqual(d["type"],"PDF document")
            self.assertEqual(len(d["sha256"]),64)

    def test_pcap_rejects_invalid(self):
        from modules.toolkit_core import parse_classic_pcap
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"bad.pcap"; p.write_bytes(b"not a pcap")
            with self.assertRaises(ValueError): parse_classic_pcap(p)

    def test_pcap_parses_udp_frame(self):
        from modules.toolkit_core import parse_classic_pcap
        import struct
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"sample.pcap"
            # Classic little-endian PCAP header, Ethernet link type.
            global_header=struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,1)
            eth=b'\x00'*12+b'\x08\x00'
            ip=bytearray(20); ip[0]=0x45; ip[9]=17; ip[12:16]=b'\x0a\x00\x00\x01'; ip[16:20]=b'\x0a\x00\x00\x02'
            udp=struct.pack('!HHHH',1234,53,8,0)
            frame=eth+bytes(ip)+udp
            packet_header=struct.pack('<IIII',1,0,len(frame),len(frame))
            p.write_bytes(global_header+packet_header+frame)
            result=parse_classic_pcap(p)
            self.assertEqual(result['packets'],1)
            self.assertEqual(result['protocols'].get('UDP'),1)


if __name__ == "__main__":
    unittest.main()
