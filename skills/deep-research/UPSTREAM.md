# Upstream provenance

Fork of `daymade/claude-code-skills` → `deep-research`, adopted 2026-10-14.
Upstream is MIT licensed; its notice is kept as `LICENSE-daymade`.

- Upstream repo: https://github.com/daymade/claude-code-skills
- Base commit (last synced): `8f0486f980b14242d62068759c2f10d66864172b`
- Base state date: 2026-10-14

## Reference checkout (read-only, never mounted)

The upstream working copy lives outside this repository:

    ~/work/agent-skills/adopted/claude-code-skills    # blobless sparse checkout, full history

It must never be added to `skills.external_dirs`: this directory holds the only
Hermes-visible copy of the skill. The reference itself is never edited; a dirty
`git status` in it means the diff below cannot be trusted.

## Sync procedure

```bash
R=~/work/agent-skills/adopted/claude-code-skills
git -C "$R" status --short          # must be empty
git -C "$R" pull --ff-only          # new upstream state, files materialised
git -C "$R" log  --oneline 8f0486f980b14242d62068759c2f10d66864172b..HEAD -- deep-research/   # empty = nothing to do
git -C "$R" diff --stat 8f0486f980b14242d62068759c2f10d66864172b..HEAD -- deep-research/      # the report
```

Integrate per file class, then replace the base commit above with the new
`git -C "$R" rev-parse HEAD`.

Never `git pull` or `git merge` the upstream repository into this one; upstream is
reached only through the separate reference checkout.

## File classes

- **verbatim** — unchanged from upstream. An upstream change may be copied over
  directly, followed by `python3 <skill>/tests` (see Verification).
- **rewritten** — Hermes execution layer. Read the upstream diff and port only what
  is not Claude/provider specific: new rules, new gates, new anti-hallucination
  patterns. Provider-UI receipts, slash-command handoffs and metered-spend rules do
  not belong here.

### verbatim at the base commit

| File | sha256 |
| --- | --- |
| `references/completeness_review_checklist.md` | `657d9ae9857f3e60f847b6e9f5a8ca12025b4e9844aa75f439e68a45299d6dea` |
| `references/enterprise_analysis_frameworks.md` | `1f6887de9c180c4739a50d1d74beeb306fb44cadd69639177a09ae43c5161d01` |
| `references/enterprise_quality_checklist.md` | `e21cf841e85b62566241dc3d7aabbcdd0b1df1756c2f5ef70d056d7482b1fc61` |
| `references/enterprise_research_methodology.md` | `bf701c193cd393e3ed4c5e8ac070de0203d05102751ca6b01d76acd02e2dbbe4` |
| `references/formatting_rules.md` | `0130e9f20c965662bfd60e223eb39575a998486cc4218a87959ae33638f3f99d` |
| `references/quality_gates.md` | `bb95a3ad1f33a892f6e651b1138c86f17f89f19c8f2c12fbc8e049887c4c21d6` |
| `references/report_template_v6.md` | `b7f289f4f28e1d8aa9656764b7c29cf318088ba44998ebd805441711adbfd9dd` |
| `references/research-asset-contract.md` | `cce25bce234138df22f8288ec5ef76a6042eedeab5f133245912b5b8ef557457` |
| `references/research_notes_format.md` | `ebef73d54b5d15bdd234f485d8748383848f968aec4efae8af599cd69fa31d58` |
| `references/research_plan_checklist.md` | `e18114d8376502dee099cfb57273647e5115cafeb88474240b2a7cf16dc560be` |
| `references/research_report_template.md` | `50462ed58f958203a4cec89500d885b82b117dc15923e1c50b5faf07ec79e66b` |
| `references/source_accessibility_policy.md` | `6bd200c078a5df904d214f092680fc9e9ed37023c55678f679ea49401baa16c3` |
| `references/source_quality_rubric.md` | `366cfc639a6423d10fc0692e374ce40e2acd4612ac5561b0184408f676db884d` |
| `scripts/provider_runs.py` | `ab686b0f3b1c8c1a12ea4215bed2aa7138d704f466955a2fc5770e70a9043042` |
| `scripts/research_assets.py` | `3133ca1d341f87e980e8006ae11548d45ce7957c3ed02f93689c25136ada469d` |
| `tests/test_provider_runs.py` | `e1f8dd92939f221f997d67562d5e7ecadb121eda304568b2e44cabc02cae4667` |
| `tests/test_research_assets.py` | `1e295fbc55a828565d6cdb3a86eef4f98b0289bd9b1a91333f72441bdc451c00` |

### rewritten (never copy over)

- `SKILL.md` — the Hermes execution layer (tool mapping, gate, reference routing).

### pending rewrite — still upstream text today

These five carry the Claude- and provider-UI-bound execution text and are scheduled for
the Hermes translation (`delegate_task`, `browser_exec`, direct-source lanes). Until that
lands, treat them exactly like the rewritten class: **never copy an upstream version over
them** — read the upstream diff and port only what is not product specific.

- `references/counter_review_team_guide.md`
- `references/parallel-provider-ops.md`
- `references/provider-run-contract.md`
- `references/report-file-collection.md`
- `references/subagent_prompt.md`

## Why `scripts/` and `tests/` are never edited

`scripts/research_assets.py` and `scripts/provider_runs.py` define the study file
formats (`study.json`, `run-events.jsonl`, `source-ledger.jsonl`, `claims.jsonl`)
and `tests/` protects them. Both stay byte-identical to upstream so every sync can
take upstream fixes over as a whole file. Patching them ends the sync path.
