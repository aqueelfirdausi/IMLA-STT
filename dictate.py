"""
dictate.py -- IMLA global voice dictation utility.
Entry point: pythonw dictate.py  (run as Administrator for global hotkey)

Pipeline
--------
  Hold Caps Lock  ->  record mic  ->  Whisper STT  ->  [Groq cleanup]  ->  Ctrl+V
  Click mic button -> same pipeline

Focus handling
--------------
  The floating widget has WS_EX_NOACTIVATE so clicking it never changes which
  window is focused.  A 100-ms poller also tracks the last focused non-widget
  HWND and calls SetForegroundWindow() right before the Ctrl+V paste -- this is
  the belt-and-suspenders safety net for the mic button path.
"""

import sys
import os
import queue
import threading
import tkinter as tk
import ctypes
import time

import config

# ── Load STT model once at startup ────────────────────────────────────────────
# This takes a few seconds on first run (model download) and ~1 s thereafter.
# We do it before building the UI so the hotkey works immediately after startup.
print("[Dictate] Loading Whisper model...")
from stt.transcriber import transcribe
print("[Dictate] Whisper ready.")

from dictation.dict_recorder import record_until_stopped
from dictation.inserter       import insert_text
from dictation.cleanup        import cleanup
from dictation.hotkey         import HotkeyManager
from dictation.widget         import DictateWidget
from dictation.tray           import TrayIcon

_user32 = ctypes.WinDLL("User32.dll", use_last_error=True)


class DictationApp:
    """
    Top-level orchestrator.

    Threading model
    ---------------
    Main thread    : tkinter event loop (widget window + animation).
    Keyboard thread: `keyboard` library runs its own hook thread.
    Audio thread   : one daemon thread spawned per dictation session.
    Tray thread    : pystray's run_detached() thread.

    Rule: background threads NEVER call tkinter methods directly.
    They put ("verb", ...) tuples into self._q; the main thread drains
    the queue every 40 ms via root.after() and acts on them.

    Exception: widget.update_amplitude() is safe to call from any thread
    because it only mutates a deque and a float (GIL-atomic).
    """

    def __init__(self):
        # Hidden tk root -- only provides the event loop.
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("IMLA Dictate")

        self._q           = queue.Queue()
        self._stop_event  = threading.Event()
        self._recording   = False
        self._audio_thread: threading.Thread | None = None

        # Last focused window that is NOT our widget.
        self._last_focus_hwnd: int = 0

        # after() handle for the pending auto-hide timer (None = no timer set).
        self._hide_timer_id = None

        # Build components
        self._widget = DictateWidget(
            root=self._root,
            on_mic=self._on_mic_click,
        )

        self._hotkey = HotkeyManager(
            on_start=self._on_start,
            on_stop=self._on_stop,
        )

        self._tray = TrayIcon(
            on_quit    =self._quit,
            get_cleanup=lambda: config.DICTATION_AI_CLEANUP,
            set_cleanup=self._set_cleanup,
            get_mode   =lambda: config.DICTATION_MODE,
            set_mode   =self._set_mode,
            on_show    =self._on_tray_click,   # left-click summons widget
        )

    # ── App lifecycle ─────────────────────────────────────────────────────────

    def run(self):
        self._tray.start()
        self._hotkey.start()
        self._root.after(40,  self._drain_queue)
        self._root.after(100, self._poll_focus)    # start focus tracker
        print(
            "[Dictate] Running.\n"
            f"  Hotkey : {config.DICTATION_HOTKEY!r}  ({config.DICTATION_MODE} mode)\n"
            f"  Cleanup: {'ON' if config.DICTATION_AI_CLEANUP else 'OFF'}\n"
            "  Mic button on the floating bar also starts dictation.\n"
            "  Right-click the tray icon to toggle options or quit.\n"
        )
        self._root.mainloop()

    def _quit(self, icon=None, item=None):
        print("[Dictate] Shutting down...")
        self._hotkey.stop()
        self._tray.stop()
        self._root.quit()

    # ── Focus tracker (main thread, every 100 ms) ─────────────────────────────

    def _poll_focus(self):
        """
        Remember the last non-widget focused window so we can restore it
        before inserting text (safety net for the mic-button click path).
        """
        hwnd = _user32.GetForegroundWindow()

        # Collect HWNDs belonging to our own windows so we can exclude them.
        try:
            widget_hwnd = _user32.GetParent(self._widget._win.winfo_id()) or \
                          self._widget._win.winfo_id()
        except Exception:
            widget_hwnd = 0

        root_hwnd = self._root.winfo_id()

        if hwnd and hwnd not in (0, widget_hwnd, root_hwnd):
            self._last_focus_hwnd = hwnd

        self._root.after(100, self._poll_focus)

    # ── Widget visibility helpers (main thread) ───────────────────────────────

    def _on_tray_click(self):
        """
        Called from the pystray thread when the user left-clicks the tray icon.
        Puts a message on the queue so the show happens on the main thread.
        """
        self._q.put(("tray_show",))

    def _hide_later(self, delay_ms: int):
        """
        Schedule the widget to hide after `delay_ms` milliseconds.
        Cancels any previously scheduled hide first so timers don't stack.
        Must be called from the main thread.
        """
        if self._hide_timer_id is not None:
            self._root.after_cancel(self._hide_timer_id)
        self._hide_timer_id = self._root.after(delay_ms, self._do_hide)

    def _do_hide(self):
        """Hide the widget immediately (main thread)."""
        self._hide_timer_id = None
        if not self._recording:   # don't hide while a session is active
            self._widget.set_state("idle")

    # ── Settings (called from tray thread) ────────────────────────────────────

    def _set_cleanup(self, value: bool):
        config.DICTATION_AI_CLEANUP = value
        print(f"[Dictate] AI cleanup: {'ON' if value else 'OFF'}")

    def _set_mode(self, value: str):
        config.DICTATION_MODE = value
        print(f"[Dictate] Mode: {value}")

    # ── Recording start / stop ────────────────────────────────────────────────

    def _on_start(self):
        """
        Called by the keyboard hook (hotkey press) or by _on_mic_click.
        Safe to call from any thread.
        """
        if self._recording:
            return
        self._recording = True
        self._stop_event.clear()
        self._q.put(("state", "listening"))
        self._audio_thread = threading.Thread(
            target=self._pipeline, daemon=True)
        self._audio_thread.start()

    def _on_stop(self):
        """
        Called by the keyboard hook (hotkey release).
        Safe to call from any thread.
        """
        self._stop_event.set()

    def _on_mic_click(self):
        """
        Called when the user clicks the mic button on the widget.
        The widget has WS_EX_NOACTIVATE so this click does NOT change focus.
        This method is called on the main (tkinter) thread.
        """
        if not self._recording:
            self._on_start()
        else:
            self._on_stop()

    # ── Audio pipeline (audio daemon thread) ──────────────────────────────────

    def _pipeline(self):
        """
        Full dictation cycle:
          record  ->  transcribe  ->  [AI cleanup]  ->  restore focus  ->  insert
        """
        try:
            # 1. Record -- pass the widget's update_amplitude directly.
            #    It's safe to call from this thread (GIL-atomic deque/float ops).
            audio = record_until_stopped(
                self._stop_event,
                amplitude_callback=self._widget.update_amplitude,
            )

            if audio is None:
                return

            # 2. Transcribe
            self._q.put(("state", "transcribing"))
            raw_text = transcribe(audio)

            if not raw_text.strip():
                return

            print(f"[STT]    {raw_text}")

            # 3. AI cleanup (optional, falls back to raw on timeout/error)
            if config.DICTATION_AI_CLEANUP:
                final_text = cleanup(raw_text)
                if final_text != raw_text:
                    print(f"[Clean]  {final_text}")
            else:
                final_text = raw_text

            # 4. Restore focus to the target window.
            #    With WS_EX_NOACTIVATE this is usually a no-op (focus never
            #    left), but it's the safety net for the mic-button click path.
            target = self._last_focus_hwnd
            if target:
                _user32.SetForegroundWindow(target)
                time.sleep(0.06)    # give Windows time to activate the window

            # Small pause after key-release so Ctrl+V doesn't race the key-up event.
            time.sleep(0.10)

            # 5. Insert
            insert_text(final_text)
            print(f"[Insert] done.")

        except Exception as exc:
            print(f"[Pipeline] error: {exc}")

        finally:
            self._recording = False
            self._q.put(("state", "idle"))
            self._tray.set_recording(False)

    # ── Queue drain (main thread, every 40 ms) ─────────────────────────────────

    def _drain_queue(self):
        try:
            while True:
                msg = self._q.get_nowait()
                self._dispatch(msg)
        except queue.Empty:
            pass
        finally:
            self._root.after(40, self._drain_queue)

    def _dispatch(self, msg: tuple):
        verb = msg[0]

        if verb == "state":
            state = msg[1]
            self._widget.set_state(state)
            self._tray.set_recording(state == "listening")
            # After insertion completes (state → idle), hide the widget after 2 s.
            if state == "idle":
                self._hide_later(2_000)

        elif verb == "tray_show":
            # User left-clicked the tray icon: show the widget so they can
            # click the mic button.  Auto-hide after 8 s if nothing happens.
            if not self._recording:
                self._widget.show()
                self._hide_later(8_000)


# ─────────────────────────────────────────────────────────────────────────────

def main():
    if not config.GROQ_API_KEY and config.DICTATION_AI_CLEANUP:
        print(
            "[Dictate] WARNING: GROQ_API_KEY not set -- "
            "AI cleanup will be skipped (raw transcription inserted)."
        )
    DictationApp().run()


if __name__ == "__main__":
    main()
