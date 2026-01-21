# Component Types Reference

Understanding the six types of OCX components and their purposes.

## Component Type Overview

| Type | Install Location | Purpose | File Format |
|------|-----------------|---------|-------------|
| `ocx:skill` | `.opencode/skill/{name}/` | AI behavior instructions | Markdown |
| `ocx:agent` | `.opencode/agent/` | Custom agent definitions | Markdown |
| `ocx:plugin` | `.opencode/plugin/` | Functionality extensions | TypeScript |
| `ocx:command` | `.opencode/command/` | CLI commands | Markdown |
| `ocx:tool` | `.opencode/tool/` | Custom tools | TypeScript |
| `ocx:bundle` | Varies | Component collections | JSON |

## ocx:skill

**Purpose**: Reusable AI behavior instructions and workflows

**Location**: `.opencode/skill/{name}/SKILL.md`

**Structure**:
```
skill/
└── {skill-name}/
    └── SKILL.md          # Main skill file
```

**Example SKILL.md**:
```markdown
---
name: code-reviewer
description: Systematic code review methodology
---

# Code Review Skill

## When to Use
- Reviewing pull requests
- Pre-commit code checks
- Learning code quality

## Instructions
1. Check correctness
2. Review security
3. Assess performance
4. Verify style
```

**Usage**:
- Provides step-by-step guidance for AI
- Reusable across projects
- Can depend on other skills
- Supports triggers and keywords

## ocx:agent

**Purpose**: Custom agent personas with specialized behavior

**Location**: `.opencode/agent/{name}.md`

**Structure**:
```
agent/
└── {agent-name}.md
```

**Example agent**:
```markdown
# Agent: Code Reviewer

You are a meticulous code reviewer focused on quality.

## Role
- Review code for bugs, security issues
- Suggest improvements with explanations
- Be constructive, not critical

## Permissions
- Read any file in codebase
- Run static analysis tools
- Cannot modify files directly

## Response Format
### Summary
Brief overview

### Issues Found
- [SEVERITY] Description

### Recommendations
Prioritized improvements
```

**Usage**:
- Specialized AI personas
- Custom permissions and behaviors
- Defined response formats
- Role-based interactions

## ocx:plugin

**Purpose**: Functionality extensions that add tools and hooks

**Location**: `.opencode/plugin/{name}.ts`

**Structure**:
```
plugin/
└── {plugin-name}.ts
```

**Example plugin**:
```typescript
import type { Plugin, ToolDefinition } from "opencode"

const myTool: ToolDefinition = {
  name: "my-tool",
  description: "Does something useful",
  parameters: {
    type: "object",
    properties: {
      input: { type: "string" }
    }
  },
  execute: async (params, ctx) => {
    return { result: `Processed: ${params.input}` }
  }
}

export default {
  name: "my-plugin",
  version: "1.0.0",
  tools: [myTool],
  onSessionStart: async (ctx) => {
    console.log("Plugin initialized")
  }
} satisfies Plugin
```

**Usage**:
- Add custom tools
- Implement lifecycle hooks
- Extend OpenCode functionality
- Can be npm packages: `ocx add npm:package-name`

## ocx:command

**Purpose**: Custom TUI commands users can invoke

**Location**: `.opencode/command/{name}.md`

**Structure**:
```
command/
└── {command-name}.md
```

**Example command**:
```markdown
# Command: Project Setup

Initialize a new project with best practices.

## Usage
```
/project-setup [template-name]
```

## Parameters
- `template-name`: Type of project (optional)

## Examples
- `/project-setup node` - Setup Node.js project
- `/project-setup python` - Setup Python project
- `/project-setup` - Interactive setup
```

**Usage**:
- User-invokable commands
- Start with `/` in chat
- Can accept parameters
- Interactive workflows

## ocx:tool

**Purpose**: Custom tool implementations

**Location**: `.opencode/tool/{name}.ts`

**Structure**:
```
tool/
└── {tool-name}.ts
```

**Example tool**:
```typescript
import type { ToolDefinition } from "opencode"

export const myTool: ToolDefinition = {
  name: "my-custom-tool",
  description: "Custom tool implementation",
  parameters: {
    type: "object",
    properties: {
      param1: { type: "string", description: "Parameter 1" },
      param2: { type: "number", description: "Parameter 2" }
    },
    required: ["param1"]
  },
  execute: async (params, ctx) => {
    // Tool implementation
    return { result: "Tool executed" }
  }
}
```

**Usage**:
- Custom tool implementations
- Available to AI agents
- Type-safe parameter definitions
- Async execution

## ocx:bundle

**Purpose**: Meta-packages that group multiple components

**Location**: Varies (specified in bundle manifest)

**Structure**:
```
bundle/
└── {bundle-name}/
    └── bundle.json        # Bundle manifest
```

**Example bundle**:
```json
{
  "name": "starter-kit",
  "type": "ocx:bundle",
  "description": "Everything needed to get started",
  "version": "1.0.0",
  "dependencies": [
    "kdco/workspace",
    "kdco/agents",
    "kdco/skills"
  ]
}
```

**Usage**:
- Install multiple related components
- Version management for component groups
- Simplified installation
- Dependency resolution

## Component Dependencies

**Skill Dependencies**:
```json
{
  "dependencies": ["other-skill"]
}
```

**Plugin Dependencies**:
```json
{
  "dependencies": ["ocx:plugin/npm-package"]
}
```

**Automatic Resolution**:
- OCX resolves dependencies in correct order
- Prevents circular dependencies
- Validates compatibility

## File Installation Paths

**Default Paths**:
- `ocx:skill` → `.opencode/skill/{name}/SKILL.md`
- `ocx:agent` → `.opencode/agent/{name}.md`
- `ocx:plugin` → `.opencode/plugin/{name}.ts`
- `ocx:command` → `.opencode/command/{name}.md`
- `ocx:tool` → `.opencode/tool/{name}.ts`
- `ocx:bundle` → Varies by bundle

**Custom Paths**:
```json
{
  "files": [
    {
      "source": "src/SKILL.md",
      "target": ".opencode/skill/my-skill/SKILL.md"
    }
  ]
}
```

## Component Metadata

**Required Fields**:
- `name`: Component identifier
- `type`: Component type (`ocx:skill`, etc.)
- `version`: Version string
- `description`: Human-readable description

**Optional Fields**:
- `dependencies`: Array of component names
- `files`: File installation instructions
- `opencode`: Configuration to merge

**Example Component Manifest**:
```json
{
  "name": "my-skill",
  "type": "ocx:skill",
  "version": "1.0.0",
  "description": "A helpful skill",
  "files": ["skill/my-skill/SKILL.md"],
  "dependencies": [],
  "opencode": {
    "instructions": [
      "Use my-skill when appropriate"
    ]
  }
}
```

## Configuration Injection

**Global Instructions**:
```json
{
  "opencode": {
    "instructions": [
      "Use this skill when needed",
      "Additional global guidance"
    ]
  }
}
```

**MCP Server Configuration**:
```json
{
  "opencode": {
    "mcp": {
      "my-server": {
        "type": "remote",
        "url": "https://api.example.com/mcp"
      }
    }
  }
}
```

**Tool Configuration**:
```json
{
  "opencode": {
    "tools": {
      "enabled": ["Read", "Edit"],
      "disabled": ["Write"]
    }
  }
}
```

## Best Practices

**Skill Guidelines**:
- Focus on single, clear purpose
- Include examples and use cases
- Add anti-patterns to avoid
- Keep instructions scannable

**Plugin Guidelines**:
- Minimal dependencies
- Handle errors gracefully
- Use TypeScript strictly
- Document hooks clearly

**Agent Guidelines**:
- Define clear scope
- Set explicit boundaries
- Provide response format
- List forbidden actions

**General Guidelines**:
- Use semantic versioning
- Choose descriptive names
- Fill all metadata fields
- Follow naming conventions