"""
steps/step5_export.py — Convert book.md to PDF using ReportLab.
Clickable citation timestamps and reference links preserved in PDF.

Install: pip install reportlab
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import BOOK_DIR, BOOK_TITLE, BOOK_SUBTITLE


def clean_for_reportlab(text: str) -> str:
    """
    Convert a markdown paragraph to ReportLab XML markup.
    Preserves clickable hyperlinks for citation timestamps and references.

    Citation format in book.md:  [▶ 4:32](https://...&t=272)
    PDF output:                  clickable [4:32] in blue
    """
    # Step 1: escape XML special chars
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # Step 2: citation timestamp links
    # Matches: [▶ 4:32](url) or [4:32](url) — the ▶ may be encoded as &#9658;
    # After XML escaping, & becomes &amp; so &t=272 becomes &amp;t=272 in text
    # We need to un-escape the URL portion for the href attribute
    def make_timestamp_link(m):
        timestamp = m.group(1).strip()
        url       = m.group(2).replace('&amp;', '&')  # restore & in URL
        return f'<link href="{url}" color="#2563eb">[{timestamp}]</link>'

    # Match [▶ MM:SS](url) — ▶ is unicode U+25B6, may appear as literal or escaped
    text = re.sub(
        r'\[(?:▶|&#9658;|&amp;#9658;)?\s*([\d:]+)\]\(([^)]+)\)',
        make_timestamp_link,
        text
    )

    # Step 3: regular markdown links [label](url)
    def make_regular_link(m):
        label = m.group(1)
        url   = m.group(2).replace('&amp;', '&')
        return f'<link href="{url}" color="#2563eb">{label}</link>'

    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        make_regular_link,
        text
    )

    # Step 4: bold **text** → <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    # Step 5: inline code `text` → monospace
    text = re.sub(
        r'`([^`]+)`',
        r'<font name="Courier" size="9">\1</font>',
        text
    )

    # Step 6: strip any remaining non-latin-1 characters ReportLab can't handle
    # but preserve the XML tags we just added
    def safe_encode(s):
        return s.encode('latin-1', errors='replace').decode('latin-1')

    # Only encode the text parts, not the XML tags
    parts  = re.split(r'(<[^>]+>)', text)
    result = ''.join(p if p.startswith('<') else safe_encode(p) for p in parts)

    return result.strip()


def clean_plain(text: str) -> str:
    """Strip all markdown for headings/blockquotes where we don't want links."""
    text = re.sub(r'\[(?:▶|&#9658;)?\s*[\d:]+\]\([^)]+\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*',     r'\1', text)
    text = re.sub(r'`([^`]+)`',     r'\1', text)
    text = text.encode('latin-1', errors='replace').decode('latin-1')
    return text.strip()


def md_to_elements(md_text: str) -> list[dict]:
    """Parse markdown into typed elements."""
    elements = []
    lines    = md_text.splitlines()
    in_code  = False
    code_buf = []

    for line in lines:
        if line.startswith("```"):
            if in_code:
                elements.append({"type": "code", "text": "\n".join(code_buf)})
                code_buf = []
                in_code  = False
            else:
                in_code = True
            continue

        if in_code:
            code_buf.append(line)
            continue

        stripped = line.strip()

        if line.startswith("### "):
            elements.append({"type": "h3", "text": stripped[4:]})
        elif line.startswith("## "):
            elements.append({"type": "h2", "text": stripped[3:]})
        elif line.startswith("# "):
            elements.append({"type": "h1", "text": stripped[2:]})
        elif line.startswith("> "):
            elements.append({"type": "blockquote", "text": line[2:].strip()})
        elif stripped in ("---", "***", "___"):
            elements.append({"type": "hr"})
        elif re.match(r'^[-*] ', stripped):
            elements.append({"type": "bullet", "text": stripped[2:]})
        elif stripped:
            elements.append({"type": "p", "text": stripped})

    return elements


def run():
    print("\n" + "="*60)
    print("STEP 5: Export PDF (ReportLab)")
    print("="*60)

    md_path  = BOOK_DIR / "book.md"
    pdf_path = BOOK_DIR / "book.pdf"

    if not md_path.exists():
        print("ERROR: book.md not found. Run Step 4 first.")
        sys.exit(1)

    print(f"\n  Source : {md_path}")
    print(f"  Output : {pdf_path}\n")

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            HRFlowable, PageBreak, Preformatted,
        )
        from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
    except ImportError:
        print("ERROR: pip install reportlab")
        sys.exit(1)

    # ── Styles ────────────────────────────────────────────────────────────────
    base = getSampleStyleSheet()

    def S(name, **kw):
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    styles = {
        "h1": S("H1",
            fontName="Helvetica-Bold", fontSize=22, leading=28,
            spaceAfter=16, textColor=colors.HexColor("#111111")),
        "h2": S("H2",
            fontName="Helvetica-Bold", fontSize=15, leading=20,
            spaceBefore=0, spaceAfter=8,
            textColor=colors.HexColor("#1a1a1a")),
        "h3": S("H3",
            fontName="Helvetica-Bold", fontSize=12, leading=16,
            spaceBefore=12, spaceAfter=5,
            textColor=colors.HexColor("#333333")),
        "p": S("Body",
            fontName="Times-Roman", fontSize=11, leading=18,
            spaceAfter=7, alignment=TA_JUSTIFY),
        "blockquote": S("BQ",
            fontName="Times-Italic", fontSize=10, leading=15,
            spaceAfter=7, leftIndent=20,
            textColor=colors.HexColor("#444444")),
        "bullet": S("Bullet",
            fontName="Times-Roman", fontSize=11, leading=16,
            spaceAfter=4, leftIndent=20),
        "code": ParagraphStyle("Code",
            fontName="Courier", fontSize=8.5, leading=13,
            spaceAfter=8, spaceBefore=4,
            leftIndent=12, rightIndent=12,
            backColor=colors.HexColor("#f4f4f4")),
    }

    # ── Footer ────────────────────────────────────────────────────────────────
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#999999"))
        canvas.drawCentredString(A4[0] / 2.0, 1.2 * cm, str(canvas.getPageNumber()))
        canvas.restoreState()

    # ── Parse ─────────────────────────────────────────────────────────────────
    with open(md_path, encoding="utf-8") as f:
        md_text = f.read()

    elements = md_to_elements(md_text)
    print(f"  Parsed {len(elements)} elements from book.md")

    # ── Build story ───────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=3*cm, rightMargin=3*cm,
        topMargin=2.5*cm, bottomMargin=2.5*cm,
        title=BOOK_TITLE,
    )

    story    = []
    chap_num = 0

    for el in elements:
        t = el.get("type")
        try:
            if t == "h1":
                story.append(Paragraph(clean_plain(el["text"]), styles["h1"]))
                story.append(Spacer(1, 0.3*cm))

            elif t == "h2":
                if chap_num > 0:
                    story.append(PageBreak())
                chap_num += 1
                story.append(Paragraph(clean_plain(el["text"]), styles["h2"]))
                story.append(HRFlowable(
                    width="100%", thickness=0.5,
                    color=colors.HexColor("#aaaaaa"), spaceAfter=10))

            elif t == "h3":
                story.append(Paragraph(clean_plain(el["text"]), styles["h3"]))

            elif t == "p":
                # Use rich markup to preserve clickable timestamp links
                rich = clean_for_reportlab(el["text"])
                if rich:
                    story.append(Paragraph(rich, styles["p"]))

            elif t == "blockquote":
                text = clean_plain(el["text"])
                if text:
                    story.append(Paragraph(text, styles["blockquote"]))

            elif t == "bullet":
                text = clean_plain(el["text"])
                if text:
                    story.append(Paragraph(f"• {text}", styles["bullet"]))

            elif t == "code":
                code = el["text"].encode("ascii", errors="replace").decode("ascii")
                story.append(Preformatted(code, styles["code"]))

            elif t == "hr":
                story.append(Spacer(1, 0.15*cm))
                story.append(HRFlowable(
                    width="100%", thickness=0.3,
                    color=colors.HexColor("#dddddd")))
                story.append(Spacer(1, 0.15*cm))

        except Exception as exc:
            print(f"  Warning: skipped element ({t}): {exc}")
            continue

    if not story:
        print("ERROR: No content could be parsed from book.md")
        sys.exit(1)

    # ── Render ────────────────────────────────────────────────────────────────
    print(f"  Rendering {len(story)} elements...")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)

    size_kb = pdf_path.stat().st_size // 1024
    print(f"\nStep 5 done -- PDF exported ({size_kb} KB)")
    print(f"Output: {pdf_path}")


if __name__ == "__main__":
    run()