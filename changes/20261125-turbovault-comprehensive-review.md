---
change_id: 20261125-turbovault-comprehensive-review
date: 2026-11-25
branch: edit/turbovault-comprehensive-review
status: reviewed
affected_skills:
  - turbovault-use (0.21.0 -> 0.22.0)
  - vault-ops (0.25.0 -> 0.25.1)
  - csl-vault (0.4.0 -> 0.4.1, in bosch-skills)
---

# Change: Comprehensive TurboVault 4.x Review & Domain Restructure (`turbovault-use`)

## Goal Statement

Align `turbovault-use` strictly with TurboVault 4.x (verified against `Epistates/turbovault` v4.0.2 and 4.1.0 source code, live JSON-RPC probes, and live MCP tool schemas), remove remaining pre-4.0 relics and project/vault-specific leaks, eliminate cross-file duplication and contradictions, consolidate 12 overlapping references into 8 domain-disjoint references (6 topic + 2 `wf-*` workflows), tighten `SKILL.md` and its routing table, and fix concrete defects in the bundled scripts/template.

## Summary

- **Metadata & `SKILL.md` tightening:**
  - Updated `description` to `"Use when operating Obsidian/OKF vaults via TurboVault."` (54 chars, within the 57-char Hermes routing budget while preserving Obsidian + OKF scope).
  - Reduced `SKILL.md` from 195 lines (~23 KB) to 110 lines (~9.2 KB) with a complete 4.x 52-tool surface table (30 core + 22 advanced + opt-in plugin) and a single unambiguous 8-row routing table.
- **Factual corrections against TurboVault 4.x source & live 4.0.2 probes (`cli.rs`, `multi_vault.rs`, `config.rs`, `cache.rs`, `rollback.rs`, `graph.rs`, `CHANGELOG.md`):**
  - **Config & `is_default` startup behavior:** `~/.turbovault/config.yaml` *is* loaded automatically for `vaults:` when `--config` is omitted. `is_default: bool` is required on every `vaults:` entry (`config.rs:189`), **but does not select `active_vault` at startup**: `ObsidianMcpServer` starts vault-agnostic and registers entries via `add_vault` in list order, where only the **first** vault sets `default_vault` (`multi_vault.rs:118-127`). Top-level `list_vaults` `data.vaults[].is_default` reports the active pointer; the YAML flag lives at `data.vaults[].config.is_default`.
  - **Project cache key, trigger & precedence:** The project cache ID is hashed from the nearest ancestor containing `.git`, `.obsidian`, `Cargo.toml`, `package.json`, or `.project` (falling back to CWD; `cache.rs`), and is written only when runtime `add_vault` or `set_active_vault` runs (which snapshots YAML vaults too). On restart, cache recovery runs before `register_configured_vaults` and skips any YAML entry whose `(name, path)` already exists in cache (`cli.rs:697-700`), while re-checking restored paths against `allowed_vault_roots`. Persisted default repair therefore requires putting the target vault **first** under `vaults:` AND rotating/clearing the project cache if present.
  - **Destructive authorization & elicitation:** Anchored explicit user authorization for destructive operations as a `SKILL.md` core invariant independent of client/bridge/elicitation (a client without `elicitation.form` is never prompted at all). Clarified 4.0.x (3 paths) vs. 4.1.0+ (5 paths: `batch_execute` prompts for `DeleteNote` and destination-replacing `MoveNote`, **not** overwriting `WriteNote`). Instructed passing `force: false` by default on Direct `delete_note`, retrieving Direct audit IDs via `audit_log` (since `delete_note` does not return one), and recording commit SHAs on Git.
  - **Hash-conflict & batch/vault-switch accuracy:** On the first `expected_hash` mismatch, reconcile prior read, current disk content, and intended edit before retrying (never blindly replay with a fresh hash). Distinguished Direct batch precondition/validation failures (zero writes) from mid-execution failures (partial state, including inside multi-file Direct moves). Restricted `set_active_vault` fallback to single-session / isolated connections.
  - **Direct audit `MOVE` recording:** Plain `move_note` records one `MOVE` entry (`new_path`; `rollback_note` does not support `MOVE` -> repair by moving back), whereas `move_note(update_backlinks: true)` records `DELETE` + `CREATE` (undo both halves).
  - **Additional 4.x accuracy fixes:** `edit_note` 8+-character delimiter form; `query_tasks` `status`/`priority` array parameters; `excluded_paths` defaults vs. hard-protected `.turbovault`; `--allowed-vault-roots`, per-vault `git:` config block, and search index location under `$XDG_CACHE_HOME/turbovault/search/`; `validate_vault` skipped-notes reporting accurately labeled as unreleased post-4.1.0; separated clean-start probe verification from effective live configuration verification.
- **Pre-4.x relics, scope leaks & deliberate pruning:**
  - Removed obsolete `template_dirs` claim, misleading "removed `force` argument" note, and pre-4.0 bare-link mass-conversion recipe (`LinkGraph::resolve_link` resolves bare stems first in 4.0+).
  - Removed vault/project/instance leaks (`area/<folder>/`, `wiki/`, `system/templates/`, `dossier`/`cases:`/`sources:`, `Sprache: DE.`, `dft-csl`/`drivalia-csl`, hardcoded `/Users/<user>/...`, `~/work/skills`).
  - **Deliberate removals vs. retained checks:** Dropped non-TurboVault generic agent hygiene (transcript JSON-escaping/token masking, prose typo proofreading, generic `tool_describe`/`tool_call` envelope syntax, `read_file` merge-conflict heuristic, trivial liveness/install prose). Retained operational TurboVault checks: stray-`=======` detection (`^=======` / heading-count drop), splitting oversized writes at section boundaries with fresh hashes, and `--no-confirm-destructive` spawn-time restart requirement.
- **Domain consolidation (12 -> 8 references):**
  - `references/editing-and-mutations.md` (merges `editing-and-batch-operations.md`, `renames-and-refactors.md`, and write/template mechanics from `frontmatter-and-templates.md`).
  - `references/search-and-graph.md` (absorbs metadata-query/YAML-invalid notes from `frontmatter-and-templates.md`).
  - `references/audit-and-drift.md` (merges `audit-and-rollback.md` and `audit-and-drift.md`).
  - `references/vault-configuration.md` (purely declarative schema, startup/cache mechanics, `add_vault`/`obsidian.json`, backend & visibility policy).
  - `references/wf-turbovault-config.md` (procedural setup, audit, default diagnosis/repair with vault reordering + cache rotation, post-update check).
  - `references/wf-upgrading.md` (replaces `upgrading.md` and absorbs isolated-test gates from `vault-configuration.md`).
  - `references/troubleshooting.md` (runtime failure symptoms only; resolves the `mcporter` `--no-confirm-destructive` contradiction).
  - `references/vector-search.md` (merges `vector-search.md` and `vector-search-setup.md`).
  - Deleted retired references: `editing-and-batch-operations.md`, `renames-and-refactors.md`, `frontmatter-and-templates.md`, `audit-and-rollback.md`, `upgrading.md`, `vector-search-setup.md`.
- **Bundled script, template & regression test fixes:**
  - `scripts/probe-config.py`: pins `-t stdio` in a sanitized child environment (stripping ambient `OBSIDIAN_VAULT_PATH` and `TURBOVAULT_*` vars), supports explicit `--allow-env VAR` forwarding for YAML `${VAR}` vault paths (rejecting blocked TurboVault/Obsidian override vars and failing loudly with an actionable hint when an unallowed path var is referenced), uses `communicate(timeout=...)` (eliminating stderr pipe-buffer deadlocks under one total deadline), validates the initialize handshake plus both MCP responses (`error`, `isError`, `success: true`, required arrays; non-zero exit on any error), isolates `XDG_CACHE_HOME` by default (`--use-existing-cache` opt-in), verifies registered vault names and resolved paths against the YAML on clean-start probes, prints per-vault `path`, `write_backend`, `allowed_operations`, `reconcile_external_changes`, `active` vs. `yaml:is_default` with mismatch warning, and supports `--list-tools`.
  - `scripts/vault-drift-check.py`: skips symlinks and non-regular files at scan and store time via component-by-component `dir_fd` traversal (`O_DIRECTORY | O_NOFOLLOW` on every parent directory, `O_NOFOLLOW` + `fstat(S_ISREG)` on the leaf — eliminating parent-directory symlink swap TOCTOU windows), matches repeatable `--exclude` case-insensitively with Unicode NFC folding and trailing dot/space stripping (matching TurboVault's `protected_component` parity), handles `MOVE` audit entries (source deletion + `new_path` audited write, excluding `MOVE` from `missing_despite_audit`), streams+hashes exact bytes into a temp file before atomic `os.replace` to `objects/<sha256>` (eliminating TOCTOU hash/content mismatches), surfaces `--store` snapshot errors with exit `1` while holding back failed manifest entries for retry, preserves prior manifest state for both temporarily unreadable files and unreadable directory subtrees (`os.walk(..., onerror=...)`), and removes project-specific path examples from comments.
  - `scripts/vault-drift-all.py`: requires PyYAML explicitly (removing the fragile regex fallback that rejected unindented YAML lists), forwards each vault's `excluded_paths` via `--exclude`, makes `--store` opt-in (default hash-only) with optional `--vault <name>` scoping, expands `~`/`$VAR`, and fixes exit code (`return 1 if errors else 0`).
  - `references/audit-and-drift.md`: documents opt-in `--store`, `excluded_paths` + symlink/non-regular exclusion, snapshot-error retry & exit codes, unreadable-file preservation, PyYAML dependency, mandatory SHA-256 verification before object-store restore, and restoring through `write_note(mode: "overwrite", expected_hash: ...)`.
  - `templates/vault-drift-shim.py`: defaults `HERMES_HOME` to `~/.hermes` and removes the hardcoded `~/work/skills` layout leak.
  - `scripts/test_turbovault_scripts.py`: added `unittest` regression suite (17 tests covering JSON-RPC errors, >256 KB stderr non-deadlock, ambient `OBSIDIAN_VAULT_PATH`/`TURBOVAULT_TRANSPORT` isolation, `${VAR}` path `--allow-env` enforcement, live 2-vault `is_default` mismatch + invalid YAML, live MCP vs. watchdog case-folded `excluded_paths` parity on `Private/fixture.md`, `dir_fd` parent-directory symlink rejection + leaf symlink exclusion for excluded & external targets, snapshot failure exit `1` + retry on recovery, temporarily unreadable files and directory subtrees not reported as deleted/re-created, unindented YAML + `excluded_paths` + opt-in `--store`, atomic `store_object` hash/content integrity, `MOVE` drift classification, error-preserving drift exit codes, and shim missing-config exit).

## Conceptual Deltas (Input for Concept Documentation Update)

### 1. Real TurboVault 4.x Startup Order, `is_default`, & Cache Precedence

- `~/.turbovault/config.yaml` is read automatically for `vaults:`, `tool_visibility`, and `security`; `--config <path>` overrides it for per-profile isolation.
- `is_default: bool` is required on every `vaults:` entry, but startup `active_vault` on a clean cache is always the **first** vault listed under `vaults:` (not the entry with `is_default: true`).
- The project cache (keyed by nearest project-marker ancestor or CWD) is written on `add_vault`/`set_active_vault`, runs before configured-vault registration on restart, and skips YAML entries with a matching `(name, path)`. Changing persisted startup default or per-vault YAML properties therefore requires reordering `vaults:` AND rotating/clearing the project cache when cached state exists.

### 2. Eight Domain-Disjoint References (`6 topic + 2 wf-*`) & Client-Neutral Elicitation

- Operations split cleanly by domain: mutations (`editing-and-mutations.md`), discovery/graph/structured reads (`search-and-graph.md`), audit/rollback/elicitation/drift (`audit-and-drift.md`), declarative config (`vault-configuration.md`), procedural config workflow (`wf-turbovault-config.md`), procedural upgrade workflow (`wf-upgrading.md`), runtime troubleshooting (`troubleshooting.md`), and the opt-in plugin (`vector-search.md`).
- Elicitation guidance is client-capability-based (not pinned to an outdated Hermes bug); `--no-confirm-destructive` is an explicit user choice, not a baseline default.

## Consumer Migration (Completed)

- Migrated all three consumer pointers to the new `turbovault-use` reference filenames in the same release:
  - `skills/vault-ops/references/propagation-audits.md` (lines 11, 57): `renames-and-refactors.md` -> `editing-and-mutations.md` (`vault-ops` bumped `0.25.0 -> 0.25.1`).
  - `skills/vault-ops/references/refactoring-workflows.md` (line 86): `audit-and-rollback.md` -> `audit-and-drift.md`.
  - `bosch-skills/bosch/csl-vault/references/csl-overrides-and-mocs.md` (line 30): `renames-and-refactors.md` -> `editing-and-mutations.md` and `get_broken_links` -> `graph_report(kind="broken_links")` (`csl-vault` bumped `0.4.0 -> 0.4.1`).
