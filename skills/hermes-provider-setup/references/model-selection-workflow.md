# Model selection: from a provider plan to the right config slot

Depth for the SKILL.md section *Live Provider Inventory and Quota*. Use it when the question is not "how do I configure X" but **"which model should run where on the plan I already pay for"** — a new provider or tier, a review of an existing setup, or a request to make routing smarter.

This is a **procedure**, not a price list. Model names, prices and caps are volatile instance state: they belong in a dated note in the user's knowledge base with a refresh command, never in a skill and never in memory.

## Step order

1. **List the purposes before any model.** The purpose decides the slot, and the slot decides which knob you write:

   | Purpose | Knob |
   |---|---|
   | the model the user actually talks to | `model.default` + `model.provider` |
   | work every `delegate_task` child inherits | `delegation.model` + `delegation.provider` |
   | one side task (compression, titles, vision, review, curator) | `auxiliary.<slot>` |
   | the path taken when the primary fails | `fallback_providers` |

   One model rarely wins more than one purpose: a cheap high-throughput model is usually right for subagent bulk work and wrong for the session's hard reasoning. Decide per slot.

   These four seams are also the **only** per-role routing Hermes offers: a planner/worker/utility tier split has no counterpart beyond them, because every `delegate_task` child inherits the one `delegation.*` pin (SKILL.md Pitfall 7).

2. **Read the live inventory and quota from the provider's own endpoint.** Never start from the docs page or a remembered model list — see `references/live-provider-probes.md` for key loading (the value never enters the transcript), the `/models` + `/usage` shapes, and the honest reading of unlabeled percentages. Diff live IDs against the published list in both directions and report the delta.

3. **Apply the hard filters before ranking anything.** Not tradeable, therefore not a score: privacy (zero-data-retention, prompt/completion training, extra retention windows), region availability, residency, and the plan tier the user is actually on (read it, or ask — never infer the column from the price). Drop candidates that fail a filter; do not rank them lower and do not soften the finding.

4. **Treat the caps as a budget, not a footnote.** Read the *shape* of the metering before budgeting: an allowance can be **per model** (separate buckets — on the OpenCode plans each model carries its own monthly dollar cap, of which the 5-hour window is 20 % and the week 50 %) or per account (one bucket, reported as a percentage of a rolling window). The shape decides whether routing buys room: with per-model caps, splitting roles over different models genuinely multiplies usable room, and a strong model on a narrow cap is an **escalation** model, never a volume model. Compute against the window that binds first, state which window that is, and give the high-volume role the wide-cap model.

5. **Get quality and speed data for the survivors over the same slugs.** Use a comparison source (for the `model-analysis` CLI that is the `artificial-analysis-cli` skill: fetch the catalogue once into a file, then filter locally). Match the reported axis to the purpose — coding/agentic indices for code work and agents, economics for cost-efficiency, median tok/s and TTFT when latency matters. Missing index values are **unmeasured**, not zero: say so per model instead of substituting a similarly named one. Cost efficiency is the ranking axis only where volume is: for a rarely-firing slot whose point is quality (vision, review), rank by the quality axis and let price break ties.

6. **Write the decision into the knob, one line per slot.** Each line carries the evidence (index value with its field name, price, cap, fetch time) and the trade-off accepted, so the next session can re-evaluate instead of re-deriving. A decision that exists only as a changed config value cannot be reviewed.

7. **Probe before trusting the decision.** A model can be listed and still fail on credentials, credits or billing: answer probe first, then the tool probe (see *Which Knob Decides Which Model*). Report the failure string verbatim — it names the missing piece.

8. **Store the snapshot where it ages visibly.** The plan's model list, caps and quota snapshot go into a dated knowledge-base note with a fetch-time stamp and a refresh command; the skill keeps only the procedure. Re-fetch rather than re-citing an older snapshot, and re-date the note instead of appending a second one.

## Pitfalls

- **Don't rank what you should filter.** A privacy or region failure placed in a scoring table invites a cost argument that must never win. Filter first, then rank the survivors.
- **Documented list ≠ live list ≠ what the plan actually serves.** All three drift; only the endpoint is current. An undocumented model has an unknown cap — not zero, not unlimited.
- **Never derive one tier's column from another.** Tier caps are not constant multiples of each other; read the tier the user is on.
- **The metering shape decides whether routing adds room — read the provider's limits table, not just the usage endpoint.** The OpenCode plans cap every model separately (5-hour window = 20 % of that model's monthly dollar cap, week = 50 %, month = 100 %), so two models are two buckets and splitting roles across them adds real room. The `/usage` endpoint answers with only one percentage per window: it aggregates and therefore cannot say which model's cap is close — never read that single number as "one shared bucket". Get the per-model caps before promising savings from "route the bulk to the cheap model".
- **A no-index candidate is unmeasured, not bad.** Preserve the distinction in the answer; the user may still prefer it on price or privacy grounds.
- **Latency data is a per-model measurement, not a provider property.** Mixing numbers from two fetch times makes a comparison that cannot be reproduced — quote one fetch basis, and label which source each column carries (benchmark index vs. catalogue price vs. own probe). A benchmark's TTFT is measured on the benchmark's harness and can sit an order of magnitude above the endpoint's real answer; confirm latency-critical picks with an own probe against the endpoint the slot will actually use.
- **A price is not one number when the plan has time-of-day tiers.** Peak windows can double input and output prices for the same model, so a peak-vs-off-peak comparison produces a preference that flips with the clock. Name the basis either way, and never compare across bases.
- **A re-evaluation of an existing setup is a proposal, not a rewrite.** Produce the analysis and a per-slot recommendation first, change config only after the user picks, and stay inside the declared scope — slots routed to a provider outside the plan under review are constraints, not candidates.
- **Do not put the table into the skill or into memory.** Volatile lists harden into stale claims a later session will trust; the procedure plus a dated note is the durable pair.
