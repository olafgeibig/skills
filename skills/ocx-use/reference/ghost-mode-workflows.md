# Ghost Mode Advanced Workflows

Ghost Mode allows working in any repository without modifying it, using your own portable configuration.

## Setup and Configuration

**Initialize Ghost Mode:**
```bash
ocx ghost init                          # Creates default profile
ocx ghost config                        # Edit in $EDITOR
```

**Profile Structure:**
```
~/.config/opencode/profiles/
├── current -> default                  # Active profile symlink
├── default/
│   ├── ghost.jsonc                    # Ghost configuration
│   └── opencode.jsonc                  # OpenCode config
└── work/
    └── ...
```

## Profile Management Commands

**Create and Manage Profiles:**
```bash
# List all profiles
ocx ghost profile list

# Create new profile (clones from current)
ocx ghost profile add work

# Create from specific profile
ocx ghost profile add client-project --from default

# Switch active profile
ocx ghost profile use work

# Show profile configuration
ocx ghost profile show work

# Edit profile config
ocx ghost profile config work

# Remove profile
ocx ghost profile remove old-project
```

## Registry Configuration in Ghost Mode

**Add Registries to Profile:**
```bash
# Add KDCO registry
ocx ghost registry add https://registry.kdco.dev --name kdco

# Add custom registry
ocx ghost registry add https://registry.company.com --name internal

# List registries
ocx ghost registry list

# Remove registry
ocx ghost registry remove internal
```

**Example Ghost Config:**
```jsonc
// ~/.config/opencode/profiles/default/ghost.jsonc
{
  "registries": {
    "kdco": "https://registry.kdco.dev"
  },
  "componentPath": ".opencode"
}
```

## Component Installation in Ghost Mode

**Add Components:**
```bash
# Add registry components
ocx ghost add kdco/workspace kdco/agents

# Add npm plugins
ocx ghost add npm:@franlol/opencode-md-table-formatter

# Add multiple at once
ocx ghost add kdco/researcher npm:opencode-plugin-foo
```

**Search in Ghost Mode:**
```bash
# Search available components
ocx ghost search agents

# List installed in profile
ocx ghost search --installed
```

## Using Ghost Mode in Repositories

**Standard Workflow:**
```bash
# Navigate to any repository
cd ~/oss/some-project

# Run OpenCode with your ghost config
ocx ghost opencode

# Terminal shows: ghost[profile]:username/project-name
```

**Advanced Usage:**
```bash
# Run with specific profile
ocx ghost opencode --profile work

# Pass arguments to OpenCode
ocx ghost opencode -- --help

# Disable terminal renaming
ocx ghost opencode --no-rename
```

**Session Identification:**
- Terminal/tmux window automatically renamed to `ghost[profile]:repo/branch`
- Helps identify which profile you're using
- Can be disabled with `--no-rename` flag or `renameWindow: false` in config

## Customizing File Visibility

By default, Ghost Mode hides all OpenCode project files. Customize with include/exclude patterns:

```jsonc
// ~/.config/opencode/profiles/default/ghost.jsonc
{
  "registries": {
    "kdco": "https://registry.kdco.dev"
  },
  
  // Safety limit for symlink farm (0 = unlimited)
  "maxFiles": 10000,
  
  // Include specific files
  "include": [
    "**/AGENTS.md",                     # Include AGENTS.md files
    ".opencode/skills/**"               # Include skills directory
  ],
  
  // Exclude patterns
  "exclude": [
    "**/vendor/**"                     # But exclude vendor dirs
  ]
}
```

**Include/Exclude Rules:**
- `include` selects files to show in ghost sessions
- `exclude` filters the include results
- Follows TypeScript-style glob patterns
- No confusing negation patterns

## How Ghost Mode Works

1. **Profile Resolution**: Selects config based on priority:
   - `--profile` flag (highest)
   - `$OCX_PROFILE` environment variable
   - `current` symlink
   - `default` profile (fallback)

2. **File Isolation**: Creates temporary symlink farm hiding project files

3. **Git Integration**: Sets `GIT_WORK_TREE` and `GIT_DIR` to see real project

4. **Real-time Sync**: New files created during session sync back to project

5. **Terminal Naming**: Sets informative window name for session tracking

## Environment Variables

**Profile Selection:**
```bash
export OCX_PROFILE=work
ocx ghost opencode                     # Uses 'work' profile
```

**Editor Configuration:**
```bash
export EDITOR=code                    # Use VS Code
export EDITOR=vim                     # Use vim
ocx ghost config                      # Opens in your editor
```

## Cross-Repository Workflow Examples

**Personal Development Setup:**
```bash
# Setup personal profile with all tools
ocx ghost init
ocx ghost profile add personal
ocx ghost profile use personal
ocx ghost registry add https://registry.kdco.dev --name kdco
ocx ghost add kdco/workspace kdco/researcher kdco/agents

# Use in any project
cd ~/client-project
ocx ghost opencode

# Terminal: ghost[personal]:username/client-project
```

**Work/Personal Separation:**
```bash
# Create separate profiles
ocx ghost profile add work
ocx ghost profile add personal

# Configure differently
ocx ghost profile use work
ocx ghost registry add https://registry.internal.company.com --name work-reg

ocx ghost profile use personal
ocx ghost registry add https://registry.kdco.dev --name kdco

# Switch easily
ocx ghost profile use work           # For work projects
ocx ghost profile use personal      # For personal projects
```

## Troubleshooting Ghost Mode

**Profile Issues:**
```bash
# List profiles to verify exists
ocx ghost profile list

# Check current profile
ocx ghost profile show

# Recreate if corrupted
ocx ghost profile add new-profile --from default
ocx ghost profile use new-profile
```

**Configuration Issues:**
```bash
# Verify config syntax
ocx ghost config                     # $EDITOR opens file

# Check registry accessibility
curl https://registry.kdco.dev/index.json
```

**Session Issues:**
```bash
# Disable window renaming if problematic
ocx ghost opencode --no-rename

# Check file sync issues
# New files should appear in real project after session
```

## Benefits of Ghost Mode

- **Zero Repository Modifications**: Work in any repo without touching it
- **Portable Configuration**: Same setup across all projects
- **Profile Isolation**: Separate configs for work/personal/clients
- **Real-time File Sync**: Changes go directly to real project
- **Session Tracking**: Terminal names show profile and repo
- **Git Integration**: Full git functionality works normally
- **No Manual Setup**: Just run `ocx ghost opencode`