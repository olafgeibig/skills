#!/usr/bin/env python3
"""Run the vault drift check across vaults registered in a TurboVault config.

Requires PyYAML (`pip install pyyaml`). Reads `vaults:` (including per-vault
`excluded_paths`) from the TurboVault config (default $TURBOVAULT_CONFIG or
~/.turbovault/config.yaml) and runs `vault-drift-check.py --quiet` for each
selected vault.

Content snapshotting (`--store`) is **opt-in** (off by default) so sensitive
note contents are never copied into the state directory unless explicitly
requested. Use `--vault <name>` (repeatable) to restrict checks to specific
vaults.

Exit codes: 0 when every checked vault succeeded (with or without drift), 1 if
PyYAML is missing, the config could not be read/parsed, or any vault check
failed.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def default_config() -> Path:
    env = os.environ.get("TURBOVAULT_CONFIG")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".turbovault" / "config.yaml"


CHECKER = Path(__file__).with_name("vault-drift-check.py")


def read_vaults(config: Path) -> list[dict]:
    """Parse `vaults:` entries from TurboVault YAML via PyYAML."""
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required to parse TurboVault YAML configs (pip install pyyaml)"
        ) from exc

    data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not isinstance(data.get("vaults"), list):
        return []
    parsed: list[dict] = []
    for entry in data["vaults"]:
        if not isinstance(entry, dict) or not entry.get("name") or not entry.get("path"):
            continue
        raw_excludes = entry.get("excluded_paths") or []
        if isinstance(raw_excludes, str):
            excludes = [raw_excludes]
        elif isinstance(raw_excludes, list):
            excludes = [str(x) for x in raw_excludes if x]
        else:
            excludes = []
        parsed.append(
            {
                "name": str(entry["name"]),
                "path": str(entry["path"]),
                "excluded_paths": excludes,
            }
        )
    return parsed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run vault-drift-check across vaults configured in TurboVault YAML."
    )
    ap.add_argument(
        "config",
        nargs="?",
        help="TurboVault YAML config path (default: $TURBOVAULT_CONFIG or ~/.turbovault/config.yaml)",
    )
    ap.add_argument(
        "--state-root",
        help="Override drift state root directory.",
    )
    ap.add_argument(
        "--vault",
        action="append",
        dest="only_vaults",
        default=[],
        help="Only check these named vault(s) (repeatable; default: all configured vaults).",
    )
    ap.add_argument(
        "--store",
        action="store_true",
        help="Opt in to copying post-baseline changed note contents into the object store.",
    )
    args = ap.parse_args(argv)

    config = Path(args.config).expanduser() if args.config else default_config()
    if not config.exists():
        print(f"config not found: {config}", file=sys.stderr)
        return 1
    try:
        vaults = read_vaults(config)
    except Exception as exc:
        print(f"failed to parse {config}: {exc}", file=sys.stderr)
        return 1
    if not vaults:
        print(f"no vaults parsed from {config}", file=sys.stderr)
        return 1

    if args.only_vaults:
        wanted = set(args.only_vaults)
        found_names = {v["name"] for v in vaults}
        missing_names = sorted(wanted - found_names)
        if missing_names:
            print(
                f"requested vault(s) not found in {config}: {', '.join(missing_names)}",
                file=sys.stderr,
            )
            return 1
        vaults = [v for v in vaults if v["name"] in wanted]

    blocks: list[str] = []
    errors: list[str] = []
    for entry in vaults:
        name = entry["name"]
        expanded = Path(os.path.expandvars(entry["path"])).expanduser()
        if not expanded.is_dir():
            errors.append(f"{name}: path missing ({expanded})")
            continue
        cmd = [
            sys.executable,
            str(CHECKER),
            "--vault",
            str(expanded),
            "--quiet",
            "--name",
            name,
        ]
        if args.store:
            cmd.append("--store")
        if args.state_root:
            cmd.extend(["--state-root", args.state_root])
        for exc_path in entry["excluded_paths"]:
            cmd.extend(["--exclude", exc_path])

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        out = proc.stdout.strip()
        if proc.returncode != 0:
            errors.append(
                f"{name}: drift check failed (exit {proc.returncode}) {proc.stderr.strip()[:200]}"
            )
            continue
        if out:
            blocks.append(out)

    if blocks:
        print(
            f"Vault drift check — {len(vaults)} vaults, {len(blocks)} with unaudited changes\n"
        )
        print("\n\n".join(blocks))
    if errors:
        print("\nErrors:", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
