# Agent Guidelines for Skills Repository

This repository contains OpenCode/Claude Code skills - reusable capabilities defined via SKILL.md files.

## Repository Structure

```
skills/
├── skill-name/
│   ├── SKILL.md (required - skill definition)
│   ├── reference/ (optional - detailed docs, lowercase names)
│   ├── scripts/ (optional - Node.js helpers)
│   └── templates/ (optional - output templates)
.claude/skills/ (personal skills - available globally)
```

## SKILL.md is Executable Code

**Important:** SKILL.md files are **executable instructions**, not static documentation. They define workflows and actions that agents follow when invoked.

### Implications

- **Commands must be complete and runnable**: Every command example should work as-is
- **Ambiguity is critical**: Any unclear or incomplete instructions will cause agent failures
- **Test by execution**: When possible, verify commands actually work before committing
- **Version sensitivity**: Tools and commands should reference current versions
- **Error handling**: Include error scenarios and how agents should handle them

### Executable-Specific Validation

When creating/editing SKILL.md:

- [ ] Every command is complete and can be executed directly
- [ ] Required flags/parameters are specified, not implied
- [ ] Error conditions are documented with expected agent behavior
- [ ] Tool version requirements are stated if critical
- [ ] No placeholder text like `[add flags]` or `[complete this]`
- [ ] Commands follow the actual tool's syntax and behavior

## Skill Creation and Editing

**Use the skill-builder skill** for all skill-related tasks:
- Creating new skills from scratch
- Editing existing skills (descriptions, structure, content)
- Converting sub-agents to skill format
- Refining skill metadata and invocation triggers

The skill-builder skill provides comprehensive guidance on SKILL.md conventions, file naming, content style, and best practices.

**Authoritative Sources:**
- agentskills.io specification - Authoritative format requirements
- Anthropic best practices - Recommended conventions (gerund form is a convention, not requirement)

## Git Conventions

### Commit Messages

Follow conventional commits format:

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Types:** feat, fix, docs, style, refactor, test, chore

**Skill Changes:**
Since SKILL.md files are executable code (not documentation), changes should be categorized as:
- **feat**: New skills or new capabilities/workflows in existing skills
- **fix**: Fixing broken commands, incorrect workflows, or agent failures
- **refactor**: Restructuring SKILL.md without changing behavior (e.g., reordering, organizing)
- **chore**: Maintenance tasks (updating tool versions, cleaning up examples)
- **docs**: Only for changes to reference/ directory or AGENTS.md itself

**Version Updates:**
Update `metadata.version` in SKILL.md when making changes:
- **feat**: Increment minor version (0.1.0 → 0.2.0)
- **fix**: Increment patch version (0.1.0 → 0.1.1)
- **refactor**/`chore`/`docs**: No version change needed

**Examples:**
```
feat(csv-processor): add xsv integration for filtering
docs(skill-builder): update description field examples
fix(container-use): correct networking command syntax
refactor(ocx-manager): simplify ghost mode workflow
```

**Good practices:**
- Start with lowercase in description
- Use imperative mood ("add" not "added", "fix" not "fixed")
- Wrap body at 72 chars
- Reference issues in footers: "Closes #123"
- Limit subject line to 72 chars

### Branch Naming

```
<type>-<short-description>

Examples:
feat/add-csv-filtering
fix/update-command-reference
docs/refine-structure-guide
```

### Workflow

When working on skills:
1. Create feature branch: `git checkout -b feat/add-new-skill`
2. Use skill-builder skill to create/edit the skill
3. Validate skill conventions
4. Run skills-ref validation: `./skills/skill-builder/scripts/skills-ref.sh validate ./skill-path`
5. Update `metadata.version` in SKILL.md according to semantic versioning:
   - `feat`: Increment minor version (0.1.0 → 0.2.0)
   - `fix`: Increment patch version (0.1.0 → 0.1.1)
   - `refactor`/`chore`: No version change needed
   - `docs`: No version change needed
6. Commit with conventional commit message
7. Push and create PR if needed

## Core Conventions

### File Naming

**Skills:**
- **Preferred in this repository**: Noun phrases (e.g., `container-use`, `ocx-use`)
- Per agentskills.io spec: Max 64 characters, lowercase letters/numbers/hyphens only, cannot start/end with hyphen
- Acceptable formats from Anthropic's conventions:
  - Noun phrases (preferred here): `container-use`, `ocx-manager`, `pdf-processing`
  - Gerund form (recommended by Anthropic): `processing-pdfs`, `analyzing-spreadsheets`
  - Action-oriented: `use-containers`, `manage-ocx`
- Avoid: Generic names like `helper`, `utils`, `tools`

**Supporting Files:**
- Lowercase, intention-revealing names
- Good: `./reference/aws-lambda-patterns.md`, `./scripts/transform-data.js`
- Bad: `./reference.md`, `./scripts/utils.js`, `./Reference.md`

### Content Style

**Be Concise:**
- Only include context Claude doesn't already know
- Remove: "You are an expert...", background info, verbose intros
- Keep: Specific workflows, domain knowledge, exact commands

**Be Actionable:**
- Start with verbs (Validate, Create, Deploy)
- Provide complete, runnable commands
- Include concrete examples with expected output

**Examples:**
```bash
# Good - complete command
gh pr create --title "Add auth" --body "$(cat <<'EOF'
## Summary
Implemented JWT authentication
EOF
)"

# Bad - incomplete
gh pr create [with flags]
```

### Code and Scripting

**Emphasis:**
- Use CLI tools liberally: `gh`, `aws`, `npm`, `git`, `jq`, domain tools
- Use Node.js v24+ with ESM for scripts (`.js` files, not TypeScript)
- Prefer global NPM packages: `npm install -g csv-parse`
- Show how to chain CLI operations

**Node.js Script Template:**
```javascript
#!/usr/bin/env node
import { readFile } from 'fs/promises';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Implementation
```

**Avoid:**
- Python scripts (use Node.js)
- TypeScript in scripts (use .js)
- Ad-hoc approaches without leveraging existing CLI tools

### File Organization

**Progressive Disclosure Pattern:**
- SKILL.md: Executable core workflow, ideally ~150-200 lines (max 500)
- reference/: Comprehensive details, 200-500+ lines acceptable
- Use skinny pointers: "See `./reference/csv-processing-methodology.md` for comprehensive approach"
- Reference with relative paths: `./filename.md` (not absolute paths)

**Recommended Structure (from official spec):**
```
skill-name/
├── SKILL.md (required - main instructions)
├── reference/ (optional - detailed documentation)
│   ├── domain-specific.md
│   └── api-reference.md
├── scripts/ (optional - Node.js helpers)
└── templates/ (optional - output templates)
```

**Executable vs Documentation:**
- SKILL.md = Executable agent instructions (treat as code)
- reference/ = Static documentation (treat as docs)
- scripts/ = Actual code (Node.js executable scripts)

**Important:** The skill-builder's SKILL.md shows an older pattern with files in the root directory, but this contradicts the official best practices. Always use the `reference/` directory structure shown above.

### Common Anti-Patterns

❌ Over-explaining obvious concepts
❌ Vague language: "process appropriately" → use exact commands
❌ Python scripts → use Node.js
❌ Generic file names: `./reference.md` → use `./reference/csv-patterns.md`
❌ Too many options: pick one primary tool and show it
❌ Windows paths: use `/Users/name` or `./relative/path`

## Skills Validation

All skills must be validated using the skills-ref tool before committing:

```bash
./skills/skill-builder/scripts/skills-ref.sh validate ./skill-path
```

This validates that skills conform to the Agent Skills specification and checks for:
- Valid YAML frontmatter syntax
- Allowed fields only (name, description, license, compatibility, metadata, allowed-tools)
- Proper naming conventions
- File structure compliance

## Validation Checklist

After creating/editing a skill:

### Executable Validation (Critical)
- [ ] Every command is complete and can be executed directly
- [ ] Required flags/parameters are specified, not implied
- [ ] Error conditions are documented with expected agent behavior
- [ ] Tool version requirements are stated if critical
- [ ] No placeholder text like `[add flags]` or `[complete this]`

### Skill Conventions
- [ ] YAML syntax valid (spaces not tabs, no illegal fields)
- [ ] Name follows agentskills.io spec: <64 chars, lowercase letters/numbers/hyphens only
- [ ] Name uses noun phrase format (e.g., `container-use`, `ocx-use`)
- [ ] Description starts with "Use this skill when...", <1024 chars, includes triggers
- [ ] SKILL.md under 500 lines (ideally ~150-200)
- [ ] All relative paths (./file.md) correct
- [ ] Supporting files lowercase, intention-revealing names
- [ ] Scripts are Node.js (not Python)
- [ ] Examples complete and runnable
- [ ] Commit message follows conventional commits format
- [ ] Metadata includes `source` (git repository URL) and `version` (e.g., "0.1.0")
- [ ] Pass skills-ref validation: Run `./skills/skill-builder/scripts/skills-ref.sh validate ./skill-path`

## Documentation Resources

- Use the `skill-builder` skill for comprehensive skill creation guidance
- https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview.md
- https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices.md
- See `.claude/skills/skill-builder/reference/` for detailed patterns
