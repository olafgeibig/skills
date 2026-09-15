---
name: skill-builder
description: "Use when creating or maintaining Agent Skills."
compatibility: Requires network access for documentation fetching, uv for package management, and npm for Node.js scripts
metadata:
  source: https://github.com/olafgeibig/skills
  version: "0.2.0"
  author: Olaf Geibig
  hermes:
    category: personal
    tags:
      - skills
      - authoring
      - validation
      - hermes
    related_skills:
      - skill-governance
---

You design and maintain Agent Skills primarily for Hermes Agent while preserving the portable Agent Skills format where practical. Treat the Agent Skills specification as the base format and Hermes documentation as the authority for Hermes-specific extensions and runtime behavior.

# Your Role

Help users create, convert, and maintain Agent Skills through:
1. **Creating New Skills**: Build skills from scratch in their canonical repository
2. **Editing Skills**: Refine and maintain existing skills without changing ownership
3. **Converting Agent Definitions**: Transform compatible agent instructions into skills

# Essential Documentation References

Before working on any skill task, refresh your understanding by reviewing these authoritative sources:

**Official base specification:**
- https://agentskills.io/specification
- https://agentskills.io/skill-creation/best-practices

**Hermes implementation:**
- https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills
- https://hermes-agent.nousresearch.com/docs/user-guide/features/skills

Refresh these sources when format or runtime behavior matters. The Agent Skills specification defines portable frontmatter; Hermes documentation defines Hermes-only extensions, discovery, `skill_manage`, and runtime behavior.

# Core Knowledge

## Skill Structure

Every skill requires a directory with a `SKILL.md` file:

```
skill-name/
├── SKILL.md (required)
├── processing-details.md (optional - use intention-revealing names!)
├── scripts/ (optional)
│   └── process-data.js (Node.js preferred)
└── templates/ (optional)
    └── output-template.txt
```

**Important File Naming Conventions:**
- Use intention-revealing names for all supporting files
- Examples: `./converting-sub-agents.md`, `./aws-deployment-patterns.md`, `./github-workflow-examples.md`
- NOT: `./reference.md`, `./helpers.md`, `./utils.md`
- Reference files with relative paths like `./filename.md` in SKILL.md

## SKILL.md Format

```yaml
---
name: skill-name
description: Use when performing a clearly bounded task.
license: MIT
metadata:
  author: Example Author
  version: "1.0.0"
  source: https://example.com/owner/repository
  hermes:
    category: personal
    tags:
      - example
    related_skills: []
---

# Main Instructions
```

`name` and `description` are required by the Agent Skills specification. `license`, `compatibility`, `metadata`, and experimental `allowed-tools` are optional standard fields. Put portable extension values such as `author`, `version`, and `source` under `metadata`.

`metadata.hermes` is a Hermes-specific extension for routing and configuration. Hermes also accepts top-level `version`, `author`, and `platforms` for its bundled-skill authoring workflow, but top-level `version` and `author` are not part of the portable Agent Skills specification. Use them only when the owning repository explicitly follows the Hermes-native convention. Do not duplicate the same value at both levels; choose one repository convention so version and attribution cannot drift.

## Critical Requirements

- **name**: Lowercase letters, numbers, and hyphens only; max 64 characters; must match the parent directory. Use the owning repository's naming convention; noun phrases are preferred in this repository.
- **description**: The primary invocation signal.
  - Describe what the skill does and when to use it.
  - Include distinguishing trigger terms without turning it into a keyword dump.
  - Keep it under the specification limit of 1024 characters and under Hermes' configured prompt budget when stricter.
- **metadata**: Use string-valued portable keys such as `author`, `version`, and `source`. Add `metadata.hermes` only when Hermes-specific routing or configuration is needed.
- **allowed-tools**: An experimental standard field. Use only when the target client supports and needs pre-approval declarations; do not add it by default.

## Skill Locations

Determine ownership before choosing a path. For Hermes profiles with several canonical repositories, follow `skill-governance`: use `skill_manage` for existing external skills, and create a new skill with filesystem tools when the single configured `skills.create_dir` is not its canonical root. Always verify `_source_path` and duplicate names afterward.

# Creating New Skills

When a user wants to create a new skill, use this interactive process:

## 1. Gather Requirements

Ask the user:
- What task or workflow should this skill handle?
- When should an agent invoke this skill? Be specific.
- Should this be personal (global) or project-specific?
- Are there similar patterns in the official docs to reference?

## 2. Design the Skill

Based on requirements:
- Choose a specification-valid name that follows the owning repository's convention.
- Draft a concise description that clearly states what the skill does and when it applies.
- Select the portable or repository-specific frontmatter convention deliberately.
- Plan the instruction structure focusing on available tools and reproducible workflows.
- Consider what supporting files need intention-revealing names.

## 3. Leverage CLI and Node.js

**Emphasize Modern Tooling:**
- Use CLI tools liberally (gh, aws, npm, etc.)
- Encourage global NPM package installation when useful
- Script with Node.js (v24+) using:
  - `.js` files (not TypeScript)
  - ESM imports (`import`/`export`)
  - Modern JavaScript features
- Provide complete, runnable commands
- Show how to chain CLI operations

Example Node.js script pattern:
```javascript
#!/usr/bin/env node
import { readFile } from 'fs/promises';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Your implementation here
```

## 4. Create the Skill

- Create the skill directory in the appropriate location
- Write the SKILL.md with YAML frontmatter
- If SKILL.md is approaching 500 lines or has multiple detailed sections:
  - Create `references/` directory: `mkdir -p skill-name/references`
  - Move detailed content to `references/` with intention-revealing names:
    - Detailed methodology → `references/methodology.md`
    - Extensive examples → `references/examples.md`
    - Command references → `references/command-reference.md`
  - Reference files in SKILL.md with `./references/filename.md` paths
- If scripts are needed, use Node.js with modern ESM syntax in `scripts/` directory
- Keep SKILL.md focused on core workflow (under 500 lines)

## 5. Validate

Check:
- Name follows the Agent Skills constraints and owning repository convention.
- Description is concise, trigger-focused, and within both specification and runtime budgets.
- Portable frontmatter uses only standard top-level fields; `author`, `version`, and `source` live under `metadata` unless the repository explicitly adopts Hermes-native extensions.
- Run skills-ref validation to verify the portable Agent Skills structure.
- Load the skill with `skill_view` to verify Hermes runtime compatibility and `_source_path`.
- Review any Hermes advisory-linter warning separately from portable-spec validation.
- Instructions are actionable and complete.
- Supporting files have intention-revealing names.

# Editing Skills

When refining existing skills:

## Common Improvements

1. **Refine Description**: Most critical for better invocation
   - Add missing trigger keywords
   - Clarify use cases
   - Ensure third person voice
   - Test if description matches typical user queries

2. **Improve Organization**: Use progressive disclosure
   - If SKILL.md is too long or has multiple detailed sections:
     - Create `references/` directory: `mkdir -p references`
     - Move detailed content to `references/` with intention-revealing names
     - Reference files with relative paths (e.g., `./references/processing-details.md`)
   - Keep SKILL.md focused on core instructions (under 500 lines)

3. **Add Supporting Files**:
   - Templates for common patterns
   - Node.js scripts for complex operations
   - Reference docs with descriptive names for detailed info

4. **Modernize Tooling**:
   - Replace Python scripts with Node.js equivalents
   - Add CLI tool examples (gh, aws, npm)
   - Show modern JavaScript patterns (ESM, async/await)

# Converting Sub-Agents to Skills

When converting existing Claude Code sub-agent configurations (those in `~/.claude/agents/`), see `./references/converting-sub-agents-to-skills.md` for comprehensive guidance.

**Quick Overview:**
1. Analyze the sub-agent's YAML frontmatter and instructions
2. Transform description to be invocation-focused with trigger keywords
3. Convert to skill format (remove `model`, `color`, `tools` fields)
4. Enhance with progressive disclosure and supporting files
5. Create in `~/.claude/skills/` for global availability

# Best Practices

## Keep SKILL.md Concise

- Target: Under 500 lines
- Challenge every piece of information: "Does Claude really need this explanation?"
- Only add context Claude doesn't already know
- Use progressive disclosure for detailed content

## Description Writing

The description is the most critical element for skill invocation:

- **Be Specific**: "Use this skill when..." not "This skill can..."
- **Include Triggers**: Keywords users might say that should invoke this skill
- **List Use Cases**: Concrete scenarios where this skill applies
- **Third Person**: Write as if describing to someone else
- **Think Like Claude**: "When would I know to use this?"

Examples:
- Good: "Use this skill when working with CSV files using xsv CLI, including exploring structure, filtering data, selecting columns, or transforming files"
- Bad: "CSV helper skill"

## Instruction Writing

- **Be Concise**: Only essential information
- **Be Actionable**: Start with verbs (Analyze, Create, Validate)
- **Be Specific**: Provide exact commands, file paths, syntax
- **Include Examples**: Show concrete usage patterns from official docs
- **Progressive Disclosure**: SKILL.md for overview, separate files for details

## Naming Conventions

**Skills:**
- Follow the Agent Skills name constraints and the owning repository's naming convention.
- Noun phrases are preferred in this repository, for example `container-use` or `vault-ops`.
- Gerund names remain valid when they describe the capability more clearly.

**Supporting Files:**
- Use intention-revealing names
- Examples: `./aws-lambda-patterns.md`, `./github-actions-workflows.md`
- Reference with relative paths in SKILL.md

## CLI and Scripting Emphasis

**Encourage:**
- Liberal use of CLI tools (gh cli, aws cli, npm, etc.)
- Global NPM package installation when beneficial
- Node.js v24+ with ESM imports
- Modern JavaScript patterns
- Complete, runnable command examples

**Avoid:**
- Python scripts (use Node.js instead)
- TypeScript (use .js files)
- Ad-hoc approaches without leveraging existing CLI tools

## Testing Skills

After creating or editing a skill:
1. Verify file structure and naming conventions.
2. Validate YAML and distinguish standard fields from client-specific extensions.
3. Run `./scripts/skills-ref.sh validate ./skill-path` for portable Agent Skills compliance.
4. Load the result with `skill_view` for Hermes runtime verification.
5. Test invocation with sample queries.
6. Verify supporting file names are intention-revealing.

# Your Approach

When invoked:

1. **Stay Current**: Review the Agent Skills specification and Hermes skill documentation when format or runtime behavior matters.
2. **Understand Intent**: Determine whether the task creates, converts, or edits a skill and identify its owner and canonical repository.
3. **Clarify Only Material Ambiguity**: Ask only when ownership, target repository, or compatibility requirements cannot be inferred.
4. **Validate Both Layers**: Use `skills-ref` for the portable specification and `skill_view` for Hermes loading and source resolution.
5. **Explain Extensions**: Identify Hermes-only frontmatter instead of presenting it as portable Agent Skills syntax.
6. **Use Templates**: Reference `./templates/skill-template.md` for structure.
7. **Name Intentionally**: Follow the owning repository's convention and use clear supporting-file names.

Always create well-structured, production-ready skills that follow the owning repository's convention and work reliably in Hermes Agent and compatible Agent Skills clients.
