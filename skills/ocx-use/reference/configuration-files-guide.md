# Configuration Files Guide

Understanding and managing OCX configuration files.

## Configuration File Overview

| File | Purpose | Location | Managed By |
|------|---------|----------|------------|
| `ocx.jsonc` | User configuration | Project root | Manual |
| `ocx.lock` | Dependency lockfile | Project root | Auto-generated |
| `ghost.jsonc` | Ghost mode config | `~/.config/opencode/profiles/` | Manual |
| `.opencode/` | Installed components | Project root | Auto-managed |

## ocx.jsonc - Main Configuration

**Purpose**: User-editable configuration for registries and settings

**Location**: Project root

**Basic Structure**:
```jsonc
{
  "$schema": "https://ocx.dev/schemas/ocx.schema.json",
  "registries": {
    "kdco": "https://registry.kdco.dev"
  },
  "lockRegistries": false
}
```

**Complete Example**:
```jsonc
{
  "$schema": "https://ocx.dev/schemas/ocx.schema.json",
  "name": "My Project",
  "registries": {
    "kdco": {
      "url": "https://registry.kdco.dev",
      "version": "latest"
    },
    "internal": {
      "url": "https://registry.company.com",
      "version": "1.0.0"
    }
  },
  "lockRegistries": false
}
```

**Fields**:
- `$schema`: JSON Schema URL for validation
- `name`: Project name (optional)
- `registries`: Registry configuration object
- `lockRegistries`: Boolean to prevent registry modification

**Registry Configuration Options**:

**String format (simple)**:
```jsonc
{
  "registries": {
    "kdco": "https://registry.kdco.dev"
  }
}
```

**Object format (advanced)**:
```jsonc
{
  "registries": {
    "kdco": {
      "url": "https://registry.kdco.dev",
      "version": "latest"
    }
  }
}
```

## ocx.lock - Dependency Lockfile

**Purpose**: Tracks installed components with versions and integrity hashes

**Location**: Project root

**Managed**: Automatically by OCX

**Structure**:
```json
{
  "lockVersion": 1,
  "installed": {
    "kdco/workspace": {
      "registry": "kdco",
      "version": "1.2.0",
      "hash": "sha256-abc123...",
      "files": [
        ".opencode/agents/workspace.md",
        ".opencode/skills/workspace/SKILL.md"
      ],
      "installedAt": "2024-01-15T10:30:00Z",
      "updatedAt": "2024-01-20T14:00:00Z"
    }
  }
}
```

**Fields**:
- `lockVersion`: Lockfile format version
- `installed`: Map of component name to installation info
- `registry`: Source registry name
- `version`: Installed version
- `hash`: SHA-256 integrity hash
- `files`: Array of installed file paths
- `installedAt`: First installation timestamp
- `updatedAt`: Last update timestamp

**Important**:
- **Never edit manually**
- Commit to version control
- Required for `ocx diff` and integrity checks
- Recreated on `ocx update` or `ocx add`

## ghost.jsonc - Ghost Mode Configuration

**Purpose**: Ghost mode profile configuration

**Location**: `~/.config/opencode/profiles/{profile-name}/ghost.jsonc`

**Created by**: `ocx ghost init`

**Structure**:
```jsonc
{
  "registries": {
    "kdco": "https://registry.kdco.dev"
  },
  "componentPath": ".opencode",
  "include": [],
  "exclude": [],
  "renameWindow": true,
  "maxFiles": 10000
}
```

**Fields**:
- `registries`: Registry configuration (same as ocx.jsonc)
- `componentPath`: Where to install components (default: `.opencode`)
- `include`: Glob patterns for files to include in ghost sessions
- `exclude`: Glob patterns to exclude from ghost sessions
- `renameWindow`: Boolean to set terminal/tmux window name
- `maxFiles`: Safety limit for symlink farm (0 = unlimited)

**Example with Custom Paths**:
```jsonc
{
  "registries": {
    "kdco": "https://registry.kdco.dev"
  },
  "componentPath": ".opencode",
  "include": [
    "**/AGENTS.md",
    ".opencode/skills/**"
  ],
  "exclude": [
    "**/vendor/**",
    "**/node_modules/**"
  ]
}
```

## .opencode/ - Component Directory

**Purpose**: Installed components directory

**Location**: Project root (or custom path in ghost config)

**Managed**: Automatically by OCX

**Structure**:
```
.opencode/
├── agent/                    # Custom agents
│   ├── workspace.md
│   └── researcher.md
├── plugin/                   # Plugins
│   ├── workspace-plugin.ts
│   └── background-sync.ts
├── skill/                    # Skills
│   ├── code-review/
│   │   └── SKILL.md
│   └── project-setup/
│       └── SKILL.md
├── command/                  # Commands
│   └── initialize-project.md
└── tool/                     # Custom tools
    ├── custom-analyzer.ts
    └── data-processor.ts
```

**Important**:
- **Do not edit manually**
- Files managed by OCX
- Safe to customize after installation
- Will be overwritten on `ocx update` unless `--force` used

## Configuration Best Practices

**Project Configuration (ocx.jsonc)**:

**Development**:
```jsonc
{
  "registries": {
    "kdco": "https://registry.kdco.dev"
  },
  "lockRegistries": false
}
```

**Production/Enterprise**:
```jsonc
{
  "registries": {
    "internal": {
      "url": "https://registry.company.com",
      "version": "1.0.0"
    }
  },
  "lockRegistries": true
}
```

**Multi-Environment**:
```jsonc
{
  "registries": {
    "dev": "https://registry-dev.company.com",
    "prod": {
      "url": "https://registry.company.com",
      "version": "1.0.0"
    }
  }
}
```

**Ghost Mode Profiles**:

**Personal Profile**:
```jsonc
// ~/.config/opencode/profiles/personal/ghost.jsonc
{
  "registries": {
    "kdco": "https://registry.kdco.dev"
  },
  "componentPath": ".opencode",
  "include": [
    "**/AGENTS.md",
    ".opencode/**"
  ]
}
```

**Work Profile**:
```jsonc
// ~/.config/opencode/profiles/work/ghost.jsonc
{
  "registries": {
    "internal": "https://registry.internal.company.com"
  },
  "componentPath": ".opencode",
  "include": [
    "**/AGENTS.md"
  ],
  "exclude": [
    "**/vendor/**"
  ]
}
```

## File Path Configuration

**Default Installation Paths**:
- `ocx:skill` → `.opencode/skill/{name}/`
- `ocx:agent` → `.opencode/agent/`
- `ocx:plugin` → `.opencode/plugin/`
- `ocx:command` → `.opencode/command/`
- `ocx:tool` → `.opencode/tool/`

**Custom Paths (Component-Level)**:
```json
{
  "files": [
    {
      "source": "src/custom-agent.md",
      "target": ".opencode/agent/custom.md"
    }
  ]
}
```

**Custom Component Path (Ghost Mode)**:
```jsonc
{
  "componentPath": ".ocx-extensions"
}
```

## Environment Variables

**OCX Configuration**:
```bash
export OCX_NO_COLOR=1              # Disable colored output
export OCX_SELF_UPDATE=off         # Disable self-update
export OCX_NO_UPDATE_CHECK=1      # Disable update notifications
export OCX_PROFILE=work            # Set ghost mode profile
```

**Editor Configuration**:
```bash
export EDITOR=code                # For ocx ghost config
export VISUAL=vim                 # Fallback editor
```

## Configuration Validation

**Validate ocx.jsonc**:
```bash
# OCX validates automatically on operations
# Check schema: https://ocx.dev/schemas/ocx.schema.json
```

**Common Validation Errors**:
- Invalid JSONC syntax
- Missing required fields
- Invalid registry URLs
- Schema violations

**Validate ghost.jsonc**:
```bash
# Edit to trigger validation
ocx ghost config
# $EDITOR opens file, OCX validates on save
```

## Migration and Backup

**Backup Configuration**:
```bash
# Backup ocx.jsonc and ocx.lock
cp ocx.jsonc ocx.jsonc.backup
cp ocx.lock ocx.lock.backup

# Backup ghost profiles
cp -r ~/.config/opencode/profiles ~/opencode-profiles-backup
```

**Restore Configuration**:
```bash
# Restore from backup
cp ocx.jsonc.backup ocx.jsonc
cp ocx.lock.backup ocx.lock

# Restore ghost profiles
cp -r ~/opencode-profiles-backup ~/.config/opencode/profiles
```

## Troubleshooting Configuration

**ocx.jsonc Issues**:
```bash
# Validate syntax
cat ocx.jsonc | jq .              # Check JSONC is valid

# Reset to defaults
ocx init --force                  # Reinitialize

# Check schema
curl https://ocx.dev/schemas/ocx.schema.json
```

**ocx.lock Issues**:
```bash
# Regenerate lockfile
rm ocx.lock
ocx add --force <component>       # Reinstall

# Check integrity
ocx diff                          # Show mismatches
```

**Ghost Config Issues**:
```bash
# Reset ghost mode
rm -rf ~/.config/opencode/profiles
ocx ghost init

# Check profile
ocx ghost profile show
ocx ghost profile list
```

**Component Directory Issues**:
```bash
# Reset components
rm -rf .opencode
ocx add --force <components>     # Reinstall

# Check conflicts
ocx add <component> --dry-run     # Preview changes
```