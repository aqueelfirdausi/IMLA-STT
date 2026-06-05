"""
dictation/inserter.py -- Type text into the focused window.

Method used: clipboard + Ctrl+V.

Why: SendKeys / keyboard.write() misses special characters and is unreliable
across apps. Ctrl+V works in virtually every Windows text field. We save the
existing clipboard contents first and restore them afterwards so the user
never loses what they had copied.
"""

import time
import pyperclip   # pip install pyperclip
import keyboard    # pip install keyboard


def insert_text(text: str) -> None:
    """
    Insert `text` at the current cursor position in the focused window.

    Steps
    -----
    1. Save the current clipboard.
    2. Copy `text` to the clipboard.
    3. Send Ctrl+V to paste.
    4. Wait briefly for the paste to land.
    5. Restore the original clipboard.
    """
    if not text.strip():
        return

    # 1. Save
    try:
        old = pyperclip.paste()
    except Exception:
        old = ""

    try:
        # 2. Set new content
        pyperclip.copy(text)
        time.sleep(0.08)   # give the clipboard time to propagate

        # 3. Paste into the focused window
        keyboard.send("ctrl+v")
        time.sleep(0.15)   # wait for the app to process the paste event

    finally:
        # 5. Restore -- always, even if pasting raised an exception
        try:
            pyperclip.copy(old)
        except Exception:
            pass
