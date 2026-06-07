"""
imla_ui/journal_reader.py
─────────────────────────
Phase 3 (Chatterbox) — the READ side of journal mode.

Reads the dated Markdown files written by journal.py and answers
questions about them via Groq. Pure logic — no UI, no Qt, no app state.
Testable in isolation from a terminal.

Mirrors journal.py exactly:
  - same JOURNAL_DIR (repo-root/journal)
  - same Groq client pattern (config.GROQ_API_KEY, config.GROQ_MODEL)
  - parses the save format: '## HH:MM' / '---' / 'tags: [...]' / '---' / text
"""
from __future__ import annotations
from pathlib import Path
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from groq import Groq

# Same journal/ location journal.py writes to (repo root, two levels up).
JOURNAL_DIR = Path(__file__).resolve().parents[1] / "journal"

_client = Groq(api_key=config.GROQ_API_KEY)

# Each entry begins with a time header line: "## HH:MM"
_ENTRY_RE = re.compile(r"^## (\d{2}:\d{2})\s*$", re.MULTILINE)
_TAGS_RE  = re.compile(r"^tags:\s*\[(.*)\]\s*$", re.MULTILINE)

_ANSWER_SYSTEM = (
    "You are a helpful assistant that answers questions about the user's "
    "personal journal. You are given dated journal entries. Answer the "
    "user's question using ONLY what is in those entries. If the entries "
    "do not contain the answer, say so plainly. Be concise and refer to "
    "dates when useful."
)


def _parse_day_file(path: Path) -> list[dict]:
    """Split one YYYY-MM-DD.md file into individual entries."""
    date = path.stem  # 'YYYY-MM-DD'
    raw = path.read_text(encoding="utf-8")

    entries: list[dict] = []
    # Find each '## HH:MM' marker; the entry runs until the next marker (or EOF).
    matches = list(_ENTRY_RE.finditer(raw))
    for i, m in enumerate(matches):
        time = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        block = raw[start:end]

        # Pull tags from the frontmatter, if present.
        tag_match = _TAGS_RE.search(block)
        if tag_match:
            inner = tag_match.group(1).strip()
            tags = [t.strip().lower() for t in inner.split(",") if t.strip()]
        else:
            tags = []

        # The body is everything after the closing '---' of the frontmatter.
        # Frontmatter is: ---\ntags: [...]\n---\n<text>
        parts = block.split("---")
        body = parts[-1].strip() if len(parts) >= 3 else block.strip()

        if body:
            entries.append({"date": date, "time": time, "tags": tags, "text": body})

    return entries


def load_all_entries() -> list[dict]:
    """Read every journal day-file. Returns entries sorted oldest → newest."""
    if not JOURNAL_DIR.exists():
        return []
    entries: list[dict] = []
    for path in sorted(JOURNAL_DIR.glob("*.md")):
        # day-files are named YYYY-MM-DD.md
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.stem):
            entries.extend(_parse_day_file(path))
    return entries


def _format_entries(entries: list[dict]) -> str:
    """Turn entries into a plain block of context for the model."""
    lines = []
    for e in entries:
        tag_str = f" [tags: {', '.join(e['tags'])}]" if e["tags"] else ""
        lines.append(f"({e['date']} {e['time']}){tag_str}\n{e['text']}")
    return "\n\n".join(lines)


def answer(question: str) -> str:
    """Answer a question against ALL journal entries via Groq.

    Sends every entry as context (simplest correct approach for a small
    journal). Tag-filtering can be added later if volume demands it.
    Returns a plain-language answer, or a clear message on empty/failure.
    """
    question = (question or "").strip()
    if not question:
        return "Ask me something about your journal."

    entries = load_all_entries()
    if not entries:
        return "Your journal is empty — nothing to answer from yet."

    context = _format_entries(entries)
    try:
        response = _client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": _ANSWER_SYSTEM},
                {"role": "user",
                 "content": f"Journal entries:\n\n{context}\n\nQuestion: {question}"},
            ],
            max_tokens=600,
            temperature=0.3,
        )
        return (response.choices[0].message.content or "").strip() \
            or "I couldn't form an answer from your entries."
    except Exception as exc:
        return f"Couldn't reach the assistant ({exc})."
