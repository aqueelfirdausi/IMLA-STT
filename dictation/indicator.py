"""
dictation/indicator.py -- Small floating status bar.

Requirements
------------
* Always on top.
* Must NOT steal focus from the window the user is dictating into, or the
  Ctrl+V paste will land in the wrong place.
* No title bar / chrome.

How non-focus-stealing is achieved
-----------------------------------
After the Toplevel is created we call SetWindowLongW to add the extended style
WS_EX_NOACTIVATE (0x08000000). This tells Windows never to activate (focus)
this window, even on click. WS_EX_TOOLWINDOW keeps it out of Alt+Tab.
"""

import tkinter as tk
import ctypes

# Extended window style constants
_GWL_EXSTYLE      = -20
_WS_EX_NOACTIVATE = 0x08000000
_WS_EX_TOOLWINDOW = 0x00000080


class IndicatorWindow:
    """
    Tiny pill-shaped floating label.

    States
    ------
    "hidden"        -- window is withdrawn (invisible)
    "listening"     -- red, "Listening..."
    "transcribing"  -- orange, "Transcribing..."
    """

    _STATES = {
        "hidden":       (None,      None),
        "listening":    ("#C0392B", "  Listening...  "),
        "transcribing": ("#D35400", "  Transcribing...  "),
    }

    def __init__(self, root: tk.Tk):
        self._root = root
        self._win = tk.Toplevel(root)
        self._win.overrideredirect(True)          # no decorations
        self._win.attributes("-topmost", True)    # always on top
        self._win.withdraw()                      # hidden until first call

        self._label = tk.Label(
            self._win,
            text="",
            font=("Segoe UI", 11, "bold"),
            fg="white",
            bg="#2C2C2C",
            padx=0, pady=0,
        )
        self._label.pack()

        # Apply WS_EX_NOACTIVATE after the window exists.
        # We schedule it slightly deferred so the HWND is fully created.
        self._win.after(100, self._set_no_activate)

    # ── Public API (call only from the main/tkinter thread) ───────────────────

    def set_state(self, state: str):
        color, text = self._STATES.get(state, (None, None))
        if color is None:
            self._win.withdraw()
            return

        self._label.configure(text=text, bg=color)
        self._win.configure(bg=color)

        # Position: top-centre of the primary screen
        self._win.update_idletasks()
        w = self._win.winfo_reqwidth()
        sw = self._win.winfo_screenwidth()
        self._win.geometry(f"+{(sw - w) // 2}+24")

        self._win.deiconify()
        # Re-apply no-activate after deiconify (Windows can reset it)
        self._root.after(20, self._set_no_activate)

    # ── Windows API ───────────────────────────────────────────────────────────

    def _set_no_activate(self):
        try:
            # GetParent returns 0 for a top-level -- use the window handle directly.
            hwnd = ctypes.windll.user32.GetParent(self._win.winfo_id())
            if hwnd == 0:
                hwnd = self._win.winfo_id()
            cur = ctypes.windll.user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, _GWL_EXSTYLE,
                cur | _WS_EX_NOACTIVATE | _WS_EX_TOOLWINDOW,
            )
        except Exception:
            pass   # non-fatal; indicator may steal focus on very old Windows
