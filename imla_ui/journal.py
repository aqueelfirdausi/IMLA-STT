"""
imla_ui/journal.py
──────────────────
Phase 3 (Chatterbox / journal mode), minimal slice.
Saves a finished transcript to a dated Markdown file under journal/.
Pure file I/O — no UI, no Qt, no app state. Easy to test in isolation.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from groq import Groq

# journal/ lives at the repo root (two levels up from this file: imla_ui/ -> root)
JOURNAL_DIR = Path(__file__).resolve().parents[1] / "journal"

_client = Groq(api_key=config.GROQ_API_KEY)

_TAG_SYSTEM = (
    "You are a topic tagger. Return ONLY 1-3 short lowercase topic tags, "
    "comma-separated, no other text, no explanations. "
    "Example: imla-stt, late-night-coding"
)


def get_tags(text: str) -> list[str]:
    """Return up to 3 lowercase topic tags for *text* via Groq. Returns [] on any failure."""
    try:
        response = _client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": _TAG_SYSTEM},
                {"role": "user", "content": text},
            ],
            max_tokens=40,
            temperature=0.2,
        )
        raw = response.choices[0].message.content or ""
        tags = [t.strip().lower() for t in raw.split(",")]
        return [t for t in tags if t][:3]
    except Exception as exc:
        print(f"[journal] tag LLM call failed ({exc}) — saving with empty tags.")
        return []


def save_entry(text: str) -> Path:
    """Append `text` as a timestamped entry to today's journal file.
    Returns the path written. Creates journal/ if missing.
    One file per day: journal/YYYY-MM-DD.md ; each entry stamped with the time.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("Refusing to save an empty journal entry.")

    tags = get_tags(text)

    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    day_file = JOURNAL_DIR / f"{now:%Y-%m-%d}.md"

    # If the day file is new, start it with a date header.
    new_file = not day_file.exists()
    tags_line = f"[{', '.join(tags)}]" if tags else "[]"
    with day_file.open("a", encoding="utf-8") as f:
        if new_file:
            f.write(f"# Journal — {now:%A, %d %B %Y}\n\n")
        f.write(f"## {now:%H:%M}\n---\ntags: {tags_line}\n---\n{text}\n\n")
    return day_file
