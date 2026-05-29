# INSTALL.md — Setup Guide

> This file is read by an agent to set up the improvements skill.
> Delete it after successful installation.

## Prerequisites

- The agent has `clarify` and `terminal` tools available
- The bundle's core skills are already installed
- Hermes CLI is available

## Installation Steps (for the agent)

### Step 1: Ask the user

Use the `clarify` tool to ask the user for four things:

1. **Bundle name** — e.g. `vault` (creates `vault-improvements`)
2. **Core skills** — comma-separated, e.g. `vault-ops, vault-wiki`
3. **Hermes profile** — e.g. `hermes-agent` (the improvements skill goes into `<hermes-home>/skills/`)
4. **Short description** — what does this bundle do?

Example clarify call:

```json
{
  "question": "To set up the improvements skill, I need:\n1. **Bundle name** — e.g. 'vault'\n2. **Core skills** — comma-separated, e.g. 'vault-ops, vault-wiki'\n3. **Hermes profile** — e.g. 'hermes-agent' (installation target for profile-specific skills)\n4. **Short description** — what does this bundle do?"
}
```

### Step 2: Resolve profile skills directory

```bash
# Default profile → ~/.hermes/skills/
# Named profile → ~/.hermes/profiles/<profile>/skills/
if [ "<profile>" = "default" ]; then
  SKILL_DIR="$HOME/.hermes/skills"
else
  SKILL_DIR="$HOME/.hermes/profiles/<profile>/skills"
fi
mkdir -p "$SKILL_DIR"
```

### Step 3: Install from template

```bash
cp -r <TEMPLATE_PATH> "$SKILL_DIR/<bundle>-improvements"
```

Where `<TEMPLATE_PATH>` is the location of this `skill-improvements` template.

### Step 4: Patch the copied files

```bash
# Replace placeholders in SKILL.md
sed -i 's/{{BUNDLE_NAME}}/<bundle>/g' "$SKILL_DIR/<bundle>-improvements/SKILL.md"
sed -i 's/{{SKILL_NAMES}}/<comma-separated skill names>/g' "$SKILL_DIR/<bundle>-improvements/SKILL.md"
sed -i 's/{{SKILL_LIST}}/<human-readable list>/g' "$SKILL_DIR/<bundle>-improvements/SKILL.md"
```

For the vault example:
```bash
SKILL_DIR="$HOME/.hermes/skills"
sed -i 's/{{BUNDLE_NAME}}/vault/g' "$SKILL_DIR/vault-improvements/SKILL.md"
sed -i 's/{{SKILL_NAMES}}/vault-ops, vault-wiki/g' "$SKILL_DIR/vault-improvements/SKILL.md"
sed -i 's/{{SKILL_LIST}}/vault-ops and vault-wiki/g' "$SKILL_DIR/vault-improvements/SKILL.md"
```

### Step 5: Create the Hermes bundle

```bash
hermes bundles create <bundle> \
  --skill <core-skill-1> \
  --skill <core-skill-2> \
  --skill <bundle>-improvements \
  --description "<description>"
```

The bundle references skills by name — Hermes resolves them globally (both `~/.agents/skills/` and profile-specific directories).

### Step 6: Git init in the new skill

```bash
cd "$SKILL_DIR/<bundle>-improvements"
git init
git add -A
git commit -m "init: <bundle>-improvements from template"
```

### Step 7: Clean up

```bash
rm "$SKILL_DIR/<bundle>-improvements/INSTALL.md"
```

## Verification

```bash
ls -la "$SKILL_DIR/<bundle>-improvements/"
hermes bundles list | grep <bundle>
git -C "$SKILL_DIR/<bundle>-improvements" log --oneline
```
