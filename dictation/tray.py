"""
dictation/tray.py -- Windows system-tray icon and menu.

Uses pystray (run_detached so it runs in its own thread) + Pillow to draw
a simple microphone-shaped icon programmatically (no image file needed).
"""

import threading
from PIL import Image, ImageDraw
import pystray

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


def _make_icon(recording: bool = False) -> Image.Image:
    """Draw a 64x64 mic icon. Red when recording, white when idle."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    body_color = "#E74C3C" if recording else "#FFFFFF"
    base_color = "#C0392B" if recording else "#CCCCCC"

    # Mic capsule body
    d.rounded_rectangle([20, 4, 44, 38], radius=12, fill=body_color)

    # Mic stand arc (bottom semi-circle)
    d.arc([10, 22, 54, 50], start=0, end=180, fill=base_color, width=4)

    # Vertical stand line
    d.line([32, 50, 32, 58], fill=base_color, width=4)

    # Base platform
    d.line([20, 58, 44, 58], fill=base_color, width=4)

    return img


class TrayIcon:
    """
    Manages the system-tray icon and its right-click menu.

    Callbacks
    ---------
    on_quit        : called when the user clicks Quit.
    get_cleanup    : called to read current DICTATION_AI_CLEANUP state.
    set_cleanup    : called with a bool when the user toggles cleanup.
    get_mode       : called to read current DICTATION_MODE.
    set_mode       : called with a str ("hold"/"toggle") when toggled.
    """

    def __init__(self, on_quit, get_cleanup, set_cleanup, get_mode, set_mode,
                 on_show=None):
        self._on_quit     = on_quit
        self._get_cleanup = get_cleanup
        self._set_cleanup = set_cleanup
        self._get_mode    = get_mode
        self._set_mode    = set_mode
        self._on_show     = on_show   # called on left-click to summon widget
        self._icon: pystray.Icon | None = None

    def start(self):
        """Start the tray icon in a background thread (non-blocking)."""
        menu = pystray.Menu(
            # "Show widget" is the default action (invoked on left-click too).
            pystray.MenuItem(
                "Show widget",
                self._show,
                default=True,    # bold in menu; also fired on left-click
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "AI Cleanup",
                self._toggle_cleanup,
                checked=lambda item: self._get_cleanup(),
            ),
            pystray.MenuItem(
                "Hold mode",
                self._toggle_mode,
                checked=lambda item: self._get_mode() == "hold",
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit IMLA Dictate", self._quit),
        )

        self._icon = pystray.Icon(
            name="IMLA Dictate",
            icon=_make_icon(recording=False),
            title="IMLA Dictate — left-click to show widget",
            menu=menu,
        )
        self._icon.run_detached()   # runs in a background thread

    def set_recording(self, recording: bool):
        """Swap the tray icon to red while recording."""
        if self._icon:
            self._icon.icon = _make_icon(recording=recording)

    def stop(self):
        if self._icon:
            self._icon.stop()

    # ── Menu callbacks ────────────────────────────────────────────────────────

    def _show(self, icon, item):
        if self._on_show:
            self._on_show()

    def _toggle_cleanup(self, icon, item):
        self._set_cleanup(not self._get_cleanup())

    def _toggle_mode(self, icon, item):
        new = "toggle" if self._get_mode() == "hold" else "hold"
        self._set_mode(new)

    def _quit(self, icon, item):
        self._on_quit()
