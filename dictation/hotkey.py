"""
dictation/hotkey.py -- Global hotkey manager.

Hooks DICTATION_HOTKEY system-wide (requires admin on Windows).

Hold mode  : press to start, release to stop.
Toggle mode: first press starts, second press stops.

Caps Lock suppression:
  keyboard.hook_key(..., suppress=True) intercepts the key before the OS sees it,
  so the toggle behaviour never fires. A background monitor thread checks the Caps
  Lock LED state every 200 ms and restores it if something else flipped it.
"""

import threading
import ctypes
import time

import keyboard  # pip install keyboard

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

_VK_CAPITAL = 0x14
_user32 = ctypes.WinDLL("User32.dll", use_last_error=True)


def _get_capslock_state() -> bool:
    """Return True if Caps Lock LED is currently on."""
    return bool(_user32.GetKeyState(_VK_CAPITAL) & 0x0001)


def _set_capslock_state(target: bool):
    """Force Caps Lock on (True) or off (False) using a synthetic keypress."""
    if _get_capslock_state() != target:
        # Send a full key-down + key-up cycle for VK_CAPITAL.
        _user32.keybd_event(_VK_CAPITAL, 0x45, 0x0000, 0)          # key down
        _user32.keybd_event(_VK_CAPITAL, 0x45, 0x0002, 0)          # key up (KEYEVENTF_KEYUP)
        time.sleep(0.03)


class HotkeyManager:
    """
    Installs a global key hook and calls `on_start` / `on_stop` callbacks.

    Parameters
    ----------
    on_start : callable
        Called (from the keyboard thread) when recording should begin.
    on_stop : callable
        Called (from the keyboard thread) when recording should end.
    """

    def __init__(self, on_start, on_stop):
        self._on_start = on_start
        self._on_stop  = on_stop

        self._initial_capslock = _get_capslock_state()
        self._key_down = False       # True while the key is physically held
        self._toggle_armed = False   # toggle-mode: True while waiting for 2nd press

        self._monitor_stop = threading.Event()
        self._monitor_thread: threading.Thread | None = None

    # ── Public ────────────────────────────────────────────────────────────────

    def start(self):
        """Install the hook. Call once at app startup."""
        hotkey  = config.DICTATION_HOTKEY
        suppress = (
            hotkey.lower().replace("_", " ") == "caps lock"
            and config.DICTATION_SUPPRESS_CAPSLOCK
        )

        self._initial_capslock = _get_capslock_state()
        keyboard.hook_key(hotkey, self._dispatch, suppress=suppress)

        if suppress:
            self._monitor_stop.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_capslock, daemon=True)
            self._monitor_thread.start()

    def stop(self):
        """Remove the hook and restore Caps Lock state."""
        keyboard.unhook_all()
        self._monitor_stop.set()
        _set_capslock_state(self._initial_capslock)

    # ── Event dispatch ─────────────────────────────────────────────────────────

    def _dispatch(self, event):
        if event.event_type == keyboard.KEY_DOWN:
            self._handle_down()
        elif event.event_type == keyboard.KEY_UP:
            self._handle_up()

    def _handle_down(self):
        mode = config.DICTATION_MODE

        if mode == "hold":
            # Fire on_start only once per press (guard against key-repeat events).
            if not self._key_down:
                self._key_down = True
                self._on_start()

        elif mode == "toggle":
            if not self._toggle_armed:
                self._toggle_armed = True
                self._on_start()
            else:
                self._toggle_armed = False
                self._on_stop()

    def _handle_up(self):
        if config.DICTATION_MODE == "hold" and self._key_down:
            self._key_down = False
            self._on_stop()

    # ── Caps Lock monitor ─────────────────────────────────────────────────────

    def _monitor_capslock(self):
        """Background thread: restore Caps Lock LED if it gets accidentally toggled."""
        while not self._monitor_stop.wait(0.2):
            if _get_capslock_state() != self._initial_capslock:
                _set_capslock_state(self._initial_capslock)
