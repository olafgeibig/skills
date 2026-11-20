#!/usr/bin/env python3
"""check.py — shape, completeness and generated sections for a dossier-project.

    python3 check.py --report  <project-dir>   # hard findings, exit 1 on any
    python3 check.py --audit   <project-dir>   # what a human has to decide
    python3 check.py --rebuild <project-dir>   # propose the changes, write nothing

This script never writes. `--rebuild` prints a unified diff of every generated
section that would change and stops; the write happens afterwards, through
TurboVault, on the user's approval of exactly those bytes.

Only stdlib. Frontmatter is read with a small parser that accepts what vault
notes actually use: block lists at any indentation (including column 0), inline
lists, quoted scalars.
"""

import argparse
import difflib
import json
import os
import re
import sys
import unicodedata

# --- the model, as code -----------------------------------------------------

FOLDER_TYPES = {
    "inbox": set(),                       # no frontmatter expected at all
    "raw": {"document", "transcript"},
    "resources": {"extract", "research"},
    "analyses": {"analysis"},
    "dossiers": {"dossier"},
    "cases": {"case"},
    "events": {"event"},
    "artifacts": {"artifact"},
    "masterdata": {"masterdata"},
    "utility": {"utility"},
}

ROOT_TYPES = {"utility", "moc"}           # allowed directly in the project root
NOT_NOTES = {"AGENTS.md", "conventions.md", "README.md", "INDEX.md"}

REQUIRED_HEADINGS = {
    "case": ["Stand", "Ereignisse", "Aufgaben"],
    "dossier": ["Stand", "Wissen", "Dokumente", "Fälle", "Aufgaben"],
    "extract": ["Kurzfassung", "Fakten"],
    "research": ["Kurzfassung", "Befunde"],
    "analysis": ["Kurzfassung", "Analyse", "Ergebnis"],
}

STATUS_VALUES = {
    "case": {"open", "blocked", "closed"},
    "analysis": {"draft", "final"},
}

ALL_TYPES = set().union(*FOLDER_TYPES.values(), ROOT_TYPES)
CHILD_TYPES = {"event", "artifact", "document", "transcript", "extract", "research", "analysis"}
EVENT_ROWS = {"event", "artifact", "document", "transcript"}   # what ## Ereignisse lists
FOCUS_TYPES = set(ALL_TYPES) - {"utility", "moc"}

DATE_PREFIX = re.compile(r"^(\d{4})-?(\d{2})-?(\d{2})")
UNKNOWN_DATE = "????-??-??"
TASK_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[[^\]\r\n]\](?:\s|$)")
LINK_RE = re.compile(r"\[\[([^\]|#]+)")


def name_key(text):
    return unicodedata.normalize("NFC", text.casefold())


# --- reading ----------------------------------------------------------------

class Note:
    __slots__ = ("path", "rel", "folder", "name", "fm", "body", "raw", "stem")

    def __init__(self, path, rel, raw):
        self.path = path
        self.rel = rel
        self.raw = raw
        self.folder = os.path.basename(os.path.dirname(path))
        self.name = os.path.basename(path)[:-3]
        self.stem = self.name
        self.fm, self.body = parse_frontmatter(raw)

    @property
    def type(self):
        v = self.fm.get("type")
        return v if isinstance(v, str) else None

    @property
    def date(self):
        """The date this note contributes to a chronology, or None.

        Only the filename carries it: the prefix is the date on the document,
        the day of the happening or the day of dispatch. `created:` is never
        used — it says when the note was written, not when the thing happened.
        """
        return date_from_name(self.name)


def parse_frontmatter(raw):
    opening = re.match(r"\A---[ \t]*\r?\n", raw)
    if not opening:
        return {}, raw
    tail = raw[opening.end():]
    closing = re.search(r"^---[ \t]*\r?$", tail, re.M)
    if not closing:
        raise ValueError("frontmatter opening delimiter has no closing delimiter")
    block = tail[:closing.start()].splitlines()
    body = tail[closing.end():]
    fm, key = {}, None
    for line in block:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        top = not line[:1].isspace()
        if top:
            m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
            if m:
                key, val = m.group(1), strip_comment(m.group(2))
                if val == "":
                    fm[key] = []
                elif val.startswith("["):
                    if not val.endswith("]"):
                        raise ValueError("unterminated inline list for %s" % key)
                    fm[key] = [clean(v) for v in split_inline(val) if v.strip()]
                else:
                    fm[key] = clean(val)
                continue
        # list item: indented OR at column 0 (both occur in this vault)
        m = re.match(r"^\s*-\s+(.*)$", line)
        if m and key is not None:
            if not isinstance(fm.get(key), list):
                fm[key] = [] if fm.get(key) in (None, "") else [fm[key]]
            fm[key].append(clean(strip_comment(m.group(1))))
    return fm, body


def strip_comment(val):
    """Remove YAML comments outside quoted scalars, including inline lists."""
    v = val.strip()
    quote, i = None, 0
    while i < len(v):
        ch = v[i]
        if quote:
            if quote == "'" and ch == "'" and i + 1 < len(v) and v[i + 1] == "'":
                i += 2
                continue
            if quote == '"' and ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'" and (i == 0 or v[:i].rstrip().endswith(("[", ","))):
            quote = ch
        elif ch == "#" and (i == 0 or v[i - 1].isspace()):
            return v[:i].rstrip()
        i += 1
    if quote:
        raise ValueError("unterminated quoted scalar")
    return v


def split_inline(val):
    out, buf, quote, i = [], "", None, 1
    while i < len(val) - 1:
        ch = val[i]
        if quote:
            buf += ch
            if quote == "'" and ch == "'" and i + 1 < len(val) - 1 and val[i + 1] == "'":
                buf += val[i + 1]
                i += 1
            elif quote == '"' and ch == "\\" and i + 1 < len(val) - 1:
                buf += val[i + 1]
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "\"'" and not buf.strip():
            quote = ch
            buf += ch
        elif ch == ",":
            out.append(buf)
            buf = ""
        else:
            buf += ch
        i += 1
    if quote:
        raise ValueError("unterminated quoted scalar in inline list")
    out.append(buf)
    return out


def clean(v):
    """Decode supported YAML scalars, refusing malformed quoted values."""
    v = v.strip()
    if v.startswith("'"):
        if len(v) < 2 or not v.endswith("'") or "'" in v[1:-1].replace("''", ""):
            raise ValueError("invalid single-quoted scalar")
        return v[1:-1].replace("''", "'")
    if v.startswith('"'):
        try:
            return json.loads(v)
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid or unsupported double-quoted scalar") from exc
    return v


def as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return [x for x in v if x]
    return [v] if v else []


def is_url(value):
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", str(value).strip()))


def targets(values):
    """Identity: `[[a/b#c|label]]` -> `b` (the file stem). URLs are not notes."""
    out = []
    for v in as_list(values):
        if is_url(v):
            continue
        m = re.match(r"^\[\[([^\]|#]+)", str(v))
        ref = (m.group(1) if m else str(v)).strip()
        out.append(ref.split("/")[-1])
    return [t for t in out if t]


def render_source(value):
    """How one `sources:` entry appears in the footer — lossless.

    A URL stays a URL (it is the only evidence for `research`), and an internal
    link keeps its anchor and label: `[[Bericht#Frist|Frist]]` shortened to
    `[[Bericht]]` would point somewhere else.
    """
    v = str(value).strip()
    if is_url(v) or (v.startswith("[[") and v.endswith("]]")):
        return v
    return "[[%s]]" % v


def footer_lines(note):
    """What the note's `Quellen:` footer currently lists, verbatim."""
    fb = footer_block(note.body)
    if fb is None:
        return None
    return [l.strip()[2:].strip()
            for l in note.body[fb[0]:fb[1]].splitlines()[1:] if l.strip().startswith("- ")]


def date_from_name(name):
    m = DATE_PREFIX.match(name)
    if not m:
        return None
    return "-".join(m.groups())


FENCE = re.compile(r"^\s*(```|~~~)")


def scan(body):
    """[(line, visible)] — invisible inside fenced code and HTML comments."""
    out, in_fence, in_comment = [], False, False
    for ln in body.splitlines():
        st = ln.strip()
        vis = True
        if in_fence:
            vis = False
            if FENCE.match(ln):
                in_fence = False
        elif in_comment:
            vis = False
            if "-->" in st:
                in_comment = False
        elif FENCE.match(ln):
            vis = False
            in_fence = True
        elif st.startswith("<!--"):
            vis = False
            if "-->" not in st:
                in_comment = True
        out.append((ln, vis))
    return out


def headings(body):
    """`## ` headings that are neither in a fence nor in an HTML comment."""
    out = []
    for line, vis in scan(body):
        if not vis:
            continue
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            out.append(m.group(1))
    return out


def section(body, heading):
    """(start, end) of a `## heading` block outside fences and comments, or None."""
    raw = body.splitlines(keepends=True)
    offsets, pos = [], 0
    for ln in raw:
        offsets.append(pos)
        pos += len(ln)
    vis_flags = [v for _, v in scan(body)]
    start = None
    for i, ln in enumerate(raw):
        if not vis_flags[i]:
            continue
        m = re.match(r"^##\s+(.+?)\s*$", ln.rstrip("\n"))
        if m and m.group(1) == heading:
            start = offsets[i]
            continue
        if m and start is not None:
            return start, offsets[i]
    if start is None:
        return None
    return start, len(body)


def footer_block(body):
    """(start, end) of a trailing `Quellen:` block, or None.

    Only a `Quellen:` label followed exclusively by list items counts — a
    `Quellen:` mentioned in prose must never be replaced.
    """
    lines = body.splitlines(keepends=True)
    visible = [v for _, v in scan(body)]
    idx = None
    for i, ln in enumerate(lines):
        if visible[i] and re.match(r"^Quellen:\s*$", ln.rstrip("\n")):
            idx = i
    if idx is None:
        return None
    for ln in lines[idx + 1:]:
        s = ln.strip()
        if not s or re.match(r"^-\s+", s):
            continue
        return None                       # something else follows — not a footer
    start = sum(len(x) for x in lines[:idx])
    return start, len(body)


def footer_problems(note, block):
    """Reject ambiguous or handwritten footer content, not just tasks."""
    labels = [line for line, visible in scan(note.body)
              if visible and re.match(r"^Quellen:\s*$", line)]
    if block is None:
        return ["existing Quellen: is not a trailing list; preserve its content"] if labels else []
    if len(labels) != 1:
        return ["multiple Quellen: labels are ambiguous"]
    bad = []
    for value in footer_lines(note) or []:
        wikilink = bool(re.fullmatch(r"\[\[[^\[\]\r\n]+\]\]", value))
        url = is_url(value) and not any(ch.isspace() for ch in value)
        if not (wikilink or url):
            bad.append(value)
    return bad


# --- discovering ------------------------------------------------------------

def find_vault_root(project):
    cur = os.path.abspath(project)
    while cur != os.path.dirname(cur):
        if os.path.isfile(os.path.join(cur, "AGENTS.md")) and os.path.isdir(os.path.join(cur, "projects")):
            return cur
        cur = os.path.dirname(cur)
    sys.exit("error: no vault root found above %s (needs AGENTS.md and projects/)" % project)


def load_notes(project_dir):
    notes = []
    for dirpath, dirnames, filenames in os.walk(project_dir):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for f in filenames:
            if not f.endswith(".md") or f in NOT_NOTES:
                continue
            p = os.path.join(dirpath, f)
            try:
                with open(p, encoding="utf-8", newline="") as fh:
                    notes.append(Note(p, os.path.relpath(p, project_dir), fh.read()))
            except (UnicodeDecodeError, ValueError) as exc:
                sys.exit("error: cannot read %s: %s" % (os.path.relpath(p, project_dir), exc))
    return notes


def vault_basenames(root):
    seen = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != ".turbovault"]
        for f in filenames:
            if f.endswith(".md") and f not in NOT_NOTES:
                seen.setdefault(name_key(f[:-3]), []).append(os.path.relpath(os.path.join(dirpath, f), root))
    return {k: v for k, v in seen.items() if len(v) > 1}


def link_targets(note):
    """Every note this one points at — body links and frontmatter links alike.

    Only *notes* count as sources: conventions.md and AGENTS.md are not parsed,
    so they can never be the reason a raw or artifact note looks reachable.
    """
    return text_targets(note.raw)


def text_targets(text):
    return [name_key(t.strip().split("/")[-1]) for t in LINK_RE.findall(text)]


def vault_stems(root):
    """Every note name in the vault, lowercased — what a parent link may resolve to."""
    seen = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != ".turbovault"]
        for f in filenames:
            if f.endswith(".md") and f not in NOT_NOTES:
                seen.add(name_key(f[:-3]))
    return seen


def row(note):
    return "- %s · %s · [[%s]]%s" % (
        note.date or UNKNOWN_DATE,
        note.type,
        note.name,
        (" · " + note.fm["description"]) if isinstance(note.fm.get("description"), str) else "",
    )


def valid_child_folder(note):
    """A linked child must be a class note in its direct class folder."""
    folder = os.path.dirname(note.rel)
    return note.type in FOLDER_TYPES.get(folder, set())


def names_parent(child, field, parent):
    return name_key(parent.stem) in map(name_key, targets(child.fm.get(field)))


def children(note, notes):
    """(rows, uninterpretable) for a parent note.

    A child that names this note as its parent but carries a type that cannot be
    a child here is *not* silently dropped: dropping it would make the rebuild
    propose the removal of a row that still belongs, which is the one mistake
    this section must not make.
    """
    rows, odd = [], []
    if note.type == "case":
        for c in notes:
            if not names_parent(c, "cases", note):
                continue
            # Working knowledge is cited in ## Stand, not listed as an event: an
            # extract, research or analysis has a date, but it is not something
            # that happened to the matter.
            if c.type in CHILD_TYPES and c.type not in EVENT_ROWS:
                continue
            if (c.type not in CHILD_TYPES | {"case"}) or not valid_child_folder(c):
                odd.append((c.rel, c.type))
            else:
                rows.append(row(c))
        return sorted(rows, reverse=True), odd
    if note.type == "dossier":
        for c in notes:
            if not names_parent(c, "dossier", note):
                continue
            if c.type is None or c.type not in ALL_TYPES:
                odd.append((c.rel, c.type))
            elif not valid_child_folder(c) and (os.path.dirname(c.rel) or c.type not in ROOT_TYPES):
                odd.append((c.rel, c.type))
            elif c.type == "case":
                status = c.fm.get("status")
                if not valid_child_folder(c) or not isinstance(status, str) or status not in STATUS_VALUES["case"]:
                    odd.append((c.rel, c.type))
                else:
                    desc = c.fm.get("description")
                    desc = " ".join(desc.split()) if isinstance(desc, str) else ""
                    desc = desc.replace("|", "\\|") or "—"
                    rows.append("| [[%s]] | %s | %s |" % (c.name, status, desc))
        return sorted(rows), odd
    return [], []


def expected(note, notes):
    """The rows a parent's generated section must contain."""
    return children(note, notes)[0]


def current_rows(note):
    head = "Ereignisse" if note.type == "case" else "Fälle"
    sec = section(note.body, head)
    if sec is None:
        return None
    if head == "Fälle":
        return [l.strip() for l in note.body[sec[0]:sec[1]].splitlines()
                if l.strip().startswith("| [[")]
    return [l.strip() for l in note.body[sec[0]:sec[1]].splitlines() if l.strip().startswith("- ")]


GEN_MARK = re.compile(r"^<!--\s*generiert\b", re.I)
ROW_CASE = re.compile(r"^- (?:\d{4}-\d{2}-\d{2}|" + re.escape(UNKNOWN_DATE) +
                      r") · (?:" + "|".join(sorted(CHILD_TYPES | {"case"})) +
                      r") · \[\[[^\]]+\]\](?: · .*)?$")
ROW_DOSSIER = re.compile(r"^\| \[\[[^\]]+\]\] \| (?:open|blocked|closed) \| .+ \|$")
TABLE_HEAD = ["| Fall | Status | Worum es geht |", "| --- | --- | --- |"]


def gen_prefix(head):
    """The fixed lines a generated section opens with, after the marker."""
    return TABLE_HEAD if head == "Fälle" else []


def row_re(head):
    return ROW_CASE if head == "Ereignisse" else ROW_DOSSIER


def gen_state(note, head):
    """('missing' | 'unmarked' | 'foreign' | 'ok', offending lines).

    A generated section is only ours when the first non-blank line is the marker
    and every following line is a generated row. Without the marker the author is
    unknown, so nothing is proposed; a line that is not a row is somebody's text,
    so the section is refused rather than rewritten.
    """
    sec = section(note.body, head)
    if sec is None:
        return "missing", []
    lines = [l.strip() for l in note.body[sec[0]:sec[1]].splitlines()[1:] if l.strip()]
    if not lines or not GEN_MARK.match(lines[0]):
        return "unmarked", lines[:3]
    rest = lines[1:]
    pre = gen_prefix(head)
    if pre and rest:
        if rest[:len(pre)] != pre:
            return "foreign", rest[:3]
        rest = rest[len(pre):]
    bad = [l for l in rest if not row_re(head).match(l)]
    return ("foreign", bad) if bad else ("ok", [])


def stale(note, notes):
    """(expected, current, section) when the generated section disagrees."""
    if note.type not in ("case", "dossier"):
        return None
    want = expected(note, notes)
    have = current_rows(note)
    head = "Ereignisse" if note.type == "case" else "Fälle"
    if have is None:
        return want, None, head
    if have != want:
        return want, have, head
    return None


# --- report -----------------------------------------------------------------

def report(notes, root, project_dir):
    bad = []
    known = vault_stems(root)
    pointed_at = {}
    for n in notes:
        for t in link_targets(n):
            pointed_at.setdefault(t, set()).add(n.rel)
    # Reachability only says something once the project has an entry point.
    has_entry = any(n.type == "moc" for n in notes)

    for n in notes:
        if n.folder == "inbox":
            if n.fm:
                bad.append((n.rel, "inbox/ must hold markdown without frontmatter"))
            continue
        if n.type is None:
            bad.append((n.rel, "no type: — classify it (inbox/ is the place for unclassified notes)"))
            continue
        if n.type not in ALL_TYPES:
            bad.append((n.rel, "type: %r is not a kind type" % n.type))
            continue
        allowed = FOLDER_TYPES.get(n.folder)
        if allowed is None:
            if n.folder == os.path.basename(os.path.abspath(project_dir)):
                if n.type not in ROOT_TYPES:
                    bad.append((n.rel, "type: %s is not allowed in the project root (only %s)"
                                % (n.type, ", ".join(sorted(ROOT_TYPES)))))
            else:
                bad.append((n.rel, "folder %r is not a dossier-project folder" % n.folder))
            continue
        if n.type not in allowed:
            bad.append((n.rel, "type: %s not allowed in %s/ (allowed: %s)"
                        % (n.type, n.folder, ", ".join(sorted(allowed)) or "none")))

        for h in REQUIRED_HEADINGS.get(n.type, []):
            if h not in headings(n.body):
                bad.append((n.rel, "missing required heading: ## %s" % h))

        if n.type in STATUS_VALUES:
            st = n.fm.get("status")
            if not isinstance(st, str) or st not in STATUS_VALUES[n.type]:
                bad.append((n.rel, "status: %r invalid for %s (expected %s)"
                            % (st, n.type, " | ".join(sorted(STATUS_VALUES[n.type])))))

        has_task = n.type in ("masterdata", "dossier") and any(
            TASK_RE.match(line) for line, visible in scan(n.body) if visible)
        if n.type == "masterdata" and (has_task or "Aufgaben" in headings(n.body)):
            bad.append((n.rel, "masterdata must not carry tasks — they belong to a case"))

        if n.type == "dossier":
            if has_task:
                bad.append((n.rel, "a dossier must not carry a task — a task is the decision to "
                                   "act, and the matter it belongs to is a case"))

        if n.type == "case" and not targets(n.fm.get("dossier")):
            bad.append((n.rel, "case without dossier: — a case belongs to exactly one subject"))

        if n.type in CHILD_TYPES and not targets(n.fm.get("cases")) \
                and not targets(n.fm.get("dossier")):
            bad.append((n.rel, "orphan: neither cases: nor dossier: — the parent must be able "
                               "to find it"))

        if n.type == "event" and not targets(n.fm.get("cases")):
            bad.append((n.rel, "event without a case — a happening too small for a case is a "
                               "sentence in ## Stand, not an event"))

        for key in ("cases", "dossier"):
            for t in targets(n.fm.get(key)):
                if name_key(t) not in known:
                    bad.append((n.rel, "%s: names [[%s]], and no note of that name exists in "
                                       "the vault" % (key, t)))

        if has_entry and n.type in ("document", "transcript", "artifact") \
                and not pointed_at.get(name_key(n.stem)):
            bad.append((n.rel, "evidence nothing points at — a document or artifact no note "
                               "refers to is invisible; cite it from its case"))

        if n.type in ("masterdata", "dossier"):
            for h in headings(n.body):
                if h.lower().startswith(("erledigt", "verlauf")):
                    bad.append((n.rel, "no history on a %s (## %s) — what was done lives in "
                                       "the case, what changed in ## Stand" % (n.type, h)))

        if n.type in ("extract", "analysis") and not as_list(n.fm.get("sources")):
            bad.append((n.rel, "no sources: — the evidence link is the point of the class"))

        if n.type in ("extract", "analysis"):
            want = [render_source(v) for v in as_list(n.fm.get("sources"))]
            have = footer_lines(n) or []
            missing = [w for w in want if w not in have]
            extra = [h for h in have if h not in want]
            if missing:
                bad.append((n.rel, "`Quellen:` is missing %s — the footnote is where a reader "
                                   "looks for the evidence" % ", ".join(missing)))
            if extra:
                bad.append((n.rel, "`Quellen:` lists %s, which is not in `sources:`"
                            % ", ".join(extra)))

        if n.type in ("document", "transcript", "event", "artifact") and not n.date:
            bad.append((n.rel, "filename carries no YYYYMMDD prefix — a chronology note without "
                               "its date cannot be placed"))

        if n.type in ("case", "dossier"):
            head0 = "Ereignisse" if n.type == "case" else "Fälle"
            state0, fl = gen_state(n, head0)
            if state0 == "unmarked":
                bad.append((n.rel, "## %s lacks the generated marker — a section whose author is "
                                   "unknown is never rebuilt" % head0))
            elif state0 == "foreign":
                bad.append((n.rel, "## %s holds text that is not a generated row — move it out, "
                                   "the rebuild will not overwrite it" % head0))

        st = stale(n, notes)
        if st is not None:
            want, have, head = st
            if have is None:
                bad.append((n.rel, "## %s is missing — run --rebuild and review the proposal" % head))
            else:
                bad.append((n.rel, "## %s is stale (%d row(s) present, %d expected) — run --rebuild"
                            % (head, len(have), len(want))))

    proj = os.path.abspath(project_dir)
    for name, paths in vault_basenames(root).items():
        if any(os.path.commonpath((proj, os.path.join(root, p))) == proj
               for p in paths):
            bad.append((name, "duplicate basename in the vault" +
                        (" — " + " | ".join(paths) if len(paths) < 5 else "")))

    if bad:
        print("REPORT — %d finding(s)\n  kind vocabulary: %s"
              % (len(bad), ", ".join(sorted(ALL_TYPES))))
        for rel, msg in bad:
            print("  %-58s %s" % (rel, msg))
        return 1
    print("REPORT — clean (%d notes)" % len(notes))
    return 0


# --- audit ------------------------------------------------------------------

def tasks_scope(project_path):
    path = re.sub(r"([/\\.^$*+?{}\[\]|()])", r"\\\1", project_path)
    return r"path regex matches /^" + path + r"\/cases\//"


def task_blocks(body):
    """Top-level Tasks fences, not examples inside other fences or comments."""
    fence, block, comment = None, None, False
    for line in body.splitlines():
        if fence:
            if re.fullmatch(r" {0,3}" + fence[0] + "{%d,}[ \t]*" % len(fence), line):
                if block is not None:
                    yield block
                fence, block = None, None
            elif block is not None:
                block.append(line.strip())
        elif comment or line.lstrip().startswith("<!--"):
            comment = "-->" not in line
        else:
            m = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
            if m:
                fence = m.group(1)
                block = [] if m.group(2).strip() == "tasks" else None


def audit(notes, project_dir, root):
    out = []

    pointed_at = {}
    for n in notes:
        for t in link_targets(n):
            pointed_at.setdefault(t, set()).add(n.rel)

    for n in notes:
        if n.type not in ("document", "transcript", "artifact") \
                and not pointed_at.get(name_key(n.stem)):
            out.append((n.rel, "no incoming link — nothing in the project points here; link it "
                               "from its case, its dossier or the router"))
        if n.type == "case" and n.fm.get("status") == "blocked":
            out.append((n.rel, "blocked — confirm that ## Stand names the blocker"))
        if n.type == "dossier":
            w, d = section(n.body, "Wissen"), section(n.body, "Dokumente")
            empty = (lambda s: not (s and "[[" in n.body[s[0]:s[1]]))
            kids = [c for c in notes if c is not n and (
                names_parent(c, "dossier", n) or names_parent(c, "cases", n))]
            if empty(w) and empty(d) and kids:
                out.append((n.rel, "## Wissen and ## Dokumente are empty while %d note(s) point here"
                            % len(kids)))

    if not any(n.type in FOCUS_TYPES for n in notes):
        out.append(("<project>", "no note carries a kind type — this project is not on the "
                                 "dossier-project model yet"))
    hubs = [(n, block) for n in notes if not os.path.dirname(n.rel) and n.type in ROOT_TYPES
            for block in task_blocks(n.body)]
    if len(hubs) != 1 or hubs[0][0].type != "utility":
        out.append(("<root>", "expected exactly one task hub (utility) with one tasks block at the project root"))
    else:
        hub, block = hubs[0]
        scope = tasks_scope(os.path.relpath(project_dir, root))
        if scope not in block:
            out.append((hub.rel, "task hub must use the exact cases/ subtree: " + scope))

    if out:
        print("AUDIT — %d item(s) for a human" % len(out))
        for rel, msg in out:
            print("  %-58s %s" % (rel, msg))
    else:
        print("AUDIT — nothing missing")
    return 0


# --- rebuild: propose, then apply -------------------------------------------

def plan(notes, blocked=None):
    """[(note, head, old_block, new_block)] for every section that differs.

    A generated section that contains anything but rows is never rewritten; it is
    reported through `blocked` instead, because that content is not ours to drop.
    """
    if blocked is None:
        blocked = []
    out = []
    for n in notes:
        newline = "\r\n" if "\r\n" in n.raw else "\n"
        if n.type in ("case", "dossier"):
            rows, odd = children(n, notes)
            head = "Ereignisse" if n.type == "case" else "Fälle"
            block = "\n".join(gen_prefix(head) + rows)
            new = ("## %s\n\n<!-- GENERIERT — nicht von Hand bearbeiten. -->\n\n%s\n\n" % (
                head, block)).replace("\n", newline)
            state, bad = gen_state(n, head)
            if odd:
                blocked.append((n.rel, head,
                                ["%s carries type: %r, which the model does not know or does not "
                                 "allow in that folder or parent — fix it first" % (rel, ty)
                                 for rel, ty in odd]))
            elif state == "missing":
                out.append((n, head, None, new))
            elif state != "ok":
                blocked.append((n.rel, head, bad or ["(no marker)"]))
            else:
                sec = section(n.body, head)
                old = n.body[sec[0]:sec[1]]
                if old != new:
                    out.append((n, head, old, new))
        if n.type in ("extract", "analysis"):
            srcs = [render_source(v) for v in as_list(n.fm.get("sources"))]
            if not srcs:
                continue
            block = ("Quellen:\n" + "\n".join("- %s" % s for s in srcs) + "\n").replace("\n", newline)
            fb = footer_block(n.body)
            problems = footer_problems(n, fb)
            old = None if fb is None else n.body[fb[0]:fb[1]]
            if problems:
                blocked.append((n.rel, "Quellen:", problems))
            elif old != block and n.type == "analysis" and n.fm.get("status") == "final":
                blocked.append((n.rel, "Quellen:", ["final analysis is frozen; do not rewrite its footer"]))
            elif old != block:
                out.append((n, "Quellen:", old, block))
    return out


def insertion(note, head):
    """Where a new section goes: before the next required heading that exists."""
    order = REQUIRED_HEADINGS.get(note.type, [])
    present = headings(note.body)
    if head in order:
        for nxt in order[order.index(head) + 1:]:
            if nxt in present:
                return "inserted before `## %s`" % nxt
    return "appended at the end of the note"


def rebuild(notes, project_dir):
    blocked = []
    changes = plan(notes, blocked)
    for rel, head, lines in blocked:
        print("REFUSED %s — ## %s holds content that is not a generated row:" % (rel, head))
        for l in lines[:4]:
            print("          %s" % l[:96])
    if blocked and not changes:
        print("\nREBUILD — nothing written; resolve the sections above by hand")
        return 1
    if not changes:
        print("REBUILD — nothing to change")
        return 0

    for n, head, old, new in changes:
        label = " (new section)" if old is None else ""
        print("\n=== %s — ## %s%s ===" % (n.rel, head, label))
        if old is None:
            print(insertion(n, head))
            for line in new.splitlines(keepends=True):
                if line.endswith(("\n", "\r")):
                    print("+ " + line, end="")
                else:
                    print("+ " + line)
                    print("\\ No newline at end of file")
        else:
            for line in difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                             "current", "proposed", lineterm="\n", n=1):
                if line.endswith("\n"):
                    print(line, end="")
                else:
                    print(line)
                    print("\\ No newline at end of file")

    print("REBUILD — %d note(s) would change. Nothing written. Review the proposal, then "
          "apply it through TurboVault after approval." % len(changes))
    return 1 if blocked else 0



# --- main -------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Shape, completeness and generated sections "
                                             "for a dossier-project.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--report", action="store_true", help="hard findings, exit 1 on any")
    g.add_argument("--audit", action="store_true", help="what a human has to decide")
    g.add_argument("--rebuild", action="store_true", help="propose the generated sections, write nothing")
    ap.add_argument("project", help="project directory, e.g. projects/example")
    a = ap.parse_args()

    project_dir = a.project.rstrip("/")
    if not os.path.isdir(project_dir):
        sys.exit("error: %s is not a directory" % project_dir)
    root = find_vault_root(project_dir)
    notes = load_notes(project_dir)

    if a.report:
        return report(notes, root, project_dir)
    if a.audit:
        return audit(notes, project_dir, root)
    return rebuild(notes, project_dir)


if __name__ == "__main__":
    sys.exit(main())