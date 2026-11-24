---
name: smart-document-converter
description: "Use when converting PDF/DOCX/HTML to Markdown (docling)."
version: "1.1.1"
author: Olaf Geibig
license: MIT
compatibility: "macOS (ocrmac/Apple Vision OCR); requires docling CLI and poppler."
metadata:
  source: https://github.com/olafgeibig/skills
  hermes:
    category: personal
    tags:
      - pdf
      - docling
      - markdown
      - conversion
      - rag
      - ocr
    related_skills:
      - pdf-document-processing
---

# Smart Document Converter

Convert PDF, DOCX and HTML to Markdown with docling and get either
validated output with an actionable report, or an explicit failure. The
decision logic — probe, OCR-mode choice, sampling, one bounded backend
retry, mechanical verification, staged publication — lives in
`scripts/smart_convert.py`. This file is the routing layer: when to use
it, how to read the result, and the judgement the script cannot automate.

## When to Use

- "Convert this PDF / Word / HTML file to Markdown"
- Preparing documents for RAG ingestion (chunks with heading paths)
- Batch conversion where heading nesting must survive

For PDF editing, plain text extraction, or vision-based reading of small
batches / non-Latin scripts, use `pdf-document-processing` instead.

## Run the script

```bash
python3 <skill_dir>/scripts/smart_convert.py input.pdf --out out.md
```

It probes each sampled page (text layer, image inventory, that page's
size), classifies from that evidence, picks the OCR mode, samples pages
1-10 first when the document exceeds 30 pages, converts into a staging
directory on the destination filesystem, validates the staged bytes, and
publishes only afterwards.

Exit code and `status` travel together; orchestration reads `status`.

| status | exit | meaning |
|---|---|---|
| `ok` | 0 | requested artifact published, no warnings |
| `warning` | 2 | requested artifact published, with warnings |
| `planned` | 0 / 2 | `--probe-only`: decision and command, nothing written |
| `sample` | 0 / 2 | `--sample-only`: durable sample, no full conversion |
| `help` | 0 | `--json --help`: usage text in the `help` field; nothing written |
| `error` | 1 | no completed output; `error` carries stage, code, diagnostics |

Exit 2 always means a usable artifact (or an explicitly requested
plan/sample) — never an aborted conversion. Every report, including a
successful one, states `semantic_validation: "not_performed"`, and
`--json` emits exactly one object on stdout with `schema_version: 1` on
every path, including usage errors and help. Progress and plain-text
errors go to stderr. Staging cleanup failures after publication are warnings;
the report still lists the published artifacts.

Flags:

- `--profile general|structured` — verification strictness (default
  `general`: no heading expectation at all; `structured`: missing
  headings and level jumps become warnings)
- `--probe-only` — decision + proposed command, no conversion
- `--sample-only` / `--force-full` / `--sample-threshold N` /
  `--sample-size N` — sampling
- `--chunks --out <dir>` — RAG export (md + chunks.jsonl) into a **new**
  directory
- `--strip-pua` — remove symbol-font glyphs, then re-verify the result
- `--ocr-mode` / `--pdf-backend` — override the automatic decisions
- `--lang de-DE,en-US` / `--device mps|cpu` — OCR languages and
  accelerator; Intel Macs need `--device cpu`
- `--keep-sample` — publish the sample beside the final Markdown
- `--overwrite` — replace an existing single Markdown output only
- `--timeout` — seconds per Docling invocation (default 900)
- `--json` / `--online` — machine-readable report; allow model downloads

Rejected combinations (usage error, nothing converted): `--strip-pua`
with `--chunks`, `--overwrite` with `--chunks` or `--keep-sample`, and
`--sample-only` with `--force-full`/`--probe-only`/`--chunks`/
`--keep-sample` or a non-PDF input.

Existing outputs are not replaced without `--overwrite`. A symlink,
the source itself, or an existing chunk directory is always rejected.
`--keep-sample` requires a final Markdown filename distinct from the
sample filename. Chunk bundles are validated and then published chunks
first, Markdown last. This is not a filesystem transaction: wait for the
success report, not for the directory to appear.

Manual commands and the reasoning behind each decision:
`references/manual-commands.md` (fallback if the script breaks).

Package tests are stdlib `unittest` only, with no docling, GPU or network:
`python3 -m unittest discover -s <skill_dir>/tests` — run them after any
change to the script.

## Requirements

Check before the first conversion on a machine; never assume another
machine's setup carries over:

1. **docling** — converter CLI (uv tool).
2. **ocrmac** — Apple Vision OCR, installed INTO docling's venv (macOS,
   offline, no HF models).
3. **poppler** (`pdfinfo`, `pdftotext`, `pdfimages`) — probe + page count.
4. Cached docling models for any PDF parsing, plus a cached HF tokenizer
   for hybrid chunking.

Install/verify commands and the child-environment note:
`references/required-software.md`.

## Verification — the part the script cannot do

The script's exit 0 means "mechanically clean", NOT "content correct".
It samples pages; it never certifies meaning. Before handing over output,
still check semantically:

- **Structured text** (directives, manuals): heading tree matches the
  source; unnumbered sub-headings sit under their parent. The script
  catches level jumps in the `structured` profile but NOT a heading
  silently demoted to a list item (seen in a directive document with
  unnumbered sub-headings) — compare against
  bookmarks/numbering, or A/B backends.
- **RAG target**: chunk `headings` arrays carry the expected parent chain.
- **Invoices / forms**: amounts, identifiers (VIN, invoice no., HSN/TSN),
  dates checked against the page image — a native layer can be silently
  wrong, not empty. Full-page OCR can drop narrow table columns.

For batches: confirm the directory scope and convert one file for
approval before the rest (rule home: `pdf-document-processing`).

## Pitfalls the script does not cover

- H1 offset is by design: PDF/DOCX top-level sections export as `##`
  (H1 reserved for the title), HTML `h1` exports as `#`. Relative nesting
  is correct either way — do not "fix" it.
- DOCX headings come from real Word heading styles; HTML→DOCX via
  textutil produces bold text only and loses the hierarchy.
- **Form scans** (Prüfberichte, invoices, vouchers) export with values
  detached from their labels: the layout model emits each field box as
  its own block and orders them by column, so a label such as
  `Bericht Nr.` and its value land dozens of lines apart and the
  heading-jump warning fires on the fee line. No backend retry fixes this — the markdown is a faithful but
  unreadable transcript. Verify the values against the page image and
  say so; a readable summary is a separate authoring step, not a
  conversion.
- Small print in scanned forms loses umlauts selectively (`Prufbescheinigung`, `Luneburg`) —
  a known ocrmac limit, not a broken run. Do not "repair" it by hand-editing;
  correct spellings go into whatever summary you derive from the file.
- **Check legal citations against the page image** when the probe warns
  `section-sign-mimic`: a scan's text layer can misread `§` even when the
  surrounding prose is clean. For scans, compare `--ocr-mode layout_regions`
  with `--ocr-mode full_page` and verify both citations and reading order.
  This flag never counts toward automatic re-OCR.
- Tiled scans (a page built from several partial images) are not detected
  as full-page images; the heuristic stays conservative and may keep a
  weak text layer. Inspect such output.
