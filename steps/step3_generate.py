"""
steps/step3_generate.py — Generate book chapters from cleaned transcripts via Gemini.

Uses the new google-genai SDK (replaces deprecated google-generativeai).
Install: pip install google-genai

Citation design:
  - Each paragraph sent to Gemini includes its timestamp and video URL
  - Gemini is instructed to include a citation link on every prose paragraph
  - temperature=0 for maximum determinism (no creative invention)

Output:
  data/chapters/{folder}.md   one chapter per video, with inline citations
"""

import json
import sys
import time
from pathlib import Path

from google import genai
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    CLEAN_DIR, CHAPTERS_DIR, PROMPTS_DIR, RAW_DIR,
    GEMINI_API_KEY, GEMINI_MODEL, GEMINI_DELAY_SEC,
)

MAX_CHARS = 90_000


def build_transcript_block(paragraphs, video_url):
    lines = []
    for p in paragraphs:
        ts_sec = int(p["start_sec"])
        ts_fmt = p["start_fmt"]
        cite   = f"{video_url}&t={ts_sec}"
        lines.append(f"[{ts_fmt} | t={ts_sec} | url={cite}]\n{p['text']}\n")
    return "\n".join(lines)


def call_gemini(client, system_prompt, user_message):
    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.0,
                    max_output_tokens=8192,
                ),
            )
            return response.text.strip()
        except Exception as exc:
            err = str(exc)
            if "429" in err or "quota" in err.lower() or "rate" in err.lower():
                wait = 30 * (attempt + 1)
                print(f"    Rate limited -- waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Gemini failed after 4 retries")


def generate_chapter(client, system_prompt, video, paragraphs):
    pos     = video["position"]
    title   = video["title"]
    url     = video["url"]
    dur_min = video["duration"] // 60

    transcript_block = build_transcript_block(paragraphs, url)

    user_msg = (
        f"VIDEO TITLE: {title}\n"
        f"VIDEO URL: {url}\n"
        f"DURATION: {dur_min} minutes\n"
        f"PLAYLIST POSITION: {pos}\n"
        f"CHAPTER NUMBER: {pos}\n\n"
        f"TRANSCRIPT (each paragraph prefixed with its timestamp):\n\n"
        f"{transcript_block}\n\n"
        f"Write the complete chapter now. "
        f"Every prose paragraph must end with its citation link."
    )

    if len(user_msg) <= MAX_CHARS:
        return call_gemini(client, system_prompt, user_msg)

    print(f"    Long transcript -- splitting into sections...")
    mid    = len(paragraphs) // 2
    parts  = [paragraphs[:mid], paragraphs[mid:]]
    chunks = []

    for i, part in enumerate(parts, 1):
        print(f"    Section {i}/{len(parts)}...")
        block = build_transcript_block(part, url)
        msg   = (
            f"VIDEO: {title} | Chapter {pos}, Section {i} of {len(parts)}\n"
            f"URL: {url}\n\n"
            f"TRANSCRIPT SECTION:\n\n{block}\n\n"
            f"Write this section. Start with a ### heading. "
            f"Every prose paragraph must end with its citation link."
        )
        chunks.append(call_gemini(client, system_prompt, msg))
        time.sleep(GEMINI_DELAY_SEC)

    header = (
        f"## Chapter {pos}: {title}\n\n"
        f"> **Source video**: [{title}]({url})\n"
        f"> **Duration**: {dur_min} min | Playlist position {pos}\n\n"
    )
    return header + "\n\n".join(chunks) + f"\n\n---\n*End of Chapter {pos}. Source: {url}*"


def run():
    print("\n" + "="*60)
    print("STEP 3: Generate Book Chapters (Gemini)")
    print("="*60)

    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set. Add it to your .env file.")
        sys.exit(1)

    index_path = RAW_DIR / "playlist_index.json"
    if not index_path.exists():
        print("ERROR: Run Step 1 first.")
        sys.exit(1)

    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)

    to_process = [
        v for v in index
        if (CLEAN_DIR / f"{v['folder']}.json").exists()
    ]

    if not to_process:
        print("ERROR: No clean transcripts found. Run Steps 1 and 2 first.")
        sys.exit(1)

    print(f"\nModel  : {GEMINI_MODEL}")
    print(f"Videos : {len(to_process)}\n")

    client = genai.Client(api_key=GEMINI_API_KEY)

    with open(PROMPTS_DIR / "chapter_writer.txt", encoding="utf-8") as f:
        system_prompt = f.read()

    ok = skipped = failed = 0

    for v in to_process:
        pos    = v["playlist_position"]
        title  = v["title"]
        folder = v["folder"]

        out_path = CHAPTERS_DIR / f"{folder}.md"
        if out_path.exists() and out_path.stat().st_size > 300:
            print(f"  [{pos:02d}] Already generated -- {title[:55]}")
            skipped += 1
            continue

        print(f"  [{pos:02d}] Generating -- {title[:55]}")

        with open(CLEAN_DIR / f"{folder}.json", encoding="utf-8") as f:
            data = json.load(f)

        paragraphs = data["paragraphs"]
        if not paragraphs:
            print(f"         WARNING: Empty transcript -- skipping")
            skipped += 1
            continue

        try:
            chapter_md = generate_chapter(client, system_prompt, data, paragraphs)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(chapter_md)

            words = len(chapter_md.split())
            cites = chapter_md.count("[")
            print(f"         OK: {words:,} words, {cites} citations")
            ok += 1

        except Exception as exc:
            print(f"         FAILED: {exc}")
            failed += 1

        time.sleep(GEMINI_DELAY_SEC)

    print(f"\nStep 3 done -- {ok} generated, {skipped} skipped, {failed} failed.")
    print(f"Output: {CHAPTERS_DIR}")


if __name__ == "__main__":
    run()
