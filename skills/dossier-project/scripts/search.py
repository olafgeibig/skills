#!/usr/bin/env python3
"""search.py — deterministic candidate retrieval for a dossier-project.

    python3 search.py topic     <project-dir> --query "Gebührenbefreiung Frist"
    python3 search.py similar   <project-dir> --note "Beispielfall"
    python3 search.py chain     <project-dir> --note "cases/Beispielfall.md"
    python3 search.py calibrate <project-dir> --questions eval-questions.json

Three modes, one ranking. `topic` answers "what do we know about X", `similar`
answers "which earlier case or note is the same shape", `chain` walks the typed
edges (`sources:`, `cases:`, `dossier:`, `attachment:`) that the vault's link
table cannot tell apart. `calibrate` re-derives the fusion weights from a
question set with known answers, so the built-in numbers are a default with a
provenance, never a truth.

This script never writes and needs no server: it reads the project's markdown
the way check.py does, and imports the model and the frontmatter parser from
it. One model, one parser, no index that could drift.

Only stdlib.
"""

import argparse
import json
import math
import os
import re
import sys
import time
from datetime import date

import check

# --- the ranking, as declared numbers ---------------------------------------

# One place only. `calibrate` re-derives them; every output names the weights
# and where they came from, so a stale set is visible instead of silent.
DEFAULT_WEIGHTS = {
    "lexical": 1.0,     # BM25 over title, description and body
    "head": 0.6,        # query term inside ## Stand / ## Kurzfassung
    "centrality": 0.2,  # inbound links inside the project
    "recency": 0.2,     # how recently the note was touched
    "status": 0.1,      # blocked / open / draft / final / closed
}

STATUS_SIGNAL = {"blocked": 1.0, "open": 0.6, "draft": 0.6, "final": 1.0, "closed": 0.2}
STATUS_DEFAULT = 0.5

HEADINGS = {
    "case": ("Stand",),
    "dossier": ("Stand",),
    "extract": ("Kurzfassung",),
    "research": ("Kurzfassung",),
    "analysis": ("Kurzfassung",),
}
HEAD_FALLBACK = ("Kurzfassung", "Stand")

EDGE_FIELDS = ("sources", "cases", "dossier", "attachment", "topics")

TOKEN_RE = re.compile(r"[^\W_]+")
RECENCY_HALF_LIFE_DAYS = 90.0
BM25_K1, BM25_B = 1.5, 0.75


# --- corpus -----------------------------------------------------------------

def tokenize(text):
    return TOKEN_RE.findall(check.name_key(text))


def head_text(note):
    """The cheap version of a note: its curated head section, as text."""
    for heading in HEADINGS.get(note.type, HEAD_FALLBACK):
        span = check.section(note.body, heading)
        if span:
            start, end = span
            text = note.body[start:end]
            text = re.sub(r"^##\s+.+?\n", "", text, count=1)
            if text.strip():
                return text.strip()
    return ""


def _days_from_civil(y, m, d):
    """Days since 1970-01-01 — exact, no datetime needed."""
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def today_ordinal():
    return _days_from_civil(*time.localtime()[:3])


def normalise(values):
    top = max(values.values()) if values else 0
    if top <= 0:
        return {k: 0.0 for k in values}
    return {k: v / top for k, v in values.items()}


class Corpus:
    def __init__(self, notes, project=None):
        self.notes = sorted(notes, key=lambda n: n.rel)
        self.project = project
        self.by_stem = {}
        for n in self.notes:
            self.by_stem.setdefault(check.name_key(n.name), []).append(n)
        self.tokens, self.heads, self.updated = {}, {}, {}
        for n in notes:
            desc = n.fm.get("description")
            desc = desc if isinstance(desc, str) else ""
            head = head_text(n)
            body = n.body.replace(head, "", 1) if head else n.body
            self.heads[n.rel] = head
            self.tokens[n.rel] = (tokenize(n.name) * 3          # a title hit counts three times
                                  + tokenize(desc) * 2
                                  + tokenize(body))
            stamp = n.fm.get("updated")
            self.updated[n.rel] = stamp if isinstance(stamp, str) else (n.date or "")
        self.df = {}
        for toks in self.tokens.values():
            for t in set(toks):
                self.df[t] = self.df.get(t, 0) + 1
        self.avg_len = sum(len(t) for t in self.tokens.values()) / max(1, len(self.tokens))
        self.backlinks = self._backlinks()

    def _backlinks(self):
        """Inbound links inside the project — body and frontmatter alike, one per source."""
        counts = {n.rel: 0 for n in self.notes}
        for n in self.notes:
            for target in set(check.link_targets(n)):
                hits = self.by_stem.get(target, [])
                if len(hits) == 1 and hits[0].rel != n.rel:
                    counts[hits[0].rel] += 1
        return counts

    def idf(self, term):
        df = self.df.get(term, 0)
        return math.log(1 + (len(self.notes) - df + 0.5) / (df + 0.5))

    # --- signals; each is normalised over the candidate set before fusing ---

    def bm25(self, query_tokens, rel):
        toks = self.tokens.get(rel, [])
        if not toks or not query_tokens:
            return 0.0
        tf = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for term in sorted(set(query_tokens)):
            f = tf.get(term, 0)
            if not f:
                continue
            denom = f + BM25_K1 * (1 - BM25_B + BM25_B * len(toks) / self.avg_len)
            score += self.idf(term) * f * (BM25_K1 + 1) / denom
        return score

    def cosine(self, rel_a, rel_b):
        a, b = self.tokens.get(rel_a, []), self.tokens.get(rel_b, [])
        if not a or not b:
            return 0.0
        va, vb = {}, {}
        for t in a:
            va[t] = va.get(t, 0) + 1
        for t in b:
            vb[t] = vb.get(t, 0) + 1
        dot = sum(self.idf(t) ** 2 * va[t] * vb.get(t, 0) for t in va)
        if not dot:
            return 0.0
        na = math.sqrt(sum((self.idf(t) * va[t]) ** 2 for t in va))
        nb = math.sqrt(sum((self.idf(t) * vb[t]) ** 2 for t in vb))
        return dot / (na * nb) if na and nb else 0.0

    def head_hit(self, query_tokens, rel):
        head, query = self.heads.get(rel, ""), set(query_tokens or [])
        if not head or not query:
            return 0.0
        return len(query.intersection(tokenize(head))) / len(query)

    def recency(self, rel, today):
        stamp = self.updated.get(rel, "")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(stamp)):
            return 0.0
        try:
            y, m, d = date.fromisoformat(stamp).timetuple()[:3]
        except ValueError:
            return 0.0
        days = max(0, today - _days_from_civil(y, m, d))
        return 0.5 ** (days / RECENCY_HALF_LIFE_DAYS)

    @staticmethod
    def status(note):
        status = note.fm.get("status")
        return STATUS_SIGNAL.get(status, STATUS_DEFAULT) if isinstance(status, str) else STATUS_DEFAULT


# --- ranking ----------------------------------------------------------------

def rank(corpus, weights, query_tokens=None, reference=None, types=None, status=None, today=None):
    today = today if today is not None else today_ordinal()
    candidates = []
    for n in corpus.notes:
        if types and n.type not in types:
            continue
        if status and n.fm.get("status") != status:
            continue
        if reference is not None and n.rel == reference.rel:
            continue
        candidates.append(n)
    if not candidates:
        return []

    if reference is not None:
        rel = normalise({n.rel: corpus.cosine(reference.rel, n.rel) for n in candidates})
        head = {n.rel: 0.0 for n in candidates}
    else:
        rel = normalise({n.rel: corpus.bm25(query_tokens or [], n.rel) for n in candidates})
        head = normalise({n.rel: corpus.head_hit(query_tokens or [], n.rel) for n in candidates})
    candidates = [n for n in candidates if rel[n.rel] or head[n.rel]]
    cent = normalise({n.rel: float(corpus.backlinks.get(n.rel, 0)) for n in candidates})
    rec = normalise({n.rel: corpus.recency(n.rel, today) for n in candidates})
    stat = normalise({n.rel: corpus.status(n) for n in candidates})

    ranked = []
    for n in candidates:
        signals = {"lexical": rel[n.rel], "head": head[n.rel], "centrality": cent[n.rel],
                   "recency": rec[n.rel], "status": stat[n.rel]}
        score = sum(weights[k] * signals[k] for k in weights)
        ranked.append((round(score, 4), n, signals))
    ranked.sort(key=lambda row: (-row[0], row[1].rel))
    return ranked


# --- modes ------------------------------------------------------------------

def resolve(corpus, needle):
    if not needle:
        sys.exit("error: this mode needs --note")
    key = check.name_key(needle.strip())
    if "/" in key:
        if not key.endswith(".md"):
            key += ".md"
        prefix = "projects/" + os.path.basename(corpus.project or "") + "/"
        hits = [n for n in corpus.notes if key in (check.name_key(n.rel), check.name_key(prefix + n.rel))]
    else:
        hits = corpus.by_stem.get(key[:-3] if key.endswith(".md") else key, [])
    if len(hits) != 1:
        if hits:
            sys.exit("error: ambiguous note %r: %s" % (needle, ", ".join(n.rel for n in hits)))
        sys.exit("error: no note named %r in this project" % needle)
    return hits[0]


def cmd_topic(corpus, args):
    query_tokens = tokenize(args.query or "")
    if not query_tokens:
        sys.exit("error: topic needs --query")
    return rank(corpus, args.weights, query_tokens=query_tokens,
                types=_types(args), status=args.status)


def cmd_similar(corpus, args):
    """Same class by default: a case is compared to other cases, not to the
    letter that happens to be about it. Pass --type to override."""
    reference = resolve(corpus, args.note)
    types = _types(args) or ({reference.type} if reference.type else None)
    return rank(corpus, args.weights, reference=reference, types=types, status=args.status)


def cmd_chain(corpus, args):
    """Typed expansion: the field is the edge, which no single query can say."""
    start = resolve(corpus, args.note)
    def fields(n):
        result = {}
        for field, value in n.fm.items():
            links = [v for v in check.as_list(value)
                     if field in EDGE_FIELDS or check.text_targets(v)]
            if links:
                result[field] = links
        body = list(dict.fromkeys(re.findall(r"\[\[[^\[\]\r\n]+\]\]", n.body)))
        if body:
            result["body"] = result.get("body", []) + body
        return result

    incoming = {}
    for n in corpus.notes:
        if n.rel == start.rel:
            continue
        matched = [f for f, links in fields(n).items()
                   if check.name_key(start.name) in map(check.name_key, check.targets(links))]
        if matched:
            incoming[n.rel] = matched
    return {"note": start.rel, "type": start.type, "outgoing": fields(start), "incoming": incoming}


def _types(args):
    return {t.strip() for t in args.type.split(",") if t.strip()} if args.type else None


# --- calibrate --------------------------------------------------------------

VARIANTS = {
    "default": DEFAULT_WEIGHTS,
    "lexical only": {"lexical": 1.0, "head": 0.0, "centrality": 0.0, "recency": 0.0, "status": 0.0},
    "lexical+head": {"lexical": 1.0, "head": 0.6, "centrality": 0.0, "recency": 0.0, "status": 0.0},
    "+centrality": {"lexical": 1.0, "head": 0.6, "centrality": 0.3, "recency": 0.0, "status": 0.0},
    "+recency": {"lexical": 1.0, "head": 0.6, "centrality": 0.2, "recency": 0.3, "status": 0.0},
    "head heavy": {"lexical": 0.6, "head": 1.0, "centrality": 0.2, "recency": 0.2, "status": 0.1},
    "flat": {"lexical": 1.0, "head": 1.0, "centrality": 1.0, "recency": 1.0, "status": 1.0},
}


def cmd_calibrate(corpus, args):
    questions = read_json(args.questions, "questions")
    if not isinstance(questions, list) or not questions or any(
            not isinstance(item, dict) or not isinstance(item.get("q"), str) or not tokenize(item["q"])
            or not isinstance(item.get("expect"), list) or not item["expect"]
            or any(not isinstance(e, str) or not e.strip() for e in item["expect"])
            for item in questions):
        sys.exit('error: questions must be a non-empty JSON list of {"q": "query", "expect": ["note"]}')
    k = args.limit
    rows = []
    for name, weights in VARIANTS.items():
        hits, rr, misses = 0, 0.0, []
        for item in questions:
            ranked = rank(corpus, weights, query_tokens=tokenize(item["q"]))
            names = [check.name_key(r[1].name) for r in ranked[:k]]
            expect = [check.name_key(e) for e in item["expect"]]
            found = [e for e in expect if e in names]
            if found:
                hits += 1
                rr += 1.0 / (min(names.index(e) for e in found) + 1)
            else:
                misses.append(item["q"])
        rows.append((name, hits / max(1, len(questions)), rr / max(1, len(questions)), misses))
    if args.json:
        best = max(rows, key=lambda r: (r[1], r[2]))
        print(json.dumps({"limit": k, "questions": len(questions), "best": best[0],
                          "weights": VARIANTS[best[0]], "variants": [
                              {"name": name, "hit_rate": hit, "mrr": mrr, "misses": misses}
                              for name, hit, mrr, misses in rows]}, ensure_ascii=False, indent=2))
        return
    print("%-14s hit@%d  mrr   (n=%d)" % ("weights", k, len(questions)))
    for name, hit, mrr, _ in rows:
        print("%-14s %5.2f  %.2f" % (name, hit, mrr))
    best = max(rows, key=lambda r: (r[1], r[2]))
    print("\nbest: %s (hit@%d %.2f)" % (best[0], k, best[1]))
    print("weights: " + json.dumps(VARIANTS[best[0]], ensure_ascii=False))
    if best[3]:
        print("\nmisses under %s:" % best[0])
        for q in best[3]:
            print("  - " + q)


# --- output -----------------------------------------------------------------

def print_ranked(ranked, args, corpus, label):
    print("search: %s   scope: %s   %d notes" % (label, args.project, len(corpus.notes)))
    print("weights: %s — %s" % (args.weight_origin, " · ".join(
        "%s %s" % (k, v) for k, v in args.weights.items())))
    if not ranked:
        print("\nno candidate matched.")
        return
    for i, (score, note, signals) in enumerate(ranked[:args.limit], 1):
        print("\n%d  %.3f  %s" % (i, score, note.rel))
        print("   %s · %s · updated %s · %d backlinks"
              % (note.type, note.fm.get("status", "—"),
                 corpus.updated.get(note.rel) or "—", corpus.backlinks.get(note.rel, 0)))
        print("   " + " · ".join("%s %.2f" % (k, v) for k, v in signals.items()))
        desc = note.fm.get("description")
        if isinstance(desc, str) and desc:
            print("   " + desc)
        if i <= args.heads:
            head = " ".join(corpus.heads.get(note.rel, "").split())
            if head:
                if len(head) > args.head_chars:
                    head = head[:args.head_chars].rstrip() + " …"
                print("   > " + head)


def read_json(path, label):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        sys.exit("error: cannot read %s %s: %s" % (label, path, exc))


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("mode", choices=["topic", "similar", "chain", "calibrate"])
    ap.add_argument("project", help="the project directory (projects/<x>)")
    ap.add_argument("--query", help="free text (topic)")
    ap.add_argument("--note", help="reference note: project-relative path, vault-relative path or basename")
    ap.add_argument("--type", help="comma-separated types, e.g. case,analysis")
    ap.add_argument("--status", help="only notes with this status")
    ap.add_argument("--limit", type=int, default=5, help="results shown, and k for calibrate (default 5)")
    ap.add_argument("--heads", type=int, default=3, help="how many results show their head (default 3)")
    ap.add_argument("--head-chars", type=int, default=320, help="head excerpt length (default 320)")
    ap.add_argument("--weights", help="JSON file overriding the default weights")
    ap.add_argument("--questions", help="question set for calibrate")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()
    if args.limit < 1 or args.heads < 0 or args.head_chars < 0:
        ap.error("--limit must be positive; --heads and --head-chars must be non-negative")
    if args.type and (not _types(args) or _types(args) - check.ALL_TYPES):
        ap.error("--type must name known dossier types")

    args.project = os.path.abspath(args.project)
    if not os.path.isdir(args.project):
        sys.exit("error: not a directory: %s" % args.project)

    weights, origin = dict(DEFAULT_WEIGHTS), "default"
    if args.weights:
        loaded = read_json(args.weights, "weights")
        if not isinstance(loaded, dict):
            ap.error("--weights must contain a JSON object")
        unknown = sorted(set(loaded) - set(DEFAULT_WEIGHTS))
        if unknown:
            sys.exit("error: unknown weight(s): %s (known: %s)"
                     % (", ".join(unknown), ", ".join(DEFAULT_WEIGHTS)))
        try:
            if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in loaded.values()):
                raise ValueError
            weights.update({k: float(v) for k, v in loaded.items()})
        except (ValueError, OverflowError):
            ap.error("weights must be finite non-negative numbers")
        origin = "file %s" % args.weights
    args.weights, args.weight_origin = weights, origin

    corpus = Corpus(check.load_notes(args.project), args.project)

    if args.mode == "chain":
        result = cmd_chain(corpus, args)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        print("chain: %s (%s)" % (result["note"], result["type"]))
        for field, values in result["outgoing"].items():
            print("  → %-10s %s" % (field, ", ".join(values)))
        if result["incoming"]:
            print("  ← cited by")
            for rel, fields in sorted(result["incoming"].items()):
                print("      %-56s %s" % (rel, ", ".join(fields)))
        else:
            print("  ← cited by nothing in this project")
        return

    if args.mode == "calibrate":
        if not args.questions:
            sys.exit("error: calibrate needs --questions")
        cmd_calibrate(corpus, args)
        return

    ranked = cmd_topic(corpus, args) if args.mode == "topic" else cmd_similar(corpus, args)
    if args.json:
        print(json.dumps([{
            "score": score, "path": note.rel, "type": note.type,
            "status": note.fm.get("status"), "updated": corpus.updated.get(note.rel),
            "backlinks": corpus.backlinks.get(note.rel, 0),
            "signals": {k: round(v, 4) for k, v in signals.items()},
            "head": " ".join(corpus.heads.get(note.rel, "").split())[:args.head_chars],
        } for score, note, signals in ranked[:args.limit]], ensure_ascii=False, indent=2))
        return
    label = ('topic "%s"' % args.query) if args.mode == "topic" else ('similar to %s' % args.note)
    print_ranked(ranked, args, corpus, label)


if __name__ == "__main__":
    main()
