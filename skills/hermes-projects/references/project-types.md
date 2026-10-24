# Project types — one page per shape

Checklist for each shape: what exists on disk, which file an agent actually loads, what travels on which channel, and where it typically goes wrong.

## A — worktree only

```
<work tree>/                        # the project directory
├── AGENTS.md                       # the manual — loads when a session starts here
├── .git/                           # the only history there is
└── …                               # code, data, output
[optional] <work tree>/<name>/      # a working vault in a subdirectory
```

- **Loads:** the work tree's `AGENTS.md` — for real, by the runtime, and for every other agent that honors the convention.
- **Travels:** by Git, to every machine that clones it. That is why checkout paths per machine live in the manual, not in a vault.
- **No notes project.** There is no notes knowledge source to consult; if the work produces knowledge worth keeping, the shape is wrong and the project should become C.
- **Fails when:** someone writes a vault copy "for documentation" — then two manuals exist and one of them is stale.

## B — notes only

```
<vault>/projects/<x>/
├── AGENTS.md                       # the manual — this directory is the project directory
├── +<X>.md                         # MoC, the single index
├── conventions.md                  # optional long tail
└── …                               # notes
```

- **Loads:** the `AGENTS.md` only when the session runs in that directory; otherwise it is read because the vault's constitution or `vault-ops` requires it.
- **Travels:** by vault sync, so it is readable on the phone and present on machines that never saw the work tree.
- **Publishing:** into itself — notes are the output.
- **Fails when:** the project outgrows notes and gets files that do not belong in a vault (PDFs, code). Move to C rather than parking binaries in the vault.

## C — hybrid

```
<work tree>/                        # the project directory
├── AGENTS.md                       # the manual — loads when a session starts here
├── .git/
├── …                               # PDFs, code, generated output
└── [optional] <name>/              # working vault: AGENTS.md, INDEX.md, own type system

<vault>/projects/<x>/
├── AGENTS.md                       # optional router — only for vault-only discovery
├── +<X>.md
└── …                               # notes
```

- **Loads:** the work tree's manual where the work happens. Keep the vault router only when an agent with just the vault must discover the work tree; otherwise the MoC says that the work tree is the project directory and these notes are its knowledge source.
- **Travels:** work tree by Git, notes project by vault sync. Checkout paths have one authoritative home: the manual by default, or the router when vault-only discovery requires it — never both.
- **Publishing:** declare the target per project. The notes project may be a knowledge source, an `authoring` working vault's target, or both. A `csl` working vault follows `analysis → compiled → docs` and may publish inside itself or to an external repository.
- **Fails when:** the router grows into a second manual or duplicates the checkout paths. If a rule is about doing the work, it belongs in the work tree; if it is about the notes, it belongs in the vault.

## The working vault overlay

Applies to A and C. Lives in a **subdirectory** of the work tree. Registration is per profile; without it, the working vault has no TurboVault audit, rollback or drift check, so its own version control is the safety net.

| kind | What it is | Skill |
|---|---|---|
| `knowledge-base` | hand-written knowledge, no publication target | none — plain files |
| `authoring` | analysis → distilled → deliverables; commonly publishes into the associated notes project | `authoring-vault` |
| `csl` | Bosch security lifecycle: evidence, manifest, `analysis → compiled → docs`; target declared per project | `csl-vault` |

Never apply the notes vault's types (`zettel`, `article`, …) inside a working vault, and never translate its notes across the boundary except at publication.

## Choosing, in one line

Files a tool consumes → **A**. Everything is thinking, and it must be readable from anywhere → **B**. Both → **C**, and then the interesting question is not where the files are but what the notes are *for*: knowledge source, publication target, or both.
