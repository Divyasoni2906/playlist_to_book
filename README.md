# Building LLMs from Scratch -- YouTube to eBook Pipeline

Converts a YouTube playlist into a professionally formatted PDF manuscript.
Every claim traces back to a source video with a clickable timestamp citation.
No hallucinations. Fully reproducible. Runs on any Windows/Mac/Linux laptop.

---

## Quick Start

```bash
# 1. Enter the project folder
cd video_to_book

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 3. Install dependencies
pip install yt-dlp google-genai groq python-dotenv reportlab

# 4. Add API keys
cp .env.example .env
# Edit .env with your keys (see API Keys section below)

# 5. Run the full pipeline
python pipeline.py
```

Output: `data/book/book.pdf` and `data/book/book.md`

---

## API Keys

Create a `.env` file with:

```
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here
```

| Key | Where to get it | Used for |
|-----|----------------|----------|
| `GEMINI_API_KEY` | aistudio.google.com | Chapter generation (steps 1-4) |
| `GROQ_API_KEY` | console.groq.com | Reference extraction (step 4b) |

Both are free. No credit card required.

---

## Pipeline Steps

```
Step 1   FETCH      YouTube playlist  -->  VTT caption files
Step 2   CLEAN      VTT files         -->  Structured JSON with timestamps
Step 3   GENERATE   Transcripts       -->  Chapter markdown (Gemini)
Step 4b  REFERENCES Chapter markdown  -->  References appendix (Groq)
Step 4   ASSEMBLE   All chapters      -->  book.md with TOC + references
Step 5   EXPORT     book.md           -->  book.pdf with clickable links
```

Each step reads from files and writes to files.
Re-running any step skips already-completed work automatically.

---

## Running Individual Steps

```bash
# Run everything (default)
python pipeline.py

# Run specific steps
python pipeline.py --steps 3
python pipeline.py --steps 4b
python pipeline.py --steps 4,5
python pipeline.py --steps 3,4b,4,5

# Check what is done so far
python pipeline.py --status

# Process full playlist (overrides TEST_MODE_LIMIT in config.py)
python pipeline.py --full
```

---

## Configuration

Edit `config.py` to change settings:

```python
PLAYLIST_URL         = "https://www.youtube.com/playlist?list=..."
GEMINI_MODEL_PRIMARY = "gemini-2.5-flash-lite"   # 10 RPM, 20 RPD
GEMINI_MODEL_FALLBACK= "gemini-2.5-flash"         # 5 RPM, 20 RPD (separate quota)
GROQ_MODEL           = "llama-3.1-8b-instant"     # reference extraction
BOOK_TITLE           = "Building LLMs from Scratch"
TEST_MODE_LIMIT      = 3      # set to None for full playlist
LLM_DELAY_SEC        = 50      # seconds between API calls
```

---

## LLM Strategy

**Step 3 -- Chapter generation (Gemini only):**

Two Gemini models with separate daily quota pools:
- Primary: `gemini-2.5-flash-lite` -- higher RPM, used first for every chapter
- Fallback: `gemini-2.5-flash` -- different quota pool, activated automatically on 429

You will see `Model: gemini-2.5-flash-lite` or `Flash Lite rate limited -- switching to Flash...`
per chapter depending on which model was used.

**Step 4b -- Reference extraction (Groq only):**

Uses `llama-3.1-8b-instant` on Groq. Small model, very low token usage, completely
separate from Gemini quota. Reference extraction is a pattern-matching task -- 8B is sufficient.

**Why this split:**
Gemini free tier allows only 20 requests/day per model. A 43-video playlist exceeds
this in a single run. Two Gemini models = 40 effective RPD for chapter generation.
Groq for references keeps that quota separate so both tasks do not compete.

---

## Anti-Hallucination Design

| Mechanism | What it prevents |
|-----------|-----------------|
| temperature=0 | Stochastic invention |
| "Only from transcript" prompt rule | Adding content not in source video |
| [Transcript unclear] flag | Silent guessing on garbled captions |
| Citation on every paragraph | Unverifiable claims |
| Clickable timestamps in PDF | Reader cannot verify -- links go directly to moment in video |
| References appendix | Uncited foundational paper claims |
| Raw transcripts saved in data/clean/ | Full audit trail of pipeline inputs |

---

## Known Limitations

**Screen-only code is not captured.**
When the instructor writes code on screen without narrating it, that code is absent
from the transcript and therefore absent from the book. Clickable timestamp citations
let readers jump directly to the video at that moment.

**Auto-caption code term mangling.**
YouTube captions garble Python identifiers: `nn.Linear` becomes "en en dot linear".
The system prompt contains a reconstruction table. Ambiguous terms are flagged with
`[Transcript unclear]` so readers know to check the source video.

**43 chapters across 20 RPD per model.**
The pipeline takes 2-3 days on free tier. Each day processes up to 40 chapters
(20 from Flash Lite + 20 from Flash fallback). Already-generated chapters are never
re-processed -- just re-run `python pipeline.py --steps 3` each day.

---

## Output Files

```
data/
  raw/
    playlist_index.json        -- video metadata for all videos
    {folder}/meta.json         -- per-video metadata
    {folder}/captions.vtt      -- raw YouTube captions
  clean/
    {folder}.json              -- structured paragraphs with timestamps
    {folder}.txt               -- plain text for auditing
  chapters/
    {folder}.md                -- one chapter per video
  book/
    references.md              -- deduplicated paper references
    book.md                    -- full manuscript with TOC
    book.pdf                   -- final PDF with clickable links
```

---

## Project Structure

```
video_to_book/
  pipeline.py                  -- main entry point
  config.py                    -- all settings
  requirements.txt
  .env.example
  README.md
  steps/
    step1_fetch.py             -- yt-dlp caption download
    step2_clean.py             -- VTT parser and timestamp extractor
    step3_generate.py          -- Gemini chapter generation
    step4b_references.py       -- Groq reference extraction
    step4_assemble.py          -- manuscript assembly with TOC
    step5_export.py            -- ReportLab PDF export
  prompts/
    chapter_writer.txt         -- system prompt for chapter generation
  data/                        -- auto-created, all outputs live here
```

---

## Troubleshooting

**Gemini 429 rate limit**
Normal on free tier. The pipeline automatically switches to `gemini-2.5-flash`
(separate quota pool) for that chapter. No action needed.

**Both Gemini models rate limited**
Daily quota (20 RPD each) is exhausted. Re-run tomorrow -- already-generated
chapters are skipped automatically.

**Groq 429 on step 4b**
The 8B model has generous limits. If hit, wait a few minutes and re-run
`python pipeline.py --steps 4b` -- it will resume from where it failed.

**PDF is very small**
book.md may be empty. Check status: `python pipeline.py --status`
