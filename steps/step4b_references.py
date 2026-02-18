"""
steps/step4b_references.py — Extract key technical claims and match to external references.

Asks Gemini to identify any papers, concepts, or claims in the chapters
that correspond to known published work, and outputs a references appendix.

Output: data/book/references.md  (appended to book.md by step4_assemble)
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CHAPTERS_DIR, BOOK_DIR, GEMINI_API_KEY, GEMINI_MODEL, GEMINI_DELAY_SEC

REFERENCE_PROMPT = """
You are a technical editor reviewing a book chapter about building LLMs.

Your task: identify every concept, technique, or claim in this chapter that
corresponds to a known published paper or foundational work.

For each one, output a reference entry in this format:
- **[ConceptName]** — Brief description of what it is. Source: *Paper Title* (Author(s), Year). https://arxiv.org/abs/...

Rules:
- Only list references you are highly confident about (well-known papers)
- Do NOT invent paper titles, authors, or URLs
- If you are not sure of the exact paper, write: Source: *[Could not verify — refer to original video]*
- Focus on: Transformer architecture, attention mechanism, tokenization methods,
  training techniques, specific model architectures (GPT, BERT etc.), loss functions,
  optimizers, and any named algorithms

Chapter content:
"""


def run():
    print("\n" + "="*60)
    print("STEP 4b: Extract References Appendix")
    print("="*60)

    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set.")
        sys.exit(1)

    chapter_files = sorted(CHAPTERS_DIR.glob("*.md"))
    if not chapter_files:
        print("ERROR: No chapters found. Run Step 3 first.")
        sys.exit(1)

    from google import genai
    from google.genai import types
    client = genai.Client(api_key=GEMINI_API_KEY)

    all_references = set()

    for ch_file in chapter_files:
        print(f"  Scanning {ch_file.name}...")
        with open(ch_file, encoding="utf-8") as f:
            content = f.read()

        # Only send first 40k chars to keep it fast
        excerpt = content[:40_000]

        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=REFERENCE_PROMPT + excerpt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=2048,
                ),
            )
            refs = response.text.strip()
            if refs:
                for line in refs.splitlines():
                    line = line.strip()
                    if line.startswith("- ") and "**" in line:
                        all_references.add(line)
            time.sleep(GEMINI_DELAY_SEC)

        except Exception as exc:
            print(f"  Warning: {exc}")
            continue

    # Write references appendix
    out_path = BOOK_DIR / "references.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("## Appendix: References and Further Reading\n\n")
        f.write("> *References identified from chapter content. ")
        f.write("Entries marked [Could not verify] should be confirmed against the source video.*\n\n")
        if all_references:
            for ref in sorted(all_references):
                f.write(ref + "\n")
        else:
            f.write("*No references could be automatically identified.*\n")

    print(f"\nStep 4b done -- {len(all_references)} references found.")
    print(f"Output: {out_path}")
    print("\nNow re-run Step 4 to include references in book.md:")
    print("  python pipeline.py --steps 4,5")


if __name__ == "__main__":
    run()
