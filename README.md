# Building LLMs from Scratch — Playlist → Book Pipeline

Converts the YouTube playlist **“Building LLMs from Scratch”** into an eBook-quality manuscript (Markdown + PDF).

Every paragraph in the generated book:

- Is derived directly from the video transcript  
- Contains a clickable timestamp citation linking back to YouTube  
- Can be verified against the exact moment in the source video  

No summarization shortcuts. No vector database. No external knowledge injection.  
The playlist order becomes the book order.

The repository also includes a detailed **Pipeline Architecture & Design Decisions** document explaining system design choices, tradeoffs, and system maturity assessment.

---

# Architecture Summary

The pipeline is fully file-based and resumable. Each step reads from disk and writes to disk. There is no shared in-memory state between steps.

Step 1 → Fetch captions (yt-dlp)
Step 2 → Clean VTT → timestamped paragraphs
Step 3 → Gemini → chapter prose with citations
Step 4 → Assemble book.md
Step 4b → Generate references appendix
Step 5 → Export PDF


Each step:

- Skips completed work automatically  
- Can be re-run independently  
- Can resume after interruption  

---

# Setup (One Time)

## 1. Install dependencies

```bash
pip install -r requirements.txt
2. Create .env
Rename .env.example to .env and add:

GEMINI_API_KEY=your_key_here
Free key:
https://aistudio.google.com

Test Mode (Recommended First Run)
By default, config.py contains:

TEST_MODE_LIMIT = 3
This processes only the first 3 videos.

Run:
python pipeline.py
Check:
data/book/book.md
data/book/book.pdf
If satisfied, run full playlist:
python pipeline.py --full
Or set:
TEST_MODE_LIMIT = None
Commands
python pipeline.py               # run all steps (test mode)
python pipeline.py --full        # run full playlist
python pipeline.py --steps 1,2   # run specific steps
python pipeline.py --steps 3     # re-run chapter generation only
python pipeline.py --status      # show progress
All steps are safe to re-run.

## What Each Step Does

Step	Purpose
1	Downloads captions using yt-dlp
2	Parses VTT → clean paragraphs with timestamps
3	Gemini converts transcript → structured book prose with citations
4	Assembles all chapters into book.md
4b	Generates references appendix
5	Exports book.pdf with working links

# Output Structure
data/
├── raw/                 # Original captions + metadata
├── clean/               # Structured transcript (timestamped)
├── chapters/            # One Markdown file per video
└── book/
    ├── book.md          # Full manuscript
    ├── references.md    # Generated references appendix (Step 4b)
    ├── book.html
    └── book.pdf

# Citation Model
Each prose paragraph ends with a clickable citation:
[▶ 4:32](https://youtube.com/watch?v=VIDEO_ID&t=272)
Clicking the link opens YouTube at that exact timestamp.
This ensures every claim is traceable to source content.

# No-Hallucination Safeguards

Transcript is the sole source of content
temperature=0 for deterministic generation
System prompt explicitly forbids adding new information
Raw transcript files preserved for verification
Unclear transcript sections are flagged, not guessed
References appendix generated separately (Step 4b)
Note: Deterministic generation reduces hallucination risk but does not eliminate model variability across API versions. The transcript remains the ground truth.

# Known Limitations

Code written silently on screen is not captured in captions.
Auto-captioned technical terms may occasionally contain transcription errors.
Chapters are generated independently (no cross-chapter reasoning).
Free Gemini tier is rate-limited.
All architectural tradeoffs are documented in the included architecture file.

# Reproducing the Book
git clone <repo>
pip install -r requirements.txt
# add GEMINI_API_KEY to .env
python pipeline.py --full
The manuscript can be regenerated end-to-end from the playlist.
