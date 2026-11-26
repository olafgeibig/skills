# Ingest and Compile (`knowledge/`)

Use this reference when triaging `inbox/` or compiling **timeless project knowledge** (`knowledge/raw → distilled → kb`). Notes under `knowledge/` carry **no `case_id` filename prefix**.

If a meeting, email, or analysis belongs to a specific finite incident, investigation, or change request, route it to `activities/` under its `case_id` instead (`references/case-workflow.md`).

## Triage from `inbox/`

Quick captures, pasted links, or unprocessed drops land in `inbox/` without required frontmatter. When triaging `inbox/`:

- Pure external link / pointer → append to `Bookmarks <X>.md` and remove the inbox item.
- Timeless raw document, web/Docupedia export, or knowledge meeting → move to `knowledge/raw/` (Step 1 below).
- Case-bound transcript, email, or note → move to `activities/raw/` or `activities/` with `case_id:` (`references/case-workflow.md`).
- New bounded work item (incident, investigation, feature/compliance change) → open a `case` in `cases/` (`simple` or `complex`).
- Artifact belonging to another vault/project (e.g. formal compliance or code deliverable) → flag for move to that project.

## Tier 0 → Tier 1 → Tier 2 Flow (Timeless Knowledge)

### Step 1: Ingest Raw Source (`knowledge/raw/`)

- Use `assets/template-document.md` (`type: document` or `type: transcript`, `status: raw`).
- Name with a date prefix: `YYYY-MM-DD <Short Title>.md`.
- Record `created`, `source` (relative path, URL, or prose — never a wikilink), and `sha256` when known.
- Keep body verbatim; **never edit a raw note after ingest**.

### Step 2: Distill (`knowledge/distilled/`)

- Use `assets/template-distilled.md`:
  - `type: meeting` — timeless architecture/strategy/domain meeting digest (`YYYY-MM-DD <Title>.md`).
  - `type: research` — digest of external standards, compliance rules, or technical docs.
  - `type: analysis` — multi-source reasoning about timeless project knowledge.
- Set `status: current`, `as_of: YYYY-MM-DD`, and `sources: ["[[...]]"]` (or external source description).
- Open with `## Summary` / `## Kurzfassung`. Separate verified facts from assumptions.
- When replaced, set `status: superseded` + `superseded_by: "[[...]]"` and flag dependent `fact` notes `status: stale`.

### Step 3: Delta-Compile into `knowledge/kb/`

Before creating a new `fact` note, search existing `knowledge/kb/` notes (`search` with `exclude_paths: ["archive/"]` and `frontmatter_filters: [{"key": "type", "value": "fact"}]`):

1. **Confirmation (no substantive change):** append source to `sources:`, bump `as_of:`, keep `status: reviewed` and `reviewed_on:` untouched.
2. **Update (facts changed or expanded):** rewrite affected claims **in place** (current state only), update `sources:` and `as_of:`, reset `status: draft` (clear `reviewed_on:`), and log one line in `knowledge/kb/KB Log <X>.md`.
3. **Contradiction (conflicts with a `reviewed` fact):** do not overwrite silently; set `status: disputed`, record the conflicting claim/source, and surface to the user.
4. **New atomic fact:** create from `assets/template-fact.md` (`type: fact`, `scope: domain | solution`, `status: draft`), link from `+<X>.md`, and log in `KB Log <X>.md`.

### Step 4: Human Review & Cascade Staleness

- When a `distilled/` note becomes `superseded`, check `get_links(path, direction="incoming")` and set dependent `fact` notes to `status: stale` (logged in `KB Log <X>.md`).
- Only explicit user approval transitions a `fact` to `status: reviewed` and sets `reviewed_on: YYYY-MM-DD`.
