# Legacy Methodology Mapping

This reference captures why the simplified v2 transcript-fixer replaces the old implementation without losing the useful method.

## Old method worth preserving

The legacy skill used this effective pattern:

1. Apply deterministic dictionary corrections first.
2. Read the full transcript or all Stage 1 outputs before making contextual fixes.
3. Classify possible ASR errors by confidence.
4. Apply high-confidence fixes directly.
5. Ask the user about uncertain proper nouns, product names, filenames, roles, or platform terms.
6. Save confirmed stable patterns for future transcripts.
7. Verify with diff/search before claiming completion.

## What changed in v2

The v2 skill keeps the method but removes the wrong abstractions:

- Replaces global `~/.transcript-fixer/corrections.db` with project-local `.transcript-fixer/corrections.tsv`.
- Replaces hidden internal GLM/Anthropic API calls with native Hermes model review in the current session.
- Replaces fixed glossary importer assumptions with configured project glossaries in `.transcript-fixer/config.yaml`.
- Keeps deterministic helpers small: `init`, `list`, `terms`, `add`, and `apply`.

## Quality guardrail

Do not treat v2 as dictionary-only. The quality comes from the combination:

- deterministic first pass from TSV corrections,
- complete transcript reading,
- glossary-aware native model review,
- explicit user review of uncertain terms,
- final patch and verification.

If an agent skips the native review and only runs `apply`, quality will be lower than the legacy workflow.

## When to store a correction

Store only stable, low-risk, project-specific ASR variants. Good examples:

- `Bit-Z Insights` -> `BitC-Insights`
- `S-Bomb` -> `SBOM`
- `power time service` -> `Connected Powertrain Service`

Avoid storing short/common/contextual words unless the replacement is impossible to misapply.
