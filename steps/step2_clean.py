"""
steps/step2_clean.py — Parse VTT captions into clean text WITH timestamp data.

Key design: we keep the start timestamp for each caption line so that
step3 can embed citation links in the form:
    [▶ 4:32](https://youtube.com/watch?v=VIDEO_ID&t=272)

Output per video:
  data/clean/{folder}.json  ← list of {text, start_sec, start_fmt} segments
  data/clean/{folder}.txt   ← plain text version (human readable)
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import RAW_DIR, CLEAN_DIR


# ── VTT parsing patterns ──────────────────────────────────────────────────────
RE_TIMESTAMP = re.compile(
    r"(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2}\.\d{3})"
)
RE_INLINE_TAGS  = re.compile(r"<[^>]+>")
RE_POSITION     = re.compile(r"align:\w+|position:\d+%|line:\d+%|size:\d+%")
RE_HEADER_LINE  = re.compile(r"^(WEBVTT|Kind:|Language:|NOTE|^\d+$)")


def ts_to_seconds(ts: str) -> float:
    """Convert HH:MM:SS.mmm to float seconds."""
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def seconds_to_display(sec: float) -> str:
    """Convert seconds to MM:SS or H:MM:SS display string."""
    total = int(sec)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def parse_vtt(vtt_path: Path) -> list[dict]:
    """
    Parse a VTT file into a list of timed segments.

    Returns:
        List of dicts: {text, start_sec, end_sec, start_fmt}
        Duplicates (overlapping auto-caption lines) are removed.
    """
    with open(vtt_path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    segments   = []
    seen_texts = set()
    current_start = 0.0
    current_end   = 0.0
    in_text_block = False

    for line in content.splitlines():
        line = line.strip()

        # Timestamp line
        m = RE_TIMESTAMP.match(line)
        if m:
            current_start = ts_to_seconds(m.group(1))
            current_end   = ts_to_seconds(m.group(2))
            in_text_block = True
            continue

        # Skip headers, sequence numbers, blank lines
        if not line or RE_HEADER_LINE.match(line) or RE_POSITION.search(line):
            in_text_block = False
            continue

        if in_text_block:
            # Clean the text
            text = RE_INLINE_TAGS.sub("", line).strip()
            text = (text
                    .replace("&amp;", "&").replace("&lt;", "<")
                    .replace("&gt;", ">").replace("\u200b", "")
                    .replace("\ufeff", ""))

            if not text:
                continue

            # Deduplicate: VTT auto-captions repeat lines as words stream in
            if text in seen_texts:
                continue
            seen_texts.add(text)

            segments.append({
                "text":       text,
                "start_sec":  current_start,
                "end_sec":    current_end,
                "start_fmt":  seconds_to_display(current_start),
            })

    return segments


def group_into_paragraphs(segments: list[dict], gap_threshold: float = 3.0) -> list[dict]:
    """
    Group consecutive segments into paragraphs based on time gaps.

    A new paragraph starts when there's a gap > gap_threshold seconds
    between segments (natural pause = topic shift).

    Returns:
        List of paragraph dicts: {text, start_sec, start_fmt}
    """
    if not segments:
        return []

    paragraphs = []
    current_texts  = [segments[0]["text"]]
    current_start  = segments[0]["start_sec"]
    current_fmt    = segments[0]["start_fmt"]
    prev_end       = segments[0]["end_sec"]

    for seg in segments[1:]:
        gap = seg["start_sec"] - prev_end

        if gap > gap_threshold:
            # Start a new paragraph
            paragraphs.append({
                "text":      " ".join(current_texts),
                "start_sec": current_start,
                "start_fmt": current_fmt,
            })
            current_texts = [seg["text"]]
            current_start = seg["start_sec"]
            current_fmt   = seg["start_fmt"]
        else:
            current_texts.append(seg["text"])

        prev_end = seg["end_sec"]

    # Last paragraph
    if current_texts:
        paragraphs.append({
            "text":      " ".join(current_texts),
            "start_sec": current_start,
            "start_fmt": current_fmt,
        })

    return paragraphs


def run():
    print("\n" + "="*60)
    print("STEP 2: Clean Transcripts + Extract Timestamps")
    print("="*60)

    index_path = RAW_DIR / "playlist_index.json"
    if not index_path.exists():
        print("❌  Run Step 1 first.")
        sys.exit(1)

    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)

    ok = skipped = 0

    for video in index:
        pos    = video.get("playlist_position", 0)
        title  = video.get("title", "")
        folder = video.get("folder", "")

        if not video.get("captions_available"):
            print(f"  [{pos:02d}] ⚠️  No captions — skipping")
            skipped += 1
            continue

        out_json = CLEAN_DIR / f"{folder}.json"
        out_txt  = CLEAN_DIR / f"{folder}.txt"

        if out_json.exists():
            print(f"  [{pos:02d}] Already clean — {title[:55]}")
            ok += 1
            continue

        vtt_path = RAW_DIR / folder / (video.get("vtt_file") or "captions.en.vtt")
        vtt_files = list((RAW_DIR / folder).glob("*.vtt"))
        if not vtt_files:
            print(f"  [{pos:02d}] ⚠️  VTT missing — {title[:55]}")
            skipped += 1
            continue
        vtt_path = vtt_files[0]

        try:
            segments   = parse_vtt(vtt_path)
            paragraphs = group_into_paragraphs(segments)

            if not paragraphs:
                print(f"  [{pos:02d}] ⚠️  Empty after parsing — {title[:55]}")
                skipped += 1
                continue

            # Save structured JSON (used by step3 for citation links)
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump({
                    "video_id":   video["video_id"],
                    "title":      title,
                    "url":        video.get("url", ""),
                    "duration":   video.get("duration_seconds", 0),
                    "position":   pos,
                    "paragraphs": paragraphs,
                }, f, indent=2, ensure_ascii=False)

            # Save human-readable plain text
            lines = [f"# {title}", f"# URL: {video.get('url','')}", ""]
            for p in paragraphs:
                lines.append(f"[{p['start_fmt']}] {p['text']}")
                lines.append("")
            with open(out_txt, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            word_count = sum(len(p["text"].split()) for p in paragraphs)
            print(f"  [{pos:02d}] ✓ {title[:50]} — {len(paragraphs)} paragraphs, {word_count:,} words")
            ok += 1

        except Exception as exc:
            print(f"  [{pos:02d}] ❌  {exc}")
            skipped += 1

    print(f"\n✅  Step 2 done — {ok} cleaned, {skipped} skipped.")
    print(f"    Output → {CLEAN_DIR}")


if __name__ == "__main__":
    run()
