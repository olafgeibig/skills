# Node.js and CLI Patterns

Use this reference only when the owning repository permits or prefers Node.js. The Agent Skills specification does not require a scripting language.

## Choose a script only when needed

Prefer an existing client tool or short command when it already performs the task safely. Add a script when the workflow needs repeatable parsing, validation, transformation, or error handling.

## Repository convention

This repository prefers:

- Node.js scripts rather than Python;
- `.js` files with ESM imports;
- explicit dependency and version requirements;
- local or pinned dependencies rather than unnecessary global installation;
- complete commands and useful errors.

Other repositories may choose Python, Bash, or another language.

## Minimal script

```javascript
#!/usr/bin/env node
import { readFile, writeFile } from 'node:fs/promises';

async function main() {
  const inputPath = process.argv[2];
  const outputPath = process.argv[3];

  if (!inputPath || !outputPath) {
    throw new Error('Usage: node transform.js <input.json> <output.json>');
  }

  const data = JSON.parse(await readFile(inputPath, 'utf8'));
  await writeFile(outputPath, `${JSON.stringify(data, null, 2)}\n`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
```

## Command execution

Prefer argument-safe process APIs over interpolated shell strings when values are dynamic:

```javascript
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);
const { stdout } = await execFileAsync('git', ['status', '--short']);
console.log(stdout);
```

## Dependency discipline

- Use built-in modules when sufficient.
- Pin externally executed package versions where reproducibility matters.
- Document installation and required runtime versions.
- Avoid global installations unless the owning environment explicitly manages them.
- Never embed tokens, passwords, or private endpoints.

## Verification

For every bundled script:

1. Run a valid-input case.
2. Run at least one malformed- or missing-input case.
3. Confirm nonzero exit status on failure.
4. Confirm outputs are deterministic and correctly formatted.
5. Document the exact invocation in `SKILL.md` or the owning reference.
