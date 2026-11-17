# Required Software

Tested with docling 2.145.0 on macOS (Apple Silicon). Re-verify flags
after major docling upgrades.

## 1. docling — the converter

```bash
uv tool install docling
docling --version
```

- CLI: `~/.local/bin/docling`
- Tool venv (needed for the ocrmac injection below):
  `~/.local/share/uv/tools/docling/bin/python`

## 2. ocrmac — OCR engine (macOS only)

Apple Vision framework bindings: local, offline, no HF models. Install
INTO docling's tool venv, not as a separate tool:

```bash
uv pip install --python ~/.local/share/uv/tools/docling/bin/python ocrmac
~/.local/share/uv/tools/docling/bin/python -c "import ocrmac; print('ok')"
```

- `uv tool inject docling ocrmac` does NOT work (unknown option).
- `uv tool upgrade docling` rebuilds the venv — re-check ocrmac afterwards
  and reinstall if the import fails.
- First OCR run: one-time framework warmup (about a minute); afterwards
  roughly 3 s/page.

## 3. poppler — text-layer probe

```bash
brew install poppler
command -v pdftotext pdfimages
```

Used for the pre-conversion probe (`pdfinfo`, `pdftotext -layout`,
`pdfimages -list`). Needed only for PDF input: HTML and DOCX conversion
never calls it, and `--probe-only` on a PDF does not need docling.

## 4. Cached models — required for offline PDF parsing

Docling downloads its layout and table models on first use. With the
script's default `HF_HUB_OFFLINE=1` a PDF conversion fails until those
models are cached, so run **one** conversion of the target format once
with `--online` (or manually without `HF_HUB_OFFLINE`), then work offline.
This applies to parsing itself, not only to chunking.

For hybrid chunking a tokenizer is downloaded as well (default:
`sentence-transformers/all-MiniLM-L6-v2`); the same one-time warm-up
applies. Match `--chunks-tokenizer` to the embedding model used
downstream.

## Child environment isolation

Docling runs in its own tool venv, and a `PYTHONPATH` or `PYTHONHOME`
inherited from the calling shell can point that interpreter at a foreign
package tree — typically another Python version's site-packages. The
symptom is an import or ABI error from inside docling that disappears when
the variables are unset.

The script already handles this: it removes `PYTHONPATH` and `PYTHONHOME`
from the **Docling child process only** and leaves the parent environment
untouched. Do not "fix" the symptom by exporting variables globally or by
editing shell profiles; if a manual command hits it, scope the fix to that
command:

```bash
env -u PYTHONPATH -u PYTHONHOME docling convert ... input.pdf
```

For scripted helpers that need docling's own interpreter (e.g. building
DOCX or image fixtures with Pillow), use the tool venv explicitly and the
same scoping:

```bash
env -u PYTHONPATH -u PYTHONHOME ~/.local/share/uv/tools/docling/bin/python script.py
```

## Notes

- `python-docx` ships inside docling's venv as a dependency — usable for
  creating test DOCX with real heading styles; no extra install needed.
- `--device mps` uses the Apple Silicon GPU; on Intel Macs use
  `--device cpu`.
- On Linux, ocrmac is unavailable — a different OCR engine (e.g.
  easyocr/tesseract) would be needed; this skill's commands assume macOS.
