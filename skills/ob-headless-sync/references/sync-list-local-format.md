# ob sync-list-local output format

The `ob sync-list-local` CLI does NOT output a friendly `Vault: <name> (<id>)`
line. The actual format (as of obsidian-headless 2025–2026) is a 4-line block
per vault:

```
Configured vaults:
  <32-hex-vault-id>          ← 2 leading spaces, 32 lowercase hex chars
    Path: <vault-path>       ← 4 leading spaces
    Host: <server-host>      ← 4 leading spaces, ignored
```

The vault-id is a 32-character lowercase hex string. It is **also** the
directory name under `~/.config/obsidian-headless/sync/<vault-id>/`, and the
basename of `state.db` lives one level below that.

## Pitfalls

### 1. Don't match `Vault: <name> (<id>)`

The `ob` documentation or third-party examples sometimes show a
`Vault: <name> (<id>)` format. That is wrong for the current CLI. Trying to
parse that will silently produce an empty vault list (no error, no warning),
and the script will exit as if "no vaults to sync". Always parse the
4-line block format above.

### 2. Don't strip the whole line before matching the vault-id

`line.strip()` then matching `^[a-f0-9]{32}$` will succeed only if the
vault-id is on its own line with no other content. In practice the line is
indented with 2 leading spaces. Either:
- `line.lstrip()` then check the original line has the right indent
  (`len(line) - len(stripped) >= 2`), or
- match the indented form directly: `^\s+([a-f0-9]{32})\s*$` (capture group 1).

Stripping everything and then matching as a bare 32-hex string will give
false positives on `Path: <hex-string>` and similar lines.

### 3. A Path line always follows a vault-id, but not immediately

The `Path:` line follows on the next line of the block, but if `ob` adds
new fields in the future (e.g. a `Last synced: ...` line), the parser must
be tolerant. Use a state machine: after seeing the vault-id, the next
`Path:` line ends the block, and any other non-blank line aborts the
current block (rather than treating it as the start of a new block that
has no Path yet).

## Reference regex

```python
import re

HEX32 = re.compile(r"^[a-f0-9]{32}$")
PATH_LINE = re.compile(r"^\s+Path:\s+(.+)$")

def parse_sync_list_local(out: str) -> list[tuple[str, str]]:
    """Return [(vault_id, vault_path), ...] from `ob sync-list-local` output."""
    pairs: list[tuple[str, str]] = []
    pending_id: str | None = None
    for line in out.splitlines():
        stripped = line.lstrip()
        if pending_id is None and HEX32.match(stripped) and len(line) - len(stripped) >= 2:
            pending_id = stripped
            continue
        if pending_id is not None:
            m = PATH_LINE.match(line)
            if m:
                pairs.append((pending_id, m.group(1).strip()))
                pending_id = None
                continue
            if stripped:  # non-blank, non-Path line: abort this block
                pending_id = None
    return pairs
```

This is the same parser used in the wrapper script
(`ob-sync-all-vaults`) and in `references/scripts/check-dirty.py`. Single
source of truth; copy-paste rather than re-derive.
