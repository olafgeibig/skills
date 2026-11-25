#!/usr/bin/env python3
"""Probe what a TurboVault config file registers over MCP stdio.

    python3 probe-config.py [--allow-env VAR ...] [--use-existing-cache] [--list-tools] config.yaml [...]

Runs TurboVault with `-t stdio` in a sanitized environment (always blocking
ambient `OBSIDIAN_VAULT_PATH` and `TURBOVAULT_*` variables so shell state
cannot inject extra vaults or override flags). If a YAML `vaults[].path`
references an environment variable (`$VAR` / `${VAR}`) outside the minimal safe
set (`HOME`, etc.), pass `--allow-env VAR` explicitly so both the server and
the expected-path comparison receive the exact same value; otherwise the probe
fails cleanly with an actionable hint instead of silently expanding differently.

Validates the MCP initialize handshake plus `list_vaults` and `tools/list`
under one total deadline (draining stdout and stderr concurrently via
`communicate()`), and verifies registered vault names and resolved paths
against the YAML file on clean-start probes when PyYAML is available.

Exit 0 only when every config succeeded with valid MCP responses and matched
expected clean-start registrations; exit 1 on any startup, timeout, protocol,
tool, env-var, or vault-mismatch error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SAFE_ENV_KEYS = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT")
ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def _is_blocked_env_var(name: str) -> bool:
    return name == "OBSIDIAN_VAULT_PATH" or name.startswith("TURBOVAULT_")


def find_binary() -> str:
    explicit = os.environ.get("TURBOVAULT_BIN")
    if explicit:
        return explicit
    found = shutil.which("turbovault")
    if found:
        return found
    local = Path.home() / ".local" / "bin" / "turbovault"
    if local.exists():
        return str(local)
    raise SystemExit("turbovault binary not found; set TURBOVAULT_BIN")


def _sanitized_env(
    isolate_cache: bool,
    tmpdir: str | None,
    allow_env: list[str] | None = None,
) -> dict[str, str]:
    """Build a minimal child environment without ambient TURBOVAULT_* or OBSIDIAN_VAULT_PATH."""
    env: dict[str, str] = {}
    for key in SAFE_ENV_KEYS:
        val = os.environ.get(key)
        if val is not None:
            env[key] = val
    for key in allow_env or []:
        if _is_blocked_env_var(key):
            raise ValueError(
                f"refusing --allow-env {key}: TurboVault/Obsidian override variables stay blocked"
            )
        val = os.environ.get(key)
        if val is not None:
            env[key] = val
    if isolate_cache and tmpdir is not None:
        env["XDG_CACHE_HOME"] = tmpdir
    elif not isolate_cache and "XDG_CACHE_HOME" in os.environ:
        env["XDG_CACHE_HOME"] = os.environ["XDG_CACHE_HOME"]
    return env


def _expand_path_with_env(raw: str, env: dict[str, str]) -> Path:
    def repl(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        return env.get(name, match.group(0))

    expanded = ENV_VAR_RE.sub(repl, raw)
    if expanded == "~" or expanded.startswith("~/"):
        home = env.get("HOME") or str(Path.home())
        expanded = home + expanded[1:]
    return Path(expanded).resolve()


def _parse_yaml_vaults(config_path: Path) -> tuple[list[tuple[str, str]], list[str]] | None:
    """Return `(entries[(name, raw_path)], referenced_env_vars)` using PyYAML if installed."""
    try:
        import yaml  # type: ignore
    except ImportError:
        return None
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("vaults"), list):
        return [], []
    entries: list[tuple[str, str]] = []
    ref_vars: list[str] = []
    seen_vars: set[str] = set()
    for entry in data["vaults"]:
        if isinstance(entry, dict) and entry.get("name") and entry.get("path"):
            raw_path = str(entry["path"])
            entries.append((str(entry["name"]), raw_path))
            for m in ENV_VAR_RE.finditer(raw_path):
                vname = m.group(1) or m.group(2)
                if vname and vname not in seen_vars:
                    seen_vars.add(vname)
                    ref_vars.append(vname)
    return entries, ref_vars


def _payload(msg: dict) -> dict | None:
    """Return the JSON payload of a tools/call result, structured or textual."""
    result = msg.get("result") or {}
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    for block in result.get("content") or []:
        if block.get("type") == "text":
            try:
                return json.loads(block.get("text", ""))
            except json.JSONDecodeError:
                return None
    return None


def _fmt_error(err: object) -> str:
    if isinstance(err, dict):
        code = err.get("code")
        message = err.get("message") or str(err)
        return f"code={code} {message}" if code is not None else str(message)
    return str(err)


def probe(
    config: str,
    profile: str = "production",
    timeout: int = 60,
    isolate_cache: bool = True,
    allow_env: list[str] | None = None,
) -> dict:
    out: dict = {
        "ok": False,
        "error": None,
        "server_version": None,
        "vaults": None,
        "active": None,
        "tools": None,
        "stderr": "",
    }
    tmpdir = (
        tempfile.TemporaryDirectory(prefix="turbovault-probe-")
        if isolate_cache
        else None
    )
    try:
        try:
            env = _sanitized_env(
                isolate_cache,
                tmpdir.name if tmpdir is not None else None,
                allow_env=allow_env,
            )
        except ValueError as exc:
            out["error"] = str(exc)
            return out

        yaml_info = _parse_yaml_vaults(Path(config))
        if yaml_info is not None:
            yaml_entries, ref_vars = yaml_info
            missing_allowed = [v for v in ref_vars if v not in env]
            if missing_allowed:
                hint = " ".join(f"--allow-env {v}" for v in missing_allowed)
                out["error"] = (
                    f"vault path references env var(s) {missing_allowed} not present in "
                    f"isolated probe env; set them and pass `{hint}` to forward explicitly"
                )
                return out
        else:
            yaml_entries = None

        reqs = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "probe-config", "version": "1"},
                },
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "list_vaults", "arguments": {}},
            },
            {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
        ]
        stdin_payload = "\n".join(json.dumps(r) for r in reqs) + "\n"

        proc = subprocess.Popen(
            [find_binary(), "-t", "stdio", "-p", profile, "--config", config],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        try:
            stdout, stderr = proc.communicate(input=stdin_payload, timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            out["stderr"] = (stderr or "").strip()
            out["error"] = f"timed out after {timeout}s"
            return out

        out["stderr"] = (stderr or "").strip()
        by_id: dict[int, dict] = {}
        for line in (stdout or "").splitlines():
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(msg, dict) and isinstance(msg.get("id"), int):
                by_id[msg["id"]] = msg

        # 1. Validate initialize handshake
        init_msg = by_id.get(1)
        if init_msg is None:
            out["error"] = f"missing initialize response (exit {proc.returncode})"
            return out
        if "error" in init_msg:
            out["error"] = f"initialize failed: {_fmt_error(init_msg['error'])}"
            return out
        init_result = init_msg.get("result")
        if not isinstance(init_result, dict):
            out["error"] = "initialize returned non-object result"
            return out
        server_info = init_result.get("serverInfo")
        if isinstance(server_info, dict):
            out["server_version"] = server_info.get("version")

        # 2. Validate list_vaults response
        lv_msg = by_id.get(2)
        if lv_msg is None:
            out["error"] = f"missing list_vaults response (exit {proc.returncode})"
            return out
        if "error" in lv_msg:
            out["error"] = f"list_vaults JSON-RPC error: {_fmt_error(lv_msg['error'])}"
            return out
        lv_result = lv_msg.get("result")
        if not isinstance(lv_result, dict):
            out["error"] = "list_vaults returned non-object result"
            return out
        if lv_result.get("isError"):
            out["error"] = f"list_vaults MCP error: {lv_result.get('content')}"
            return out
        payload = _payload(lv_msg)
        if not isinstance(payload, dict) or payload.get("success") is not True:
            out["error"] = f"list_vaults failed payload validation: {payload}"
            return out
        data = payload.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("vaults"), list):
            out["error"] = f"list_vaults missing data.vaults array: {payload}"
            return out

        parsed_vaults = []
        for v in data["vaults"]:
            if not isinstance(v, dict):
                continue
            cfg = v.get("config") if isinstance(v.get("config"), dict) else {}
            parsed_vaults.append(
                {
                    "name": v.get("name"),
                    "path": v.get("path") or cfg.get("path"),
                    "write_backend": v.get("write_backend") or cfg.get("write_backend"),
                    "allowed_operations": cfg.get("allowed_operations"),
                    "reconcile_external_changes": cfg.get("reconcile_external_changes"),
                    "is_active": bool(v.get("is_default")),
                    "yaml_default": cfg.get("is_default"),
                }
            )
        out["vaults"] = parsed_vaults
        out["active"] = data.get("active_vault")

        # 3. Validate tools/list response
        tl_msg = by_id.get(3)
        if tl_msg is None:
            out["error"] = f"missing tools/list response (exit {proc.returncode})"
            return out
        if "error" in tl_msg:
            out["error"] = f"tools/list JSON-RPC error: {_fmt_error(tl_msg['error'])}"
            return out
        tl_result = tl_msg.get("result")
        if not isinstance(tl_result, dict) or not isinstance(tl_result.get("tools"), list):
            out["error"] = f"tools/list missing tools array: {tl_msg}"
            return out
        out["tools"] = sorted(
            t["name"]
            for t in tl_result["tools"]
            if isinstance(t, dict) and isinstance(t.get("name"), str)
        )

        # 4. On clean-start probes, verify registered vaults match YAML declarations
        if isolate_cache and yaml_entries is not None:
            expected = {
                name: _expand_path_with_env(raw_path, env)
                for name, raw_path in yaml_entries
            }
            actual = {
                v["name"]: Path(v["path"]).expanduser().resolve()
                for v in parsed_vaults
                if v.get("name") and v.get("path")
            }
            if set(actual.keys()) != set(expected.keys()):
                out["error"] = (
                    f"registered vault names {sorted(actual.keys())} != "
                    f"expected YAML vaults {sorted(expected.keys())}"
                )
                return out
            for name, exp_path in expected.items():
                if actual[name] != exp_path:
                    out["error"] = (
                        f"vault '{name}' path {actual[name]} != expected {exp_path}"
                    )
                    return out

        out["ok"] = True
        return out
    finally:
        if tmpdir is not None:
            tmpdir.cleanup()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Probe what a TurboVault config file registers over MCP stdio."
    )
    ap.add_argument(
        "--use-existing-cache",
        action="store_true",
        help="Do not isolate XDG_CACHE_HOME (tests interaction with existing project cache).",
    )
    ap.add_argument(
        "--allow-env",
        action="append",
        default=[],
        metavar="VAR",
        help="Explicitly forward this environment variable for YAML path expansion (repeatable; OBSIDIAN_VAULT_PATH and TURBOVAULT_* stay blocked).",
    )
    ap.add_argument(
        "--list-tools",
        action="store_true",
        help="Also print sorted tool names returned by tools/list.",
    )
    ap.add_argument(
        "--profile",
        default="production",
        help="TurboVault --profile value (default: production).",
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Total timeout in seconds per config probe (default: 60).",
    )
    ap.add_argument("configs", nargs="+", help="One or more TurboVault YAML config paths.")
    args = ap.parse_args(argv)

    failed = False
    for config in args.configs:
        path = Path(config).expanduser()
        if not path.exists():
            print(f"== {config}\n   ERROR: MISSING config file")
            failed = True
            continue
        res = probe(
            str(path),
            profile=args.profile,
            timeout=args.timeout,
            isolate_cache=not args.use_existing_cache,
            allow_env=args.allow_env,
        )
        cache_mode = "existing" if args.use_existing_cache else "isolated"
        if not res["ok"]:
            print(f"== {path} (cache: {cache_mode})")
            print(f"   ERROR: {res['error']}")
            if res["stderr"]:
                last = res["stderr"].splitlines()[-1]
                print(f"   stderr: {last}")
            failed = True
            continue

        vaults = res["vaults"] or []
        tools = res["tools"] or []
        yaml_defaults = [v["name"] for v in vaults if v["yaml_default"] is True]
        ver = f", server: {res['server_version']}" if res["server_version"] else ""
        print(f"== {path} (cache: {cache_mode}{ver})")
        print(f"   active: {res['active']}")
        print(f"   vaults ({len(vaults)}):")
        for v in vaults:
            flags = []
            if v["is_active"]:
                flags.append("active")
            flags.append(f"yaml:is_default={v['yaml_default']}")
            flags.append(f"backend={v['write_backend']}")
            ops = v["allowed_operations"]
            flags.append(f"ops={ops if ops is not None else 'default(all)'}")
            rec = v["reconcile_external_changes"]
            flags.append(f"reconcile={rec if rec is not None else 'default'}")
            print(f"     - {v['name']} -> {v['path']} [{', '.join(flags)}]")
        if yaml_defaults and res["active"] not in yaml_defaults:
            print(
                f"   WARNING: active vault '{res['active']}' differs from YAML "
                f"is_default=true ({', '.join(yaml_defaults)}) — reorder vaults: "
                "so the desired default is first"
            )
        print(f"   tools listed: {len(tools)}")
        if args.list_tools:
            print(f"   tool names: {', '.join(tools)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
