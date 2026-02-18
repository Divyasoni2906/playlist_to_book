"""
steps/step1_fetch.py — Download playlist metadata and captions.

Key design: we keep timestamps in the raw VTT so step2 can build
citation anchors (video_url&t=seconds) for every paragraph.

Output per video:
  data/raw/{pos:02d}_{video_id}/
      captions.en.vtt   ← raw VTT (timestamps preserved)
      meta.json         ← title, url, duration, chapters
  data/raw/playlist_index.json
"""

import json
import sys
from pathlib import Path

import yt_dlp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PLAYLIST_URL, RAW_DIR, TEST_MODE_LIMIT


def run():
    print("\n" + "="*60)
    print("STEP 1: Fetch Playlist Captions")
    if TEST_MODE_LIMIT:
        print(f"         [TEST MODE — first {TEST_MODE_LIMIT} videos only]")
    print("="*60)

    # ── Get playlist listing ──────────────────────────────────────────────────
    print(f"\nFetching playlist: {PLAYLIST_URL}\n")
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
        info = ydl.extract_info(PLAYLIST_URL, download=False)

    entries = info.get("entries", [])
    if not entries:
        print("❌  No videos found. Check PLAYLIST_URL in config.py")
        sys.exit(1)

    # Apply test mode limit
    if TEST_MODE_LIMIT:
        entries = entries[:TEST_MODE_LIMIT]

    print(f"Processing {len(entries)} video(s)...\n")

    index_data = []

    for pos, entry in enumerate(entries, start=1):
        video_id    = entry.get("id", "")
        url         = f"https://www.youtube.com/watch?v={video_id}"
        folder_name = f"{pos:02d}_{video_id}"
        out_dir     = RAW_DIR / folder_name
        meta_file   = out_dir / "meta.json"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Skip if already downloaded
        existing_vtt = list(out_dir.glob("*.vtt"))
        if existing_vtt and meta_file.exists():
            print(f"  [{pos:02d}] Already downloaded — {entry.get('title','')[:55]}")
            with open(meta_file , encoding="utf-8") as f:
                index_data.append(json.load(f))
            continue

        print(f"  [{pos:02d}] Downloading — {entry.get('title','')[:55]}")

        ydl_opts = {
            "skip_download":     True,
            "writeautomaticsub": True,
            "writesubtitles":    True,
            "subtitleslangs":    ["en"],
            "subtitlesformat":   "vtt",
            "outtmpl":           str(out_dir / "captions"),
            "quiet":             True,
            "no_warnings":       True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                full_info = ydl.extract_info(url, download=True)

            vtt_files = list(out_dir.glob("*.vtt"))
            has_captions = bool(vtt_files)

            meta = {
                "playlist_position": pos,
                "video_id":          video_id,
                "title":             full_info.get("title", ""),
                "url":               url,
                "duration_seconds":  full_info.get("duration", 0),
                "description":       (full_info.get("description") or "")[:1000],
                "chapters":          full_info.get("chapters") or [],
                "upload_date":       full_info.get("upload_date", ""),
                "folder":            folder_name,
                "captions_available": has_captions,
                "vtt_file":          vtt_files[0].name if vtt_files else None,
            }

            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)

            status = "✓" if has_captions else "⚠️  no captions"
            print(f"         {status}")
            index_data.append(meta)

        except Exception as exc:
            print(f"         ❌  {exc}")
            index_data.append({
                "playlist_position": pos, "video_id": video_id,
                "title": entry.get("title", ""), "url": url,
                "folder": folder_name, "captions_available": False,
                "error": str(exc),
            })

    # Save index
    index_path = RAW_DIR / "playlist_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)

    ok = sum(1 for v in index_data if v.get("captions_available"))
    print(f"\n✅  Step 1 done — {ok}/{len(index_data)} videos have captions.")
    print(f"    Index → {index_path}")


if __name__ == "__main__":
    run()
