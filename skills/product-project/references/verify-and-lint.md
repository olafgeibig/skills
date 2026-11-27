# Verification and TurboVault-Native Lint

Use this reference for two-tier epistemic verification (Knowledge Grounding and Constraint Satisfaction) and the 100% TurboVault-native Lint cycle. Do **not** create `check.py` or external epistemic stores.

---

## Part 1 — Two-Tier Epistemic Verification Protocol

### 1. Verification Modes (Priority Order)

1. **Primary — Knowledge Grounding & Contradiction Check (`mode: grounding`):**
   Verifies that every factual claim in a target note is supported by its `## Citations` / `## Quellen` (and primary `raw/` evidence for critical facts, figures, and dates) with zero *bare assertions* and no contradiction against active `reviewed` facts in `knowledge/kb/`.
   - **Default Tier-2 triggers:** `knowledge/kb/` `draft` facts before `draft → reviewed` (including mid-case/close promotions), `artifacts/` and `product/` `SPEC` before `draft → reviewed`, and periodic semantic lint.
   - **Selective Tier-2 triggers:** Decision-bearing `activities/` (`analysis` / `research`) used as input for deliverables, evaluations, specs, or KB promotions, and dense or high-stakes `knowledge/distilled/` notes.
2. **Secondary — Constraint Satisfaction Check (`mode: constraints`):**
   Verifies whether candidate solutions or a case satisfy every `requirement` constraint or numbered `## Goal & Acceptance Criteria` item.
   - **Default trigger:** **On demand** (user-requested) or when explicitly enabled in `projects/<x>/AGENTS.md` (Tier-1 visible chat table by default; Tier-2 subagent when requested).

### 2. Core Epistemic Rules (Mandatory in Both Modes & Tiers)

- **Atomic, explicit decomposition:** Break the target note into atomic, **explicitly stated**, externally verifiable items $C_1 \dots C_n$ (exclude implicit assumptions or formatting constraints). Assess each item **independently** — never bundle multiple claims into a single verdict.
- **TurboVault-only retrieval:** Read via TurboVault (`exclude_paths: ["archive/"]` on `search`; `AND path NOT LIKE 'projects/<x>/archive/%'` on SQL; `get_links(path, direction="outgoing")` for citations).
- **Strict tri-state verdict per item:**
  - `true`: explicit, unambiguous textual proof matching the exact **scope, subject, and meaning** + `[[Note]]` + section/timestamp + short verbatim quote.
  - `false`: explicit contradiction **or scope mismatch** (related-but-different fact that does not satisfy the exact scope, e.g., attributing a single-model result to all models of that size) + `[[Note]]` + section/timestamp + short verbatim quote.
  - `null`: no conclusive evidence found in the read notes — **evidence MUST stay `null`** (never attach decorative citations to an unverified claim).
- **Hard ban on the Exhaustion Rule:** Never convert `null` to `false` solely because a search returned no hit; in an incomplete vault, absence of evidence is a gap (`null`), not a refutation.
- **Stagnation Stop ($N = 3$):** After 3 search steps that change zero verdicts, stop searching, do not guess, and report the remaining `null` gaps to the user.
- **Primary-Evidence Rule:** Critical figures, dates, existence claims, and compliance/legal citations must be traced back to `raw/` or the authoritative primary text — never copied blindly from curated prose.

### 3. Tier 1 vs. Tier 2 Execution & Graceful Fallback

- **Tier 1 (Lightweight / Ad-Hoc):** Present a visible evidence table directly in chat (`Item | Verdict | Evidence`). Ephemeral unless the user asks to save it.
- **Tier 2 (Isolated Verifier Subagent via `delegate_task`):**
  - **Context isolation — pass ONLY:**
    1. Target vault name (`vault="<vault>"`) and project subtree (`projects/<x>/`).
    2. `mode` (`grounding` or `constraints`).
    3. Exact target note path(s) (and explicit constraint list when `mode: constraints`).
    4. Cited paths (`get_links(target, direction="outgoing")`) and/or `knowledge/kb/` scope paths.
    **Never** pass the working agent's draft rationale, assumptions, or conclusions.
  - **Prompt contract for the verifier subagent:**
    - Read only the target and cited notes via TurboVault (`vault="<vault>"`, excluding `archive/`).
    - Decompose into atomic items $C_1 \dots C_n$ and evaluate each strictly against read text.
    - Return an `Item | Verdict (true/false/null) | Evidence ([[Note]] + section/timestamp + short verbatim quote)` table.
    - Explicitly flag bare assertions, overlooked refutations, contradictions against `reviewed` KB facts, and internal inconsistencies.
    - Never apply the Exhaustion Rule; stop after $N = 3$ stagnant lookups and report remaining `null` gaps.
  - **Graceful Fallback:** If `delegate_task` is unavailable or fails (e.g. model/endpoint error), degrade explicitly to a strict Tier-1 line-by-line evidence table and state prominently that independent Tier-2 verification could not run.

### 4. Where Verification Outcomes Are Persisted (No New Note Type)

- **`knowledge/kb/` `fact`:** Do **not** add verification tables to `fact` bodies. Fix flagged `draft` gaps directly (or set `status: disputed`), show the verifier summary in the review dialog, and append `- YYYY-MM-DD | verified | [[Fact]] — grounded against citations (verifier subagent)` to `KB Log <X>.md`.
- **Verified `activities/` (`analysis`/`research`), `artifacts/`, `product/` `SPEC`:** Optional compact one-line note directly above `## Citations` / `## Quellen` (e.g., `*Verified YYYY-MM-DD (verifier subagent): 8/8 claims grounded against Citations.*`).
- **On-demand `cases/<ID>.md` or `evaluation` constraint checks:** Compact `## Verification` table placed directly inside the existing note (`cases/<ID>.md` after `## Goal & Acceptance Criteria`, or inside `evaluation` `## Comparison` / `## Rationale`).

### 5. 3-Level Gate Configurability

1. **Skill defaults (`product-project`):** Grounding-first Tier-2 defaults above; constraint checks on demand.
2. **Project override (`projects/<x>/AGENTS.md`):** May tighten (e.g., require Tier-2 on every `analysis`, `evaluation`, or `complex` case `done`) or relax (e.g., batch-only or on-demand).
3. **Case specificity (`cases/<ID>.md`):** Numbered `## Goal & Acceptance Criteria` defines case-specific criteria when checked.

---

## Part 2 — 100% TurboVault-Native Lint Cycle

**Mandatory scoping prefix for EVERY `query_frontmatter_sql` query over active notes:**
`WHERE path LIKE 'projects/<x>/%' AND path NOT LIKE 'projects/<x>/archive/%'`

### 1. Deterministic Pass (TurboVault Tools Only)

- **Check 1 — Superseded cascades (`→ stale`):**
  ```sql
  SELECT path, type, superseded_by FROM files
  WHERE path LIKE 'projects/<x>/%' AND path NOT LIKE 'projects/<x>/archive/%'
    AND status = 'superseded'
  ```
  For each returned path, call `get_links(path, direction="incoming")`. Any active `knowledge/kb/` `fact` still referencing it becomes `status: stale` (logged in `KB Log <X>.md`); any active `spec` whose `evaluation` is `superseded` becomes `status: stale`.

- **Check 2 — Missing `case_id` across ALL 5 Case Knowledge folders:**
  ```sql
  SELECT path, type FROM files
  WHERE (path LIKE 'projects/<x>/cases/%'
      OR path LIKE 'projects/<x>/activities/%'
      OR path LIKE 'projects/<x>/artifacts/%'
      OR path LIKE 'projects/<x>/product/%')
    AND path NOT LIKE 'projects/<x>/archive/%'
    AND (case_id IS NULL OR case_id = '')
  ```
  *(Note: `activities/%` covers both `activities/` and `activities/raw/`.)*

- **Check 3 — Case completeness:**
  For each active `case`:
  ```sql
  SELECT path, case_id FROM files
  WHERE path LIKE 'projects/<x>/cases/%'
    AND path NOT LIKE 'projects/<x>/archive/%'
    AND status IN ('open', 'active')
  ```
  Query all active files with that `case_id` and compare against `get_links(case_path, direction="outgoing")`; alert on any unlinked file.

- **Check 4 — Review, decision & supersession date/link gates:**
  ```sql
  SELECT path, type, status, reviewed_on, decided_on, superseded_by FROM files
  WHERE path LIKE 'projects/<x>/%' AND path NOT LIKE 'projects/<x>/archive/%'
    AND ((status = 'reviewed' AND (reviewed_on IS NULL OR reviewed_on = ''))
      OR (type = 'evaluation' AND status = 'decided' AND (decided_on IS NULL OR decided_on = ''))
      OR (status = 'superseded' AND (superseded_by IS NULL OR superseded_by = '')))
  ```

- **Check 5 — Mandatory scalar `product/` relations & enum hygiene:**
  ```sql
  SELECT path, type, requirement, concept, evaluation FROM files
  WHERE path LIKE 'projects/<x>/product/%'
    AND path NOT LIKE 'projects/<x>/archive/%'
    AND ((type IN ('concept', 'evaluation') AND (requirement IS NULL OR requirement = ''))
      OR (type = 'spec' AND (concept IS NULL OR concept = '' OR evaluation IS NULL OR evaluation = '')))
  ```
  Also check valid enums for `fact.scope` (`domain` | `solution`), `requirement.origin` (`feature` | `problem` | `compliance` | `initiative`), `case.case_kind` (`simple` | `complex`), `spec.implementation_status` (`planned` | `in-progress` | `implemented` or empty), and `masterdata.class` (`people` | `system` | `schedule` | `glossary`).

- **Check 6 — `knowledge/masterdata/` checkbox & status hygiene:**
  ```sql
  SELECT path, status, class FROM files
  WHERE path LIKE 'projects/<x>/knowledge/masterdata/%'
    AND path NOT LIKE 'projects/<x>/archive/%'
    AND (status IS NOT NULL AND status != '')
  ```
  And run `query_tasks(path="projects/<x>/knowledge/masterdata")` confirming zero checkboxes.

- **Check 7 — Open epistemic queue:**
  ```sql
  SELECT path, scope, status, as_of FROM files
  WHERE path LIKE 'projects/<x>/knowledge/kb/%'
    AND path NOT LIKE 'projects/<x>/archive/%'
    AND type = 'fact'
    AND status IN ('draft', 'stale', 'disputed')
  ```

- **Check 8 — Archive isolation:**
  Query `SELECT path FROM files WHERE path LIKE 'projects/<x>/archive/%'`. For each archived path, call `get_links(path, direction="incoming")` and verify zero links originate outside `projects/<x>/archive/`.

- **Check 9 — MoC index completeness, horizontal `kb/fact` linkage & unprocessed `raw/` (advisory):**
  - Compare active `knowledge/kb/` `fact` and `knowledge/masterdata/` files against `get_links("projects/<x>/+<X>.md", direction="outgoing")` to surface unindexed KB notes.
  - Once `knowledge/kb/` holds ≥2 facts, check `get_links(fact_path, direction="outgoing")` to ensure each `fact` carries at least one horizontal link to another `knowledge/kb/` or `knowledge/masterdata/` note (preventing vertical source-summary silos).
  - Advisory: For `knowledge/raw/` files with `status = 'raw'`, call `get_links(raw_path, direction="incoming")` — zero links from `knowledge/distilled/` or `knowledge/kb/` identifies unprocessed raw sources without mutating raw frontmatter.
- **Check 10 — Graph & age signals:**
  Run `graph_report(kind="broken_links")` and `graph_report(kind="isolated_clusters")` (filtered to `projects/<x>/`), plus `find_stale_notes` as an advisory age signal.

### 2. Semantic Pass (Tier-2 Verifier Subagent / Agent Audit)

- **Pairwise contradiction check:** Group active `reviewed` `fact` notes by `scope` and topic; pass related pairs/groups to the Tier-2 verifier subagent to detect direct contradictions → mark `status: disputed` with the conflict callout (`references/ingest-and-compile.md`) and surface to the user.
- **Grounding spot-check:** Sample `knowledge/kb/` `fact` notes; fetch outgoing citation paths via `get_links(path, direction="outgoing")` and run the Tier-2 verifier (`mode: grounding`) to catch *bare assertions*.
