#!/usr/bin/env python3
"""Regression tests for turbovault-use bundled scripts and shim template.

Runs with Python stdlib + PyYAML (`python3 scripts/test_turbovault_scripts.py`).
Tests requiring the `turbovault` binary skip cleanly when it is not installed.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPTS_DIR.parent / "templates"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _has_turbovault() -> bool:
    return bool(
        os.environ.get("TURBOVAULT_BIN")
        or shutil.which("turbovault")
        or (Path.home() / ".local" / "bin" / "turbovault").exists()
    )


class TestProbeConfig(unittest.TestCase):
    def _write_fake_bin(self, directory: Path, script_body: str) -> Path:
        exe = directory / "fake-turbovault"
        exe.write_text(f"#!{sys.executable}\n{script_body}\n", encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
        return exe

    def test_jsonrpc_error_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "cfg.yaml"
            cfg.write_text("vaults: []\n", encoding="utf-8")
            fake = self._write_fake_bin(
                Path(d),
                """
import json, sys
for line in sys.stdin:
    msg = json.loads(line)
    mid = msg.get("id")
    if mid == 1:
        print(json.dumps({"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"version":"4.1.0"}}}))
    elif mid == 2:
        print(json.dumps({"jsonrpc":"2.0","id":2,"error":{"code":-32603,"message":"boom"}}))
    elif mid == 3:
        print(json.dumps({"jsonrpc":"2.0","id":3,"result":{"tools":[]}}))
""",
            )
            env = os.environ.copy()
            env["TURBOVAULT_BIN"] = str(fake)
            r = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "probe-config.py"), str(cfg)],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("JSON-RPC error", r.stdout)

    def test_large_stderr_does_not_deadlock(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "cfg.yaml"
            cfg.write_text("vaults: []\n", encoding="utf-8")
            fake = self._write_fake_bin(
                Path(d),
                """
import json, sys
sys.stderr.write("X" * 300000 + "\\n")
sys.stderr.flush()
for line in sys.stdin:
    msg = json.loads(line)
    mid = msg.get("id")
    if mid == 1:
        print(json.dumps({"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"version":"4.1.0"}}}))
    elif mid == 2:
        print(json.dumps({"jsonrpc":"2.0","id":2,"result":{"structuredContent":{"success":True,"data":{"active_vault":None,"vaults":[]}}}}))
    elif mid == 3:
        print(json.dumps({"jsonrpc":"2.0","id":3,"result":{"tools":[{"name":"list_vaults"}]}}))
""",
            )
            env = os.environ.copy()
            env["TURBOVAULT_BIN"] = str(fake)
            r = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "probe-config.py"), "--timeout", "10", str(cfg)],
                capture_output=True,
                text=True,
                env=env,
                timeout=15,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    @unittest.skipUnless(_has_turbovault(), "turbovault binary not installed")
    def test_live_ignores_ambient_obsidian_vault_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v1, extra = Path(d) / "v1", Path(d) / "extra"
            v1.mkdir()
            extra.mkdir()
            cfg = Path(d) / "cfg.yaml"
            cfg.write_text(
                f"vaults:\n  - name: only\n    path: {v1}\n    is_default: true\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["OBSIDIAN_VAULT_PATH"] = str(extra)
            env["TURBOVAULT_TRANSPORT"] = "http"
            r = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "probe-config.py"), str(cfg)],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("vaults (1):", r.stdout)
            self.assertNotIn("default ->", r.stdout)

    @unittest.skipUnless(_has_turbovault(), "turbovault binary not installed")
    def test_live_env_var_vault_path_explicit_allow_env(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v1, extra = Path(d) / "v1", Path(d) / "extra"
            v1.mkdir()
            extra.mkdir()
            cfg = Path(d) / "cfg.yaml"
            cfg.write_text(
                "vaults:\n  - name: envv\n    path: ${REVIEW_VAULT}\n    is_default: true\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["REVIEW_VAULT"] = str(v1)
            env["OBSIDIAN_VAULT_PATH"] = str(extra)

            # Without --allow-env: fails cleanly with actionable hint
            r_deny = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "probe-config.py"), str(cfg)],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(r_deny.returncode, 1)
            self.assertIn("--allow-env REVIEW_VAULT", r_deny.stdout)

            # With --allow-env REVIEW_VAULT: succeeds while still blocking OBSIDIAN_VAULT_PATH
            r_ok = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "probe-config.py"),
                    "--allow-env",
                    "REVIEW_VAULT",
                    str(cfg),
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(r_ok.returncode, 0, r_ok.stdout + r_ok.stderr)
            self.assertIn("vaults (1):", r_ok.stdout)
            self.assertNotIn("default ->", r_ok.stdout)

            # Refuses --allow-env OBSIDIAN_VAULT_PATH
            r_blk = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "probe-config.py"),
                    "--allow-env",
                    "OBSIDIAN_VAULT_PATH",
                    str(cfg),
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(r_blk.returncode, 1)
            self.assertIn("refusing --allow-env", r_blk.stdout)

    @unittest.skipUnless(_has_turbovault(), "turbovault binary not installed")
    def test_live_two_vault_is_default_mismatch_and_details(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v1, v2 = Path(d) / "v1", Path(d) / "v2"
            v1.mkdir()
            v2.mkdir()
            cfg = Path(d) / "cfg.yaml"
            cfg.write_text(
                f"vaults:\n"
                f"  - name: first\n    path: {v1}\n    is_default: false\n    allowed_operations: read\n"
                f"  - name: wanted\n    path: {v2}\n    is_default: true\n"
                f"tool_visibility:\n  show_advanced_tools: true\n  disabled: [fanout, list_orphan_fanouts]\n",
                encoding="utf-8",
            )
            r = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "probe-config.py"), "--list-tools", str(cfg)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("active: first", r.stdout)
            self.assertIn(
                "WARNING: active vault 'first' differs from YAML is_default=true (wanted)",
                r.stdout,
            )
            self.assertIn("ops=['read']", r.stdout)
            self.assertIn("tool names:", r.stdout)
            self.assertIn("list_vaults", r.stdout)

    @unittest.skipUnless(_has_turbovault(), "turbovault binary not installed")
    def test_live_invalid_yaml_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v1 = Path(d) / "v1"
            v1.mkdir()
            cfg = Path(d) / "bad.yaml"
            cfg.write_text(f"vaults:\n  - name: broken\n    path: {v1}\n", encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "probe-config.py"), str(cfg)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("ERROR:", r.stdout)


class TestVaultDriftScripts(unittest.TestCase):
    def test_open_regular_nofollow_rejects_symlink_parent_directory(self) -> None:
        mod = _load_module("vault_drift_check", SCRIPTS_DIR / "vault-drift-check.py")
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "v"
            (v / "private").mkdir(parents=True)
            (v / "private" / "secret.md").write_text("# Secret\n", encoding="utf-8")
            os.symlink(v / "private", v / "linked_dir")
            objects = Path(d) / "objects"

            with self.assertRaises(mod._NonRegularOrSymlink):
                mod._open_regular_nofollow(v.resolve(), ("linked_dir", "secret.md"))

            status, _ = mod.store_object(objects, v.resolve(), "linked_dir/secret.md")
            self.assertEqual(status, "skipped")
            self.assertEqual(list(objects.glob("*")) if objects.exists() else [], [])

    def test_symlinks_never_hashed_or_stored(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "v"
            (v / "private").mkdir(parents=True)
            outside = Path(d) / "outside.md"
            outside.write_text("# Outside secret\n", encoding="utf-8")
            (v / "private" / "secret.md").write_text("# Excluded secret\n", encoding="utf-8")
            (v / "ok.md").write_text("# OK\n", encoding="utf-8")
            os.symlink(v / "private" / "secret.md", v / "link-to-excluded.md")
            os.symlink(outside, v / "link-to-outside.md")

            st = Path(d) / "state"
            cfg = Path(d) / "cfg.yaml"
            cfg.write_text(
                f"vaults:\n- name: main\n  path: {v}\n  excluded_paths: [private]\n",
                encoding="utf-8",
            )
            # Baseline
            r0 = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "vault-drift-all.py"), "--store", "--state-root", str(st), str(cfg)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r0.returncode, 0, r0.stdout + r0.stderr)

            # Modify targets behind symlinks + regular file
            (v / "private" / "secret.md").write_text("# Excluded secret v2\n", encoding="utf-8")
            outside.write_text("# Outside secret v2\n", encoding="utf-8")
            (v / "ok.md").write_text("# OK v2\n", encoding="utf-8")

            r1 = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "vault-drift-all.py"), "--store", "--state-root", str(st), str(cfg)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
            self.assertIn("~ ok.md", r1.stdout)
            self.assertNotIn("link-to-excluded.md", r1.stdout)
            self.assertNotIn("link-to-outside.md", r1.stdout)
            stored = list(st.glob("*/objects/*"))
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0].read_text(encoding="utf-8"), "# OK v2\n")

    def test_failed_snapshot_exits_nonzero_and_retries_when_writable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "v"
            v.mkdir()
            (v / "a.md").write_text("# v1\n", encoding="utf-8")
            st = Path(d) / "state"
            cfg = Path(d) / "cfg.yaml"
            cfg.write_text(f"vaults:\n- name: main\n  path: {v}\n", encoding="utf-8")

            # 1. Baseline
            r0 = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "vault-drift-all.py"), "--store", "--state-root", str(st), str(cfg)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r0.returncode, 0, r0.stdout + r0.stderr)

            # 2. Block object store (replace objects path with a regular file so mkdir/open fails reliably even under root)
            vault_state = next(st.iterdir())
            blocker = vault_state / "objects"
            blocker.write_text("not a dir", encoding="utf-8")
            (v / "a.md").write_text("# v2\n", encoding="utf-8")

            r1 = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "vault-drift-all.py"), "--store", "--state-root", str(st), str(cfg)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r1.returncode, 1, "snapshot failure must exit 1")
            self.assertIn("store error", r1.stderr)

            # 3. Restore writable object store -> next run MUST retry and save the missing v2 snapshot!
            blocker.unlink()
            r2 = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "vault-drift-all.py"), "--store", "--state-root", str(st), str(cfg)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
            expected_sha = hashlib.sha256(b"# v2\n").hexdigest()
            obj = vault_state / "objects" / expected_sha
            self.assertTrue(obj.exists(), "held-back entry must be snapshotted on retry")
            self.assertEqual(obj.read_text(encoding="utf-8"), "# v2\n")

    @unittest.skipUnless(_has_turbovault(), "turbovault binary not installed")
    def test_live_excluded_paths_case_folded_parity_with_mcp(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "v"
            (v / "Private").mkdir(parents=True)
            (v / "Private" / "fixture.md").write_text("# Excluded Case\n", encoding="utf-8")
            (v / "public.md").write_text("# Public\n", encoding="utf-8")
            cfg = Path(d) / "cfg.yaml"
            cfg.write_text(
                f"vaults:\n"
                f"- name: main\n"
                f"  path: {v}\n"
                f"  is_default: true\n"
                f"  excluded_paths: [private]\n",
                encoding="utf-8",
            )

            # 1. Ask real TurboVault MCP to read Private/fixture.md -> must be refused
            env = os.environ.copy()
            env["XDG_CACHE_HOME"] = str(Path(d) / "cache")
            p = subprocess.Popen(
                ["turbovault", "-t", "stdio", "-p", "production", "--config", str(cfg)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            reqs = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "read_note", "arguments": {"path": "Private/fixture.md"}}},
            ]
            out, _ = p.communicate("\n".join(json.dumps(x) for x in reqs) + "\n", timeout=15)
            msgs = {json.loads(line)["id"]: json.loads(line) for line in out.splitlines() if line.strip() and "id" in json.loads(line)}
            mcp_resp = msgs[2]
            mcp_refused = "error" in mcp_resp or bool((mcp_resp.get("result") or {}).get("isError"))
            self.assertTrue(mcp_refused, f"expected TurboVault MCP to refuse Private/fixture.md: {mcp_resp}")

            # 2. Watchdog with --store must ALSO refuse/skip Private/fixture.md
            st = Path(d) / "state"
            r0 = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "vault-drift-all.py"), "--store", "--state-root", str(st), str(cfg)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r0.returncode, 0, r0.stdout + r0.stderr)
            (v / "Private" / "fixture.md").write_text("# Excluded Case v2\n", encoding="utf-8")
            (v / "public.md").write_text("# Public v2\n", encoding="utf-8")
            r1 = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "vault-drift-all.py"), "--store", "--state-root", str(st), str(cfg)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
            self.assertIn("~ public.md", r1.stdout)
            self.assertNotIn("fixture.md", r1.stdout)
            stored = list(st.glob("*/objects/*"))
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0].read_text(encoding="utf-8"), "# Public v2\n")

    @unittest.skipIf(os.geteuid() == 0, "root ignores chmod 000")
    def test_temporarily_unreadable_directory_preserves_subtree(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "v"
            sub = v / "sub"
            sub.mkdir(parents=True)
            (sub / "nested.md").write_text("# Nested\n", encoding="utf-8")
            st = Path(d) / "state"
            checker = str(SCRIPTS_DIR / "vault-drift-check.py")

            r0 = subprocess.run(
                [sys.executable, checker, "--vault", str(v), "--state-root", str(st)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r0.returncode, 0, r0.stdout + r0.stderr)

            sub.chmod(0o000)
            try:
                r1 = subprocess.run(
                    [sys.executable, checker, "--vault", str(v), "--state-root", str(st), "--json"],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
                rep1 = json.loads(r1.stdout)
                self.assertEqual(rep1["window"]["external_delete"], [])
                self.assertIn("sub/", rep1["new_unreadable"])
            finally:
                sub.chmod(0o755)

            r2 = subprocess.run(
                [sys.executable, checker, "--vault", str(v), "--state-root", str(st), "--json"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
            rep2 = json.loads(r2.stdout)
            self.assertEqual(rep2["window"]["external"], [])
            self.assertEqual(rep2["window"]["external_delete"], [])

    @unittest.skipIf(os.geteuid() == 0, "root ignores chmod 000")
    def test_temporarily_unreadable_file_not_deleted_or_recreated(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "v"
            v.mkdir()
            note = v / "flaky.md"
            note.write_text("# Stable\n", encoding="utf-8")
            st = Path(d) / "state"
            checker = str(SCRIPTS_DIR / "vault-drift-check.py")

            # 1. Baseline
            r0 = subprocess.run(
                [sys.executable, checker, "--vault", str(v), "--state-root", str(st)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r0.returncode, 0, r0.stdout + r0.stderr)

            # 2. Make temporarily unreadable -> must NOT be classified as external_delete
            note.chmod(0o000)
            try:
                r1 = subprocess.run(
                    [sys.executable, checker, "--vault", str(v), "--state-root", str(st), "--json"],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
                rep1 = json.loads(r1.stdout)
                self.assertEqual(rep1["window"]["external_delete"], [])
                self.assertEqual(rep1["new_unreadable"], ["flaky.md"])
            finally:
                note.chmod(0o644)

            # 3. Restore read permission on unchanged file -> must NOT be classified as external create/change
            r2 = subprocess.run(
                [sys.executable, checker, "--vault", str(v), "--state-root", str(st), "--json"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
            rep2 = json.loads(r2.stdout)
            self.assertEqual(rep2["window"]["external"], [])
            self.assertEqual(rep2["window"]["external_delete"], [])

    def test_unindented_yaml_and_excluded_paths_and_opt_in_store(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v1 = Path(d) / "v1"
            (v1 / "private").mkdir(parents=True)
            (v1 / "public.md").write_text("# Public\n", encoding="utf-8")
            (v1 / "private" / "secret.md").write_text("# Secret\n", encoding="utf-8")
            st = Path(d) / "state"
            cfg = Path(d) / "cfg.yaml"
            cfg.write_text(
                f"vaults:\n"
                f"- name: main\n"
                f'  path: "{v1}" # inline comment\n'
                f"  is_default: true\n"
                f"  excluded_paths: [private]\n",
                encoding="utf-8",
            )
            r0 = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "vault-drift-all.py"), "--state-root", str(st), str(cfg)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r0.returncode, 0, r0.stdout + r0.stderr)

            (v1 / "public.md").write_text("# Public v2\n", encoding="utf-8")
            (v1 / "private" / "secret.md").write_text("# Secret v2\n", encoding="utf-8")

            r1 = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "vault-drift-all.py"), "--state-root", str(st), str(cfg)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
            self.assertIn("~ public.md", r1.stdout)
            self.assertNotIn("secret.md", r1.stdout)
            self.assertEqual(list(st.glob("*/objects/*")), [])

            (v1 / "public.md").write_text("# Public v3\n", encoding="utf-8")
            (v1 / "private" / "secret.md").write_text("# Secret v3\n", encoding="utf-8")
            r2 = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "vault-drift-all.py"), "--store", "--state-root", str(st), str(cfg)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
            stored_objs = list(st.glob("*/objects/*"))
            self.assertEqual(len(stored_objs), 1)
            self.assertEqual(stored_objs[0].read_text(encoding="utf-8"), "# Public v3\n")
            self.assertEqual(
                stored_objs[0].name,
                hashlib.sha256(b"# Public v3\n").hexdigest(),
            )

    def test_store_object_guarantees_filename_matches_exact_bytes(self) -> None:
        mod = _load_module("vault_drift_check", SCRIPTS_DIR / "vault-drift-check.py")
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "v"
            v.mkdir()
            objects = Path(d) / "objects"
            note = v / "note.md"
            note.write_text("version 1\n", encoding="utf-8")
            note.write_text("version 2 changed mid-run\n", encoding="utf-8")
            status, actual_hash = mod.store_object(objects, v, "note.md")
            self.assertEqual(status, "stored")
            expected_hash = hashlib.sha256(b"version 2 changed mid-run\n").hexdigest()
            self.assertEqual(actual_hash, expected_hash)
            obj_path = objects / expected_hash
            self.assertTrue(obj_path.exists())
            self.assertEqual(
                hashlib.sha256(obj_path.read_bytes()).hexdigest(),
                obj_path.name,
            )

    def test_drift_all_exits_nonzero_on_error_even_with_drift(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v1 = Path(d) / "v1"
            v1.mkdir()
            (v1 / "a.md").write_text("# A\n", encoding="utf-8")
            st = Path(d) / "state"
            cfg = Path(d) / "cfg.yaml"
            cfg.write_text(
                f"vaults:\n  - name: ok\n    path: {v1}\n  - name: missing\n    path: {d}/nope\n",
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "vault-drift-all.py"), "--state-root", str(st), str(cfg)],
                capture_output=True,
                text=True,
            )
            (v1 / "a.md").write_text("# A changed\n", encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "vault-drift-all.py"), "--state-root", str(st), str(cfg)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("~ a.md", r.stdout)
            self.assertIn("missing: path missing", r.stderr)

    @unittest.skipUnless(_has_turbovault(), "turbovault binary not installed")
    def test_drift_check_recognizes_audited_move(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "v"
            v.mkdir()
            (v / "a.md").write_text("# Hello\n", encoding="utf-8")
            st = Path(d) / "state"
            checker = str(SCRIPTS_DIR / "vault-drift-check.py")

            r0 = subprocess.run(
                [sys.executable, checker, "--vault", str(v), "--state-root", str(st), "--store"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r0.returncode, 0, r0.stdout + r0.stderr)

            env = os.environ.copy()
            env["XDG_CACHE_HOME"] = str(Path(d) / "cache")
            p = subprocess.Popen(
                ["turbovault", "-t", "stdio", "-p", "production", "--vault", str(v), "--no-confirm-destructive"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            reqs = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "move_note", "arguments": {"from": "a.md", "to": "b.md"}}},
            ]
            p.communicate("\n".join(json.dumps(x) for x in reqs) + "\n", timeout=15)
            self.assertTrue((v / "b.md").exists())

            r1 = subprocess.run(
                [sys.executable, checker, "--vault", str(v), "--state-root", str(st), "--json"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
            report = json.loads(r1.stdout)
            self.assertEqual(report["window"]["external"], [])
            self.assertEqual(report["window"]["external_delete"], [])
            self.assertIn("b.md", report["window"]["audited"])
            self.assertIn("a.md", report["window"]["audited_delete"])
            self.assertEqual(report["historical"]["diverging"], [])
            self.assertEqual(report["historical"]["missing_despite_audit"], [])


class TestShimTemplate(unittest.TestCase):
    def test_shim_missing_config_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            env = os.environ.copy()
            env["TURBOVAULT_DRIFT_SKILL_SCRIPTS"] = str(SCRIPTS_DIR)
            env["TURBOVAULT_CONFIG"] = str(Path(d) / "does-not-exist.yaml")
            r = subprocess.run(
                [sys.executable, str(TEMPLATES_DIR / "vault-drift-shim.py")],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("config not found", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
