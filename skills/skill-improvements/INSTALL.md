# Install: {{BUNDLE_NAME}} Improvements

This is a **template skill** that must be installed and configured
before use. Follow these steps exactly.

## Prerequisites

- The core skills you want to bundle are already installed in the hermes profile skills directory or an external skill directory
  (e.g., `vault-ops`, `vault-wiki`, `turbovault-use`)
- Hermes Agent is installed and `hermes` CLI is available
- Git is available

## Installation Steps

Execute these steps in order. After each step, confirm success before proceeding.

### Step 1 — Ask the User

Use the `clarify` tool to ask the user the following questions.
Ask **all three questions at once** in a single `clarify` call:

1. **Bundle name:** What should the bundle be called? (one word, lowercase, e.g. `vault`)
2. **Skills:** Which skills belong in the bundle? (comma-separated, e.g. `vault-ops, vault-wiki, turbovault-use`)
3. **Description:** Short description of the bundle (e.g. "Vault Operations + Wiki + Learnings")

Example:

```markdown
Ich brauche ein paar Infos für die Einrichtung:

1. **Bundle-Name** — Ein Wort, lowercase, z.B. `vault`
2. **Skills im Bundle** — Komma-getrennt, z.B. `vault-ops, vault-wiki, turbovault-use`
3. **Beschreibung** — Kurzer Satz, z.B. "Vault Operations + Wiki + Learnings"
```

### Step 2 — Copy and Rename

```bash
# Source: the directory this INSTALL.md lives in
# Target: ~/.agents/skills/<bundle-name>-improvements
SKILL_SOURCE_DIR=$(dirname "$(dirname "$(readlink -f "$0")")")
cp -r "$SKILL_SOURCE_DIR" ~/.agents/skills/<bundle-name>-improvements
```

Replace `<bundle-name>` with the user's answer from Step 1.

### Step 3 — Patch SKILL.md

Replace all placeholders in the copied SKILL.md:

| Placeholder | Replace with |
|---|---|
| `{{BUNDLE_NAME}}` | The bundle name (e.g. `vault`) |
| `{{SKILL_NAMES}}` | Comma-separated skill names (e.g. `vault-ops, vault-wiki, turbovault-use`) |
| `{{SKILL_LIST}}` | Natural language list (e.g. `vault-ops and vault-wiki`) |

Use `terminal` with `sed` for the replacements:

```bash
cd ~/.agents/skills/<bundle-name>-improvements
sed -i 's/{{BUNDLE_NAME}}/<bundle-name>/g' SKILL.md INSTALL.md
sed -i 's/{{SKILL_NAMES}}/<skills-csv>/g' SKILL.md INSTALL.md
sed -i 's/{{SKILL_LIST}}/<skills-natural>/g' SKILL.md
```

### Step 4 — Create the Hermes Bundle

```bash
hermes bundles create <bundle-name> \
  --skill <skill-1> \
  --skill <skill-2> \
  --skill <bundle-name>-improvements \
  --description "<description>"
```

Replace with the user's answers. List the core skills first, then the improvements skill last.

### Step 5 — Initialize Git

```bash
cd ~/.agents/skills/<bundle-name>-improvements
git init
git add -A
git commit -m "init: <bundle-name>-improvements"
```

### Step 6 — Delete INSTALL.md

```bash
rm ~/.agents/skills/<bundle-name>-improvements/INSTALL.md
```

## Verification

After installation, verify with:
- `hermes bundles list` — confirm the bundle exists with the correct skills
- `ls ~/.agents/skills/<bundle-name>-improvements/` — confirm SKILL.md, CHANGELOG.md, references/
- `cd ~/.agents/skills/<bundle-name>-improvements && git log --oneline` — confirm git commit exists
