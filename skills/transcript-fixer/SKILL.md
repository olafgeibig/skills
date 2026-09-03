---
name: transcript-fixer
description: Use this skill when fixing speech-to-text transcripts, meeting transcripts, interview notes, or ASR output with misheard names, product terms, acronyms, or domain vocabulary. Uses project-local config, glossary files, deterministic corrections, and native agent review. No internal AI API calls; optional scripts only apply configured replacements and extract glossary terms.
---

# Transcript Fixer

Fix ASR/STT transcripts with project-specific vocabulary while keeping the source of truth in the current project.

This is the simplified v2 workflow:
- Project-local configuration in `.transcript-fixer/config.yaml`
- Project-local correction rules in TSV files
- Glossaries configured per project
- Deterministic first pass via helper script
- Native Hermes/agent review for context-dependent fixes
- Explicit uncertainty list instead of guessing
- No hidden global SQLite database
- No internal AI API calls

## Default Quality Bar

The agent must produce a corrected transcript backed by real file edits and verification. Do not stop after a plan.

Hard rules:
1. Read the complete transcript before final correction. For long files, read chunks, but finish the full file before applying context-dependent fixes.
2. Read configured glossaries before proposing domain corrections.
3. Apply only high-confidence fixes directly.
4. Present uncertain terms to the user instead of guessing.
5. After user confirmation, patch the transcript and verify by searching for stale variants.
6. Keep original speaker structure unless the user asks for grammar cleanup or meeting minutes.
7. Never use internal API calls from this skill. The AI review is performed by the current Hermes model in the chat.

## Project Layout

Use this project-local directory:

```text
.transcript-fixer/
  config.yaml
  corrections.tsv
  outputs/
```

`corrections.tsv` is the source of truth. SQLite is not used.

Recommended TSV columns:

```text
from	to	domain	notes
Bit-Z Insights	BitC-Insights	drivalia	confirmed project term
S-Bomb	SBOM	bosch	common ASR error
```

## Design Rationale

The user frequently fixes project-specific transcripts and explicitly prefers this skill to avoid hidden global state and hidden secondary AI clients. Keep the workflow project-local and transparent: configured glossaries + TSV corrections are deterministic support; the current Hermes model performs the contextual review and asks about uncertain terms.

## Config Format

Create `.transcript-fixer/config.yaml` in the project root:

```yaml
project: my-project

glossaries:
  - path: csl/context/drivalia-glossary.md
    domain: drivalia
    format: markdown-bold-terms
  - path: /absolute/path/to/bosch-security-glossary.md
    domain: bosch
    format: markdown-bold-terms

corrections:
  - path: .transcript-fixer/corrections.tsv
    domain: project

output:
  suffix: _corrected
  diff: true
  keep_original: true

ai:
  mode: native-agent
```

`format: markdown-bold-terms` supports glossary entries such as:
- `**TERM**` followed by a description
- `- **TERM**` followed by a description
- terms with parenthesized abbreviations such as `Battery in the Cloud (BitC)`

## Helper Script

Use `scripts/transcript_fix.py` from this skill for deterministic support.

Typical commands:

```bash
# Create project-local config and TSV skeleton
python /path/to/skill/scripts/transcript_fix.py init

# List configured glossaries and corrections
python /path/to/skill/scripts/transcript_fix.py list

# Add a confirmed correction
python /path/to/skill/scripts/transcript_fix.py add "wrong phrase" "Correct Phrase" --domain drivalia --notes "confirmed by user"

# Apply deterministic corrections only
python /path/to/skill/scripts/transcript_fix.py apply notes/transcripts/input.txt

# Extract glossary terms for agent review
python /path/to/skill/scripts/transcript_fix.py terms
```

The script discovers `.transcript-fixer/config.yaml` by walking upward from the current directory.

## Workflow

### 1. Discover config

Treat `.transcript-fixer/config.yaml` in the current project root as the canonical configuration location.
If it exists, use it. Do not stop at a failed file search if the path is known or directly readable — a direct read of `.transcript-fixer/config.yaml` overrides an earlier empty search result.
If the file does not exist, create one only when the user asks or when working in a project where this is clearly desired.

Mandatory rule once the config has been found:
- read the config
- read every configured glossary
- read every configured corrections TSV
- only then start the correction pass

When recurring ASR variants are confirmed during review, add them back to the project-local `.transcript-fixer/corrections.tsv` so later runs catch them deterministically.

Use the helper script or normal file tools to inspect:
- configured glossary paths
- correction TSV files
- transcript path

Pitfall:
- Do not silently fall back into a manual-only correction pass after discovering the config.
- If the config names glossaries, the glossary pass is mandatory, not optional.

### 2. Read evidence

Always read:
- the transcript
- each configured glossary
- configured correction TSV files

If no `.transcript-fixer/config.yaml` exists, say that plainly and do not pretend glossary-based checking is active.
In that case, run a manual canonical-terms pass using immediately available project evidence before correcting:
- transcript filename
- nearby transcript filenames
- curated project context such as `csl/context/*.md`
- obvious project/product names already established in the workspace

For very large transcripts, read in chunks and keep a running list of possible ASR errors. Do not apply context-dependent corrections until the full transcript has been read.

### 2a. Canonical term cross-check (mandatory)

Even without configured glossaries, do a targeted canonical-name audit for:
- project names
- product names
- customer/company names
- people/team names when project-local evidence exists
- stable acronyms and environment names

Minimum check:
- compare the transcript content against the filename and other local project context
- search for near-variants of canonical names, especially plausible-looking ASR variants that are not obvious non-words

Important pitfall:
- do not restrict direct fixes only to bizarre or visibly broken tokens such as `Bitsy` or `Seattle bank`
- plausible-looking variants such as `Trivalia` can still be high-confidence ASR errors when the filename and project context clearly establish `Drivalia` as canonical

### 2b. Verification patterns

After the first correction pass, verify not only known wrong forms but also canonical-name drift:
- search for stale mishearings you fixed
- explicitly search for canonical-vs-variant pairs such as `Drivalia|Trivalia`
- when the transcript filename contains a project/customer/product name, include that name in the verification query

### 3. Run deterministic first pass

If corrections TSV exists, run:

```bash
python <skill>/scripts/transcript_fix.py apply <transcript>
```

This creates `<stem>_corrected<suffix>` unless overridden by config.

If no correction rules exist, skip this step and correct from the original file.

### 4. Native agent correction

Use the current Hermes model to identify ASR errors, with the glossaries as context.

Classify candidates:
- High confidence: non-words, obvious acronym/product/team/name variants, glossary matches with strong context
- Medium confidence: plausible but context-dependent terms
- Unknown: unclear phrases, possible proper nouns, role names, ticket names, filenames, or platform terms

Apply high-confidence fixes directly with file patch tools. Present medium/unknown items to the user.

### 5. User review loop

For uncertain items, provide compact context and ask for intended wording.

After the user answers:
- patch the corrected transcript
- if the correction is stable and low-risk, add it to `.transcript-fixer/corrections.tsv`
- do not add rules for short/common words unless context makes false positives impossible

### 6. Verification

Before final response:
- search the corrected transcript for known stale variants
- read the changed sections or generate a diff
- report the corrected file path and unresolved terms, if any

## What to Store as Corrections

Good TSV rules:
- unique non-words -> canonical term
- stable ASR variants of project names
- stable ASR variants of people/team names
- acronym misrecognitions with low false-positive risk
- longer context phrases when a short fragment would create awkward grammar or duplicated words
- canonical product/customer spellings that already appear in configured glossaries, such as project names, product names, and stakeholder names

High-value deterministic follow-up rule:
- when a glossary establishes a single canonical project/customer/product spelling and the transcript contains a close phonetic/visual variant, add that confirmed variant to `corrections.tsv` after the user confirms it. Do not rely on re-discovering the same variant manually in future transcripts.

Avoid global/context-free rules for:
- common words
- one-letter or two-letter tokens
- words that are valid in other contexts
- ambiguous proper names not confirmed by the user
- short fragments that only work inside one larger sentence

When in doubt, leave it out and rely on native review.

See `./references/deterministic-rule-design.md` for the rule-design checklist and the "short rule caused duplicate term" pitfall.

## Optional OpenAI-Compatible Batch Mode

Not part of the default workflow.

If batch AI is added later, it must be separate from this default flow and use only explicit OpenAI-compatible configuration:
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

Do not add Anthropic/GLM-specific hidden clients or shell-profile API-key discovery to the default workflow.

## Script behavior

If the companion script is used, it should first resolve `.transcript-fixer/config.yaml` in the current working directory as the canonical path.
An upward directory walk is acceptable only as a compatibility fallback for nested working directories, not as the primary interpretation of where project config belongs.

## Legacy Skill

The old implementation was renamed to `transcript-fixer-old` and kept only for reference. Do not use it by default.

See `./references/legacy-methodology-mapping.md` for the mapping from the old skill's useful method to the simplified v2 workflow. Use that reference when reviewing whether a future change preserves transcript-fixing quality.
