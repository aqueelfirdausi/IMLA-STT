"""
imla_ui/app_state.py
────────────────────
Single source of truth for all application state.

Rules
─────
• Every piece of mutable UI-relevant state lives here – never in widgets.
• Widgets READ from AppState via signals and properties.
• Business logic (audio, STT) WRITES to AppState via its setter methods.
• The elapsed timer is self-contained here so the StatusBar just reacts to
  elapsed_seconds_changed without knowing anything about wall-clock time.
"""
from PySide6.QtCore import QObject, Signal, QTimer


class AppState(QObject):
    # ── Signals ───────────────────────────────────────────────────────────────
    # Each signal is emitted ONLY when the value actually changes.

    mode_changed            = Signal(str)    # "panel" | "pill"
    engine_status_changed   = Signal(str)    # "idle" | "listening" | "processing" | "error"
    is_recording_changed    = Signal(bool)
    elapsed_seconds_changed = Signal(int)    # whole seconds since recording started
    final_text_changed      = Signal(str)    # full committed transcript so far
    interim_text_changed    = Signal(str)    # current in-progress recognition chunk
    amplitude_changed       = Signal(float)  # 0.0 – 1.0  RMS from the audio worker
    journal_mode_changed    = Signal(bool)   # True = journal mode on

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── Private backing fields ────────────────────────────────────────────
        self._mode            = "panel"
        self._engine_status   = "idle"
        self._is_recording    = False
        self._elapsed_seconds = 0
        self._final_text      = ""
        self._interim_text    = ""
        self._amplitude       = 0.0
        self._journal_mode    = False

        # ── Elapsed timer (self-contained) ────────────────────────────────────
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def engine_status(self) -> str:
        return self._engine_status

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def elapsed_seconds(self) -> int:
        return self._elapsed_seconds

    @property
    def final_text(self) -> str:
        return self._final_text

    @property
    def interim_text(self) -> str:
        return self._interim_text

    @property
    def amplitude(self) -> float:
        return self._amplitude

    @property
    def journal_mode(self) -> bool:
        return self._journal_mode

    # ── Setters ───────────────────────────────────────────────────────────────

    def set_mode(self, value: str) -> None:
        """Switch between "panel" and "pill" view."""
        if self._mode != value:
            self._mode = value
            self.mode_changed.emit(value)

    def set_engine_status(self, value: str) -> None:
        """Update engine status label.  Accepted values: idle / listening / processing / error."""
        if self._engine_status != value:
            self._engine_status = value
            self.engine_status_changed.emit(value)

    def set_is_recording(self, value: bool) -> None:
        """
        Start or stop the elapsed timer.
        NOTE: engine_status is NOT set here; the AudioWorker controls it
        exclusively via its status_changed signal so there is one authority.
        """
        if self._is_recording != value:
            self._is_recording = value
            if value:
                self._elapsed_seconds = 0
                self._elapsed_timer.start()
            else:
                self._elapsed_timer.stop()
                self.set_interim_text("")    # clear dangling interim on stop
            self.is_recording_changed.emit(value)

    def set_journal_mode(self, on: bool) -> None:
        """Toggle journal mode. When on, transcripts are saved to file instead of pasted."""
        if self._journal_mode != on:
            self._journal_mode = on
            self.journal_mode_changed.emit(on)

    def set_amplitude(self, value: float) -> None:
        """Update waveform amplitude.  Clamps to [0.0, 1.0]."""
        clamped = max(0.0, min(1.0, value))
        self._amplitude = clamped
        self.amplitude_changed.emit(clamped)

    def append_final_text(self, chunk: str) -> None:
        """
        Append a committed transcript chunk.
        Trims the stored text to MAX_CHARS to prevent unbounded growth.
        """
        MAX_CHARS = 8000   # TUNE: trim threshold for long sessions
        self._final_text = (self._final_text + chunk)[-MAX_CHARS:]
        self.final_text_changed.emit(self._final_text)
        self.set_interim_text("")   # committed chunk clears interim

    def set_interim_text(self, value: str) -> None:
        """Update the in-progress (not yet committed) recognition text."""
        if self._interim_text != value:
            self._interim_text = value
            self.interim_text_changed.emit(value)

    def clear_transcript(self) -> None:
        """Clear both final and interim text."""
        self._final_text  = ""
        self._interim_text = ""
        self.final_text_changed.emit("")
        self.interim_text_changed.emit("")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _tick_elapsed(self) -> None:
        self._elapsed_seconds += 1
        self.elapsed_seconds_changed.emit(self._elapsed_seconds)
