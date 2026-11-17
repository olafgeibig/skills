#!/usr/bin/env python3
"""smart-convert — probe, decide, sample, convert, verify, publish.

Part of the smart-document-converter skill. One local pass over a PDF, DOCX
or HTML file:

  1. probe the text layer and the image inventory per sampled page (poppler)
  2. pick a conservative OCR mode from that evidence, never from a model
  3. sample first on long documents, verify, optionally retry one backend
  4. convert into staging, validate the staged bytes, then publish atomically

The script reports what it measured and never certifies meaning: every
report carries ``semantic_validation: "not_performed"``. Amounts,
identifiers and table completeness still need a human or a vision check.

Stdlib only. Requires poppler (pdfinfo, pdftotext, pdfimages) for PDF
probing and the docling CLI for conversion.

Exit codes: 0 clean · 2 usable output with warnings · 1 failed.
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCHEMA_VERSION = 1
PROBE_TIMEOUT = 30.0            # seconds per poppler probe command
DEFAULT_TIMEOUT = 900.0         # seconds per docling invocation
FULLPAGE_RATIO = 0.8
SUPPORTED_SUFFIXES = (".pdf", ".docx", ".html", ".htm")
STAGES = ("usage", "preflight", "probe", "sample", "convert", "verify", "publish")

# --- red-flag patterns (seen in real broken text layers) -----------------
PUA = re.compile(r"[\ue000-\uf8ff]")                        # symbol-font bullets
SALAD = re.compile(r"[A-ZÄÖÜ]{2,}[a-zäöüß][A-ZÄÖÜ]")        # WEERTEwÖE
AMOUNT_AMPERSAND = re.compile(r"\d[.,]\d{1,2}\s*&")         # 300,00&
REPLACEMENT = re.compile("\ufffd")                          # undecodable byte
HEADING = re.compile(r"^(#{1,6})\s+\S")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
PAGE_SIZE = re.compile(r"Page(?:\s+\d+)?\s+size:\s+([\d.]+)\s+x\s+([\d.]+)\s+pts")
PAGE_COUNT = re.compile(r"^Pages:\s+(\d+)\s*$", re.M)

# only these three suggest a broken text layer; private-use is a cleanup hint
SCAN_SUSPECT = ("replacement-character", "case-salad", "amount-ampersand")

_STAGE = {"value": "usage"}


def set_stage(stage):
    _STAGE["value"] = stage


# --- errors and reports ---------------------------------------------------
class JobError(Exception):
    """A failed stage with a stable code and the captured diagnostic."""

    def __init__(self, stage, code, message, *, command=None,
                 returncode=None, stdout="", stderr=""):
        super().__init__(message)
        self.detail = {
            "stage": stage, "code": code, "message": message,
            "command": command, "returncode": returncode,
            "stdout_tail": _as_text(stdout)[-8000:],
            "stderr_tail": _as_text(stderr)[-8000:],
        }


class ReportParser(argparse.ArgumentParser):
    def error(self, message):
        raise JobError("usage", "invalid_arguments", message)


def _as_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def new_report():
    """Every mandatory key, in the documented order."""
    return {
        "schema_version": SCHEMA_VERSION,
        "status": None,
        "exit_code": None,
        "input": None,
        "output": None,
        "chunks": None,
        "sample_md": None,
        "semantic_validation": "not_performed",
        "decision": None,
        "reason": None,
        "probe": None,
        "verify": None,
        "warnings": [],
        "logs": [],
        "error": None,
    }


def finish(report, logs, code, *, status=None, json_mode=False):
    """The single report finalizer: status, exit code, one JSON object."""
    if status is None:
        status = "error" if code == 1 else ("warning" if code == 2 else "ok")
    report["status"] = status
    report["exit_code"] = code
    report["semantic_validation"] = "not_performed"
    report["logs"] = logs
    if json_mode:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return code


# --- process boundary -----------------------------------------------------
def need(binary):
    if shutil.which(binary) is None:
        raise JobError("preflight", "missing_tool",
                       f"required tool '{binary}' not found on PATH")


def docling_env(online=False):
    """The Docling child environment: parent stays untouched."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    if online:
        env.pop("HF_HUB_OFFLINE", None)
    else:
        env["HF_HUB_OFFLINE"] = "1"
    return env


def _timeout_error(cmd, stage, exc):
    return JobError(stage, "tool_timeout",
                    f"{cmd[0]} timed out after {exc.timeout}s",
                    command=cmd,
                    stdout=getattr(exc, "output", ""),
                    stderr=getattr(exc, "stderr", ""))


def _spawn_error(cmd, stage, exc):
    if isinstance(exc, FileNotFoundError):
        return JobError(stage, "missing_tool",
                        f"required tool '{cmd[0]}' not found", command=cmd)
    return JobError(stage, "io_error", f"could not run {cmd[0]}: {exc}", command=cmd)


def run(cmd, *, timeout=PROBE_TIMEOUT, stage="probe"):
    """Run one probe command; any failure is a structured error."""
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise _timeout_error(cmd, stage, exc)
    except OSError as exc:
        raise _spawn_error(cmd, stage, exc)
    if done.returncode != 0:
        raise JobError(stage, "tool_failed", f"{cmd[0]} failed",
                       command=cmd, returncode=done.returncode,
                       stdout=done.stdout or "", stderr=done.stderr or "")
    return done


def convert(cmd, log, *, online=False, timeout=DEFAULT_TIMEOUT):
    """Run one Docling invocation; returns (returncode, seconds)."""
    env = docling_env(online)
    started = time.perf_counter()
    try:
        done = subprocess.run(cmd, capture_output=True, text=True,
                              env=env, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        log(f"[convert] TIMEOUT after {timeout}s")
        raise _timeout_error(cmd, "convert", exc)
    except OSError as exc:
        raise _spawn_error(cmd, "convert", exc)
    elapsed = time.perf_counter() - started
    if done.returncode != 0:
        tail = "\n".join((done.stderr or done.stdout or "").strip().splitlines()[-6:])
        log(f"[convert] FAILED (exit {done.returncode}, {elapsed:.1f}s):\n{tail}")
        raise JobError("convert", "tool_failed", "docling failed",
                       command=cmd, returncode=done.returncode,
                       stdout=done.stdout or "", stderr=done.stderr or "")
    log(f"[convert] exit 0 in {elapsed:.1f}s")
    return done.returncode, elapsed


# --- probe ----------------------------------------------------------------
def detect_text_flags(text):
    """Stable diagnostic flags for one page's text. Sorted, no prose."""
    flags = []
    if REPLACEMENT.search(text):
        flags.append("replacement-character")
    if len(SALAD.findall(text)) >= 2:
        flags.append("case-salad")
    if AMOUNT_AMPERSAND.search(text):
        flags.append("amount-ampersand")
    if PUA.search(text):
        flags.append("private-use")
    return sorted(flags)


def select_probe_pages(pages, image_pages):
    """Front/middle/end plus image-bearing pages, sorted and deduplicated."""
    selected = {1, min(2, pages), max(1, pages // 2), pages}
    images = sorted({p for p in image_pages if 1 <= p <= pages})
    if images:
        selected.update((images[0], images[len(images) // 2], images[-1]))
    return sorted(selected)


def parse_page_count(text):
    match = PAGE_COUNT.search(text)
    if not match:
        raise JobError("probe", "invalid_probe",
                       "pdfinfo reported no usable page count")
    pages = int(match.group(1))
    if pages < 1:
        raise JobError("probe", "invalid_probe",
                       f"pdfinfo reported an impossible page count: {pages}")
    return pages


def parse_page_size(text, page):
    match = PAGE_SIZE.search(text)
    if not match:
        raise JobError("probe", "invalid_probe",
                       f"pdfinfo reported no page size for page {page}")
    width, height = float(match.group(1)), float(match.group(2))
    if width <= 0 or height <= 0:
        raise JobError("probe", "invalid_probe",
                       f"pdfinfo reported a degenerate page size for page {page}")
    return width, height


def parse_image_inventory(text):
    """One metadata-only record per image: page and area in points²."""
    records = []
    for line in text.splitlines()[2:]:
        cols = line.split()
        if len(cols) < 14 or cols[2] != "image":
            continue
        try:
            page, width, height = int(cols[0]), int(cols[3]), int(cols[4])
            xppi, yppi = float(cols[12]), float(cols[13])
        except ValueError:
            continue
        if page < 1 or xppi <= 0 or yppi <= 0:
            continue
        records.append({"page": page, "area": (width / xppi * 72) * (height / yppi * 72)})
    return records


def probe_pdf(path: Path, log):
    """Sampled, per-page evidence. Unknown evidence is never a negative finding."""
    info = run(["pdfinfo", str(path)])
    pages = parse_page_count(info.stdout)
    inventory = parse_image_inventory(run(["pdfimages", "-list", str(path)]).stdout)
    selected = select_probe_pages(pages, [rec["page"] for rec in inventory])
    log(f"[probe] pages={pages} sampled={','.join(str(p) for p in selected)}")

    records = []
    for page in selected:
        size = run(["pdfinfo", "-f", str(page), "-l", str(page), str(path)])
        width, height = parse_page_size(size.stdout, page)
        page_area = width * height
        fullpage = any(rec["page"] == page and rec["area"] / page_area >= FULLPAGE_RATIO
                       for rec in inventory)
        text = run(["pdftotext", "-layout", "-f", str(page), "-l", str(page),
                    str(path), "-"]).stdout
        records.append({
            "page": page,
            "words": len(text.split()),
            "has_text": bool(text.strip()),
            "fullpage_image": bool(fullpage),
            "flags": detect_text_flags(text),
        })
    return {
        "pages": pages,
        "sampled_pages": records,
        "fullpage_pages": [r["page"] for r in records if r["fullpage_image"]],
        "words_sampled": sum(r["words"] for r in records),
        "scope": "sampled",
    }


# --- conservative decisions ----------------------------------------------
def _page_suspicion(record):
    return {flag for flag in record.get("flags") or () if flag in SCAN_SUSPECT}


def _sampled(probe):
    return probe.get("sampled_pages") or []


def decide(probe):
    """Return (label, extra_flags, reason) from sampled evidence only."""
    pages = probe.get("pages")
    records = _sampled(probe)
    text_pages = [r for r in records if r.get("has_text")]
    fullpage_pages = [r for r in records if r.get("fullpage_image")]
    suspect_pages = [r for r in records if _page_suspicion(r)]
    categories = sorted({flag for r in suspect_pages for flag in _page_suspicion(r)})

    if suspect_pages:
        if pages == 1 and fullpage_pages and len(categories) >= 2:
            return ("scan-suspect-layer", ["--ocr-mode", "full_page"],
                    "single-page scan with " + ", ".join(categories)
                    + " over a full-page image — heuristic, not proof")
        return ("suspect-layer", [],
                "text layer looks suspect on sampled page(s): "
                + ", ".join(categories) + " — re-OCR not forced")
    if not text_pages:
        if fullpage_pages:
            return ("scan-no-layer", [],
                    "no text on the sampled page(s) plus a full-page image; "
                    "Docling OCR fires automatically")
        return ("unknown", [],
                "no text and no full-page image on the sampled page(s) — inspect the input")
    if fullpage_pages:
        return ("scan-layer-unverified", [],
                "text exists over a sampled full-page image and looks clean; "
                "the layer is not verified")
    return ("digital-no-red-flags", [],
            "No heuristic red flags on sampled pages; content not verified.")


def decision_warnings(probe, label):
    """Actionable warnings implied by the decision, in stable wording."""
    warnings = []
    categories = sorted({flag for r in _sampled(probe) for flag in _page_suspicion(r)})
    if label == "scan-suspect-layer":
        warnings.append("heuristic re-OCR selected (--ocr-mode full_page) from "
                        + ", ".join(categories)
                        + "; review identifiers and tables against the page image")
    elif label == "suspect-layer":
        warnings.append("suspicious text layer (" + ", ".join(categories)
                        + ") but re-OCR is not forced; inspect the pages or pass "
                        "--ocr-mode full_page explicitly")
    elif label == "unknown":
        warnings.append("sampled pages show neither text nor a full-page image; "
                        "inspect the input before trusting the output")
    if any("private-use" in (r.get("flags") or ()) for r in _sampled(probe)):
        warnings.append("private-use glyphs in the text layer — strip them with "
                        "--strip-pua before import; they are not evidence of bad OCR")
    return warnings


# --- verification ---------------------------------------------------------
def verify_md(md_path, pages_hint, *, profile="general"):
    """Mechanical checks on the final bytes. Never a semantic certificate."""
    path = Path(md_path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise JobError("verify", "invalid_output", f"output is not valid UTF-8: {exc}")
    except OSError as exc:
        raise JobError("verify", "invalid_output", f"cannot read output: {exc}")

    lines = text.splitlines()
    levels = [len(m.group(1)) for m in (HEADING.match(line) for line in lines) if m]
    jumps = sum(1 for a, b in zip(levels, levels[1:]) if b - a > 1)
    words = len(text.split())
    substantive = HTML_COMMENT.sub(" ", text).strip()

    issues, warnings = [], []
    if not substantive:
        issues.append("output is empty (whitespace or image placeholders only)")
    elif words < 10:
        warnings.append(f"short output: {words} word(s) — check the source and the OCR mode")
    if profile == "structured":
        if not levels and (pages_hint or 1) >= 3:
            warnings.append(f"no headings in a {pages_hint}-page document — "
                            "check the nesting or A/B the backend")
        if jumps:
            warnings.append(f"{jumps} heading level jump(s) — check nesting/backend")
    pua = len(PUA.findall(text))
    if pua:
        warnings.append(f"{pua} private-use glyph(s) — strip before import (--strip-pua)")
    tables = sum(1 for line in lines if line.lstrip().startswith("|"))
    return {
        "headings": len(levels), "level_jumps": jumps, "words": words,
        "table_lines": tables, "pua_glyphs": pua,
        "issues": issues, "warnings": warnings, "profile": profile,
    }


def prepare_markdown(path, pages, profile="general", strip_pua=False, log=None):
    """Optional cleanup first, then a full re-read verification of those bytes."""
    if strip_pua:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise JobError("verify", "invalid_output", f"cannot read converter output: {exc}")
        cleaned = PUA.sub("", text)
        if cleaned != text:
            Path(path).write_text(cleaned, encoding="utf-8")
            if log:
                log(f"[clean] stripped {len(PUA.findall(text))} private-use glyph(s)")
    return verify_md(path, pages, profile=profile)


def quality(result):
    """Lower is better. More headings alone do not prove quality."""
    return (len(result["issues"]), result["level_jumps"])


# --- artifacts -----------------------------------------------------------
def publish_file(staged, target, overwrite=False):
    """Create-or-fail without overwrite; replace with it."""
    if overwrite:
        os.replace(staged, target)
    else:
        os.link(staged, target)


def validate_chunks(path):
    """Every nonblank line must be a JSON object; at least one must exist."""
    path = Path(path)
    if not path.is_file():
        raise JobError("verify", "invalid_chunks",
                       f"converter produced no chunks file: {path.name}")
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise JobError("verify", "invalid_chunks", f"chunks file is unreadable: {exc}")
    objects = 0
    for number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise JobError("verify", "invalid_chunks",
                           f"chunks line {number} is not JSON: {exc.msg}")
        if not isinstance(value, dict):
            raise JobError("verify", "invalid_chunks",
                           f"chunks line {number} is not a JSON object")
        objects += 1
    if not objects:
        raise JobError("verify", "invalid_chunks", "chunks file has no objects")
    return objects


def publish_bundle(entries, target_dir):
    """Exclusively created directory; chunks first, Markdown last."""
    created = False
    linked = []
    try:
        Path(target_dir).mkdir(parents=False, exist_ok=False)
        created = True
        for staged, target in entries:
            publish_file(staged, target, overwrite=False)
            linked.append(target)
    except (OSError, JobError) as exc:
        for target in reversed(linked):
            Path(target).unlink(missing_ok=True)
        if created:
            shutil.rmtree(target_dir, ignore_errors=True)
        if isinstance(exc, JobError):
            raise
        code = "output_exists" if isinstance(exc, FileExistsError) else "io_error"
        raise JobError("publish", code, f"could not publish {target_dir}: {exc}")


# --- command line ---------------------------------------------------------
def base_cmd(args, inp):
    cmd = ["docling", "convert", "--device", args.device,
           "--heading-hierarchy", "--ocr-engine", "ocrmac",
           "--image-export-mode", "placeholder", "--fail-on", "partial"]
    if args.lang != "auto":
        cmd += ["--ocr-lang", args.lang]
    return cmd


def cmd_for(args, inp, target, extra, backend, *, page_range=None, chunks=False):
    cmd = base_cmd(args, inp)
    cmd += list(extra)
    if backend != "docling_parse" and "--pdf-backend" not in cmd:
        cmd += ["--pdf-backend", backend]
    if page_range:
        cmd += ["--page-range", page_range]
    if chunks:
        cmd += ["--to", "md", "--to", "chunks", "--chunks-type", "hybrid",
                "--chunks-max-tokens", str(args.chunks_max_tokens),
                "--output", str(target)]
    else:
        cmd += ["--to", "md", "--output-file", str(target)]
    cmd.append(str(inp))
    return cmd


def build_parser():
    ap = ReportParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", type=Path)
    ap.add_argument("--out", type=Path, help="output .md file (or dir with --chunks)")
    ap.add_argument("--chunks", action="store_true",
                    help="also export RAG chunks (needs --out dir)")
    ap.add_argument("--chunks-max-tokens", type=int, default=512)
    ap.add_argument("--lang", default="de-DE,en-US", help="OCR languages, or 'auto'")
    ap.add_argument("--device", default="mps", choices=["mps", "cpu", "cuda"])
    ap.add_argument("--profile", choices=["general", "structured"], default="general",
                    help="verification profile: general prose, or heading structure")
    ap.add_argument("--probe-only", action="store_true",
                    help="print decision + command, no conversion")
    ap.add_argument("--sample-only", action="store_true", help="stop after the sample")
    ap.add_argument("--force-full", action="store_true", help="skip sampling")
    ap.add_argument("--sample-size", type=int, default=10)
    ap.add_argument("--sample-threshold", type=int, default=30)
    ap.add_argument("--ocr-mode", choices=["full_page", "layout_regions", "default"],
                    help="override the automatic OCR-mode decision")
    ap.add_argument("--pdf-backend", choices=["docling_parse", "pypdfium2"],
                    help="override backend (disables automatic retry)")
    ap.add_argument("--strip-pua", action="store_true",
                    help="remove private-use glyphs from output")
    ap.add_argument("--keep-sample", action="store_true",
                    help="keep the sample .md next to the output")
    ap.add_argument("--overwrite", action="store_true",
                    help="replace an existing single Markdown output")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                    help="seconds per Docling invocation")
    ap.add_argument("--online", action="store_true",
                    help="allow HF downloads in the child process (no document upload)")
    ap.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    return ap


def validate_options(args):
    if args.chunks and args.out is None:
        raise JobError("usage", "invalid_arguments", "--chunks needs --out <directory>")
    if args.chunks and args.out.suffix.lower() == ".md":
        raise JobError("usage", "invalid_arguments",
                       "--chunks needs --out <directory>, not a .md file")
    if args.strip_pua and args.chunks:
        raise JobError("usage", "invalid_arguments",
                       "--strip-pua cannot be combined with --chunks in this release")
    if args.overwrite and args.chunks:
        raise JobError("usage", "invalid_arguments",
                       "--overwrite applies to a single Markdown output only")
    if args.overwrite and args.keep_sample:
        raise JobError("usage", "invalid_arguments",
                       "--overwrite cannot be combined with --keep-sample")
    if args.sample_only:
        for flag, value in (("--force-full", args.force_full),
                            ("--probe-only", args.probe_only),
                            ("--chunks", args.chunks),
                            ("--keep-sample", args.keep_sample)):
            if value:
                raise JobError("usage", "invalid_arguments",
                               f"--sample-only cannot be combined with {flag}")
    if args.sample_size <= 0:
        raise JobError("usage", "invalid_arguments", "--sample-size must be positive")
    if args.sample_threshold < 0:
        raise JobError("usage", "invalid_arguments", "--sample-threshold must not be negative")
    if args.chunks_max_tokens <= 0:
        raise JobError("usage", "invalid_arguments", "--chunks-max-tokens must be positive")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise JobError("usage", "invalid_arguments", "--timeout must be a finite positive number")


def plan_targets(args, inp):
    """Absolute destinations, computed without touching the filesystem."""
    if args.chunks:
        bundle = _absolute(args.out)
        return {
            "kind": "chunks", "parent": bundle.parent, "bundle": bundle,
            "final_md": bundle / (inp.stem + ".md"),
            "chunks": bundle / (inp.stem + ".chunks.jsonl"),
            "sample_md": bundle / (inp.stem + ".sample.md"),
        }
    final_md = _absolute(args.out) if args.out else inp.with_suffix(".md")
    if args.sample_only and args.out:
        sample_md = final_md
    else:
        sample_md = final_md.parent / (inp.stem + ".sample.md")
    return {"kind": "file", "parent": final_md.parent, "bundle": None,
            "final_md": final_md, "chunks": None, "sample_md": sample_md}


def _absolute(path):
    """Absolute path without dereferencing a symlink."""
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def _identity(path):
    return os.path.realpath(str(path))


def _check_target(target, source_id, role, *, overwrite):
    if _identity(target) == source_id:
        raise JobError("preflight", "source_collision",
                       f"{role} path equals the source; refusing to alter the input")
    if target.is_symlink():
        raise JobError("preflight", "output_exists",
                       f"{role} path is a symlink; refusing to replace it: {target}")
    if target.exists() and not overwrite:
        raise JobError("preflight", "output_exists",
                       f"{role} already exists; pass --overwrite to replace it: {target}")


def check_targets(args, inp, paths):
    """Reject collisions before any converter runs."""
    source_id = _identity(inp)
    if paths["kind"] == "chunks":
        bundle = paths["bundle"]
        if bundle.is_symlink() or os.path.lexists(bundle):
            raise JobError("preflight", "output_exists",
                           f"destination directory already exists: {bundle}")
        if _identity(paths["final_md"]) == source_id:
            raise JobError("preflight", "source_collision",
                           "destination directory would hold the source file")
        return
    if args.sample_only:
        # the sample is the only artifact of a sample-only run
        _check_target(paths["sample_md"], source_id, "sample output",
                      overwrite=args.overwrite)
        return
    _check_target(paths["final_md"], source_id, "output", overwrite=args.overwrite)
    if args.keep_sample:
        _check_target(paths["sample_md"], source_id, "sample output", overwrite=False)


def run_job(args, report, logs):
    def log(msg):
        logs.append(msg)
        print(msg, file=sys.stderr, flush=True)

    validate_options(args)
    set_stage("preflight")
    inp = Path(args.input).expanduser().resolve()
    report["input"] = str(inp)
    if not inp.is_file():
        raise JobError("preflight", "missing_input", f"input not found: {inp}")
    suffix = inp.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise JobError("preflight", "unsupported_format",
                       f"unsupported input format: {suffix or inp.name}")
    is_pdf = suffix == ".pdf"
    if args.sample_only and not is_pdf:
        raise JobError("usage", "invalid_arguments", "--sample-only needs a PDF input")

    paths = plan_targets(args, inp)
    if not args.probe_only:
        check_targets(args, inp, paths)

    if is_pdf:
        for binary in ("pdfinfo", "pdftotext", "pdfimages"):
            need(binary)
    if not args.probe_only:
        need("docling")

    # 1-2. probe + decision (PDF only; DOCX/HTML go straight to the command)
    set_stage("probe")
    if is_pdf:
        probe = probe_pdf(inp, log)
        label, extra, reason = decide(probe)
        log(f"[probe] fullpage={probe['fullpage_pages'] or 'none'} "
            f"words~{probe['words_sampled']} (scope {probe['scope']})")
        report.update(probe=probe, decision=label, reason=reason)
        for warning in decision_warnings(probe, label):
            report["warnings"].append(warning)
            log(f"[warn] {warning}")
    else:
        probe = {"pages": None}
        label, extra, reason = "non-pdf", [], "DOCX/HTML: no page probe and no sampling"
        report.update(decision=label, reason=reason)
    log(f"[decision] {label}: {reason}")

    if args.ocr_mode:
        extra = ["--ocr-mode", args.ocr_mode]
        report["ocr_mode_override"] = {"explicit": True, "value": args.ocr_mode}
        log(f"[override] --ocr-mode {args.ocr_mode} (explicit; not the heuristic's choice)")
    else:
        report["ocr_mode_override"] = {
            "explicit": False, "value": extra[1] if extra else None}
    backend = args.pdf_backend or "docling_parse"
    if args.pdf_backend:
        extra = extra + ["--pdf-backend", args.pdf_backend]

    pages = probe.get("pages")
    do_sample = bool(is_pdf and (args.sample_only or (
        pages and pages > args.sample_threshold and not args.force_full)))
    sample_range = f"1-{min(args.sample_size, pages)}" if do_sample else None
    sample_pages = min(args.sample_size, pages) if do_sample else 0

    if args.probe_only:
        target = args.out or inp.with_suffix(".md")
        shown = cmd_for(args, inp, target, extra, backend,
                        page_range=sample_range, chunks=args.chunks)
        log("[command] " + " ".join(shown))
        report["command"] = shown
        report["sample_first"] = do_sample
        return (2 if report["warnings"] else 0), "planned"

    # 3. conversion into staging on the destination filesystem
    paths["parent"].mkdir(parents=True, exist_ok=True)
    used_backend = backend
    stage_sample = None
    sample_verify = None
    set_stage("convert")
    with tempfile.TemporaryDirectory(prefix=".smart-convert-",
                                     dir=str(paths["parent"])) as staging_root:
        staging = Path(staging_root)
        if do_sample:
            trigger = ("--sample-only requested" if args.sample_only
                       else f"{pages} pages > {args.sample_threshold}")
            log(f"[sample] {trigger} → converting pages {sample_range} first")
            stage_sample = staging / "sample.md"
            set_stage("sample")
            rc, _ = convert(cmd_for(args, inp, stage_sample, extra, used_backend,
                                    page_range=sample_range),
                            log, online=args.online, timeout=args.timeout)
            if rc != 0:
                raise JobError("sample", "tool_failed", "sample conversion failed",
                               returncode=rc)
            if not stage_sample.is_file():
                raise JobError("sample", "invalid_output",
                               "sample conversion produced no file")
            sample_verify = prepare_markdown(stage_sample, sample_pages, args.profile,
                                             args.strip_pua, log)
            log(f"[verify:sample] headings={sample_verify['headings']} "
                f"jumps={sample_verify['level_jumps']} words={sample_verify['words']}")

            structure_suspect = (
                (not sample_verify["headings"] and sample_pages >= 3)
                or sample_verify["level_jumps"])
            if (args.profile == "structured" and not args.pdf_backend
                    and structure_suspect and not sample_verify["issues"]):
                log("[sample] structure suspicious → one bounded retry with pypdfium2")
                alt = staging / "sample-pypdfium2.md"
                try:
                    rc2, _ = convert(cmd_for(args, inp, alt, extra, "pypdfium2",
                                             page_range=sample_range),
                                     log, online=args.online, timeout=args.timeout)
                    if rc2 != 0:
                        raise JobError("sample", "tool_failed",
                                       "alternate backend failed", returncode=rc2)
                    if not alt.is_file():
                        raise JobError("sample", "invalid_output",
                                       "alternate backend produced no file")
                    alt_verify = prepare_markdown(alt, sample_pages, args.profile,
                                                  args.strip_pua, log)
                    log(f"[verify:sample:pypdfium2] headings={alt_verify['headings']} "
                        f"jumps={alt_verify['level_jumps']}")
                    if quality(alt_verify) < quality(sample_verify):
                        used_backend = "pypdfium2"
                        stage_sample, sample_verify = alt, alt_verify
                        report["warnings"].append(
                            "backend switched to pypdfium2; re-check identifier "
                            "spacing (CD - 02900)")
                        log("[sample] pypdfium2 wins on the sample")
                    else:
                        log("[sample] tie/regression on the sample → default backend kept")
                except JobError as exc:
                    diagnostic = exc.detail.get("stderr_tail") or exc.detail.get("message")
                    report["warnings"].append(
                        "alternate backend unavailable: "
                        f"{exc.detail.get('code')} — {diagnostic.strip()[:200]}")
                    log(f"[sample] retry failed, keeping the usable default sample: "
                        f"{diagnostic.strip()[:400]}")

            if sample_verify["issues"]:
                raise JobError("verify", "invalid_output",
                               "sample failed validation: "
                               + "; ".join(sample_verify["issues"]))
            report["sample_verify"] = sample_verify
            for warning in sample_verify["warnings"]:
                report["warnings"].append(f"sample: {warning}")
                log(f"[warn] sample: {warning}")

            if args.sample_only:
                set_stage("publish")
                try:
                    publish_file(stage_sample, paths["sample_md"],
                                 overwrite=args.overwrite)
                except OSError as exc:
                    raise JobError("publish",
                                   "output_exists" if isinstance(exc, FileExistsError)
                                   else "io_error",
                                   f"could not publish the sample: {exc}")
                report["backend"] = used_backend
                report["sample_md"] = str(paths["sample_md"])
                log(f"[done] --sample-only: sample at {paths['sample_md']}")
                return (2 if report["warnings"] else 0), "sample"
        else:
            log("[sample] skipped" + (f" ({pages} pages <= {args.sample_threshold})"
                                      if pages else ""))

        # 4. full conversion
        set_stage("convert")
        if paths["kind"] == "chunks":
            staged_bundle = staging / "bundle"
            staged_md = staged_bundle / (inp.stem + ".md")
            staged_chunks = staged_bundle / (inp.stem + ".chunks.jsonl")
            rc, elapsed = convert(cmd_for(args, inp, staged_bundle, extra, used_backend,
                                          chunks=True),
                                  log, online=args.online, timeout=args.timeout)
        else:
            staged_md = staging / "converted.md"
            staged_chunks = None
            rc, elapsed = convert(cmd_for(args, inp, staged_md, extra, used_backend),
                                  log, online=args.online, timeout=args.timeout)
        if rc != 0:
            raise JobError("convert", "tool_failed", "conversion failed", returncode=rc)
        if not staged_md.is_file():
            raise JobError("convert", "invalid_output",
                           "converter exited 0 but wrote no Markdown")

        # 5. verify the staged bytes, then publish
        set_stage("verify")
        result = prepare_markdown(staged_md, pages or 1, args.profile,
                                  args.strip_pua, log)
        log(f"[verify] headings={result['headings']} jumps={result['level_jumps']} "
            f"words={result['words']} tables={result['table_lines']} "
            f"pua={result['pua_glyphs']}")
        if result["issues"]:
            raise JobError("verify", "invalid_output",
                           "conversion failed validation: " + "; ".join(result["issues"]))
        if staged_chunks is not None:
            validate_chunks(staged_chunks)
        for warning in result["warnings"]:
            report["warnings"].append(warning)
            log(f"[warn] {warning}")

        set_stage("publish")
        published_sample = None
        try:
            if paths["kind"] == "chunks":
                entries = []
                if args.keep_sample and stage_sample is not None:
                    entries.append((stage_sample, paths["sample_md"]))
                entries.append((staged_chunks, paths["chunks"]))
                entries.append((staged_md, paths["final_md"]))
                publish_bundle(entries, paths["bundle"])
                if args.keep_sample and stage_sample is not None:
                    published_sample = paths["sample_md"]
            else:
                if args.keep_sample and stage_sample is not None:
                    publish_file(stage_sample, paths["sample_md"], overwrite=False)
                    published_sample = paths["sample_md"]
                publish_file(staged_md, paths["final_md"], overwrite=args.overwrite)
        except OSError as exc:
            if published_sample is not None:
                Path(published_sample).unlink(missing_ok=True)
            raise JobError("publish",
                           "output_exists" if isinstance(exc, FileExistsError)
                           else "io_error",
                           f"could not publish the output: {exc}")
        except JobError:
            if published_sample is not None:
                Path(published_sample).unlink(missing_ok=True)
            raise

        report["backend"] = used_backend
        report["convert_seconds"] = round(elapsed, 1)
        report["verify"] = result
        report["output"] = str(paths["final_md"])
        if paths["kind"] == "chunks":
            report["chunks"] = str(paths["chunks"])
        if published_sample is not None:
            report["sample_md"] = str(published_sample)
        log(f"[result] {'WARNINGS' if report['warnings'] else 'OK'} → "
            f"{paths['final_md']}")
        log("[reminder] semantic checks remain: amounts/identifiers vs the page "
            "image, table completeness")
        return (2 if report["warnings"] else 0), None


def fail(report, logs, error):
    report["error"] = error.detail
    for key in ("output", "chunks", "sample_md"):
        report[key] = None
    return 1


def main():
    argv = sys.argv[1:]
    json_mode = "--json" in argv
    report = new_report()
    logs = []
    try:
        args = build_parser().parse_args(argv)
        json_mode = bool(args.json)
        set_stage("usage")
        code, status = run_job(args, report, logs)
        return finish(report, logs, code, status=status, json_mode=json_mode)
    except JobError as exc:
        code = fail(report, logs, exc)
        return finish(report, logs, code, status="error", json_mode=json_mode)
    except Exception as exc:                      # no blanket silent recovery
        error = JobError(_STAGE["value"], "internal_error",
                         f"{type(exc).__name__}: {exc}")
        code = fail(report, logs, error)
        return finish(report, logs, code, status="error", json_mode=json_mode)


if __name__ == "__main__":
    sys.exit(main())
