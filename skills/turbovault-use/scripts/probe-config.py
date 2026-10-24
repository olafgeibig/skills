#!/usr/bin/env python3
"""Probe what a TurboVault config file actually registers, over MCP stdio.

    python3 probe-config.py ~/.turbovault/config.yaml [more.yaml ...]

Prints, per config: the registered vaults with their default flag, the active
vault, and how many tools `tools/list` exposes. That is the read-back a config
change needs — it proves the server parsed the file and what the client would
see — without restarting Hermes or disturbing a running session.

Use it when:
  * a profile gets its own config and you must show which vaults it can reach;
  * `show_advanced_tools` / `disabled` changed and you want the tool count;
  * a vault is missing from `list_vaults` and it is unclear whether the file or
    the running process is at fault.

Exit 0 when every config answered, 1 if any probe failed to produce a response.
"""

from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
from pathlib import Path


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


def probe(config: str, profile: str = "production", timeout: int = 60) -> dict:
    proc = subprocess.Popen(
        [find_binary(), "-p", profile, "--config", config],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )

    def send(obj: dict) -> None:
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05", "capabilities": {},
        "clientInfo": {"name": "probe-config", "version": "1"}}})
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
          "params": {"name": "list_vaults", "arguments": {}}})
    send({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})

    out: dict = {"vaults": None, "active": None, "tools": None}
    try:
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == 2:
                payload = _payload(msg) or {}
                data = payload.get("data", payload)
                vaults = data.get("vaults") or []
                out["vaults"] = [(v.get("name"), bool(v.get("is_default"))) for v in vaults]
                out["active"] = data.get("active_vault")
            elif msg.get("id") == 3:
                out["tools"] = len((msg.get("result") or {}).get("tools") or [])
                break
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
    return out


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 1
    failed = False
    for config in argv:
        path = Path(config).expanduser()
        if not path.exists():
            print(f"== {config}\n   MISSING config file")
            failed = True
            continue
        res = probe(str(path))
        if res["vaults"] is None and res["tools"] is None:
            print(f"== {config}\n   no MCP response — binary or config failed to start")
            failed = True
            continue
        names = ", ".join(f"{n}{' (default)' if d else ''}" for n, d in res["vaults"] or [])
        print(f"== {path}")
        print(f"   vaults: {len(res['vaults'] or [])} — {names or '(none registered)'}")
        print(f"   active: {res['active']}")
        print(f"   tools listed: {res['tools']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
