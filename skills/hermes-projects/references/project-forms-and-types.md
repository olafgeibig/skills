# Projektform and Projekttyp — one page per combination

For each **Projektform**: what exists on disk, which file an agent actually loads, what travels on which channel, and where it typically goes wrong. The second half maps the **Projekttyp** onto the **Containertyp** it requires.

## `workdir` — content only outside vaults

```
<workdir>/                          # the project directory
├── AGENTS.md                       # the manual — loads when a session starts here
├── .git/                           # the only history there is
└── …                               # code, data, output
```

- **Loads:** the workdir's `AGENTS.md` — for real, by the runtime, and for every other agent that honors the convention.
- **Travels:** by Git, to every machine that clones it. That is why checkout paths per machine live in the manual, not in a vault.
- **Notes:** none. If the work produces knowledge worth keeping, the form is wrong and the project should become `hybrid`.
- **Projekttyp:** almost always `flat`, because there are no notes to govern. A `workdir` Containertyp only appears with a type whose skill declares it.
- **Fails when:** someone writes a vault copy "for documentation" — then two manuals exist and one of them is stale.

## `vault` — content is `projects/<x>/`

```
<vault>/projects/<x>/
├── AGENTS.md                       # the manual — this directory is the project directory
├── +<X>.md                         # MoC, the single index
├── conventions.md                  # optional long tail
└── …                               # notes
```

- **Loads:** the `AGENTS.md` only when the session runs in that directory; otherwise it is read because the vault's constitution or `vault-ops` requires it.
- **Travels:** by vault sync, so it is readable on the phone and present on machines that never saw the workdir.
- **Publishing:** into itself — the notes are the output.
- **Projekttyp:** `dossier-project` or `flat`. Both declare `Containertyp: vault`, and both are governed inside `projects/<x>/` only — the rest of the vault keeps the vault's rules.
- **Fails when:** the project outgrows notes and gets files that do not belong in a vault (PDFs, code). Move to `hybrid` rather than parking binaries in the vault.

## `hybrid` — both, in two variants

```
<workdir>/                          # the project directory
├── AGENTS.md                       # the manual — loads when a session starts here
├── .git/
├── …                               # PDFs, code, generated output
└── [optional] <name>/              # the project's own vault, inside the workdir

<vault>/projects/<x>/
├── AGENTS.md                       # optional router — only for vault-only discovery
├── +<X>.md
└── …                               # notes
```

The vault sits **beside** the workdir (two independent paths) or **inside** it (a subdirectory, never the workdir's root). The second variant is the interesting one: it has a `Containertyp: workdir` and its own manual.

- **Loads:** the workdir's manual where the work happens. Keep the vault router only when an agent with just the vault must discover the workdir; otherwise the MoC says that the workdir is the project directory and these notes are its knowledge source.
- **Travels:** workdir by Git, notes project by vault sync. Checkout paths have one authoritative home: the manual by default, or the router when vault-only discovery requires it — never both.
- **Publishing:** declare the target per project. The notes project may be a knowledge source, the target of the project's own vault, or both.
- **Fails when:** the router grows into a second manual or duplicates the checkout paths. If a rule is about doing the work, it belongs in the workdir; if it is about the notes, it belongs in the vault.

## Projekttyp × Containertyp

| Projekttyp | Containertyp | Skill |
|---|---|---|
| `dossier-project` | `vault` | `dossier-project` |
| `flat` | `vault` | none — described in `SKILL.md` |
| `authoring-project` | `workdir` | `authoring-project` |
| `cs-project` | `workdir` (Projektform `hybrid`: repository plus embedded `csl/` vault as its own subdirectory) | `cs-project` for the project; `csl-vault` for the embedded vault only |

A project's own vault lives in a **subdirectory** of the workdir and is **unregistered by default**: without registration it has no TurboVault audit, rollback or drift check, so its own version control is the safety net. Never apply the notes vault's types (`zettel`, `article`, …) inside it, and never translate its notes across the boundary except at publication.

## Choosing, in one line

Files a tool consumes → `workdir`. Everything is thinking, and it must be readable from anywhere → `vault`. Both → `hybrid`, and then the question is not where the files are but what the notes are *for*: knowledge source, publication target, or both. Which Projekttyp governs it is a separate question, answered by the skill that exists for that type — `flat` when none does.
