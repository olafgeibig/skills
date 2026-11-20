"""Unit tests for scripts/smart_convert.py.

Stdlib only. No Docling, no GPU, no network, no real PDFs: the converter and
the PDF probe are explicit unit doubles, never evidence of OCR quality.
"""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "smart_convert.py"
spec = importlib.util.spec_from_file_location("converter_under_test", SCRIPT)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class ConverterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "input.pdf"
        self.source.write_bytes(b"unit fixture: probe is mocked")
        self.out = self.root / "result.md"
        self.commands = []
        self.body = "Ordinary correspondence with a reference TEST-2026 and amount 123.45 EUR. " * 3

    def probe(self, pages=1, flags=(), image=False):
        return {
            "pages": pages,
            "sampled_pages": [{"page": 1, "words": 30, "has_text": True,
                               "fullpage_image": image, "flags": list(flags)}],
            "fullpage_pages": [1] if image else [],
            "words_sampled": 30,
            "scope": "sampled",
        }

    def fake_convert(self, command, log, **kwargs):
        self.commands.append(command)
        if "--output-file" in command:
            target = Path(command[command.index("--output-file") + 1])
            target.write_text(self.body, encoding="utf-8")
        else:
            folder = Path(command[command.index("--output") + 1])
            folder.mkdir(exist_ok=True)
            (folder / "input.md").write_text(self.body, encoding="utf-8")
            (folder / "input.chunks.jsonl").write_text(
                json.dumps({"text": self.body}) + "\n", encoding="utf-8")
        return 0, 0.01

    def cli(self, *flags, pages=1, converter=None, mock_probe=True):
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = [str(SCRIPT), str(self.source), "--out", str(self.out), "--json", *flags]
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(sys, "argv", argv))
            stack.enter_context(patch.object(m, "need"))
            if mock_probe:
                stack.enter_context(patch.object(m, "probe_pdf", return_value=self.probe(pages)))
            stack.enter_context(patch.object(m, "convert", side_effect=converter or self.fake_convert))
            stack.enter_context(contextlib.redirect_stdout(stdout))
            stack.enter_context(contextlib.redirect_stderr(stderr))
            try:
                code = m.main()
            except SystemExit as exc:
                code = exc.code
        self.last_stderr = stderr.getvalue()
        raw = stdout.getvalue()
        self.assertTrue(raw.strip(), "--json must emit a report")
        report = json.loads(raw)
        self.assertEqual(code, report["exit_code"])
        return code, report

    def verify(self, text, pages=1, profile="general"):
        path = self.root / "verify.md"
        path.write_text(text, encoding="utf-8")
        return m.verify_md(path, pages, profile=profile)

    # --- 01: report framing ------------------------------------------------
    def test_report_success_contract(self):
        code, report = self.cli()
        self.assertEqual(code, 0)
        self.assertIn("schema_version", report)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["semantic_validation"], "not_performed")
        for key in ("chunks", "sample_md", "probe", "verify", "logs", "error"):
            self.assertIn(key, report)

    # --- 02: general versus structured validation --------------------------
    def test_verify_general_letter(self):
        result = self.verify(self.body, pages=3)
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["warnings"], [])

    def test_verify_short_text(self):
        result = self.verify("Received. Thank you.")
        self.assertEqual(result["issues"], [])
        self.assertTrue(result["warnings"])

    def test_verify_placeholder_is_empty(self):
        result = self.verify("<!-- image -->\n\n<!-- image -->")
        self.assertTrue(result["issues"])

    def test_verify_structured_headings_warn(self):
        result = self.verify(self.body, pages=3, profile="structured")
        self.assertEqual(result["issues"], [])
        self.assertTrue(result["warnings"])

    # --- 03: re-verify after cleanup; reject inconsistent exports ----------
    def test_strip_pua_revalidates(self):
        self.body = " ".join(["\ue001"] * 12)
        code, report = self.cli("--strip-pua")
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "error")
        self.assertIsNone(report["output"])

    def test_strip_pua_chunks_rejected(self):
        self.out = self.root / "bundle"
        code, report = self.cli("--chunks", "--strip-pua")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "invalid_arguments")
        self.assertEqual(self.commands, [])

    # --- 04: typed errors and argument errors ------------------------------
    def test_json_missing_input(self):
        self.source.unlink()
        code, report = self.cli()
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "missing_input")
        self.assertIsNone(report["output"])

    def test_json_invalid_option(self):
        code, report = self.cli("--not-a-real-option")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["stage"], "usage")

    def test_missing_tool_is_structured(self):
        with patch.object(m.shutil, "which", return_value=None):
            with self.assertRaises(m.JobError) as raised:
                m.need("docling")
        self.assertEqual(raised.exception.detail["code"], "missing_tool")

    def test_unsupported_format_rejected(self):
        self.source = self.root / "notes.txt"
        self.source.write_text("plain text", encoding="utf-8")
        code, report = self.cli()
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "unsupported_format")
        self.assertEqual(self.commands, [])

    def test_output_read_failure_is_structured(self):
        path = self.root / "binary.md"
        path.write_bytes(b"\xff\xfe\x00broken")
        with self.assertRaises(m.JobError) as raised:
            m.verify_md(path, 1)
        self.assertEqual(raised.exception.detail["code"], "invalid_output")

    def test_unhandled_exception_is_internal_error(self):
        def boom(command, log, **kwargs):
            raise RuntimeError("unexpected bug")
        code, report = self.cli(converter=boom)
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "internal_error")
        self.assertIn("RuntimeError", report["error"]["message"])

    # --- 05: child environment isolation -----------------------------------
    def test_docling_environment_isolated(self):
        done = subprocess.CompletedProcess(["docling"], 0, "", "")
        with patch.dict(os.environ, {"PYTHONPATH": "foreign", "PYTHONHOME": "foreign",
                                     "HF_HUB_OFFLINE": "1"}):
            with patch.object(m.subprocess, "run", return_value=done) as child:
                m.convert(["docling", "convert"], lambda _: None, online=True, timeout=12)
            env = child.call_args.kwargs["env"]
            self.assertNotIn("PYTHONPATH", env)
            self.assertNotIn("PYTHONHOME", env)
            self.assertNotIn("HF_HUB_OFFLINE", env)
            self.assertEqual(os.environ["PYTHONPATH"], "foreign")

    def test_docling_environment_offline(self):
        done = subprocess.CompletedProcess(["docling"], 0, "", "")
        with patch.dict(os.environ, {"HF_HUB_OFFLINE": "0"}):
            with patch.object(m.subprocess, "run", return_value=done) as child:
                m.convert(["docling"], lambda _: None)
            self.assertEqual(child.call_args.kwargs["env"]["HF_HUB_OFFLINE"], "1")

    # --- 06: bounded subprocesses, retained diagnostics --------------------
    def test_docling_timeout_is_structured(self):
        with patch.object(m.subprocess, "run", side_effect=subprocess.TimeoutExpired(
                ["docling"], 12, output=b"partial stdout", stderr=b"timeout detail")):
            with self.assertRaises(m.JobError) as raised:
                m.convert(["docling"], lambda _: None, timeout=12)
        self.assertEqual(raised.exception.detail["code"], "tool_timeout")
        self.assertIn("timeout detail", raised.exception.detail["stderr_tail"])

    def test_converter_diagnostic_survives_json(self):
        def fail(command, log, **kwargs):
            raise m.JobError("convert", "tool_failed", "synthetic failure",
                             command=command, returncode=9, stderr="specific diagnostic")
        code, report = self.cli(converter=fail)
        self.assertEqual(code, 1)
        self.assertIn("specific diagnostic", report["error"]["stderr_tail"])

    def test_convert_passes_timeout_keyword(self):
        done = subprocess.CompletedProcess(["docling"], 0, "", "")
        with patch.object(m.subprocess, "run", return_value=done) as child:
            m.convert(["docling"], lambda _: None, timeout=42)
        self.assertEqual(child.call_args.kwargs["timeout"], 42)

    def test_probe_uses_fixed_timeout(self):
        done = subprocess.CompletedProcess(["pdfinfo"], 0, "Pages: 1\n", "")
        with patch.object(m.subprocess, "run", return_value=done) as child:
            m.run(["pdfinfo", "x.pdf"])
        self.assertEqual(child.call_args.kwargs["timeout"], 30)

    def test_probe_nonzero_is_structured(self):
        with patch.object(m.subprocess, "run", return_value=subprocess.CompletedProcess(
                ["pdfinfo"], 3, "", "boom")):
            with self.assertRaises(m.JobError) as raised:
                m.run(["pdfinfo", "x.pdf"])
        self.assertEqual(raised.exception.detail["stage"], "probe")
        self.assertEqual(raised.exception.detail["code"], "tool_failed")

    def test_missing_binary_at_process_boundary(self):
        with patch.object(m.subprocess, "run", side_effect=FileNotFoundError("docling")):
            with self.assertRaises(m.JobError) as raised:
                m.convert(["docling"], lambda _: None)
        self.assertEqual(raised.exception.detail["code"], "missing_tool")

    # --- 07: bounded page samples ------------------------------------------
    def test_selected_pages_include_end_and_image_pages(self):
        self.assertEqual(m.select_probe_pages(4, []), [1, 2, 4])
        selected = m.select_probe_pages(100, [10, 30, 50, 70, 90])
        self.assertEqual(selected, [1, 2, 10, 50, 90, 100])
        self.assertLessEqual(len(selected), 7)

    # --- 08: per-page probe records ----------------------------------------
    def test_probe_page_evidence(self):
        def fake_run(command, **kwargs):
            if command[0] == "pdfimages":
                text = "header\nseparator\n4 0 image 1654 2339 rgb 3 8 jpeg no 5 0 200 200 50K 1%\n"
            elif command[0] == "pdfinfo" and "-f" not in command:
                text = "Pages: 4\n"
            elif command[0] == "pdfinfo":
                page = command[command.index("-f") + 1]
                text = f"Page {page} size: 595 x 842 pts\n"
            else:
                page = int(command[command.index("-f") + 1])
                text = "Total 300,00& WEERTEwÖE WEERTEwÖE" if page == 4 else self.body
            return subprocess.CompletedProcess(command, 0, text, "")

        with patch.object(m, "run", side_effect=fake_run):
            probe = m.probe_pdf(self.source, lambda _: None)
        self.assertEqual([r["page"] for r in probe["sampled_pages"]], [1, 2, 4])
        page4 = probe["sampled_pages"][2]
        self.assertTrue(page4["fullpage_image"])
        self.assertIn("amount-ampersand", page4["flags"])
        self.assertIn("case-salad", page4["flags"])
        page1 = probe["sampled_pages"][0]
        self.assertFalse(page1["fullpage_image"])
        self.assertNotIn("amount-ampersand", page1["flags"])
        self.assertNotIn("case-salad", page1["flags"])
        self.assertEqual(probe["fullpage_pages"], [4])
        self.assertEqual(probe["scope"], "sampled")

    def test_probe_failure_not_negative_evidence(self):
        with patch.object(m, "run", side_effect=m.JobError("probe", "tool_failed", "pdfimages failed")):
            with self.assertRaises(m.JobError):
                m.probe_pdf(self.source, lambda _: None)

    def test_probe_malformed_page_count(self):
        with patch.object(m, "run", return_value=subprocess.CompletedProcess(
                ["pdfinfo"], 0, "no count here\n", "")):
            with self.assertRaises(m.JobError) as raised:
                m.probe_pdf(self.source, lambda _: None)
        self.assertEqual(raised.exception.detail["code"], "invalid_probe")

    def test_probe_malformed_page_size(self):
        def fake_run(command, **kwargs):
            if command[0] == "pdfimages":
                return subprocess.CompletedProcess(command, 0, "", "")
            if "-f" not in command:
                return subprocess.CompletedProcess(command, 0, "Pages: 2\n", "")
            return subprocess.CompletedProcess(command, 0, "Page 1 size: unknown\n", "")
        with patch.object(m, "run", side_effect=fake_run):
            with self.assertRaises(m.JobError) as raised:
                m.probe_pdf(self.source, lambda _: None)
        self.assertEqual(raised.exception.detail["code"], "invalid_probe")

    def test_probe_uses_page_specific_dimensions(self):
        def fake_run(command, **kwargs):
            if command[0] == "pdfimages":
                return subprocess.CompletedProcess(command, 0, "", "")
            if "-f" not in command:
                return subprocess.CompletedProcess(command, 0, "Pages: 2\n", "")
            if command[0] == "pdfinfo":
                page = command[command.index("-f") + 1]
                return subprocess.CompletedProcess(command, 0, f"Page {page} size: 595 x 842 pts\n", "")
            return subprocess.CompletedProcess(command, 0, "text " * 5, "")
        with patch.object(m, "run", side_effect=fake_run):
            probe = m.probe_pdf(self.source, lambda _: None)
        self.assertEqual(probe["pages"], 2)
        self.assertEqual([r["page"] for r in probe["sampled_pages"]], [1, 2])

    # --- 09: conservative parameter decisions ------------------------------
    def test_decision_legitimate_characters(self):
        flags = m.detect_text_flags("Invoice for Şahin: 156,90 £ and a private bullet \ue001")
        self.assertEqual(flags, ["private-use"])
        label, extra, _ = m.decide(self.probe(flags=flags, image=True))
        self.assertEqual(label, "scan-layer-unverified")
        self.assertEqual(extra, [])

    def test_decision_short_suspect_scan(self):
        probe = self.probe(flags=["amount-ampersand", "case-salad"], image=True)
        probe["sampled_pages"][0]["words"] = 3
        label, extra, _ = m.decide(probe)
        self.assertEqual(label, "scan-suspect-layer")
        self.assertEqual(extra, ["--ocr-mode", "full_page"])

    def test_decision_mixed_document_not_forced(self):
        probe = self.probe(pages=4, flags=["amount-ampersand", "case-salad"], image=True)
        label, extra, _ = m.decide(probe)
        self.assertEqual(label, "suspect-layer")
        self.assertEqual(extra, [])

    def test_decision_scan_no_layer(self):
        probe = self.probe(image=True)
        probe["sampled_pages"][0]["has_text"] = False
        probe["sampled_pages"][0]["words"] = 0
        label, extra, _ = m.decide(probe)
        self.assertEqual(label, "scan-no-layer")
        self.assertEqual(extra, [])

    def test_decision_sparse_clean_native(self):
        probe = self.probe(pages=2)
        probe["sampled_pages"][0]["words"] = 3
        label, extra, _ = m.decide(probe)
        self.assertEqual(label, "digital-no-red-flags")
        self.assertEqual(extra, [])

    def test_decision_isolated_suspicion_not_image_page(self):
        probe = self.probe(flags=["replacement-character", "case-salad"])
        label, extra, _ = m.decide(probe)
        self.assertEqual(label, "suspect-layer")
        self.assertEqual(extra, [])
        self.assertTrue(m.decision_warnings(probe, label))

    def test_decision_pua_only_is_cleanup_warning(self):
        probe = self.probe(flags=["private-use"], image=True)
        label, extra, _ = m.decide(probe)
        self.assertEqual(label, "scan-layer-unverified")
        warnings = m.decision_warnings(probe, label)
        self.assertTrue(any("private-use" in w for w in warnings))
        self.assertFalse(any("full_page" in w for w in warnings))

    def test_detect_text_flags_stable(self):
        self.assertEqual(m.detect_text_flags("clean ordinary text 123.45 EUR"), [])
        self.assertEqual(m.detect_text_flags("broken \ufffd char"), ["replacement-character"])
        self.assertEqual(m.detect_text_flags("Total 300,00& WEERTEwÖE WEERTEwÖE"),
                         ["amount-ampersand", "case-salad"])

    def test_detect_text_flags_section_sign_mimic(self):
        # a scanned Finanzamt letter whose layer turned every § into a glyph
        self.assertEqual(m.detect_text_flags("gem. 8 152 AO ein Zuschlag"),
                         ["section-sign-mimic"])
        self.assertEqual(m.detect_text_flags("ergibt sich aus &$149 Abs. 1 AO"),
                         ["section-sign-mimic"])
        self.assertEqual(m.detect_text_flags("unzulässig ($ 393 Abs. 1 AO)"),
                         ["section-sign-mimic"])

    def test_detect_text_flags_section_sign_intact(self):
        self.assertEqual(m.detect_text_flags("§ 149 Abs. 1 Abgabenordnung (AO)"), [])

    def test_section_mimic_requires_legal_context(self):
        for text in ("$ 100 USD; $100 US Dollars", "$123 Value package", "8 152 Artikel",
                     "$ 100 Absorption", "$1.234 Angebot", "8 152 AON"):
            with self.subTest(text=text):
                self.assertEqual(m.detect_text_flags(text), [])

    def test_section_mimic_spacing_suffix_and_mixed_layer(self):
        for text in ("§ 149 Abs. 1 AO; vgl. 8 152 AO", "&amp;$\xa0\t149a   Abs. 1 AO",
                     "$ 1234b\nSatz 2 BGB", "8   152\tAO"):
            with self.subTest(text=text):
                self.assertIn("section-sign-mimic", m.detect_text_flags(text))

    def test_section_mimic_does_not_count_towards_automatic_ocr(self):
        probe = self.probe(flags=["section-sign-mimic", "replacement-character"], image=True)
        label, extra, _ = m.decide(probe)
        self.assertEqual((label, extra), ("suspect-layer", []))

    def test_decision_section_sign_mimic_warns_but_forces_nothing(self):
        probe = self.probe(pages=3, flags=["section-sign-mimic"], image=True)
        label, extra, _ = m.decide(probe)
        self.assertEqual(label, "suspect-layer")
        self.assertEqual(extra, [])
        warnings = m.decision_warnings(probe, label)
        self.assertTrue(any("layout_regions" in w for w in warnings))

    # --- 10: sample-only and general prose --------------------------------
    def test_sample_only_short_pdf(self):
        code, report = self.cli("--sample-only", pages=1)
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "sample")
        self.assertIsNone(report["output"])
        self.assertTrue(Path(report["sample_md"]).is_file())
        self.assertEqual(len(self.commands), 1)
        command = self.commands[0]
        self.assertEqual(command[command.index("--page-range") + 1], "1-1")

    def test_general_long_letter_completes(self):
        code, report = self.cli(pages=31)
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(len(self.commands), 2)
        self.assertNotIn("--page-range", self.commands[-1])

    def test_sample_only_rejects_full_run_flags(self):
        for flags in (["--force-full"], ["--probe-only"], ["--chunks"], ["--keep-sample"]):
            with self.subTest(flags=flags):
                code, report = self.cli("--sample-only", *flags)
                self.assertEqual(code, 1)
                self.assertEqual(report["error"]["code"], "invalid_arguments")
        self.assertEqual(self.commands, [])

    def test_sample_only_requires_pdf(self):
        self.source = self.root / "page.html"
        self.source.write_text("<html><body><p>hello</p></body></html>", encoding="utf-8")
        code, report = self.cli("--sample-only")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "invalid_arguments")
        self.assertEqual(self.commands, [])

    def test_malformed_numeric_options(self):
        for flags in (["--sample-size", "0"], ["--sample-threshold", "-1"],
                      ["--chunks-max-tokens", "0"], ["--timeout", "0"]):
            with self.subTest(flags=flags):
                code, report = self.cli(*flags)
                self.assertEqual(code, 1)
                self.assertEqual(report["error"]["code"], "invalid_arguments")
        self.assertEqual(self.commands, [])

    def test_aborted_sample_exits_one(self):
        def bad_sample(command, log, **kwargs):
            self.commands.append(command)
            target = Path(command[command.index("--output-file") + 1])
            target.write_text("   " if "--page-range" in command else self.body, encoding="utf-8")
            return 0, 0.01
        code, report = self.cli(pages=40, converter=bad_sample)
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "error")
        self.assertEqual(len(self.commands), 1)

    def test_probe_only_creates_nothing(self):
        code, report = self.cli("--probe-only")
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "planned")
        self.assertIsNone(report["output"])
        self.assertEqual(self.commands, [])
        self.assertFalse(self.out.exists())
        self.assertEqual(list(self.root.glob(".smart-convert-*")), [])

    # --- 11: bounded structural retries -----------------------------------
    def test_structured_retry_can_restore_missing_headings(self):
        def bodies(command, log, **kwargs):
            self.commands.append(command)
            target = Path(command[command.index("--output-file") + 1])
            prefix = "# Recovered\n\n" if "--pdf-backend" in command else ""
            target.write_text(prefix + self.body, encoding="utf-8")
            return 0, 0.01

        code, report = self.cli("--sample-only", "--profile", "structured",
                                pages=3, converter=bodies)
        self.assertEqual(code, 2)
        self.assertEqual(len(self.commands), 2)
        self.assertEqual(report["backend"], "pypdfium2")
        self.assertEqual(report["sample_verify"]["headings"], 1)

    def test_sample_tool_error_retains_stage_and_diagnostics(self):
        done = subprocess.CompletedProcess(["docling"], 7, "sample stdout", "sample stderr")
        with patch.object(m.subprocess, "run", return_value=done):
            code, report = self.cli("--sample-only", converter=m.convert)
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["stage"], "sample")
        self.assertEqual(report["error"]["returncode"], 7)
        self.assertEqual(report["error"]["stderr_tail"], "sample stderr")

    def test_structured_retry_tie_keeps_default(self):
        def bodies(command, log, **kwargs):
            self.commands.append(command)
            target = Path(command[command.index("--output-file") + 1])
            if "--pdf-backend" in command:
                target.write_text("# A\n\n### C\n\n### D\n\n" + self.body, encoding="utf-8")
            else:
                target.write_text("# A\n\n### C\n\n" + self.body, encoding="utf-8")
            return 0, 0.01
        code, report = self.cli("--sample-only", "--profile", "structured",
                                pages=40, converter=bodies)
        self.assertEqual(code, 2)
        self.assertEqual(len(self.commands), 2)
        self.assertEqual(report["backend"], "docling_parse")

    def test_structured_retry_failure_retained(self):
        def bodies(command, log, **kwargs):
            self.commands.append(command)
            if "--pdf-backend" in command:
                raise m.JobError("sample", "tool_failed", "pypdfium2 exploded",
                                 returncode=7, stdout="alternate stdout",
                                 stderr="alternate diagnostic")
            target = Path(command[command.index("--output-file") + 1])
            target.write_text("# A\n\n### C\n\n" + self.body, encoding="utf-8")
            return 0, 0.01
        code, report = self.cli("--sample-only", "--profile", "structured", converter=bodies)
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "sample")
        self.assertTrue(any("alternate diagnostic" in line for line in report["logs"]))
        error = report["sample_retry_error"]
        self.assertEqual(error["stdout_tail"], "alternate stdout")
        self.assertEqual(error["stderr_tail"], "alternate diagnostic")
        self.assertEqual(error["returncode"], 7)
        self.assertTrue(report["sample_md"])

    def test_explicit_backend_disables_retry(self):
        def bodies(command, log, **kwargs):
            self.commands.append(command)
            target = Path(command[command.index("--output-file") + 1])
            target.write_text("# A\n\n### C\n\n" + self.body, encoding="utf-8")
            return 0, 0.01
        code, report = self.cli("--sample-only", "--profile", "structured",
                                "--pdf-backend", "docling_parse", converter=bodies)
        self.assertEqual(len(self.commands), 1)
        self.assertEqual(code, 2)

    # --- 12: reject collisions before conversion --------------------------
    def test_existing_target_preserved(self):
        self.out.write_text("existing content", encoding="utf-8")
        code, report = self.cli()
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "output_exists")
        self.assertEqual(self.out.read_text(), "existing content")
        self.assertEqual(self.commands, [])

    def test_source_collision_rejected(self):
        original = self.source.read_bytes()
        self.out = self.source
        code, report = self.cli("--overwrite")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "source_collision")
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(self.commands, [])

    def test_existing_sample_sidecar_preserved(self):
        sidecar = self.out.parent / (self.source.stem + ".sample.md")
        sidecar.write_text("old sample", encoding="utf-8")
        code, report = self.cli("--keep-sample", pages=40)
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "output_exists")
        self.assertEqual(sidecar.read_text(), "old sample")
        self.assertEqual(self.commands, [])

    def test_keep_sample_rejects_same_target_before_probe(self):
        self.out = self.source.with_suffix(".sample.md")
        with patch.object(m, "probe_pdf", return_value=self.probe(40)) as probe:
            code, report = self.cli("--keep-sample", mock_probe=False)
        probe.assert_not_called()
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["stage"], "preflight")
        self.assertEqual(report["error"]["code"], "output_collision")
        self.assertEqual(self.commands, [])
        self.assertFalse(self.out.exists())

    def test_target_symlink_rejected(self):
        real = self.root / "real.md"
        real.write_text("real", encoding="utf-8")
        self.out.symlink_to(real)
        code, report = self.cli("--overwrite")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "output_exists")
        self.assertEqual(real.read_text(), "real")
        self.assertEqual(self.commands, [])

    def test_source_via_symlink_alias_rejected(self):
        alias = self.root / "alias.pdf"
        alias.symlink_to(self.source)
        self.out = alias
        code, report = self.cli()
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "source_collision")
        self.assertEqual(self.commands, [])

    def test_existing_chunks_directory_rejected(self):
        bundle = self.root / "bundle"
        bundle.mkdir()
        self.out = bundle
        code, report = self.cli("--chunks")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "output_exists")
        self.assertEqual(self.commands, [])

    def test_overwrite_chunks_rejected(self):
        self.out = self.root / "bundle"
        code, report = self.cli("--chunks", "--overwrite")
        self.assertEqual(report["error"]["code"], "invalid_arguments")
        self.assertEqual(self.commands, [])

    def test_overwrite_keep_sample_rejected(self):
        code, report = self.cli("--overwrite", "--keep-sample")
        self.assertEqual(report["error"]["code"], "invalid_arguments")
        self.assertEqual(self.commands, [])

    # --- 13: stage, verify, then publish ----------------------------------
    def test_stale_output_cannot_satisfy_conversion(self):
        self.out.write_text("old valid output", encoding="utf-8")
        def no_output(command, log, **kwargs):
            self.commands.append(command)
            return 0, 0.01
        code, report = self.cli("--overwrite", converter=no_output)
        self.assertEqual(code, 1)
        self.assertEqual(self.out.read_text(), "old valid output")
        self.assertIsNone(report["output"])

    def test_failed_conversion_keeps_old_output(self):
        self.out.write_text("old valid output", encoding="utf-8")
        self.body = "   "
        code, report = self.cli("--overwrite")
        self.assertEqual(code, 1)
        self.assertEqual(self.out.read_text(), "old valid output")

    def test_race_target_not_clobbered(self):
        def race(command, log, **kwargs):
            self.commands.append(command)
            target = Path(command[command.index("--output-file") + 1])
            target.write_text(self.body, encoding="utf-8")
            self.out.write_text("appeared meanwhile", encoding="utf-8")
            return 0, 0.01
        code, report = self.cli(converter=race)
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "output_exists")
        self.assertEqual(self.out.read_text(), "appeared meanwhile")

    def test_no_temp_directories_leak(self):
        code, _ = self.cli("--overwrite")
        self.assertEqual(code, 0)
        self.assertEqual(list(self.root.glob(".smart-convert-*")), [])
        code, _ = self.cli("--overwrite", converter=lambda c, log, **kw: (0, 0.01))
        self.assertEqual(code, 1)
        self.assertEqual(list(self.root.glob(".smart-convert-*")), [])

    def test_overwrite_replaces_existing(self):
        self.out.write_text("old", encoding="utf-8")
        code, report = self.cli("--overwrite")
        self.assertEqual(code, 0)
        self.assertEqual(report["output"], str(self.out))
        self.assertIn("Ordinary correspondence", self.out.read_text())

    def test_keep_sample_publishes_sidecar(self):
        code, report = self.cli("--keep-sample", pages=40)
        self.assertEqual(code, 0)
        sidecar = self.out.parent / (self.source.stem + ".sample.md")
        self.assertTrue(sidecar.is_file())
        self.assertEqual(report["sample_md"], str(sidecar))
        self.assertEqual(len(self.commands), 2)

    # --- 14: chunk bundle ------------------------------------------------
    def test_chunks_valid_bundle(self):
        self.out = self.root / "bundle"
        code, report = self.cli("--chunks")
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["output"], str(self.out / "input.md"))
        self.assertEqual(report["chunks"], str(self.out / "input.chunks.jsonl"))
        lines = [l for l in (self.out / "input.chunks.jsonl").read_text().splitlines() if l.strip()]
        self.assertTrue(lines)
        for line in lines:
            self.assertIsInstance(json.loads(line), dict)
        for value in (report["output"], report["chunks"]):
            self.assertNotIn(".smart-convert-", value)

    def test_chunks_invalid_json_rejected(self):
        self.out = self.root / "bundle"
        def bad(command, log, **kwargs):
            self.commands.append(command)
            folder = Path(command[command.index("--output") + 1])
            folder.mkdir(exist_ok=True)
            (folder / "input.md").write_text(self.body, encoding="utf-8")
            (folder / "input.chunks.jsonl").write_text("not json\n", encoding="utf-8")
            return 0, 0.01
        code, report = self.cli("--chunks", converter=bad)
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "invalid_chunks")
        self.assertIsNone(report["output"])
        self.assertIsNone(report["chunks"])
        self.assertFalse(self.out.exists())

    def test_chunks_missing_rejected(self):
        self.out = self.root / "bundle"
        def no_chunks(command, log, **kwargs):
            self.commands.append(command)
            folder = Path(command[command.index("--output") + 1])
            folder.mkdir(exist_ok=True)
            (folder / "input.md").write_text(self.body, encoding="utf-8")
            return 0, 0.01
        code, report = self.cli("--chunks", converter=no_chunks)
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "invalid_chunks")
        self.assertFalse(self.out.exists())

    def test_chunks_keep_sample_in_bundle(self):
        self.out = self.root / "bundle"
        code, report = self.cli("--chunks", "--keep-sample", pages=40)
        self.assertEqual(code, 0)
        self.assertTrue((self.out / "input.sample.md").is_file())
        self.assertEqual(report["sample_md"], str(self.out / "input.sample.md"))
        self.assertEqual(report["output"], str(self.out / "input.md"))

    def test_sample_only_existing_sample_needs_overwrite(self):
        self.out.write_text("existing sample", encoding="utf-8")
        code, report = self.cli("--sample-only")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "output_exists")
        self.assertIn("sample", report["error"]["message"])
        self.assertEqual(self.out.read_text(), "existing sample")
        self.assertEqual(self.commands, [])

    def test_sample_only_overwrite_replaces(self):
        self.out.write_text("existing sample", encoding="utf-8")
        code, report = self.cli("--sample-only", "--overwrite")
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "sample")
        self.assertIn("Ordinary", self.out.read_text())

    def test_chunks_rollback_on_markdown_failure(self):
        self.out = self.root / "bundle"
        keeper = self.root / "keeper.txt"
        keeper.write_text("unrelated", encoding="utf-8")
        real = m.publish_file
        def flaky(staged, target, overwrite=False):
            if str(target).endswith(".md"):
                raise OSError("disk full")
            return real(staged, target, overwrite)
        with patch.object(m, "publish_file", side_effect=flaky):
            code, report = self.cli("--chunks")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "io_error")
        self.assertFalse(self.out.exists())
        self.assertEqual(keeper.read_text(), "unrelated")

    # --- 15: dependency requirements, final CLI matrix --------------------
    def test_chunks_rollback_preserves_foreign_entries_and_replacements(self):
        self.out = self.root / "bundle"
        real = m.publish_file

        def flaky(staged, target, overwrite=False):
            if target.suffix == ".md":
                chunks = self.out / "input.chunks.jsonl"
                (self.out / "foreign.txt").write_text("foreign", encoding="utf-8")
                chunks.unlink()
                chunks.write_text("replacement", encoding="utf-8")
                raise OSError("publication failed")
            return real(staged, target, overwrite)

        with patch.object(m, "publish_file", side_effect=flaky):
            code, report = self.cli("--chunks")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "io_error")
        self.assertEqual((self.out / "foreign.txt").read_text(), "foreign")
        self.assertEqual((self.out / "input.chunks.jsonl").read_text(), "replacement")

    def test_file_rollback_preserves_replaced_sample(self):
        sidecar = self.source.with_suffix(".sample.md")
        real = m.publish_file

        def flaky(staged, target, overwrite=False):
            if target == self.out:
                sidecar.unlink()
                sidecar.write_text("replacement", encoding="utf-8")
                raise OSError("publication failed")
            return real(staged, target, overwrite)

        with patch.object(m, "publish_file", side_effect=flaky):
            code, report = self.cli("--keep-sample", pages=40)
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "io_error")
        self.assertEqual(sidecar.read_text(), "replacement")

    def test_cleanup_error_does_not_retract_published_output(self):
        for flags, key, status in (((), "output", "warning"),
                                   (("--sample-only",), "sample_md", "sample")):
            with self.subTest(flags=flags):
                self.out = self.root / f"{key}.md"
                with patch.object(m.tempfile.TemporaryDirectory, "cleanup",
                                  side_effect=PermissionError("cleanup blocked")):
                    code, report = self.cli(*flags)
                self.assertEqual(code, 2)
                self.assertEqual(report["status"], status)
                self.assertTrue(Path(report[key]).is_file())
                self.assertTrue(any("cleanup blocked" in line for line in report["logs"]))
                self.assertTrue(any("cleanup blocked" in line for line in report["warnings"]))

    def test_html_does_not_require_poppler(self):
        self.source = self.root / "page.html"
        self.source.write_text("<html><body><h1>T</h1><p>body</p></body></html>", encoding="utf-8")
        recorded = []
        with patch.object(sys, "argv", [str(SCRIPT), str(self.source), "--out", str(self.out), "--json"]):
            with patch.object(m, "need", side_effect=recorded.append):
                with patch.object(m, "convert", side_effect=self.fake_convert):
                    with contextlib.redirect_stdout(io.StringIO()):
                        code = m.main()
        self.assertEqual(code, 0)
        self.assertEqual(recorded, ["docling"])

    def test_probe_only_does_not_require_docling(self):
        recorded = []
        with patch.object(sys, "argv", [str(SCRIPT), str(self.source), "--out", str(self.out),
                                        "--json", "--probe-only"]):
            with patch.object(m, "need", side_effect=recorded.append):
                with patch.object(m, "probe_pdf", return_value=self.probe()):
                    with patch.object(m, "convert", side_effect=self.fake_convert):
                        with contextlib.redirect_stdout(io.StringIO()):
                            code = m.main()
        self.assertEqual(code, 0)
        self.assertNotIn("docling", recorded)
        self.assertEqual(self.commands, [])

    def test_malformed_pdf_runtime_error(self):
        with patch.object(m, "run", side_effect=m.JobError("probe", "invalid_probe", "bad pdf")):
            code, report = self.cli(mock_probe=False)
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "invalid_probe")
        self.assertEqual(self.commands, [])

    def test_help_is_plain_argparse(self):
        stdout = io.StringIO()
        with patch.object(sys, "argv", [str(SCRIPT), "--help"]):
            with contextlib.redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as raised:
                    m.main()
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("usage:", stdout.getvalue())

    def test_json_help_is_one_report_in_either_order(self):
        for flags in (("--json", "--help"), ("-h", "--json")):
            with self.subTest(flags=flags):
                result = subprocess.run([sys.executable, str(SCRIPT), *flags],
                                        capture_output=True, text=True, check=True)
                report = json.loads(result.stdout)
                self.assertEqual(report["schema_version"], 1)
                self.assertEqual(report["status"], "help")
                self.assertEqual(report["exit_code"], 0)
                self.assertIn("usage:", report["help"])
                self.assertIsNone(report["output"])

    def test_human_usage_and_preflight_errors_reach_stderr(self):
        for flags, stage, expected in (([str(self.source), "--bad-option"], "usage", "unrecognized arguments"),
                                       ([str(self.root / "missing.pdf")], "preflight", "input not found")):
            with self.subTest(flags=flags):
                result = subprocess.run([sys.executable, str(SCRIPT), *flags],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn(stage, result.stderr)
                self.assertIn(expected, result.stderr)

    def test_uppercase_suffix_supported(self):
        self.source = self.root / "INPUT.PDF"
        self.source.write_bytes(b"fake")
        code, report = self.cli()
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "ok")

    def test_default_sample_filename(self):
        # the script resolves the input, so a derived default path is resolved too
        expected = self.source.resolve().parent / "input.sample.md"
        with patch.object(sys, "argv", [str(SCRIPT), str(self.source), "--sample-only", "--json"]):
            with patch.object(m, "need"):
                with patch.object(m, "probe_pdf", return_value=self.probe()):
                    with patch.object(m, "convert", side_effect=self.fake_convert):
                        out = io.StringIO()
                        with contextlib.redirect_stdout(out):
                            code = m.main()
        report = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(report["sample_md"], str(expected))
        self.assertTrue(expected.is_file())

    def test_explicit_ocr_override_recorded(self):
        code, report = self.cli("--ocr-mode", "full_page")
        self.assertEqual(code, 0)
        self.assertTrue(report["ocr_mode_override"]["explicit"])
        self.assertEqual(report["ocr_mode_override"]["value"], "full_page")
        command = self.commands[-1]
        self.assertEqual(command[command.index("--ocr-mode") + 1], "full_page")

    def test_heuristic_ocr_is_not_marked_explicit(self):
        stdout = io.StringIO()
        argv = [str(SCRIPT), str(self.source), "--out", str(self.out), "--json"]
        suspected = self.probe(flags=["amount-ampersand", "case-salad"], image=True)
        with patch.object(sys, "argv", argv), patch.object(m, "need"), \
                patch.object(m, "probe_pdf", return_value=suspected), \
                patch.object(m, "convert", side_effect=self.fake_convert), \
                contextlib.redirect_stdout(stdout):
            code = m.main()
        report = json.loads(stdout.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(report["decision"], "scan-suspect-layer")
        self.assertFalse(report["ocr_mode_override"]["explicit"])
        self.assertEqual(report["ocr_mode_override"]["value"], "full_page")
        command = self.commands[-1]
        self.assertEqual(command[command.index("--ocr-mode") + 1], "full_page")

    def test_warning_status_publishes_output(self):
        self.body = "Received. Thank you."
        code, report = self.cli()
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "warning")
        self.assertEqual(report["output"], str(self.out))


if __name__ == "__main__":
    unittest.main()
