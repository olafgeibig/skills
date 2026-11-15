#!/usr/bin/env python3
"""selftest.py — the skill's own regression suite. No dependencies, no network.

    python3 selftest.py            # all scenarios
    python3 selftest.py -k yaml    # only scenarios whose name contains "yaml"

It builds a throwaway vault in a temp directory, instantiates every template from
`assets/`, and runs `check.py` against it. Nothing outside the temp directory is
read or written. Exit code 0 = all green.

The scenarios exist because each one was a real defect: relations lost to a YAML
comment, headings inside a code fence, one case name swallowing another, a
preview that could not be reviewed, a hand-written line proposed for deletion.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
ASSETS = os.path.join(SKILL, "assets")
CHECK = os.path.join(HERE, "check.py")

MARK = "<!-- GENERIERT — nicht von Hand bearbeiten. -->"

VALUES = {
    "{{Projekt}}": "Demo",
    "{{Dossier}}": "nachlass",
    "{{Fall}}": "grundbuch",
    "{{x}}": "demo",
    "{{action}}": "@computer",
    "{{kurz-id}}": "a1",
    "{{YYYY-MM-DD}}": "2026-11-14",
    "{{12}}": "12",
    "{{34}}": "34",
    "{{Fakt}}": "Fakt",
    "{{raw-Notiz}}": "20261103-bescheid",
    "{{raw-Version, die verwendet wurde}}": "20261103-bescheid",
    "{{Pfad oder URL des Originals}}": "https://example.org/bescheid",
    "{{Prüfsumme des Originals}}": "deadbeef",
    "{{Titel}}": "Titel",
    "{{Thema}}": "Versicherung",
    "{{Gegenstand}}": "Nachlass",
    "{{Was geschah}}": "Telefonat",
    "{{Was der Fall ist — eine Zeile}}": "Grundbuch",
    "{{Was geschehen ist und was daraus folgt — eine Zeile}}": "Telefonat",
    "{{Was das für ein Dokument ist und von wem — eine Zeile}}": "Bescheid",
    "{{Was das für ein Dokument ist — eine Zeile}}": "Antrag",
    "{{Die wesentlichen Fakten aus der Quelle — eine Zeile}}": "Auszug",
    "{{Welche Frage recherchiert wurde und was die Antwort ist — eine Zeile}}": "Recherche",
    "{{Die Frage und die Antwort — eine Zeile}}": "Analyse",
    "{{Der Gegenstand und was daran laufend gilt — eine Zeile}}": "Nachlass",
    "{{Welches Thema diese Sammlung abdeckt — eine Zeile}}": "Versicherung",
}

PLACEMENT = [
    ("template-case.md", "cases/grundbuch.md"),
    ("template-dossier.md", "dossiers/nachlass.md"),
    ("template-event.md", "events/20261114-grundbuch-telefonat.md"),
    ("template-artifact.md", "artifacts/20261112-grundbuch-antrag.md"),
    ("template-document.md", "raw/20261103-bescheid.md"),
    ("template-extract.md", "resources/bescheid-auszug.md"),
    ("template-research.md", "resources/recherche-wohnrecht.md"),
    ("template-analysis.md", "analyses/20261114-verkehrswert.md"),
    ("template-masterdata.md", "masterdata/versicherung.md"),
    ("template-task-hub.md", "Demo Aufgaben.md"),
]

ROUTER = """---
description: Router
type: moc
topics:
- '[[INDEX]]'
---
# Demo
"""

EVENTS_OK = (
    "## Ereignisse\n\n" + MARK + "\n\n"
    "- 2026-11-14 · event · [[20261114-grundbuch-telefonat]] · Telefonat\n"
    "- 2026-11-12 · artifact · [[20261112-grundbuch-antrag]] · Antrag\n"
    "- 2026-11-03 · document · [[20261103-bescheid]] · Bescheid\n"
)
FAELLE_OK = "## Fälle\n\n" + MARK + "\n\n- [[grundbuch]] · open\n"


class Vault:
    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="dossier-selftest-")
        self.write("AGENTS.md", "# vault\n")
        self.write("projects/demo/AGENTS.md", "Shape: notes only (B)\n")
        self.write("projects/demo/+Demo.md", ROUTER)

    def write(self, rel, text):
        p = os.path.join(self.root, rel) if not rel.startswith("projects/") else os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def path(self, rel):
        return os.path.join(self.root, "projects/demo", rel)

    def read(self, rel):
        with open(self.path(rel), encoding="utf-8") as fh:
            return fh.read()

    def patch(self, rel, old, new):
        cur = self.read(rel)
        assert old in cur, "fixture text not found in %s: %r" % (rel, old[:60])
        self.write_note(rel, cur.replace(old, new, 1))

    def write_note(self, rel, text):
        target = self.path(rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(text)

    def run(self, *args):
        r = subprocess.run([sys.executable, CHECK] + list(args) + ["projects/demo"],
                           cwd=self.root, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def build_templates(self):
        for name, rel in PLACEMENT:
            with open(os.path.join(ASSETS, name), encoding="utf-8") as fh:
                text = fh.read()
            for k, v in VALUES.items():
                text = text.replace(k, v)
            text = re.sub(r"\{\{[^}]*\}\}", "Platzhalter", text)
            left = re.findall(r"\{\{[^}]*\}\}", text)
            assert not left, "%s still holds placeholders: %s" % (name, left[:3])
            self.write_note(rel, text)

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


RESULTS = []


def expect(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print("  %s  %s%s" % ("PASS" if cond else "FAIL", name,
                          "" if cond else "\n        " + str(detail)[:600]))


def findings(out):
    """The message column of a REPORT / AUDIT listing."""
    return [l.split(None, 1)[1] if len(l.split(None, 1)) > 1 else l
            for l in out.splitlines() if l.startswith("  ") and "·" not in l[:4]]


# --- scenarios ---------------------------------------------------------------

def t_templates(v):
    """Every template, instantiated as written, must pass the check."""
    v.build_templates()
    code, out = v.run("--report")
    kinds = [l for l in out.splitlines() if "stale" in l]
    others = [l for l in out.splitlines()
              if l.startswith("  ") and "stale" not in l and "finding" not in l and "vocabulary" not in l]
    expect("templates: only the two generated sections are reported", len(kinds) == 2 and not others,
           out)
    expect("templates: no type/folder/heading complaint", "not allowed" not in out and "missing required" not in out,
           out)


def t_clean(v):
    """With the generated sections correct, the report is clean."""
    v.build_templates()
    v.patch("cases/grundbuch.md", "## Ereignisse\n\n" + MARK + "\n", EVENTS_OK.rstrip("\n") + "\n")
    v.patch("dossiers/nachlass.md", "## Fälle\n\n" + MARK + "\n", FAELLE_OK.rstrip("\n") + "\n")
    code, out = v.run("--report")
    expect("clean report on the hand-built fixture", code == 0 and "clean" in out, out)


def t_yaml(v):
    """Relations must survive a YAML comment — trailing, inline, and after a list."""
    v.build_templates()
    v.patch("cases/grundbuch.md", "## Ereignisse\n\n" + MARK + "\n", EVENTS_OK.rstrip("\n") + "\n")
    v.patch("dossiers/nachlass.md", "## Fälle\n\n" + MARK + "\n", FAELLE_OK.rstrip("\n") + "\n")
    for variant in ("cases:  # der Fall\n- '[[grundbuch]]'\n",
                    "cases:\n- '[[grundbuch]]'   # gehört dazu\n",
                    "cases:\n  - '[[grundbuch]]'\n  # Notiz\n"):
        v.write_note("events/20261114-zweites.md",
                     "---\ndescription: Telefonat\ntype: event\n" + variant +
                     "topics:\n- '[[+Demo]]'\n---\n\n# Telefonat\n\nInhalt.\n")
        code, out = v.run("--report")
        expect("yaml variant keeps the relation: %r" % variant.splitlines()[0].strip(),
               code == 1 and "cases/grundbuch.md" in out
               and "3 row(s) present, 4 expected" in out, out)
        code, out = v.run("--rebuild")
        expect("yaml variant: the event is proposed as a row, none removed",
               "+- 2026-11-14 · event · [[20261114-zweites]]" in out
               and "-- 2026-11" not in out, out)


def t_headings(v):
    """A `## ` inside a fence or an HTML comment is not a section."""
    v.build_templates()
    # the only "## Aufgaben" left is inside a code fence
    v.patch("cases/grundbuch.md", "## Aufgaben\n\n- [ ] 🆔 a1 Platzhalter #@computer",
            "```\n## Aufgaben\n- [ ] Beispiel\n```")
    # a case whose only "## Stand" sits in an HTML comment
    v.write_note("cases/zwei.md",
                 "---\ndescription: Zwei\ntype: case\nstatus: open\ndossier: '[[nachlass]]'\n---\n\n"
                 "# Zwei\n\n<!--\n## Stand\n-->\n\n## Ereignisse\n\n" + MARK + "\n\n## Aufgaben\n")
    code, out = v.run("--report")
    expect("a fenced heading is not a heading", "missing required heading: ## Aufgaben" in out, out)
    expect("a commented heading is not a heading", "missing required heading: ## Stand" in out, out)
    body = v.read("cases/grundbuch.md")
    expect("fenced text left alone in the file", "## Aufgaben\n- [ ] Beispiel" in body)


def t_substring(v):
    """One case name must not swallow another."""
    v.build_templates()
    v.write_note("cases/fallzwei.md",
                 "---\ndescription: Zweiter Fall\ntype: case\nstatus: open\ndossier: '[[nachlass]]'\n"
                 "topics:\n- '[[+Demo]]'\n---\n\n# FallZwei\n\n## Stand\n\nx\n\n" + EVENTS_OK.replace(
                     "20261114 · event · [[20261114-grundbuch-telefonat]] · Telefonat",
                     "20261115 · event · [[20261115-fallzwei-anruf]] · Anruf") + "\n## Aufgaben\n")
    v.write_note("events/20261115-fallzwei-anruf.md",
                 "---\ndescription: Anruf\ntype: event\ncases:\n- '[[fallzwei]]'\ntopics:\n- '[[+Demo]]'\n---\n\n"
                 "# Anruf\n\nInhalt.\n")
    code, out = v.run("--rebuild")
    section = out.split("=== cases/grundbuch.md")[1].split("===")[0] if "=== cases/grundbuch.md" in out else ""
    expect("FallZwei's event does not appear under Fall", "fallzwei-anruf" not in section, section)


def t_new_section(v):
    """A missing generated section must be reviewable: content and place."""
    v.build_templates()
    v.patch("cases/grundbuch.md", "## Ereignisse\n\n" + MARK + "\n", "")
    code, out = v.run("--rebuild")
    expect("new section shows its insertion point", "inserted before" in out, out)
    expect("new section shows its content", "+ - 2026-11-14 · event" in out and MARK in out, out)


def t_refusals(v):
    """Hand-written text in a generated section is refused, never proposed away."""
    v.build_templates()
    v.patch("cases/grundbuch.md", "## Aufgaben\n",
            "## Aufgaben\n\n- [ ] von Hand\n")
    v.patch("cases/grundbuch.md", "## Ereignisse\n\n" + MARK + "\n", EVENTS_OK.rstrip("\n") + "\n- [ ] Task, falsch einsortiert\n")
    code, out = v.run("--rebuild")
    expect("foreign content is refused", "REFUSED" in out, out)
    expect("the refusal names the line", "falsch einsortiert" in out, out)
    expect("nothing is claimed to be written", "nothing written" in out.lower() or "nothing to change" in out.lower(), out)
    code, out = v.run("--report")
    expect("report names the section", "not a generated row" in out, out)

    v.build_templates()
    v.patch("cases/grundbuch.md", MARK + "\n", "")
    code, out = v.run("--rebuild")
    expect("missing marker is refused, not guessed", "REFUSED" in out, out)


def t_readonly(v):
    """The rebuild must not touch a single byte."""
    v.build_templates()
    before = {rel: v.read(rel) for _, rel in PLACEMENT}
    v.run("--rebuild")
    v.run("--report")
    v.run("--audit")
    after = {rel: v.read(rel) for _, rel in PLACEMENT}
    expect("--rebuild/--report/--audit write nothing", before == after)


def t_source(v):
    """Provenance stays optional even if an original is on another machine."""
    v.build_templates()
    v.write_note("raw/20261201-url.md",
                 "---\ndescription: Aus dem Netz\ntype: document\nsource: https://example.org/x\n"
                 "cases:\n- '[[grundbuch]]'\n---\n\n# Aus dem Netz\n\nText.\n")
    code, out = v.run("--report")
    expect("URL source needs no sha256", "20261201-url" not in out, out)
    v.write_note("raw/20261202-pfad.md",
                 "---\ndescription: Vom Rechner\ntype: document\nsource: /home/olaf/original.pdf\n"
                 "cases:\n- '[[grundbuch]]'\n---\n\n# Vom Rechner\n\nText.\n")
    code, out = v.run("--report")
    expect("a path without a checksum is accepted", "20261202-pfad" not in out, out)
    v.write_note("raw/20261203-fern.md",
                 "---\ndescription: Auf anderer Maschine\ntype: document\n"
                 "source: /home/olaf/remote/x.pdf\nsha256: abc\ncases:\n- '[[grundbuch]]'\n---\n\n# Fern\n\nText.\n")
    code, out = v.run("--report")
    expect("an unreachable path with a checksum is fine", "20261203-fern" not in out, out)


def t_sources_render(v):
    """The footer must reproduce `sources:` — anchors kept, URLs not turned into links."""
    v.build_templates()
    v.patch("cases/grundbuch.md", "## Ereignisse\n\n" + MARK + "\n", EVENTS_OK.rstrip("\n") + "\n")
    v.patch("dossiers/nachlass.md", "## Fälle\n\n" + MARK + "\n", FAELLE_OK.rstrip("\n") + "\n")
    v.write_note("resources/mit-anker.md",
                 "---\ndescription: Anker\ntype: extract\nsources:\n- '[[20261103-bescheid#Frist|Frist]]'\n"
                 "dossier: '[[nachlass]]'\n---\n\n# Anker\n\n## Kurzfassung\n\nx\n\n## Fakten\n\n- y\n")
    v.write_note("analyses/mit-url.md",
                 "---\ndescription: Netz\ntype: analysis\nstatus: draft\nsources:\n- https://example.org/a/b?c=1\n"
                 "dossier: '[[nachlass]]'\n---\n\n# Netz\n\n## Kurzfassung\n\nx\n\n## Analyse\n\nx\n\n## Ergebnis\n\nx\n")
    code, out = v.run("--rebuild")
    expect("an anchored link keeps its anchor and label",
           "[[20261103-bescheid#Frist|Frist]]" in out and "[[20261103-bescheid]]" not in out, out)
    expect("a URL in sources: stays a URL, not a wikilink",
           "https://example.org/a/b?c=1" in out and "[[b?c=1]]" not in out, out)


def t_sources_exact(v):
    """Footer comparison must be exact: no substring hits, no unnoticed extras."""
    v.build_templates()
    v.patch("cases/grundbuch.md", "## Ereignisse\n\n" + MARK + "\n", EVENTS_OK.rstrip("\n") + "\n")
    v.patch("dossiers/nachlass.md", "## Fälle\n\n" + MARK + "\n", FAELLE_OK.rstrip("\n") + "\n")
    v.write_note("resources/alpha.md",
                 "---\ndescription: Alpha\ntype: extract\nsources:\n- '[[Alpha]]'\ndossier: '[[nachlass]]'\n"
                 "---\n\n# Alpha\n\n## Kurzfassung\n\nx\n\n## Fakten\n\n- y\n\n---\n\nQuellen:\n- [[AlphaExtended]]\n")
    code, out = v.run("--report")
    expect("a longer name is not a hit for a shorter one", "missing [[Alpha]]" in out, out)
    expect("an unlisted extra footer entry is reported", "not in `sources:`" in out, out)


def t_apostrophe(v):
    """An apostrophe in a link target must not break the relation."""
    v.build_templates()
    v.patch("cases/grundbuch.md", "## Ereignisse\n\n" + MARK + "\n", EVENTS_OK.rstrip("\n") + "\n")
    v.patch("dossiers/nachlass.md", "## Fälle\n\n" + MARK + "\n", FAELLE_OK.rstrip("\n") + "\n")
    v.write_note("events/20261116-bei-obrien.md",
                 "---\ndescription: Bei O'Brien\ntype: event\ncases:\n- '[[O''Brien]]'\n---\n\n# O'Brien\n\nx\n")
    v.write_note("cases/O'Brien.md",
                 "---\ndescription: O'Brien\ntype: case\nstatus: open\ndossier: '[[nachlass]]'\n---\n\n"
                 "# O'Brien\n\n## Stand\n\nx\n\n## Ereignisse\n\n" + MARK + "\n\n## Aufgaben\n")
    code, out = v.run("--report")
    expect("relation with an apostrophe is read",
           code == 1 and "cases/O'Brien.md" in out
           and "0 row(s) present, 1 expected" in out, out)
    code, out = v.run("--rebuild")
    expect("its row is proposed, not removal", "+- 2026-11-16 · event · [[20261116-bei-obrien]]" in out, out)
    v.write_note("events/20261116-invalid.md",
                 "---\ntype: event\ncases:\n- '[[O'Brien]]'\n---\n# Invalid YAML\n")
    code, out = v.run("--rebuild")
    expect("malformed quoted relationship refuses preview", code != 0 and "error:" in out
           and "20261116-invalid.md" in out and "Traceback" not in out and "=== " not in out, out)


def t_bad_child(v):
    """A child with an unknown type must block the preview, never shrink the list."""
    v.build_templates()
    v.patch("cases/grundbuch.md", "## Ereignisse\n\n" + MARK + "\n", EVENTS_OK.rstrip("\n") + "\n")
    v.patch("dossiers/nachlass.md", "## Fälle\n\n" + MARK + "\n", FAELLE_OK.rstrip("\n") + "\n")
    v.write_note("events/20261117-tippfehler.md",
                 "---\ndescription: Tippfehler\ntype: even\ncases:\n- '[[grundbuch]]'\n---\n\n# Tippfehler\n\nx\n")
    code, out = v.run("--rebuild")
    expect("unknown child type blocks the preview", "REFUSED" in out and "does not know" in out, out)
    expect("no row is proposed for removal", "-- 2026-11" not in out, out)


def t_dossier_row(v):
    """A hand-written line starting with a link is not a generated row."""
    v.build_templates()
    v.patch("cases/grundbuch.md", "## Ereignisse\n\n" + MARK + "\n", EVENTS_OK.rstrip("\n") + "\n")
    v.patch("dossiers/nachlass.md", "## Fälle\n\n" + MARK + "\n",
            FAELLE_OK.rstrip("\n") + "\n- [[Hinweis]] · Bitte zuerst lesen\n")
    code, out = v.run("--rebuild")
    expect("hand-written line in ## Fälle is refused", "REFUSED" in out, out)
    expect("and named", "Hinweis" in out, out)
    expect("the existing row is not dropped", "-- [[grundbuch]]" not in out, out)


def t_regressions(v):
    """Previously reproduced CLI failures, tested independently of templates."""
    v.write_note("analyses/20261115-netz.md",
                 "---\ntype: analysis\nstatus: draft\nsources:\n- https://example.org/study\n---\n"
                 "# Netz\n\n## Kurzfassung\n\nx\n\n## Analyse\n\nx\n\n## Ergebnis\n\nx\n\n"
                 "Quellen:\n- https://example.org/study\n")
    code, out = v.run("--report")
    expect("URL-only analysis is valid", code == 0 and "clean" in out, out)

    v.write_note("cases/fall.md",
                 "---\ntype: case\nstatus: open\n---\n# Fall\n\n## Stand\n\nx\n\n"
                 "## Ereignisse\n\n" + MARK + "\n\n"
                 "- 2026-11-15 · event · [[20261115-anruf]] · Anruf\n\n## Aufgaben\n")
    v.write_note("events/20261115-anruf.md",
                 "---\ntype: utility\ndescription: Anruf\ncases:\n- '[[fall]]'\n---\n# Anruf\n")
    code, out = v.run("--rebuild")
    expect("wrong but known child type blocks its parent", code != 0 and "REFUSED" in out
           and "-- 2026-11-15 · event · [[20261115-anruf]]" not in out, out)

    v.write_note("resources/evidence.md",
                 "---\ntype: extract\nsources:\n- '[[Alpha]]'\n---\n# Evidence\n\n"
                 "## Kurzfassung\n\nx\n\n## Fakten\n\nx\n\nQuellen:\n- [[Alpha]]\n"
                 "- [ ] Handwritten: preserve me\n")
    code, out = v.run("--rebuild")
    expect("handwritten footer content is refused", code != 0 and "REFUSED resources/evidence.md" in out
           and "-- [ ] Handwritten" not in out, out)

    v.write_note("analyses/20261116-final.md",
                 "---\ntype: analysis\nstatus: final\nsources:\n- '[[Raw]]'\n---\n# Final\n\n"
                 "## Kurzfassung\n\nx\n\n## Analyse\n\nx\n\n## Ergebnis\n\nx\n\n"
                 "Quellen:\n- [[Old]]\n")
    code, out = v.run("--rebuild")
    expect("final analysis is not proposed for revision", code != 0 and "REFUSED analyses/20261116-final.md" in out
           and "-- [[Old]]" not in out, out)

    v.write_note("cases/bad-status.md",
                 "---\ntype: case\nstatus: [open]\n---\n# Bad\n\n## Stand\n\nx\n\n"
                 "## Ereignisse\n\n" + MARK + "\n\n## Aufgaben\n")
    code, out = v.run("--report")
    expect("invalid status is a finding, not a traceback", code != 0 and "status:" in out
           and "invalid for case" in out and "Traceback" not in out, out)


def t_preview_safety(v):
    """The preview must expose byte differences and refuse ambiguous footers."""
    v.write_note("resources/eof.md",
                 "---\ntype: extract\nsources:\n- '[[Alpha]]'\n---\n# Evidence\n\n"
                 "## Kurzfassung\n\nx\n\n## Fakten\n\nx\n\nQuellen:\n- [[Alpha]]")
    code, out = v.run("--rebuild")
    expect("a missing final newline is shown in the diff", code == 0
           and "No newline at end of file" in out and "--- current" in out, out)
    v.write_note("resources/eof.md",
                 "---\ntype: extract\nsources:\n- '[[Alpha]]'\n---\n# Evidence\n\n"
                 "## Kurzfassung\n\nx\n\n## Fakten\n\nx\n\nQuellen:\n- [[Alpha]]\n\n"
                 "## Notes\n\nHandwritten context\n")
    code, out = v.run("--rebuild")
    expect("a footer with later prose is refused, not duplicated", code != 0
           and "REFUSED resources/eof.md" in out and "(new section)" not in out, out)


def t_review_safety(v):
    """Guard wrong dossier children, ambiguous footers and broken frontmatter."""
    v.write_note("dossiers/subject.md",
                 "---\ntype: dossier\n---\n# Subject\n\n## Stand\n\nx\n\n## Wissen\n\n"
                 "## Dokumente\n\n## Fälle\n\n" + MARK + "\n\n- [[matter]] · open\n\n## Aufgaben\n")
    v.write_note("cases/matter.md",
                 "---\ntype: event\ndossier: '[[subject]]'\n---\n# Wrong child type\n")
    code, out = v.run("--rebuild")
    expect("a wrong-type case child blocks its dossier", code != 0 and "REFUSED dossiers/subject.md" in out
           and "-- [[matter]] · open" not in out, out)

    v.write_note("resources/ambiguous.md",
                 "---\ntype: extract\nsources: ['[[Alpha]]']\n---\n# E\n\n## Kurzfassung\n\nx\n\n"
                 "## Fakten\n\nx\n\nQuellen:\n- [[Alpha]]\n- [[Alpha]] read together with [[Beta]]\n")
    code, out = v.run("--rebuild")
    expect("a sentence between links is not a footer row", code != 0 and "REFUSED resources/ambiguous.md" in out
           and "-- [[Alpha]] read together" not in out, out)

    v.write_note("events/20261115-broken.md",
                 "---\ntype: event\ncases:\n- '[[matter]]'\n# missing closing delimiter\n")
    code, out = v.run("--rebuild")
    expect("unclosed frontmatter aborts the preview", code != 0 and "error:" in out
           and "20261115-broken.md" in out and "=== " not in out and "Traceback" not in out, out)


def t_crlf(v):
    """CRLF notes and the old/new diff retain their real line endings."""
    text = ("---\ntype: extract\nsources: ['[[Alpha]]']\n---\n# E\n\n"
            "## Kurzfassung\n\nx\n\n## Fakten\n\nx\n\nQuellen:\n- [[Old]]\n")
    v.write_note("resources/crlf.md", text)
    raw = text.replace("\n", "\r\n").encode("utf-8")
    with open(v.path("resources/crlf.md"), "wb") as fh:
        fh.write(raw)
    result = subprocess.run([sys.executable, CHECK, "--rebuild", "projects/demo"],
                            cwd=v.root, capture_output=True)
    with open(v.path("resources/crlf.md"), "rb") as fh:
        unchanged = fh.read() == raw
    expect("CRLF footer diff preserves old and new line endings", result.returncode == 0 and unchanged
           and b'-- [[Old]]\r\n' in result.stdout and b'+- [[Alpha]]\r\n' in result.stdout,
           result.stdout.decode("utf-8", errors="replace"))


SCENARIOS = [
    ("review-safety", t_review_safety),
    ("crlf", t_crlf),
    ("preview-safety", t_preview_safety),
    ("regressions", t_regressions),
    ("templates", t_templates),
    ("clean", t_clean),
    ("yaml", t_yaml),
    ("headings", t_headings),
    ("substring", t_substring),
    ("new-section", t_new_section),
    ("refusals", t_refusals),
    ("readonly", t_readonly),
    ("source", t_source),
    ("sources-render", t_sources_render),
    ("sources-exact", t_sources_exact),
    ("apostrophe", t_apostrophe),
    ("bad-child", t_bad_child),
    ("dossier-row", t_dossier_row),
]


def main():
    want = None
    if len(sys.argv) > 2 and sys.argv[1] == "-k":
        want = sys.argv[2]
    print("selftest — %s" % SKILL)
    for name, fn in SCENARIOS:
        if want and want not in name:
            continue
        print("\n[%s]" % name)
        v = Vault()
        try:
            fn(v)
        except AssertionError as e:
            expect("%s crashed" % name, False, e)
        finally:
            v.close()
    bad = [r for r in RESULTS if not r[1]]
    print("\n%d checks, %d failed" % (len(RESULTS), len(bad)))
    if bad:
        for name, _, detail in bad:
            print("  FAILED: %s" % name)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())