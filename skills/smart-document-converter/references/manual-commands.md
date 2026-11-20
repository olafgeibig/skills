# Manual Commands & Decision Logic

The executable source of truth is `scripts/smart_convert.py`. This file
explains the decisions it makes and gives the manual commands as a
fallback — e.g. after a docling upgrade changes flags, or to run a step
the script does not expose. Do not treat this as a second rulebook: if
the script and this file disagree, the script wins and this file is stale.

## What the script decides, and on what evidence

Two questions, answered in this order from **sampled** pages only.

### 1. Text-layer quality → picks the OCR mode

Probe before converting:

```bash
pdfinfo input.pdf | grep Pages          # page count, instant
pdfimages -list input.pdf               # image inventory (metadata only)
pdfinfo -f 4 -l 4 input.pdf             # that page's size
pdftotext -layout -f 4 -l 4 input.pdf -  # that page's text
```

The script samples page 1, page 2, the middle page and the last page,
plus the first, middle and last page that carry images — at most seven
pages. A four-page PDF therefore includes page 4.

- **No text at all + a page-covering image** → scan without a layer → base
  command; Docling OCR fires automatically on the bitmap.
- **Text layer with red flags** → report the evidence in the sampled
  pages. Only `replacement-character` (U+FFFD), `case-salad` (at least two
  `WEERTEwÖE`-shaped tokens) and `amount-ampersand` (a decimal amount
  followed by `&`) count toward automatic `--ocr-mode full_page`. At
  least two of those categories plus a page-covering image on a
  **single-page** PDF are required; otherwise the mode stays unchanged.
- **`section-sign-mimic`** flags `8`, `$` or `&$` in a citation-shaped
  context, including paragraph suffixes or pages that also contain
  correctly rendered `§`. It never counts toward automatic re-OCR.
- **Clean-looking text, no full-page image** → digital → base command.

What the probe deliberately does **not** claim:

- A suspicious glyph proves nothing on its own. `£` in a GBP invoice and
  Turkish letters (`ı İ Ş ş Ğ ğ`) are legitimate and raise no flag.
  Private-use glyphs are a cleanup hint (`--strip-pua`), never evidence
  that the text layer is broken.
- `925€` versus `9,25 €` cannot be decided from the text alone; that needs
  the page image. No regex in the script pretends otherwise.
- Sampled pages are samples. The report says `scope: "sampled"`, and
  nothing in it implies the unsampled pages were checked.
- Image flags are never aggregated across pages to discard a whole text
  layer.

### 2. Document type → picks the verification

- **Structured text** (directives, manuals, documentation): use
  `--profile structured`. Missing headings on a PDF with at least three
  converted pages, and heading level jumps, become warnings; the sample
  gets one bounded `pypdfium2` comparison.
- **Everything else** (letters, invoices, forms): stay on `--profile
  general`. Absent headings are not a defect and are not reported as one.

`--heading-hierarchy` stays on in every case: essential for structured
text, harmless elsewhere.

Verification is mechanical: empty or placeholder-only output fails, fewer
than ten words warns, private-use glyphs warn, heading counts and jumps
are measured. None of it says the text is *correct*.

## Large documents: sample first

1. `pdfinfo input.pdf | grep Pages` — page count, instant.
2. Up to 30 pages: convert directly; the sample overhead is not worth it.
3. Above that: base command `+ --page-range 1-10` (1-based; honored by the
   PDF, XLSX and PPTX backends). Verify the sample exactly as a full
   document.
4. Sample unusable → stop. The script does not silently launch the full
   conversion, because that would pay the cost it was avoiding.
5. Sample usable → full run without `--page-range`.

Why: docling's cost is a fixed model load plus per-page work. A 10-page
sample is cheap regardless of document length; a wrong-mode 300-page run
costs minutes and must be repeated. Measured once: 5-page sample of a
14-page PDF = 9 s conversion vs 13.5 s full.

`--sample-only` publishes the sample and stops. Its report says
`status: sample` and `output: null`; an aborted sample is `status: error`
with exit 1, never a converted result with exit 2.

## Base command

```bash
HF_HUB_OFFLINE=1 docling convert \
  --device mps \
  --heading-hierarchy \
  --ocr-engine ocrmac \
  --ocr-lang de-DE,en-US \
  --image-export-mode placeholder \
  --to md \
  --fail-on partial \
  --output-file out.md input.pdf
```

- `--ocr-lang`: adjust to the corpus (e.g. add `pl-PL`) or use `auto`.
- `--tables`, `--table-mode accurate`, `--pipeline standard` are
  defaults — do not pass them.
- DOCX and HTML run through the same command (format auto-detected).
- Run it from an environment without a foreign `PYTHONPATH`/`PYTHONHOME`;
  see `required-software.md`.

## Knob 1 — re-OCR a page: `--ocr-mode full_page`

Add it when the probe found a scan whose text layer looks wrong. It
discards the native layer and re-OCRs the page; on such files it beats the
native layer on fidelity (amounts, identifiers, dates), but it is a
heuristic gamble — never use it to force consistency across a whole
corpus.

- `--replace-broken-text-layer` does NOT help here: it only detects
  unmapped glyphs, not bad OCR text, and stays silent.
- Full-page OCR can drop narrow table columns (e.g. position numbers) —
  verify the result against the page image afterwards.

## Knob 2 — wrong heading structure: backend retry

Backend choice is document-dependent, not universal:

- Default `docling_parse`: keeps identifiers intact (`CD-02900`) and
  carries font weight/italic info for the style fallback.
- `--pdf-backend pypdfium2`: can preserve unnumbered sub-headings that
  docling_parse demotes to list items, but inserts spaces around hyphens
  (`CD - 02900`).

When unnumbered sub-headings are missing or sit at the wrong level,
re-run with `--pdf-backend pypdfium2` and compare — preferably the chunk
heading paths, not just the Markdown: a demoted heading loses its parent
section in RAG metadata.

The script does this once, on the sample, only under `--profile
structured`, and only without an explicit `--pdf-backend`. It compares
`(number of issues, missing_headings, level_jumps)` in that order; a tie
keeps the default backend. Restoring missing headings can win, but merely
adding more headings cannot. A failed alternate backend leaves the usable
sample selected and records both diagnostic tails in `sample_retry_error`.

## RAG chunk export

Markdown + chunks in one pass:

```bash
HF_HUB_OFFLINE=1 docling convert \
  --device mps \
  --heading-hierarchy \
  --ocr-engine ocrmac \
  --ocr-lang de-DE,en-US \
  --image-export-mode placeholder \
  --to md --to chunks \
  --chunks-type hybrid \
  --chunks-max-tokens 512 \
  --fail-on partial \
  --output outdir input.pdf
```

Writes `outdir/input.md` + `outdir/input.chunks.jsonl`. Each chunk carries
its heading path as a text prefix plus `headings` / `page_numbers` /
`num_tokens` metadata. Set `--chunks-tokenizer` to the downstream
embedding model. The first hybrid-chunker run needs network for the
tokenizer download — run it once without `HF_HUB_OFFLINE=1`, then offline
works.

The script requires a **new** destination directory (an existing one,
even empty, fails), validates the staged JSONL line by line, then
publishes chunks first and Markdown last. That pair is not a filesystem
transaction: a consumer must wait for the success report and must not
infer readiness from the directory's existence. `--strip-pua` is refused
with `--chunks` in this release rather than producing two inconsistent
artifacts.

## Flag-level pitfalls (already encoded in the script)

Listed here only for the manual fallback:

- `--heading-hierarchy` is OFF by default; without it every heading
  flattens to `##`. Always pass it.
- Never `--no-ocr` on mixed corpora: scanned pages yield empty output
  (exit 1 with `--fail-on partial`). OCR only fires on bitmap regions, so
  a digital page pays no OCR time — the model load is paid either way.
- `--output-file` works only with a single output format; multi-format
  needs `--output <dir>`.
- ocrmac first run pays a one-time framework warmup; later runs
  ~3 s/page. Do not judge OCR speed by the first run.
- A wrong-looking heading tree is a backend question, not a flag question:
  A/B the two backends before adding any other options.
