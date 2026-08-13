"""
config.py — All settings. Only edit the USER SETTINGS section.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ================================================================
# USER SETTINGS
# SET THIS BEFORE EACH RUN — used as the book's title page and PDF metadata.
# Defaults below are just placeholders from the original test playlist.
# ================================================================

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLPTV0NXA_ZSgsLAr8YCgCwhPIJNNtexWu"

# Step 3: Chapter generation -- Gemini only, two models as primary/fallback
GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_PRIMARY = "gemini-2.5-flash-lite"   # 10 RPM, 20 RPD
GEMINI_MODEL_FALLBACK= "gemini-2.5-flash"         # 5 RPM, 20 RPD -- separate quota pool

# Step 4b: Reference extraction -- Groq only
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL   = "llama-3.1-8b-instant"


BOOK_TITLE    = "Building LLMs from Scratch"
BOOK_SUBTITLE = "A Practical Guide from First Principles"

# TEST MODE: set to a number (e.g. 3) to process only the first N videos.
# Set to None to process the full playlist.
TEST_MODE_LIMIT = None

# ================================================================
# PATHS -- do not edit
# ================================================================

ROOT         = Path(__file__).parent
DATA_DIR     = ROOT / "data"
RAW_DIR      = DATA_DIR / "raw"
CLEAN_DIR    = DATA_DIR / "clean"
CHAPTERS_DIR = DATA_DIR / "chapters"
BOOK_DIR     = DATA_DIR / "book"
PROMPTS_DIR  = ROOT / "prompts"

# 40s delay safely under Flash Lite limit
LLM_DELAY_SEC = 40

for _d in [RAW_DIR, CLEAN_DIR, CHAPTERS_DIR, BOOK_DIR, PROMPTS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)
