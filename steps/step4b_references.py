"""
steps/step4b_references.py — Extract references using Groq (llama-3.1-8b-instant).

Uses a small fast model -- reference extraction doesn't need 120B parameters.
Chunking: paragraph-based, never cuts mid-sentence.
Deduplication: groups by normalized paper title, merges concepts.

Install: pip install groq
Add to .env: GROQ_API_KEY=...
"""

import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

from groq import Groq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CHAPTERS_DIR, BOOK_DIR, GROQ_API_KEY, LLM_DELAY_SEC

# Small model for reference extraction -- low token usage, stays within free limits
GROQ_REF_MODEL = "llama-3.1-8b-instant"
MAX_CHARS      = 30_000

REFERENCE_PROMPT = """You are a technical editor reviewing a section of a book chapter about building LLMs.

Identify every concept or technique that corresponds to a known published paper.

Output each reference in EXACTLY this format (one per line, nothing else):
CONCEPT: ConceptName | PAPER: Paper Title | AUTHORS: Author(s) | YEAR: Year | URL: https://arxiv.org/abs/...

Rules:
- Only list references you are highly confident about
- Do NOT invent paper titles, authors, or URLs
- If unsure of the URL, write URL: unknown
- Focus on: Transformer architecture, attention mechanism, tokenization, training techniques,
  model architectures (GPT, BERT etc.), loss functions, optimizers, named algorithms
- If no references found, output nothing

Text to scan:
"""


def chunk_by_paragraphs(text, max_chars):
    """Split at paragraph boundaries -- never mid-sentence."""
    paragraphs = text.split("\n\n")
    chunks  = []
    current = []
    cur_len = 0
    for para in paragraphs:
        para_len = len(para)
        if cur_len + para_len > max_chars and current:
            chunks.append("\n\n".join(current))
            current = [para]
            cur_len = para_len
        else:
            current.append(para)
            cur_len += para_len
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def call_groq(client, chunk):
    response = client.chat.completions.create(
        model=GROQ_REF_MODEL,
        messages=[{"role": "user", "content": REFERENCE_PROMPT + chunk}],
        temperature=0.0,
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()


def parse_line(line):
    try:
        parts = {}
        for segment in line.split(" | "):
            if ":" in segment:
                k, v = segment.split(":", 1)
                parts[k.strip()] = v.strip()
        if "CONCEPT" in parts and "PAPER" in parts:
            return {
                "concept": parts.get("CONCEPT", "").strip(),
                "paper":   parts.get("PAPER", "").strip(),
                "authors": parts.get("AUTHORS", "").strip(),
                "year":    parts.get("YEAR", "").strip(),
                "url":     parts.get("URL", "unknown").strip(),
            }
    except Exception:
        pass
    return None


def normalize(title):
    title = title.lower().strip()
    title = re.sub(r'[^a-z0-9\s]', '', title)
    return re.sub(r'\s+', ' ', title)


def deduplicate(raw_refs):
    groups = defaultdict(lambda: {
        "concepts": set(), "paper": "", "authors": "", "year": "", "url": "unknown"
    })
    for ref in raw_refs:
        key = normalize(ref["paper"])
        if not key:
            continue
        g = groups[key]
        if len(ref["paper"]) > len(g["paper"]):
            g["paper"] = ref["paper"]
        if not g["authors"] and ref["authors"]:
            g["authors"] = ref["authors"]
        if not g["year"] and ref["year"]:
            g["year"] = ref["year"]
        if ref["url"] and ref["url"] != "unknown" and g["url"] == "unknown":
            g["url"] = ref["url"]
        if ref["concept"]:
            g["concepts"].add(ref["concept"])
    return groups


def run():
    print("\n" + "="*60)
    print("STEP 4b: Extract & Deduplicate References (Groq)")
    print("="*60)

    if not GROQ_API_KEY:
        print("ERROR: GROQ_API_KEY not set.")
        sys.exit(1)

    chapter_files = sorted(CHAPTERS_DIR.glob("*.md"))
    if not chapter_files:
        print("ERROR: No chapters found. Run Step 3 first.")
        sys.exit(1)

    print(f"\nModel  : {GROQ_REF_MODEL}")
    print(f"Chunks : paragraph-based, max {MAX_CHARS} chars each\n")

    client   = Groq(api_key=GROQ_API_KEY)
    raw_refs = []
    total_chunks = 0

    for ch_file in chapter_files:
        with open(ch_file, encoding="utf-8") as f:
            content = f.read()

        chunks = chunk_by_paragraphs(content, MAX_CHARS)
        total_chunks += len(chunks)
        print(f"  {ch_file.name} -- {len(chunks)} chunk(s)")

        for i, chunk in enumerate(chunks, 1):
            try:
                text = call_groq(client, chunk)
                for line in text.splitlines():
                    line = line.strip()
                    if line.startswith("CONCEPT:"):
                        ref = parse_line(line)
                        if ref:
                            raw_refs.append(ref)
                time.sleep(LLM_DELAY_SEC)
            except Exception as exc:
                print(f"    Warning chunk {i}: {exc}")
                time.sleep(20)   # brief pause on error before continuing
                continue

    print(f"\n  Chunks scanned  : {total_chunks}")
    print(f"  Raw refs found  : {len(raw_refs)}")

    groups = deduplicate(raw_refs)
    print(f"  Unique papers   : {len(groups)}")

    out_path = BOOK_DIR / "references.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("## Appendix: References and Further Reading\n\n")
        f.write(
            "> *References automatically identified from chapter content. "
            "Grouped and deduplicated by paper. "
            "Entries marked `URL: unknown` could not be automatically verified.*\n\n"
        )

        sorted_papers = sorted(
            groups.items(),
            key=lambda x: (x[1]["url"] == "unknown", x[1].get("year", "9999"), x[1].get("paper", ""))
        )

        for _, g in sorted_papers:
            concepts    = sorted(g["concepts"])
            concept_str = ", ".join(f"**{c}**" for c in concepts) if concepts else "**General reference**"
            citation    = f"*{g['paper']}*"
            if g["authors"]:
                citation += f" -- {g['authors']}"
            if g["year"]:
                citation += f" ({g['year']})"
            if g["url"] and g["url"] != "unknown":
                f.write(f"- {concept_str}\n  {citation}. [{g['url']}]({g['url']})\n\n")
            else:
                f.write(f"- {concept_str}\n  {citation}.\n\n")

    print(f"\nStep 4b done. Output: {out_path}")
    print("Now run: python pipeline.py --steps 4,5")


if __name__ == "__main__":
    run()
