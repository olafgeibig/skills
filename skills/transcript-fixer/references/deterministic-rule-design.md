# Deterministic Rule Design for Transcript Fixing

Use this reference when adding rules to `.transcript-fixer/corrections.tsv`.

## Core lesson

Dictionary rules are useful only when they are low-risk. A too-short rule can create a new error even when the target term is correct.

Bad pattern:

```text
from	to
power time service	Connected Powertrain Service
```

If the transcript contains `is connected power time service`, the result can become:

```text
is connected Connected Powertrain Service
```

Better pattern:

```text
from	to
is connected power time service	belongs to Connected Powertrain Service
```

This captures the whole mistranscribed phrase and avoids partial replacement artifacts.

## Rule selection checklist

Prefer adding a rule when:
- the wrong phrase is a non-word or stable ASR artifact
- the wrong phrase is long enough to be context-specific
- the replacement has been confirmed by the user or by configured glossaries plus transcript context
- the rule can be re-applied from the original transcript without producing awkward grammar

Avoid or defer a rule when:
- the wrong phrase is a common word
- the wrong phrase is short or appears in many unrelated contexts
- replacing it depends on surrounding sentence meaning
- the rule only fixes one occurrence by accident but would corrupt another occurrence

## Test loop after adding rules

1. Re-run deterministic `apply` from the original transcript, not from an already corrected output.
2. Read or search the corrected output for both:
   - stale source variants that should be gone
   - replacement artifacts such as duplicated words or broken grammar
3. If an artifact appears, replace the short rule with a longer contextual rule.
4. Only then keep the rule in `.transcript-fixer/corrections.tsv`.

## Good project-local examples

```text
from	to	domain	notes
Bit-Z Insights	BitC-Insights	project	stable project ASR variant
S-Bomb	SBOM	bosch	stable acronym ASR variant
is connected power time service	belongs to Connected Powertrain Service	project	full phrase avoids duplicate Connected
list of bins	list of VINs	project	context-bound VIN list phrase
```
