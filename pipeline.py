"""
pipeline.py — Run the full Video → Book pipeline.

Usage:
    python pipeline.py                 # run all steps (respects TEST_MODE_LIMIT)
    python pipeline.py --steps 1,2    # run specific steps only
    python pipeline.py --steps 3,4,5  # resume from step 3
    python pipeline.py --status       # show what's done so far
    python pipeline.py --full         # override TEST_MODE_LIMIT, run full playlist
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def print_status():
    from config import RAW_DIR, CLEAN_DIR, CHAPTERS_DIR, BOOK_DIR, TEST_MODE_LIMIT

    print("\n" + "="*60)
    print("PIPELINE STATUS")
    print("="*60)

    if TEST_MODE_LIMIT:
        print(f"  Mode: TEST (first {TEST_MODE_LIMIT} videos)")
    else:
        print("  Mode: FULL PLAYLIST")

    index_path = RAW_DIR / "playlist_index.json"
    if not index_path.exists():
        print("  Step 1: ❌  Not started")
        return

    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)

    total        = len(index)
    has_captions = sum(1 for v in index if v.get("captions_available"))
    cleaned      = sum(1 for v in index if (CLEAN_DIR / f"{v['folder']}.json").exists())
    generated    = sum(1 for v in index if (CHAPTERS_DIR / f"{v['folder']}.md").exists())
    book_md      = (BOOK_DIR / "book.md").exists()
    book_pdf     = (BOOK_DIR / "book.pdf").exists()

    print(f"\n  Step 1 — Fetch:    {'✅' if has_captions else '❌'}  {has_captions}/{total} videos with captions")
    print(f"  Step 2 — Clean:    {'✅' if cleaned    else '❌'}  {cleaned}/{has_captions} transcripts cleaned")
    print(f"  Step 3 — Generate: {'✅' if generated  else '❌'}  {generated}/{cleaned} chapters generated")
    print(f"  Step 4 — Assemble: {'✅' if book_md    else '❌'}  {'book.md ready' if book_md else 'not run'}")
    print(f"  Step 5 — PDF:      {'✅' if book_pdf   else '❌'}  {'book.pdf ready' if book_pdf else 'not run'}")

    if book_md:
        kb = (BOOK_DIR / "book.md").stat().st_size // 1024
        print(f"\n  Manuscript: {kb:,} KB")
    if book_pdf:
        mb = (BOOK_DIR / "book.pdf").stat().st_size / 1_000_000
        print(f"  PDF:        {mb:.1f} MB")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="YouTube Playlist → Book Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--steps",  default="1,2,3,4,5",
                        help="Comma-separated steps to run (default: all)")
    parser.add_argument("--status", action="store_true",
                        help="Show pipeline status and exit")
    parser.add_argument("--full",   action="store_true",
                        help="Process full playlist (ignores TEST_MODE_LIMIT in config)")
    args = parser.parse_args()

    if args.full:
        import config
        config.TEST_MODE_LIMIT = None
        print("⚠️  Full playlist mode — TEST_MODE_LIMIT overridden to None")

    if args.status:
        print_status()
        return

    steps = [int(s.strip()) for s in args.steps.split(",") if s.strip().isdigit()]
    print(f"\n▶  Running steps: {steps}")

    if "4b" in args.steps.split(","):
        from steps.step4b_references import run; run()

    if 1 in steps:
        from steps.step1_fetch    import run; run()
    if 2 in steps:
        from steps.step2_clean    import run; run()
    if 3 in steps:
        from steps.step3_generate import run; run()
    if 4 in steps:
        from steps.step4_assemble import run; run()

    # Optional: run step 4b first to generate references appendix
    # python pipeline.py --steps 4b  then re-run step 4
    if 5 in steps:
        from steps.step5_export   import run; run()

    print("\n" + "="*60)
    print_status()


if __name__ == "__main__":
    main()
