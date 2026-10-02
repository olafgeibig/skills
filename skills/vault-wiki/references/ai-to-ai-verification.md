# AI-to-AI Verification

**→ Trigger:** The user hands over content from a discussion with another AI ("GPT said", "Claude explained") and asks to bring it into the wiki. Verify claim by claim — never adopt it unseen, never blanket-reject it.

**Failure modes without this rule:** adopt-fail (false claims enter the wiki as if verified), reject-fail (verifiable facts discarded without ever running the check), confabulation-fail ("reviewed and approved" without checking).

## Per-Claim Verification

No blanket "basically correct" / "not correct". Table: `# | Claim | Status | Evidence/check`. Status values:

- ✅ **CORRECT** — backed by third-party evidence (official source, regulation, product documentation, etc.)
- ⚠️ **PARTIAL / OUTDATED** — core claim correct, but the detail is stale
- ❌ **FALSE** — contradicts a known fact, official documentation, geography, etc.

## Resulting Note Structure

- **Verified** — the ✅ claims, each with its source
- **Discarded / Corrected** — the ❌ claims with the reason they are wrong (often "the AI discussion confused X with Y")
- **Verification obligations** — the ⚠️ claims the user must still verify before acting

## Frontmatter Flag

`verification: partial|complete|disputed` — makes the status visible in the outline (a note-level convention; add it to the domain `SCHEMA.md`'s quality signals when the wiki tracks verification states).
- `complete` only when every claim has third-party evidence and no open verification items remain — not "most of them"
- `partial` — mix of verified claims and open obligations (the common case)
- `disputed` — claims contradict each other or cannot be verified

## Inbox Handling (keep the source attribute)

1. Do NOT delete the inbox note — the wiki note keeps it as its source attribute (`sources: ["[[inbox/<original>]]"]`); keep it for traceability.
2. Tag it `inbox/processed` (plus a thematic tag) so it is not processed again.
3. Optional top block: "Processed in [[<wiki-note>]] on <date>. Status: N ✅ / N ⚠️ / N ❌."

## Detection Heuristic

Apply this rule when the prompt contains "another AI" / "GPT said" / "Claude said" / "an AI explained" / "from a discussion", when it asks to "verify" a "note/wiki/zettel", or when a pasted/inbox note arrives with more than five connected factual claims.

## Worked Example (neutral)

An inbox note carried two dozen claims about airport transit from another AI. Checking each claim individually split them across all three statuses — correct, outdated, false. Result: a three-section note with `verification: partial`; inbox note kept as source and tagged `inbox/processed`.
