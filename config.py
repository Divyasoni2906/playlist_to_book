"""
config.py — All settings. Only edit the values in the USER SETTINGS section.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════
# USER SETTINGS — edit these
# ═══════════════════════════════════════════════════════════════

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLPTV0NXA_ZSgsLAr8YCgCwhPIJNNtexWu"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL   = "gemini-2.5-flash-lite"

BOOK_TITLE    = "Building LLMs from Scratch"
BOOK_SUBTITLE = "A Practical Guide from First Principles"

# TEST MODE: set to a small number (e.g. 3) to process only the first N videos.
# Set to None to process the full playlist.
TEST_MODE_LIMIT = None

# ═══════════════════════════════════════════════════════════════
# PATHS — do not edit
# ═══════════════════════════════════════════════════════════════

ROOT         = Path(__file__).parent
DATA_DIR     = ROOT / "data"
RAW_DIR      = DATA_DIR / "raw"        # downloaded VTT caption files
CLEAN_DIR    = DATA_DIR / "clean"      # cleaned transcripts with timestamps
CHAPTERS_DIR = DATA_DIR / "chapters"   # generated .md chapters
BOOK_DIR     = DATA_DIR / "book"       # final book.md + book.pdf
PROMPTS_DIR  = ROOT / "prompts"

# Gemini rate limit safety (free tier = 15 req/min)
GEMINI_DELAY_SEC = 5

for _d in [RAW_DIR, CLEAN_DIR, CHAPTERS_DIR, BOOK_DIR, PROMPTS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)
