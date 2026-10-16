---
name: deep-research
description: "Use when a report must trace every claim to a source."
license: MIT
platforms:
  - linux
  - macos
metadata:
  version: "0.1.0"
  author: Olaf Geibig
  source: https://github.com/olafgeibig/skills
  adapted_from: daymade/claude-code-skills@8f0486f
  hermes:
    tags:
      - research
      - report
      - sources
      - citations
      - counter-review
    related_skills:
      - grounded-citations
      - research
      - lightrag-deep-research
      - blocked-page-recovery
    # Deliberate: keep this skill OUT of the system-prompt skill index (it is
    # token-heavy and must not be chosen autonomously). No such tool exists, so
    # the index entry stays hidden — while `/deep-research` and an explicit
    # skill_view("deep-research") keep working. See "How to Invoke".
    requires_tools:
      - manual-invocation
---

# Deep Research

Produce a research report in which every load-bearing claim is bound to an original
source, with a mandatory counter-review pass and a durable study record. Use it when the
answer changes a decision, when evidence is contested, or when the report will be read by
someone who asks where a number came from. It is not for a quick lookup nobody will audit.

This is the Hermes fork of `daymade/claude-code-skills` → `deep-research`. Provenance, file
classes and the upstream sync procedure are in `UPSTREAM.md`.

## How to Invoke

Run this skill only on explicit request — `/deep-research <task>` in a chat, or an explicit
`skill_view("deep-research")`. It is hidden from the skill index on purpose
(`requires_tools: [manual-invocation]` above is a gate, not a dependency): the agent must
not pick it up on its own for an ordinary research question. Do not offer it as a
suggestion; start a run when the user asks for one.

## When to Use

- A report, market/company study, literature review or policy question with several
  decisive claims.
- Contested evidence where two sources disagree and the report must show the conflict.
- An answer that must survive review: figures, dates and quotations that will be checked.
- Enterprise research on a company or organization (load the enterprise references).

## Prerequisites

- `python3` (3.11+) for `scripts/`; the scripts are stdlib-only and make no network or
  provider calls. `pytest` only to run `tests/`.
- A writable study directory; upstream expects it inside the owning project, not inside
  this skill directory.
- POSIX host: `scripts/provider_runs.py` imports `fcntl` (hence `platforms` above).
- `terminal`, `read_file`, `web_search`, `web_extract`; `delegate_task` for parallel
  investigation; `browser_exec` only for a lane that must run in a real logged-in UI.

## How to Run

Set `SKILL=<this skill directory>` once; every command below is relative to it.

```bash
python3 "$SKILL/scripts/research_assets.py" search   --catalog <project-catalog.jsonl> --query '<entity and question>'
python3 "$SKILL/scripts/research_assets.py" start    <study-dir> --spec <prepared-study.json> --catalog <project-catalog.jsonl> --query '<entity and question>'
python3 "$SKILL/scripts/provider_runs.py"     plan     <study-dir>
python3 "$SKILL/scripts/provider_runs.py"     validate <study-dir>
python3 "$SKILL/scripts/research_assets.py" check    <study-dir> --report <study-dir>/report.md
python3 "$SKILL/scripts/research_assets.py" register <study-dir> --catalog <project-catalog.jsonl> --report <study-dir>/report.md --term '<entity>'
python3 -m pytest "$SKILL/tests" -q          # 49 tests, ~25 s: the fork's safety net
```

Lead agent and investigators:

| Upstream role | In Hermes |
| --- | --- |
| Subagents A/B/C writing `task-a.md` | `delegate_task` batch — one task per decision question or evidence route; `context` carries the study path, the exact `dispatch_context` string and the output file |
| Provider lane in a paid chat/research UI | `browser_exec` with the user's own profile (`local=true`), one lane per provider × actual mode, never two agents on one live UI |
| Direct original-source lane | `web_search` + `web_extract`, or `terminal` (`curl -sSL`) when raw HTML is needed, or `blocked-page-recovery` when a fetch is walled |
| Filesystem evidence registry | `terminal` running the two scripts above; never hand-edit the ledger files |
| Internal reviewer team | a second `delegate_task` batch in the counter-review pass |

## Procedure

### P0 — Environment and policy

Fix and report: `AS_OF` date, mode (`standard` = several decision questions or contested
evidence, `lightweight` = one bounded question), source-type policy, counter-review plan.
Check before starting: the evidence channel actually available, original-source retrieval
(without it, do not promote summaries to final evidence), a writable study directory.
Missing filesystem access means the study stays incomplete — say so instead of reporting a
finished run.

### P1 — Question map and lanes

Decompose the assignment into decision questions; create a task only where a separate
evidence route or expertise makes the work clearer. Draft `study.json` with the questions,
one lane per provider × actual mode (names are extensible strings, not synonyms), and one
exact `dispatch_context` string — seed URL, named entities, verified codes — repeated in
every lane prompt. Include a direct original-source lane even when the report is assembled
from web search and internal investigators. Run `research_assets.py start` and
`provider_runs.py plan` before dispatch; the planner is local and makes no provider calls.

### P2 — Dispatch and investigate

Investigators search, fetch and tag sources, and keep raw search noise in their own
workspace. They return evidence packets in the shape of `references/research_notes_format.md`:
per finding a locator, a short excerpt, source type, accessibility and `AS_OF`, plus explicit
unknowns. The lead agent never treats a packet as authority — it reopens the original for
every load-bearing claim, conflicting claim and exact figure/date/quotation.

### P3 — Citation registry and source governance

Merge the packets into one numbered registry; classify each source by accessibility
(`public`, `semi-public`, `exclusive-user-provided`, `authorized-first-party`) and by type
(`official`, `academic`, `secondary-industry`, `journalism`, `community`, `other`), and group
sources derived from the same disclosure, filing, dataset or sponsor into one **evidence
family**. Bind each decision-bearing claim to approved source IDs with an exact locator
(`research_assets.py source` / `claim`). Dropped sources are recorded with a reason and never
reappear. Counts, domains and type mix are diagnostics — gate on whether each decision
question has fit-for-purpose evidence, not on a source quota.

### P4 — Evidence-mapped outline

Sections are topic-first, not task-order-first. Each section lists its source numbers, its
claims, counter-claim candidates, recency checks against `AS_OF`, gaps, and marks every
load-bearing claim `supported` / `contradicted` / `unknown`.

### P5 — Draft from evidence

Write section by section with `references/report_template_v6.md`, adapted to the requested
format. Every factual claim carries a citation; numbers keep the precision of the original;
each section carries a confidence marker and, where evidence conflicts, a counter-claim
sentence. Unsupported statements are marked `[unverified]` or omitted — never filled with a
plausible value.

### P6 — Counter-review (mandatory)

For each major conclusion: could it be wrong? Which claims rest on a single evidence family
even if many domains repeat it? Which claims lack a source that can directly observe the
fact? Are stale sources used for a time-sensitive claim? Report only evidence-backed issues —
zero findings is a valid outcome, and placeholder disputes are a defect.

### P7 — Verify and register

Cross-check every `[n]` in the report against the approved registry; trace every decisive
conclusion, exact figure, date and quotation to the original; verify that no dropped source
returned. Then `provider_runs.py validate`, `research_assets.py check` and `register` — an
answer with citations but without these records does not satisfy this skill. If a lane is
still open or a source lacks a locator, report the study as bounded rather than finished.

## References

Load only what the current phase needs; this table is the routing.

| File | Load at |
| --- | --- |
| `references/research-asset-contract.md` | P0/P1 and P7: study directory, source/claim records, prior-study discovery, final check |
| `references/source_accessibility_policy.md` | P0: source classification rules |
| `references/quality_gates.md` | all phases: gates 1–5 and anti-hallucination patterns |
| `references/research_plan_checklist.md` | P1: plan and query set |
| `references/subagent_prompt.md` | P2: investigator prompt |
| `references/research_notes_format.md` | P2: evidence packet format |
| `references/research_report_template.md`, `references/formatting_rules.md` | P4/P5: outline and formatting |
| `references/report_template_v6.md` | P5: confidence markers, counter-review layout |
| `references/source_quality_rubric.md` | P3: scoring and triage |
| `references/completeness_review_checklist.md` | P7: coverage, citations, compliance |
| `references/counter_review_team_guide.md` | P6: parallel review via `delegate_task` |
| `references/provider-run-contract.md`, `references/parallel-provider-ops.md` | only for multi-lane runs: `study.json` schema, lane states, owner assignment |
| `references/report-file-collection.md` | collecting a lane's report file |
| `references/enterprise_*.md` (3 files) | enterprise mode: six-dimension workflow, frameworks, L1–L3 checks |

## Pitfalls

- **Notes are routing aids, not evidence.** A claim that exists only in a packet or a snippet
  is unknown until the original is opened.
- **One original, one family.** Several reports quoting the same press release, dataset or
  filing are not independent corroboration; agreement across models is a reason to inspect
  the original, not proof — cross-model errors correlate.
- **First-party records are not external validation.** An authorized internal record can
  establish what the organization did; it cannot establish market standing, customer
  sentiment or regulatory compliance.
- **No invented locators.** Every URL comes from an actual retrieval; unresolved ones are
  removed or marked unknown, and precision never exceeds the original's.
- **No silent resolution of conflicts.** Present the conflict and the decision rule.
- **`scripts/` and `tests/` stay unedited** — they define the study formats and are the fork's
  upstream sync path (`UPSTREAM.md`). Patch them and every later sync breaks.
- **Load references, don't front-load them.** Reading all 18 files at P0 spends the session
  context the report itself needs.

## Verification

- `python3 "$SKILL/scripts/provider_runs.py" validate <study-dir>` — every lane state and
  artifact consistent.
- `python3 "$SKILL/scripts/research_assets.py" check <study-dir> --report <report>` then
  `register` — source/claim coverage, then the catalog entry for later discovery.
- `python3 -m pytest "$SKILL/tests" -q` — 49 tests; run after any change to this directory.
- Registry cross-check: every `[n]` in the report resolves, every listed source is used, no
  dropped source resurfaces.
- The report states its unresolved unknowns and what would falsify its main conclusion.
