#!/usr/bin/env python3
"""Cron entry point for the vault drift watchdog (template).

Copy this file to `<profile>/scripts/vault-drift-all.py` and register a cron job
with `no_agent: true` that runs it. The cron runner only accepts scripts under
the profile's `scripts/` directory, which is why the shim exists at all — the
logic lives in the `turbovault-use` skill.

Two things are installation-specific and belong in the copy, not in the skill:

  CONFIG      the TurboVault config file this installation actually runs (it is
              not always `~/.turbovault/config.yaml`; a machine that starts the
              server with `--config ~/.turbovault/<name>.yaml` needs that path
              here)
  STATE_ROOT  the drift state directory, kept under this profile so scheduled
              runs share the baseline with manual ones

Everything else is discovered at runtime, so moving the skill repository does
not silently break the job: the shim fails loudly instead of reporting "clean".
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SKILL_NAME = "turbovault-use"
SKILL_SCRIPT = "vault-drift-all.py"

# --- adjust per installation -------------------------------------------------
CONFIG = Path(os.environ.get("TURBOVAULT_CONFIG")
              or (Path.home() / ".turbovault" / "config.yaml"))
HERMES_HOME = Path(os.environ.get("HERMES_HOME")
                   or (Path.home() / ".hermes" / "profiles" / "default"))
STATE_ROOT = HERMES_HOME / "state" / "vault-drift"
# -----------------------------------------------------------------------------


def candidate_dirs():
    """Directories that may hold the skill's scripts, most specific first."""
    explicit = os.environ.get("TURBOVAULT_DRIFT_SKILL_SCRIPTS")
    if explicit:
        yield Path(explicit).expanduser()
    for root in (HERMES_HOME / "skills", Path.home() / "work" / "skills"):
        if not root.is_dir():
            continue
        direct = root / SKILL_NAME / "scripts"
        if direct.is_dir():
            yield direct
        for match in sorted(root.glob(f"**/{SKILL_NAME}/scripts")):
            yield match


def find_skill_script() -> Path | None:
    for directory in candidate_dirs():
        candidate = directory / SKILL_SCRIPT
        if candidate.exists():
            return candidate
    return None


def main() -> int:
    script = find_skill_script()
    if script is None:
        print(f"cannot locate {SKILL_NAME}/scripts/{SKILL_SCRIPT}; "
              "set TURBOVAULT_DRIFT_SKILL_SCRIPTS to its directory", file=sys.stderr)
        return 1
    if not CONFIG.exists():
        print(f"TurboVault config not found: {CONFIG} — edit CONFIG in this shim "
              "to the file this installation starts the server with", file=sys.stderr)
        return 1
    return subprocess.call([
        sys.executable, str(script), str(CONFIG),
        "--state-root", str(STATE_ROOT),
    ])


if __name__ == "__main__":
    sys.exit(main())
