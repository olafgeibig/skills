# Python and CLI Patterns

Use this reference when the owning repository permits or prefers Python. The Agent Skills specification does not require a scripting language.

## Choose a script only when needed

Prefer an existing client tool or short command when it already performs the task safely. Add a script when the workflow needs repeatable parsing, validation, transformation, or error handling.

## Repository convention

This repository prefers:

- Python for Hermes-adjacent tooling;
- the standard library when sufficient;
- explicit runtime and dependency requirements;
- `uv` when third-party packages are needed;
- complete commands and useful errors.

Other repositories may choose JavaScript, Bash, or another language.

## Minimal script

```python
#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: transform.py <input.json> <output.json>", file=sys.stderr)
        return 2

    source = Path(sys.argv[1])
    target = Path(sys.argv[2])
    data = json.loads(source.read_text(encoding="utf-8"))
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

## Subprocess execution

Use argument lists rather than interpolated shell strings for dynamic values:

```python
from subprocess import run

result = run(
    ["git", "status", "--short"],
    check=True,
    capture_output=True,
    text=True,
)
print(result.stdout)
```

## Dependency discipline

- Use the standard library when sufficient.
- Declare and pin external dependencies when reproducibility matters.
- Use the active project environment instead of installing packages globally.
- Validate external inputs and paths.
- Never embed tokens, passwords, or private endpoints.

## Verification

For every bundled script:

1. Run a valid-input case.
2. Run at least one malformed- or missing-input case.
3. Confirm nonzero exit status on failure.
4. Confirm outputs are deterministic and correctly formatted.
5. Document the exact invocation in `SKILL.md` or the owning reference.
