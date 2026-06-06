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

# journal/ lives at the repo root (two levels up from this file: imla_ui/ -> root)
JOURNAL_DIR = Path(__file__).resolve().parents[1] / "journal"

def save_entry(text: str) -> Path:
    """Append `text` as a timestamped entry to today's journal file.
    Returns the path written. Creates journal/ if missing.
    One file per day: journal/YYYY-MM-DD.md ; each entry stamped with the time.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("Refusing to save an empty journal entry.")

    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    day_file = JOURNAL_DIR / f"{now:%Y-%m-%d}.md"

    # If the day file is new, start it with a date header.
    new_file = not day_file.exists()
    with day_file.open("a", encoding="utf-8") as f:
        if new_file:
            f.write(f"# Journal — {now:%A, %d %B %Y}\n\n")
        f.write(f"## {now:%H:%M}\n\n{text}\n\n")
    return day_file
