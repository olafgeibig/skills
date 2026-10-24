#!/usr/bin/env python3
"""Run the vault drift check across every vault registered with TurboVault.

Reads `vaults:` from the TurboVault config (default ~/.turbovault/bosch.yaml),
runs vault-drift-check.py --quiet --store for each, and prints the report of the
vaults that have changes the audit log does not cover. Prints nothing at all
when every vault is in sync, so it can run as a watchdog (cron, no_agent).

Exit codes: 0 always when the check ran (even if it found drift — the report is
the signal), 1 if the config or a check could not be read. A single failing
vault does not abort the rest.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

def default_config() -> Path:
    env = os.environ.get("TURBOVAULT_CONFIG")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".turbovault" / "config.yaml"
CHECKER = Path(__file__).with_name("vault-drift-check.py")


def read_vaults(config: Path) -> list[tuple[str, str]]:
    text = config.read_text(encoding="utf-8")
    vaults: list[tuple[str, str]] = []
    name = None
    for line in text.splitlines():
        m = re.match(r"\s*-\s*name:\s*\"?([^\"]+?)\"?\s*$", line)
        if m:
            name = m.group(1)
            continue
        m = re.match(r"\s*path:\s*\"?([^\"]+?)\"?\s*$", line)
        if m and name:
            vaults.append((name, m.group(1)))
            name = None
    return vaults


def main() -> int:
    argv = sys.argv[1:]
    state_root = None
    if "--state-root" in argv:
        i = argv.index("--state-root")
        state_root = argv[i + 1]
        del argv[i:i + 2]
    config = Path(argv[0]).expanduser() if argv else default_config()
    if not config.exists():
        print(f"config not found: {config}", file=sys.stderr)
        return 1
    vaults = read_vaults(config)
    if not vaults:
        print(f"no vaults parsed from {config}", file=sys.stderr)
        return 1

    blocks: list[str] = []
    errors: list[str] = []
    for name, path in vaults:
        if not Path(path).is_dir():
            errors.append(f"{name}: path missing ({path})")
            continue
        proc = subprocess.run(
            [sys.executable, str(CHECKER), "--vault", path, "--quiet", "--store",
             "--name", name] + (["--state-root", state_root] if state_root else []),
            capture_output=True, text=True, timeout=600,
        )
        out = proc.stdout.strip()
        if proc.returncode != 0:
            errors.append(f"{name}: drift check failed (exit {proc.returncode}) {proc.stderr.strip()[:200]}")
            continue
        if out:
            blocks.append(out)

    if blocks:
        print(f"Vault drift check — {len(vaults)} vaults, {len(blocks)} with unaudited changes\n")
        print("\n\n".join(blocks))
    if errors:
        print("\nErrors:", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
    return 0 if blocks or not errors else 1


if __name__ == "__main__":
    sys.exit(main())
