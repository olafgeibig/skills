# Registry Management Guide

Registries are the sources for OCX components. Learn to configure, manage, and secure them.

## Understanding Registries

**What are Registries?**
- HTTP endpoints serving OCX component metadata
- Similar to npm registry but for OpenCode components
- Can be hosted on GitHub Pages, Cloudflare Workers, Vercel, etc.

**Registry Components:**
- **Discovery endpoint**: `/.well-known/ocx.json` (optional)
- **Registry index**: `/index.json` - lists all components
- **Component packuments**: `/components/{name}.json` - full metadata
- **File content**: `/components/{name}/{path}` - actual files

## Adding Registries

**Basic Addition:**
```bash
# Name derived from hostname
ocx registry add https://registry.kdco.dev

# With custom name
ocx registry add https://registry.kdco.dev --name kdco

# Pin to specific version
ocx registry add https://registry.kdco.dev --version 1.0.0
```

**Multiple Registries:**
```bash
# Add several registries
ocx registry add https://registry.kdco.dev --name kdco
ocx registry add https://registry.internal.com --name internal
ocx registry add https://registry.partner.com --name partner
```

## Registry Configuration

**Edit ocx.jsonc:**
```jsonc
{
  "$schema": "https://ocx.dev/schemas/ocx.schema.json",
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

**Registry Object Fields:**
- `url` (required): Registry endpoint URL
- `version` (optional): Pin to specific version
- Can also be just a string: `"kdco": "https://registry.kdco.dev"`

## Registry Management Commands

**List Registries:**
```bash
# Human-readable output
ocx registry list

# JSON output
ocx registry list --json
```

**Remove Registries:**
```bash
# Remove by name
ocx registry remove kdco

# Verify removal
ocx registry list
```

## Searching Registries

**Search All Registries:**
```bash
# Search for components
ocx search agents
ocx search workspace
ocx search "code review"

# Search with limit
ocx search agents --limit 50

# Verbose output
ocx search --verbose
```

**Search Specific Registry:**
```bash
# Use qualified names
ocx search kdco/agents

# List installed from specific registry
ocx search --installed
```

## Enterprise Registry Setup

**Locked Registries:**
```jsonc
// ocx.jsonc
{
  "registries": {
    "internal": {
      "url": "https://registry.company.com",
      "version": "2.1.0"
    }
  },
  "lockRegistries": true               // Prevent registry modification
}
```

**Benefits of Locking:**
- Prevents accidental registry URL changes
- Ensures consistent component sources
- Required for compliance/audit requirements
- Registry changes require manual config edit

**Version Pinning:**
```jsonc
{
  "registries": {
    "stable": {
      "url": "https://registry.company.com",
      "version": "1.0.0"               // Pin to specific version
    },
    "latest": {
      "url": "https://registry.company.com"
      // No version = always latest
    }
  }
}
```

## Creating Your Own Registry

**Scaffold Registry:**
```bash
# Create new registry project
ocx init my-registry --registry --namespace my-org

# With custom settings
ocx init company-registry \
  --registry \
  --namespace company \
  --author "Company Name"
```

**Registry Structure:**
```
my-registry/
├── registry.jsonc          # Registry manifest
├── files/                  # Component source files
│   ├── agent/
│   ├── plugin/
│   └── skill/
└── dist/                   # Built registry (generated)
```

**Build and Deploy:**
```bash
# Build registry
ocx build

# Deploy options:
# - GitHub Pages: Push dist/ to gh-pages branch
# - Vercel: Connect repo, auto-deploys
# - Netlify: Connect repo, auto-deploys
# - Cloudflare: Use wrangler deploy
```

## Registry Security

**Verify Registry Integrity:**
```bash
# Check registry is accessible
curl https://registry.kdco.dev/index.json

# Verify component integrity
ocx diff kdco/workspace

# Check for hash mismatches
# OCX will warn if SHA-256 doesn't match
```

**Security Best Practices:**
- Use HTTPS-only registries
- Verify registry authenticity
- Pin registry versions for compliance
- Lock registries in enterprise setups
- Regularly audit with `ocx diff`

## Multi-Registry Composition

**Combine Multiple Sources:**
```bash
# Add various registries
ocx registry add https://registry.kdco.dev --name kdco
ocx registry add https://registry.opencode.ai --name opencode
ocx registry add https://internal.company.com --name internal

# Components from different registries
ocx add kdco/workspace              # From kdco registry
ocx add opencode/agents            # From opencode registry
ocx add internal/skill-set         # From internal registry
```

**Priority Resolution:**
- Components searched across all registries
- First match wins (order in ocx.jsonc)
- Use fully qualified names to be explicit: `registry/component`

## Troubleshooting Registries

**Registry Not Found:**
```bash
# Check registries are configured
ocx registry list

# Verify registry URL
curl {registry-url}/index.json

# Add registry if missing
ocx registry add {url} --name {name}
```

**Component Not Found:**
```bash
# Check if component exists
ocx search component-name

# Verify component name format
ocx search registry-name/component-name

# Check all registries
ocx search --verbose
```

**Network Issues:**
```bash
# Test registry connectivity
curl -I https://registry.kdco.dev

# Check for corporate firewall
curl --proxy {proxy-url} https://registry.kdco.dev
```

## Environment-Specific Registries

**Development:**
```jsonc
{
  "registries": {
    "dev": "https://registry-dev.company.com",
    "kdco": "https://registry.kdco.dev"
  }
}
```

**Production:**
```jsonc
{
  "registries": {
    "prod": {
      "url": "https://registry.company.com",
      "version": "1.0.0"
    }
  },
  "lockRegistries": true
}
```

## Registry Protocol Reference

**Required Endpoints:**
```
GET /.well-known/ocx.json              # Discovery (optional)
GET /index.json                        # Registry index
GET /components/{name}.json            # Component metadata
GET /components/{name}/{path}          # File content
```

**Response Formats:**
- Registry index: JSON with metadata
- Component packument: npm-style packument
- File content: Raw files with appropriate MIME types

**Hosting Options:**
- Static hosting (GitHub Pages, Netlify, Vercel)
- Cloudflare Workers
- Any HTTP server serving required endpoints
- CDN for performance