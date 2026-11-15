# Adopting an Existing Project onto the Dossier-Project Model

The rare second path: a stock project with notes in the old layout (an `akte`/`vorgang` kind, or an early hand-rolled one) becomes a dossier-project. The model is already decided; this reference is the migration itself — phases, verdicts on legacy content, gates. Setting up an empty project is `references/init-project.md`; reclassifying a single arriving note is `references/triage.md`.

## When to Load

- A project is adopted onto this kind, in whole or folder by folder
- The same migration is planned for a second project — the phases do not change

## Phase 0 — Back up and measure

1. Take a tarball of the project directory outside the vault and list it back.
2. Measure the baseline yourself. Never quote the counts from the concept or plan that proposed the migration: a stale or inverted count there is a defect to report, not a number to build on. Baseline: note count per legacy `type:`, open tasks by **ID**, which legacy sections exist (`## Verlauf`, `## Arbeitsergebnisse`, `## Vorgänge`, `## Offen`), `check.py --report` findings, the vault-wide `graph_report(kind="broken_links")` count, and every inbound link from outside the project.
3. The inbound-link list bounds the rename risk: when only the router and one dossier are linked from outside, everything inside may be renamed freely.

## Phase 1 — The target grid, before the first move

Decide every target name and class first; a note is visited once (Phase 3).

- **The dossier cut is the user's division of the subject, in their own words.** Ask how they see the subject before proposing a cut; one derived from the note inventory or from a tidy ontology is the wrong axis, and the user feels a mis-cut at once.
- Apply the class **test question** to the legacy note's content, not its old `type:`. An `akte` is not automatically a `dossier` — ask "does this ever end?": a sale ends, an estate does not. A `vorgang` is usually one `case`. An `arbeitsergebnis` splits by provenance: sent or frozen → `artifact`, unsent or synthesised → `analysis`, URLs and findings → `research`, one source distilled → `extract`.
- A legacy note whose facts belong to three classes dissolves into three notes — that is what the migration is for.
- The reverse happens too: several legacy notes may be one matter. When one matter was absorbed by another — a proceeding consumed by the case that superseded it — the absorbed note dies and its history entries take the Phase 2 verdicts; two notes for one matter is the defect the migration removes. The home of a fact is decided by the kind's *Where a fact belongs* table: values others cite → `masterdata`, state → `## Stand`, a happening with content → `event`, an arrived text → `raw/`.
- Case names name the matter and carry no date prefix; date prefixes live only in `raw/`, `artifacts/`, `events/`, `analyses/`. Several versions of one document need distinct basenames — `raw/` freezes all of them.
- Check every target name against the **whole vault**, case-insensitively (SKILL.md → Verification). A case named like a wiki concept (`grundbuchberichtigung`) resolves to the wrong note on a case-insensitive filesystem while a string-exact name check passes.
- Put the grid and the history verdicts in a plan note **outside the project subtree** — a drafts folder; inside, the plan is a note without a class and litter after the migration — and write planned note names as **code spans, not `[[…]]`**: a plan that links to notes which do not exist yet inflates the broken-link count the migration later has to prove.

### Source-kind mapping: `casefile`

When the source is the `casefile` kind, half of the grid is decided — map folder and class first, then apply the test questions to whatever does not fit:

| casefile | dossier-project | The move |
|---|---|---|
| `akten/` · `akte` | `dossiers/` · `dossier` | one akte may split into several dossiers: the test question is asked per subject, not per file |
| `vorgaenge/<YYYYMMDD Anlass>/` · `vorgang` | `cases/` · `case` | the directory dissolves: the MoC body is the case, its children move to their own class folders |
| `stammdaten/` · `stammdatum` | `masterdata/` · `masterdata` | values as they are; the agent still only cites them |
| `quellen/` · `resource` | `raw/` · `document` | the conversion note *is* the document; keep `source:` and `sha256:` |
| `arbeitsergebnis` | `artifact` / `analysis` / `extract` / `research` | by provenance: sent or frozen → `artifact`, synthesised → `analysis`, one source distilled → `extract`, URLs and findings → `research` |
| `utility` | `utility` | unchanged; router, task hub and chronology stay at the root |

Four differences that bite:

- **A Vorgang is a directory, a case is one note.** The MoC body becomes the case; `## Verlauf` dissolves through the Phase 2 verdicts, and the `## Arbeitsergebnisse` links point at the `artifact`/`analysis` notes that moved out. One Vorgang becomes one case plus its children, and the directory is gone.
- **`status:` values change.** `offen → open`, `ruht → blocked`, `geschlossen → closed`. A case left on the old values fails the class check even when its body is right.
- **`## Vorgänge` becomes generated.** The hand-maintained link list on the Akte is replaced by `## Fälle`, rebuilt from `dossier:` on the cases. Move those links into the property; never hand them to the section.
- **`Topics:` footers are dropped.** casefile mirrors `topics:` into a body footer; dossier-project keeps only `Quellen:`. Strip it during the one visit per note — `update_backlinks` never touches a footer.
- **The folder's own MoC is not in the mapping table.** `+Akten`, `+Stammdaten` and their kind are pages, not classes: give each its own verdict in Phase 1 — its entries re-home into the new hubs or drop with the folder, and the page itself dies with the folder. A `+`-page left behind holding dead entry rows is the first defect anyone finds.

## Phase 2 — Verdict on every legacy history entry

`## Verlauf`, `## Arbeitsergebnisse` and done-task lists are the old model's history. Take one row per entry and give each exactly one verdict:

| Verdict | Means | Becomes |
|---|---|---|
| document | it arrived, there is a text | a `raw` note, or a backlog entry when the original is unconverted |
| event | spoken, no document, carries content | `events/<date>-<what>.md` |
| artifact | the note already exists | a `cases:` pointer on it |
| drop | an internal working step | nothing |
| chronology | it marks a decision, a result or a deadline | one line in the project's chronology note, then the checkbox is dropped |

Then most entries are documents and drops, and the migration yields far fewer new notes than the length of the `## Verlauf` suggests. That is the finding, not a defect: the project's history is not in the vault. Put unconverted originals on a backlog; never invent an event to stand in for a document that exists on paper.

## Phase 3 — Order of operations

1. **Spec first**: rewrite the project manual to the target kind before any note moves — a note validated against a schema that does not exist yet is validated against nothing. Fill `assets/project-AGENTS.md` and stop there: the kind's classes, folder table and section rules live in the skill and are restated nowhere else — a manual repeating them is maintained twice and reads as noise. A hybrid project keeps its work-tree section: `assets/project-AGENTS.md` assumes shape B, and dropping the work tree during the rewrite is a defect.
2. **Evidence leaves first** (`raw/`, then `artifacts/`): nobody writes into them and they only link forward.
3. **The dossier**, then **the cases** — a case rewrites its own body anyway, so it can link the new names directly.
4. **Derived notes** (`extract`, `research`, `analysis`, `event`, `masterdata`), then the three root notes, then the generated sections.
5. **One visit per note**: name, folder, `type:`, properties and body in one pass. A note visited twice has its links repaired twice.

## Phase 4 — Generated sections, then the gates

- `check.py --rebuild <project>` proposes the generated rows; the user approves; `edit_note` writes exactly those bytes (SKILL.md → Verification).
- Gates, all measured: `check.py --report` findings reach 0 · `--audit` items are fixed or carry a recorded decision · the vault-wide broken-link count is unchanged and no entry's `source_file` is inside the project · a raw-text sweep finds none of the old basenames anywhere (the `links` table drops unresolvable targets — `turbovault-use` → *find dead links by content search, not SQL*) · the open-task **ID** list is diffed, not the checkbox count · every note's folder allows its `type:`.
- Only then do the empty legacy folders go.
- Then write what each gate returned (before → after) into the plan note. The plan is the migration's record; a plan that stays a plan leaves the numbers only in the transcript.
- **Then hand over, name-level** — the folder list as it now stands, every note deleted or absorbed with one reason, every page that died with its folder, and what is deliberately not migrated (the backlog). A count is not a report; the user reviews a migration by remembered names.

## Pitfalls

- Moving notes before the grid is approved. The phase order exists so no note is ever visited twice.
- Letting the plan note link to future note names — it poisons the broken-link baseline it must later prove.
- Turning each `## Verlauf` line into an event. An event earns a file only when it carries content (SKILL.md → *the recording rule*); the rest is documents and drops.
- Trusting `update_backlinks` after a rename: it rewrites wikilinks and inline links, not aliases, heading targets or plain-text mentions — the raw-text sweep is its own gate, not a formality.
- Dropping done tasks without re-scanning `⛔` blockers. A blocker whose ID is gone reads as an unresolved dependency forever; a completed blocker is unblocked, so remove the reference instead of leaving it dangling.
- Leaving a legacy `+`-page to the end. Its verdict belongs in Phase 1 like every other note's; a page of dead entry rows is what the user finds first, and finding it themselves reads as an accident.
