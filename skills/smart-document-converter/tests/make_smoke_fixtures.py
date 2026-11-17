"""Generate synthetic smoke fixtures for the smart converter.

Test tooling, not production parsing: synthetic text only, no originals and
no network. Base fixtures need nothing beyond the stdlib; --extended uses
Pillow and python-docx, which ship inside docling's tool venv:

    env -u PYTHONPATH -u PYTHONHOME \
        ~/.local/share/uv/tools/docling/bin/python make_smoke_fixtures.py RUN --extended
"""
import argparse
from pathlib import Path


def make_pdf(path, pages=3):
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    kids = []
    font_id = 3 + 2 * pages
    for page in range(pages):
        page_id = len(objects) + 1
        kids.append(f"{page_id} 0 R")
        objects.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                        f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
                        f"/Contents {page_id + 1} 0 R >>").encode())
        lines = [f"Dear recipient, this is page {page + 1} of a synthetic letter.",
                 "Please keep this document for your records and future reference.",
                 "We confirm receipt of your message and the requested documents.",
                 "The amount due is 123.45 EUR and the reference is TEST-2026.",
                 "This page deliberately contains ordinary prose without headings.",
                 "Kind regards, the synthetic document review team."]
        stream = ("BT /F1 11 Tf 50 790 Td 18 TL " +
                  " ".join(f"({line}) Tj T*" for line in lines) + " ET").encode()
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {pages} >>".encode()
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend((f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
                 f"startxref\n{start}\n%%EOF\n").encode())
    path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--extended", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    make_pdf(args.out / "letter.pdf")
    (args.out / "smoke.html").write_text(
        "<html><body><h1>Synthetic fixture</h1><h2>Details</h2>"
        "<p>We confirm receipt of your requested documents. The reference is "
        "TEST-2026 and the amount is 123.45 EUR. No private data.</p></body></html>",
        encoding="utf-8")
    if args.extended:
        from PIL import Image, ImageDraw, ImageFont
        from docx import Document
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 34)
        image = Image.new("RGB", (1654, 2339), "white")
        draw = ImageDraw.Draw(image)
        lines = ["Synthetic scan for local parser review", "Dear recipient, please keep this letter.",
                 "The amount due is 123.45 EUR.", "The reference is TEST-2026.",
                 "We confirm receipt of your documents.", "No private information is present."]
        for index, line in enumerate(lines):
            draw.text((120, 160 + index * 65), line, fill="black", font=font)
        image.save(args.out / "scan.pdf", resolution=200)
        doc = Document()
        doc.add_heading("Synthetic Word fixture", 0)
        doc.add_heading("Details", 1)
        doc.add_paragraph("We confirm receipt of your documents. Reference TEST-2026; "
                          "amount 123.45 EUR. This is synthetic data for local review.")
        doc.save(args.out / "smoke.docx")
    print(args.out.resolve())


if __name__ == "__main__":
    main()
