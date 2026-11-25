---
change_id: 20261125-turbovault-use-adaptation-sync
date: 2026-11-25
branch: edit/turbovault-use-adaptation-sync
status: reviewed
affected_skills:
  - turbovault-use (0.20.1 -> 0.21.0)
---

# Change: Add `wf-turbovault-config`, Deduplicate Config/Troubleshooting & Drop 3.x Legacy

## Goal Statement

Promote the reusable operational safeguards from `turbovault-use-adaptation` into `turbovault-use`, introduce a procedural configuration & post-update audit workflow (`references/wf-turbovault-config.md`) with clear baseline defaults, remove all 3.x / pre-v4 legacy instructions, and deduplicate overlapping guidance across `SKILL.md`, `references/vault-configuration.md`, `references/troubleshooting.md`, `references/upgrading.md`, and `references/audit-and-rollback.md`.

## Summary

- **New workflow reference (`references/wf-turbovault-config.md`):** Step-by-step workflow for initial setup, config audit, post-update config verification, default diagnosis, and default repair:
  - **Read-only inventory:** `turbovault --version` + `turbovault --help`, client MCP entry (`args`/`env`, never printing unrelated/credential sections), resolved `--config` YAML, and live `list_vaults` / `get_vault_context`.
  - **Baseline defaults checklist:**
    - Explicit `--config <path>` in MCP `args` (required for `vaults:` loading).
    - `env.XDG_CACHE_HOME` set per profile even on single-profile installations to prevent working-directory cache drift across processes (gateway, dashboard, CLI).
    - `--no-confirm-destructive` in Hermes MCP `args` as the baseline workaround while Hermes leaves MCP elicitation `requestedSchema` fields empty (explicitly noting what the flag disables and keeping `confirm_path` + audit trail discipline).
    - Clean YAML without misleading or stale comments.
    - `tool_visibility`: `show_advanced_tools: true` and `disabled: [fanout, list_orphan_fanouts]` while `write_backend: direct` is active.
    - Explicit `is_default: true|false` on every vault entry; **always show the current `is_default: true` vault and ask the user whether it is actually the intended default** (never assume an existing entry is right).
    - Optional plugins (such as `vector_search`) omitted from the baseline setup and explicitly excluded on multi-vault servers unless requested for a dedicated single-vault server.
  - **Post-update config check:** Diff installed `turbovault --help` options and config schema requirements against client MCP `args` and `--config` YAML after binary updates.
  - **Consolidated procedures:** Absorbs `Inspect existing working-vault registrations` (from `vault-configuration.md`), `Diagnose Where a Default Comes From` (with `unresolved` reporting when YAML lacks a default), and `Repair a Persisted Vault Default` (updating `is_default` booleans in place, verifying file read-back and live runtime separately, and claiming restart persistence only after an actual restart).
  - **Verification:** `scripts/probe-config.py` + live `list_vaults` / `get_vault_context`.
- **Clean responsibility split & deduplication:**
  - `references/vault-configuration.md`: declarative configuration reference (schema, `add_vault` / registration, cache isolation mechanics, `obsidian.json` discovery, pre-write orientation, isolated-test gates — removing procedural inspection duplication).
  - `references/troubleshooting.md`: runtime failure symptoms (parked spawn, `env` string typing, `mcporter` bridge, reconnect churn, stale Obsidian UI, editing errors, log diagnosis) — pointing config audits and default diagnosis to `wf-turbovault-config.md`.
  - `references/audit-and-rollback.md`: keeps the elicitation failure explanation and destructive-operation discipline without duplicating `troubleshooting.md`'s parked-spawn walkthrough.
  - `references/upgrading.md`: adds config backup alongside executable archival (version, checksum, archive path; planned vs. created archives), separates client launch flags from server YAML, decouples optional plugin evaluation, and links `wf-turbovault-config.md` for post-upgrade config verification.
- **Remove all 3.x / pre-v4 legacy & outdated patterns:**
  - Strip all references to `3.x`, `pre-v4`, `older servers`, `3.1.0`, `get_active_vault`, `get_vault_config`, `advanced_search`, `mcp_turbovault_list_vaults`, tool-consolidation history (`79 tools into 52`), and 3.x fan-out tool names (`begin_fanout`, `commit_fanout`, `abandon_fanout`) across `SKILL.md`, `vault-configuration.md`, `upgrading.md`, `editing-and-batch-operations.md`, `search-and-graph.md`, `frontmatter-and-templates.md`, and `renames-and-refactors.md`; align `vector-search-setup.md` launch flags with the baseline (`-p`, `--no-confirm-destructive`, `XDG_CACHE_HOME` note).
  - Update `vault-configuration.md` and `troubleshooting.md` so vault registration/lookup favors the per-call `vault` argument over forcing `set_active_vault` when only targeted access is needed.

## Conceptual Deltas (Input for Concept Documentation Update)

### 1. Declarative Reference vs. Procedural Config Workflow (`wf-turbovault-config.md`)

- `references/vault-configuration.md` defines the static config schema, cache behavior, and safety gates; `references/wf-turbovault-config.md` defines the operational setup, post-update check, default diagnosis, and default repair workflow.
- Standard Hermes baseline includes `XDG_CACHE_HOME` isolation even on single-profile hosts, `--no-confirm-destructive` (as the current Hermes elicitation workaround), `tool_visibility.show_advanced_tools: true`, `tool_visibility.disabled: [fanout, list_orphan_fanouts]`, clean YAML without misleading comments, and an explicit user confirmation of which vault carries `is_default: true`.

### 2. Deduplicated Error Ownership Across References

- Spawn/parking mechanics (`env` string validation) live in `troubleshooting.md`; destructive-gate trade-offs live in `audit-and-rollback.md`; config-audit/default-repair procedures live in `wf-turbovault-config.md`, with cross-links instead of repeated blocks.

### 3. TurboVault 4.0+ Baseline Only

- `turbovault-use` drops all 3.x compatibility branches and retired tool names and aligns `add_vault`/lookup guidance with the per-call `vault` parameter.

## Scope Boundary (Remains Outside `turbovault-use`)

- Machine/profile-specific config paths (resolved from the active client MCP config) and per-instance default vault choices (confirmed interactively with the user during config checks).

## Notes for Follow-up (Out of Scope Here)

- After `turbovault-use` is updated and reviewed, delete the obsolete profile-local `turbovault-use-adaptation` skill on profile `robert`.
