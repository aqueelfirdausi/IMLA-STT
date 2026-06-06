"""
imla_ui/audio_worker.py
────────────────────────
Real dictation engine on a QThread.

Thread-safety contract
──────────────────────
• run() lives entirely on the QThread.
• ALL engine imports (stt, dictation.*) happen INSIDE run() so the Whisper
  model never loads on the GUI thread. The window is never frozen on startup.
• Signals are the only channel back to the GUI; Qt's automatic queued-connection
  delivers them safely across the thread boundary.
• amplitude_ready is emitted from sounddevice's C audio callback thread (not
  even the QThread); Qt handles the queued delivery transparently — no lock needed.
• last_focus_hwnd is written on the GUI main thread (100 ms QTimer poller in
  MainWindow) and read here just before insert_text().  Python int assignment
  is GIL-atomic so no explicit lock is needed.
• The keyboard library (HotkeyManager) runs its own OS hook thread; its
  callbacks only touch threading.Event objects — thread-safe primitives.

Pipeline per dictation session
────────────────────────────────
  record_until_stopped  →  transcribe  →  [Groq cleanup]
  →  SetForegroundWindow + timing sleeps  →  insert_text (Ctrl+V)

Both trigger paths (Caps Lock hotkey AND orb/pill mic button) funnel through
the SAME _start_event / _stop_event mechanism.  No duplicated logic.
"""
from __future__ import annotations

import ctypes
import threading
import time

from PySide6.QtCore import QThread, Signal


# ── Windows API (used for focus restore only) ─────────────────────────────────
_user32 = ctypes.WinDLL("User32.dll", use_last_error=True)


class AudioWorker(QThread):
    """
    Manages mic capture, Whisper STT, Groq cleanup, and text insertion.
    Emits signals only; never touches any widget.

    Signals
    ───────
    model_ready()          – Whisper loaded; hotkey is armed; safe to dictate
    model_load_error(str)  – Whisper failed; str is the error message
    status_changed(str)    – "loading"|"idle"|"listening"|"processing"|"error"
    recording_changed(bool)– True = capture started; False = capture stopped
    amplitude_ready(float) – 0.0–1.0 RMS from each audio chunk (~30×/sec)
    interim_ready(str)     – raw Whisper text before cleanup (show in transcript)
    transcript_ready(str)  – final cleaned text (also inserted into focused app)
    """

    model_ready      = Signal()
    model_load_error = Signal(str)
    status_changed   = Signal(str)
    recording_changed = Signal(bool)
    amplitude_ready  = Signal(float)
    interim_ready    = Signal(str)
    transcript_ready = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── Shared state (GIL-atomic primitives) ──────────────────────────────
        self._running  = True            # False = shut down the loop
        self._recording = False          # True while inside _run_pipeline()
        self._start_event = threading.Event()
        self._stop_event  = threading.Event()

        # Written by MainWindow's 100 ms focus-poll timer (GUI thread),
        # read by _run_pipeline() just before paste.
        self.last_focus_hwnd: int = 0

        # Populated inside run() after lazy imports
        self._transcribe_fn  = None
        self._record_fn      = None
        self._insert_fn      = None
        self._cleanup_fn     = None
        self._journal_fn     = None   # callable → bool; set via set_journal_fn()

    def set_journal_fn(self, fn) -> None:
        """Set a callable that returns the live journal_mode bool. Call before start()."""
        self._journal_fn = fn

    # ── QThread entry point ───────────────────────────────────────────────────

    def run(self):
        """
        Everything here runs on the worker thread.

        Step 1  Load Whisper  (slow – import triggers model download/load)
        Step 2  Import remaining engine modules  (fast)
        Step 3  Block-and-run pipeline loop until stop_worker() is called
        """

        # ── Step 1: Whisper ───────────────────────────────────────────────────
        self.status_changed.emit("loading")
        try:
            from stt.transcriber import transcribe
            self._transcribe_fn = transcribe
        except Exception as exc:
            self.model_load_error.emit(str(exc))
            self.status_changed.emit("error")
            return

        # ── Step 2: remaining engine imports (all fast) ───────────────────────
        from dictation.dict_recorder import record_until_stopped
        from dictation.inserter       import insert_text
        from dictation.cleanup        import cleanup

        self._record_fn  = record_until_stopped
        self._insert_fn  = insert_text
        self._cleanup_fn = cleanup

        self.model_ready.emit()
        self.status_changed.emit("idle")

        # ── Step 3: pipeline loop ─────────────────────────────────────────────
        while self._running:
            # Block until a recording is requested (100 ms timeout to stay
            # responsive to stop_worker()).
            if not self._start_event.wait(timeout=0.1):
                continue

            self._start_event.clear()

            if self._running:
                self._run_pipeline()

        # ── Cleanup ───────────────────────────────────────────────────────────
        pass  # nothing to release; mic button is the only trigger

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def _run_pipeline(self):
        """
        One full dictation cycle.  Runs on the worker QThread.

        Record → Transcribe → [Cleanup] → Restore focus → Insert
        """
        self._recording = True
        self.recording_changed.emit(True)
        self.status_changed.emit("listening")

        try:
            # 1. Capture mic until stop_event is set (hotkey release or mic button).
            #    amplitude_ready is emitted from the sounddevice C callback thread;
            #    Qt queues it safely to the GUI thread.
            audio = self._record_fn(
                self._stop_event,
                amplitude_callback=lambda amp: self.amplitude_ready.emit(amp),
            )

            self.recording_changed.emit(False)

            if audio is None:
                # Too short or nothing recorded
                return

            # 2. Transcribe
            self.status_changed.emit("processing")
            raw_text = self._transcribe_fn(audio)

            if not raw_text.strip():
                return

            # Show raw text immediately in the transcript view
            self.interim_ready.emit(raw_text)

            # 3. AI cleanup (optional — silent fallback to raw on error/timeout)
            import config
            if config.DICTATION_AI_CLEANUP:
                final_text = self._cleanup_fn(raw_text)
            else:
                final_text = raw_text

            # Journal mode: save to file instead of pasting into another app.
            if self._journal_fn is not None and self._journal_fn():
                from imla_ui import journal
                journal.save_entry(final_text)
                self.transcript_ready.emit(final_text)
                return

            # 4. Restore focus to the window the user was typing in BEFORE
            #    pressing the hotkey / clicking the mic button.
            #    SetForegroundWindow + timing sleeps are preserved EXACTLY
            #    from the working dictate.py to avoid any paste regression.
            target = self.last_focus_hwnd
            if target:
                _user32.SetForegroundWindow(target)
                time.sleep(0.06)    # let Windows activate the target window

            time.sleep(0.10)        # key-release race guard (from dictate.py)

            # 5. Insert via clipboard + Ctrl+V
            self._insert_fn(final_text)

            # Push the final text to the transcript view
            self.transcript_ready.emit(final_text)

        except Exception as exc:
            print(f"[Worker] Pipeline error: {exc}")
            self.status_changed.emit("error")
        finally:
            self._recording = False
            self.status_changed.emit("idle")

    # ── GUI-thread controls (called from MainWindow, thread-safe) ─────────────

    def toggle_recording(self):
        """
        Called by the orb/pill mic button click.
        Toggles between start and stop.  Thread-safe via Event primitives.
        """
        if not self._transcribe_fn:
            return   # Whisper not loaded yet
        if self._recording:
            self.request_stop()
        else:
            self.request_start()

    def request_start(self):
        """Programmatic start (mic button first click).  Thread-safe."""
        if not self._recording:
            self._stop_event.clear()
            self._start_event.set()

    def request_stop(self):
        """Programmatic stop (mic button second click / key release).  Thread-safe."""
        self._stop_event.set()

    def _run_insert_only(self, text: str):
        """
        Re-paste an already-transcribed string without re-recording.
        Used by the Insert button.  Preserves the same focus-restore + timing.
        """
        if not self._insert_fn:
            return
        try:
            target = self.last_focus_hwnd
            if target:
                _user32.SetForegroundWindow(target)
                time.sleep(0.06)
            time.sleep(0.10)
            self._insert_fn(text)
        except Exception as exc:
            print(f"[Worker] Insert error: {exc}")

    def stop_worker(self):
        """Shut down the worker thread cleanly.  Call from GUI thread on close."""
        self._running = False
        self._stop_event.set()
        self._start_event.set()   # unblock the wait() in run()
        self.wait(3000)           # up to 3 s
