"""
steps/step3_generate.py — Generate book chapters using Gemini only.

Primary  : gemini-2.5-flash-lite  (10 RPM, 20 RPD)
Fallback : gemini-2.5-flash       (5 RPM, 20 RPD -- separate quota pool)

Both models receive identical prompts and temperature=0.
Fallback activates automatically on 429 from primary.
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
    GEMINI_API_KEY, GEMINI_MODEL_PRIMARY, GEMINI_MODEL_FALLBACK,
    LLM_DELAY_SEC,
)

MAX_CHARS = 90_000

ASCII_INSTRUCTION = (
    "Use only standard ASCII characters -- no curly quotes, em-dashes, or special unicode. "
    "Use straight quotes (\"), hyphens (-), and standard punctuation only."
)


class RateLimitError(Exception):
    pass


def call_gemini(client, model, system_prompt, user_message):
    try:
        response = client.models.generate_content(
            model=model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.0,
                max_output_tokens=8192,
            ),
        )
        return response.text.strip()
    except Exception as exc:
        err = str(exc).lower()
        if "429" in str(exc) or "resource_exhausted" in err or "rate" in err or "quota" in err:
            raise RateLimitError(str(exc))
        raise


def call_llm(client, system_prompt, user_message):
    """Try Flash Lite first. On rate limit, fall back to Flash (separate quota pool)."""
    try:
        result = call_gemini(client, GEMINI_MODEL_PRIMARY, system_prompt, user_message)
        return result, GEMINI_MODEL_PRIMARY
    except RateLimitError:
        print(f"    Flash Lite rate limited -- switching to Flash (separate quota)...")
        result = call_gemini(client, GEMINI_MODEL_FALLBACK, system_prompt, user_message)
        return result, GEMINI_MODEL_FALLBACK


def build_transcript_block(paragraphs, video_url):
    lines = []
    for p in paragraphs:
        ts_sec = int(p["start_sec"])
        ts_fmt = p["start_fmt"]
        cite   = f"{video_url}&t={ts_sec}"
        lines.append(f"[{ts_fmt} | t={ts_sec} | url={cite}]\n{p['text']}\n")
    return "\n".join(lines)


def split_by_paragraphs(paragraphs, max_chars):
    """Split at paragraph boundaries -- never mid-sentence."""
    chunks  = []
    current = []
    cur_len = 0
    for p in paragraphs:
        p_len = len(p["text"])
        if cur_len + p_len > max_chars and current:
            chunks.append(current)
            current = [p]
            cur_len = p_len
        else:
            current.append(p)
            cur_len += p_len
    if current:
        chunks.append(current)
    return chunks


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
        f"Every prose paragraph must end with its citation link. "
        f"{ASCII_INSTRUCTION}"
    )

    if len(user_msg) <= MAX_CHARS:
        text, model = call_llm(client, system_prompt, user_msg)
        print(f"         Model: {model}")
        return text

    # Split at paragraph boundaries
    chunks = split_by_paragraphs(paragraphs, MAX_CHARS // 2)
    total  = len(chunks)
    print(f"    Transcript split into {total} sections (paragraph boundaries)")

    parts = []
    for i, chunk_paras in enumerate(chunks, 1):
        print(f"    Section {i}/{total}...", end=" ", flush=True)
        block = build_transcript_block(chunk_paras, url)
        msg   = (
            f"VIDEO: {title} | Chapter {pos}, Section {i} of {total}\n"
            f"URL: {url}\n\n"
            f"TRANSCRIPT SECTION:\n\n{block}\n\n"
            f"Write this section. Start with a ### heading. "
            f"Every prose paragraph must end with its citation link. "
            f"{ASCII_INSTRUCTION}"
        )
        text, model = call_llm(client, system_prompt, msg)
        print(f"({model})")
        parts.append(text)
        time.sleep(LLM_DELAY_SEC)

    header = (
        f"## Chapter {pos}: {title}\n\n"
        f"> **Source video**: [{title}]({url})\n"
        f"> **Duration**: {dur_min} min | Playlist position {pos}\n\n"
    )
    return header + "\n\n".join(parts) + f"\n\n---\n*End of Chapter {pos}. Source: {url}*"


def run():
    print("\n" + "="*60)
    print("STEP 3: Generate Book Chapters (Gemini)")
    print("="*60)

    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set.")
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

    already_done = sum(
        1 for v in to_process
        if (CHAPTERS_DIR / f"{v['folder']}.md").exists()
        and (CHAPTERS_DIR / f"{v['folder']}.md").stat().st_size > 300
    )
    remaining = len(to_process) - already_done

    print(f"\nPrimary   : {GEMINI_MODEL_PRIMARY}")
    print(f"Fallback  : {GEMINI_MODEL_FALLBACK} (separate quota pool)")
    print(f"Total     : {len(to_process)} videos")
    print(f"Done      : {already_done} already generated (skipping)")
    print(f"Remaining : {remaining} to generate\n")

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
            print(f"  [{pos:02d}] Already done  -- {title[:52]}")
            skipped += 1
            continue

        print(f"  [{pos:02d}] Generating   -- {title[:52]}")

        with open(CLEAN_DIR / f"{folder}.json", encoding="utf-8") as f:
            data = json.load(f)

        paragraphs = data["paragraphs"]
        if not paragraphs:
            print(f"         WARNING: empty transcript -- skipping")
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

        time.sleep(LLM_DELAY_SEC)

    print(f"\nStep 3 done -- {ok} generated, {skipped} skipped, {failed} failed.")
    print(f"Output: {CHAPTERS_DIR}")


if __name__ == "__main__":
    run()
