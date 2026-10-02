# Source Verification

## Primary-source hierarchy on conflict
- On conflict, the order is: repo/`README`/`SCHEMA` → vendor docs → trade press → social announcement.
- The primary source wins; state the deviation in the note ("`README` calls X untested; the post calls X supported — `README` governs").
- Silently smoothing a conflict over is data loss.

## Claim-heavy sources
- Extract every claim, figure and stated condition from the source BEFORE researching; searching first loses half the list.
- Find the primary source per figure — regulator, big-4 tax summary, law-firm alert, SEC filing — never the marketing pages repeating the same number.
- Establish the currently-effective state (effective dates, transitional rules) and recheck the source's own arithmetic; name its assumptions — the classic error is mixing two vintages in one calculation.
- On cross-border topics research the home side too — residence, place of management, CFC and exit-tax rules, treaty — not only the destination side the source argues about.

## Derived figures: no fabrication

- Every derived figure or table cell needs a source — the underlying note, a linked reference, or a citable document. Without one, do not present it as fact; phrase the gap visibly ("source missing / to verify") instead of estimating.
- Never decompose a documented sum into invented components (a linear limit into per-axis dimensions), and never restate a user-supplied value in your own interpretation — the user's number goes into the cell 1:1.
- Estimates are allowed only in an explicitly labelled orientation block ("estimate — verify before use"), never in a definitive requirement list or data table.

## Two mandatory note sections
- `Quoted figures — not independently verified`: everything carried from the source unreviewed.
- `Source check`: separates right from incomplete/misleading claims, claim by claim.
- These two sections are the difference between a note and an advertorial; never omit them for a claim-heavy source.

## Named examples: stepped verdicts
- Check every named user or customer against a filing, the commercial register or office listings — never confirm in bulk.
- One tier per name: `verified in filings` / `presence verified, use not disclosed` / `widely reported, not verified here`; a blanket confirmation is never acceptable.

## Conflict of interest
- Match the poster's handle against the linked company: imprint, founder name, registry.
- Own firm → label it in the advisory section as the author's marketing.
- Put 1–2 independent starting points next to it (regulator, big-4 summary, local firm); keep third-party references from the thread separate.

## Verification language
- Write `verified` only when the primary source was actually read in this session; otherwise `not verified here` / `widely reported`.
- Put the tier in the sentence itself, not in a later source list — wording a claim as verified and having to prove it afterwards is the failure mode.

## Large primary documents
- Never search a filing, statute or regulator PDF through a paginated extractor: it returns head+tail only, so a passage in the middle is missing and zero hits look like "not in there".
- Fetch the raw document, strip tags, regex the passage, quote it verbatim.
- Cite it with URL in the sources section; details only the primary document carries (transitional dates, applied rates) become their own sentence in the note.

## Thread fact-checks
- If the thread carries a foreign fact-check, give it its own section: permalink, handle, recognisable as a quote, verdict table.
- Its ⚠️ marks are a to-do list, not a result — a fact-check tests against the sources it knows.
- Re-verify every ⚠️ against the primary source and report the outcome in the note ("unconfirmed in the fact-check; evidenced here, and stronger than claimed").

## One-liner installers (`curl … | bash`)
- Document where the short link points, which repo the bootstrap script comes from and whether it can be read before execution.
- State the security caveat explicitly — foreign code runs directly; the execution decision stays with the user.
- Name the weights licence separately: it can differ from the code licence (non-commercial weights under a permissive code licence).

## Cost/decision notes
- Every figure with an as-of date and a source; prices change weekly.
- Do not force one currency: compute break-even in hours and state the conversion assumption; mark power price, utilisation and efficiency as assumptions, not facts.
- Options as blocks (requirement → option → price → caveat → when it makes sense) plus exactly ONE recommendation for this user; keep maturity gaps and caveats in.

## Availability claims: banned, removed, mirrored, rescued
- Existence only via HTTP 200 on the API endpoint; `401` is NOT proof of existence — calibrate once with a made-up repo name.
- Size only by summing the recursive tree API, never from a card, badge or third-party listing (they show the root state at best).
- Torrent/swarm claims: fetch the raw mirror page and grep for `magnet:?xt=` plus the page's own status strings; zero magnets = metadata only.
- A "ban" narrative is a hypothesis: check whether a renamed sibling repo appeared days later; present both sides of the debate and the urgency question (is the original still served?).

## Model cards (HuggingFace)
- Facts from the API, not the rendered page; read the card text raw.
- The API endpoint is `https://huggingface.co/api/models/<owner>/<repo>`; it returns `cardData` (`base_model`, `license`, `quantized_by`, `datasets`) plus `tags`, `siblings` (the file list), `downloads`, `likes`, `createdAt`, `lastModified`; the card text is at `/raw/main/README.md`.
- Build the lineage chain from `base_model`, every step with its own source; the quant table comes from the card PLUS the file list.
- Filename trap: quant files often carry the BASE model's name — filtering the file list by the repo name finds nothing.
- Name the licence kind: `llama3.1`, `gemma`, `cc-by-nc` are community licences, not OSI.
- "abliterated"/"uncensored" means the safeguards were REMOVED, not loosened; a fine-tune's context length can sit far below the base model's — both belong in the prose, not in a field list.
