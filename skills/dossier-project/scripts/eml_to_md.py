#!/usr/bin/env python3
"""Turn an exported .eml into the body of a correspondence note.

    python3 eml_to_md.py mail.eml            # markdown body on stdout
    python3 eml_to_md.py mail.eml --no-header

The body is the outer message's header block followed by the plain-text part
of the whole thread. The conversion normalises only the surface: the
mailto:/tel:/link annotations Outlook and Gmail append to plain text, trailing
and leading whitespace, bullet characters, runs of blank lines, the date
format of the header block, and the separation of quoted messages with `---`.
Message text is never shortened, reordered or merged.

Statistics — file checksum, message count, attachment checksums — go to
stderr, so `> body.md` keeps the body clean. The attachment checksums are the
point: they prove that the file attached to the mail is the one already stored
as a vault note.

Standard library only.
"""
from __future__ import annotations

import argparse
import email
import email.utils
import hashlib
import re
import sys
from email import policy

# Annotations the mail clients append to the plain-text part: <mailto:…>, <tel:…>,
# and bare URLs in angle brackets (Google Maps links follow every address).
ANNOTATION = re.compile(r"\s*<(?:mailto:[^<>]*|tel:[^<>]*|https?://[^<>]*)>")

HEADER_FIELDS = ("Von", "Gesendet", "An", "Betreff", "Cc")

# Where a quoted message starts: Outlook's "Von: …" or Gmail's "Am … schrieb …".
QUOTED_START = re.compile(r"^(?:Von: |Am \S.{0,60} schrieb )")

BULLET = re.compile(r"^[*-][ \t]+")

# Outlook writes "<olaf@pobox.com >" — the space before the bracket is not content.
ANGLE_SPACE = re.compile(r"(<[^<>]*) >")

# Angle brackets around an address become a mail autolink in Obsidian and a
# phantom entry in the broken-link report. The address stays, the brackets go.
ANGLE_MAIL = re.compile(r"<(\S[^<>\s]*@[^<>\s]*)>")

HEADER_KEYS = (
    ("Von", "From"),
    ("An", "To"),
    ("Cc", "Cc"),
    ("Datum", "Date"),
    ("Betreff", "Subject"),
    ("Message-ID", "Message-ID"),
)


def plain_text(msg):
    part = msg.get_body(preferencelist=("plain",))
    if part is None:
        raise SystemExit(
            "kein text/plain-Teil gefunden — Mail mit Textteil erneut exportieren "
            "oder den HTML-Teil von Hand umwandeln"
        )
    return part.get_content()


def normalise(text):
    """Return the thread as a list of markdown lines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    pending_blank = False
    for raw in text.split("\n"):
        line = ANGLE_MAIL.sub(r"\1", ANGLE_SPACE.sub(r"\1>", ANNOTATION.sub("", raw).strip()))
        if not line:
            pending_blank = True
            continue
        if pending_blank and out:
            out.append("")
        pending_blank = False
        if QUOTED_START.match(line) and out:
            if out[-1] != "":
                out.append("")
            out.extend(["---", ""])
        out.append(BULLET.sub("- ", line))
        # Quoted header blocks arrive as four consecutive lines; markdown would
        # join them into one line, so each gets a blank line after it.
        if line.startswith(tuple(f + ":" for f in HEADER_FIELDS)):
            out.append("")
    # collapse runs of blank lines, including the one the loop just added
    collapsed = []
    for line in out:
        if line == "" and collapsed and collapsed[-1] == "":
            continue
        collapsed.append(line)
    while collapsed and collapsed[-1] == "":
        collapsed.pop()
    return collapsed


def header_block(msg):
    rows = []
    for label, key in HEADER_KEYS:
        value = msg.get(key)
        if not value:
            continue
        if key == "Date":
            try:
                value = email.utils.parsedate_to_datetime(str(value)).strftime("%Y-%m-%d %H:%M:%S %z")
            except (TypeError, ValueError):
                pass
        rows.append(f"{label}: {ANGLE_MAIL.sub(r'\1', str(value))}")
    attached = [p.get_filename() for p in msg.walk() if p.get_filename() and not p.get("Content-ID")]
    if attached:
        rows.append("Anhang: " + ", ".join(attached))
    return rows


def attachments(msg):
    found = []
    for part in msg.walk():
        name = part.get_filename()
        if not name:
            continue
        payload = part.get_payload(decode=True) or b""
        found.append((
            name,
            part.get_content_type(),
            len(payload),
            hashlib.sha256(payload).hexdigest(),
            "eingebettet" if part.get("Content-ID") else "anhang",
        ))
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description="Exportierte .eml als Markdown-Body einer Korrespondenz-Notiz")
    ap.add_argument("eml", help="Pfad zur .eml-Datei")
    ap.add_argument("--no-header", action="store_true", help="Kopfblock der äußeren Nachricht weglassen")
    args = ap.parse_args(argv)

    raw = open(args.eml, "rb").read()
    msg = email.message_from_bytes(raw, policy=policy.default)
    body = normalise(plain_text(msg))

    lines = [] if args.no_header else header_block(msg) + [""]
    sys.stdout.write("\n".join(lines + body).rstrip() + "\n")

    print(f"datei       {args.eml}", file=sys.stderr)
    print(f"sha256      {hashlib.sha256(raw).hexdigest()}", file=sys.stderr)
    print(f"nachrichten {sum(1 for l in body if QUOTED_START.match(l)) + 1}", file=sys.stderr)
    print(f"zeichen     {len(chr(10).join(body))}", file=sys.stderr)
    for name, ctype, size, digest, kind in attachments(msg):
        print(f"{kind:11} {name} | {ctype} | {size} B | {digest}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
