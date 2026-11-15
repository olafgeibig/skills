# Closing a Case

Closing is the only operation that makes a claim about the world. An open case asserts nothing; a closed one asserts "this is settled". That is why it has a pre-flight and not just a status change.

## When to Load

- The matter is done: an authority answered, a contract was signed, a berichtigung went through
- The matter is abandoned: it will not be pursued
- The matter is superseded: another case took over

## Pre-flight — all six, or say which one you skipped and why

1. **Every promised artifact exists.** If the case said "we will write to the court", the letter is in `artifacts/` and linked. A closed case with a missing artifact is a false statement.
2. **The outcome is in `## Stand`.** What came of it, in one or two sentences: the decision received, the amount, the date. Without an outcome the case is only a pile of documents.
3. **`## Aufgaben` is empty**, or every remaining task was explicitly dropped — and dropping is a decision, so say so in `## Stand`.
4. **What the case changed is propagated.** This is the point of the whole checklist:
   - a value changed → the master data note is updated (on the user's instruction, never on your own judgement)
   - the subject's state changed → the dossier's `## Stand` mirrors it
   - it is a milestone → the project chronology gets its line
5. **The blocker is settled.** `blocked` → `closed` needs either the third party's delivery, or one of the three ways below naming why it ended without it. A case does not become `closed` because it was set aside.
6. **The children still point here.** No event, document or artifact that now belongs to another case; no child naming a case that never listed it.

## The three ways to close

Each writes a different sentence into `## Stand`. Pick one before touching `status:`.

| Kind | The sentence | Example |
|---|---|---|
| **resolved** | what the result was | "Grundbuch berichtigt am 12.11.2026; Gebühren 185 €, Kassenzeichen im Stammdatum." |
| **abandoned** | why it is not pursued, and what that leaves | "Nicht weiterverfolgt: Kosten stehen außer Verhältnis zum Streitwert. Anspruch verjährt 2029." |
| **superseded** | by what, from when | "Übergegangen in [[hausverkauf]], weil Verkauf und Berichtigung zusammen abgewickelt werden." |

`resolved` is the only kind that lets the matter drop out of the active table without a trace. `abandoned` and `superseded` stay visible, because someone will ask later why nothing happened.

## Then

1. `status: closed`. The router's active table is hand-written and does **not** update itself — check it and remove or move the row.
2. Rebuild the generated sections: `check.py --rebuild <project>`, read the diff, and write it through TurboVault once it is approved.
3. If the chronology has no line for the outcome, add one. The milestone is the outcome, not the closing.
4. Leave the folder alone. A closed case is not archived, moved or trimmed: it is the archive.

## Reopening

An authority reopens what was closed — say so in a new line under `## Stand` with the date, set `status: open`, and do not rebuild the history. The old closing sentence stays; the case now has two outcomes in sequence, which is the truth.

## What a closed case forbids

- Editing its artifacts. They are evidence of what was sent.
- Removing `## Ereignisse` rows to make it look tidy.
- Reusing the dossier's `## Stand` as the place to park its outcome: the outcome belongs to the case, the *state* it produced belongs to the dossier.

## Pitfalls

- Closing because the case is quiet. Quiet is `open`.
- Closing to get it off the task list. The tasks go when they are decided, not when the case is hidden.
- Propagating nothing. The most expensive close is the one where the value, the dossier and the chronology keep the old truth for another six months.
