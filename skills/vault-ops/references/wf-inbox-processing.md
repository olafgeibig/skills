# Input Processing Workflow

Use this workflow to process incoming notes, ideas, clippings, or voice transcript captures from `inbox/` into the vault's two-layer knowledge system. The default pattern is **direct single-pass processing**: read the input once, classify it, write it to the final destination, link it, extract inline tasks, then clean the inbox. Do **not** simulate an asynchronous queue in markdown unless a real external scheduler/worker is actually operating that queue.

## Principles

1. **Code for data, LLM for judgment**
   - Deterministic collectors/scripts may drop raw inputs into `inbox/`, `sources/`, or `wiki/<domain>/raw/`.
   - The agent handles semantic decisions: classification, routing, linking, entity/concept extraction, and task extraction.

2. **Single-pass by default**
   - Interactive Hermes processing should go directly from input → final note/wiki/raw destination.

3. **Sparse wiki mapping**
   - Not every area/project needs its own wiki.
   - If an external source has no matching domain wiki, use a graceful fallback such as `sources/` or a vault-local equivalent.
   - Suggest a new wiki only after repeated sources accumulate around the same topic.

4. **Tasks stay with context**
   - Extracted tasks belong inline in the note/section they relate to.
   - Never append tasks to a project MoC or area MoC as a general collection.

## Pipeline

```text
[Input in inbox/ or direct user-provided text]
          │
          ▼
[1. Classify]
  - External raw source?
  - Personal capture / zettel candidate?
  - Actionable note with tasks?
  - Existing wiki domain or no matching wiki?
          │
          ▼
[2. Route and structure]
  - Known wiki source → use md-wiki workflow for wiki/<domain>/raw/ + entities/concepts
  - Unknown wiki source → graceful fallback in sources/clippings/ or vault-local collection
  - Personal capture → area/<domain>/ or projects/<project>/ as a zettel/article/capture per AGENTS.md
          │
          ▼
[3. Self-wire links]
  - Search existing vault graph before inventing links
  - Link to relevant MoCs, wiki concepts/entities, bookmarks, and related notes
          │
          ▼
[4. Extract inline tasks]
  - Convert concrete obligations into Obsidian Tasks syntax
  - Place each task directly beside the content it belongs to
          │
          ▼
[5. Clean up]
  - Move/delete/archive the processed inbox item according to AGENTS.md
  - Update logs/indexes only when the vault-local workflow requires it
```

## Step 1 — Classification

Determine the source and intent:

- **External source:** article, paper, thread, repository, transcript, clipping, exported document.
- **Personal capture:** user's thought, idea, journal fragment, voice memo, synthesis draft.
- **Actionable input:** meeting notes, obligation list, email-like content, planning note.
- **Mixed input:** split into source preservation + personal synthesis + inline tasks as needed.

Read `AGENTS.md`, `wiki/index.md`, and relevant `area/INDEX.md` / `projects/INDEX.md` when routing is unclear.

## Step 2 — Routing

### External source with matching wiki domain

Use the `md-wiki` workflow. Vault-ops should not directly edit `wiki/` unless the task explicitly activates the md-wiki layer and its rules.

### External source without matching wiki domain

Use graceful fallback:

- Store as `type: resource` or vault-local equivalent in `sources` or a domain-neutral holding area.
- Link it from any relevant area/project note if there is a clear connection.
- If multiple related sources accumulate, ask whether to create a new domain wiki.

### Personal capture

Create or update the relevant area/project note according to `note-writing.md`, `moc-writing.md`, and vault-local templates. Respect the area's language policy from `AGENTS.md`.

## Step 3 — Self-Wiring

Before adding links, search the vault graph:

- Use TurboVault search/metadata/link tools to find existing MoCs, notes, wiki entities, and concepts.
- Prefer existing canonical notes over creating duplicates.
- Add both `topics` frontmatter and body `## Topics` links when creating a note.
- Link to wiki pages as sources from area/project notes; avoid writing backlinks into `wiki/` from vault-ops.

## Step 4 — Inline Task Extraction

Identify concrete tasks, commitments, deadlines, blockers, and follow-ups.

Use Obsidian Tasks syntax, for example:

```markdown
- [ ] Call service provider about cancellation 📅 YYYY-MM-DD
- [?] Clarify missing document before submission
```

Placement rule:

- Put the task directly under or near the paragraph/section that creates the obligation.
- If the note has an obvious `## Tasks` section for that exact topic, use it.
- If no specific section is clear, append to the relevant note as a fallback — not to a MoC.

## Step 5 — Cleanup and Verification

After processing:

1. Verify the target note(s) were written.
2. Verify important links resolve when structural links changed.
3. Move the original inbox item to the vault-local processed/archive location, or delete it if it was temporary and the content is fully preserved.
4. Update INDEX/MoC/log files only when required by the vault's `AGENTS.md` or the activated workflow.
