"""
imla_ui/main_window.py
───────────────────────
Outer shell.  Owns the window, AppState, AudioWorker, system tray, and focus
tracker.  Wires everything together without containing any business logic.

Startup sequence
────────────────
1. Window appears immediately in pill mode (tiny, unobtrusive).
2. AudioWorker.run() starts on a QThread → loads Whisper in the background.
3. status_changed("loading") → StatusBar shows "Loading..."
4. model_ready() → status becomes "idle".  Hotkey is armed.  Orb accepts clicks.

Focus tracker
─────────────
A 100 ms QTimer polls GetForegroundWindow().  Any HWND that isn't our own
window is stored in worker.last_focus_hwnd.  The worker reads this just before
calling insert_text() so the paste lands in the correct application.

Glass background
────────────────
paintEvent() draws a single rounded-rect fill.  In pill mode the rect is small
(stadium shape).  In panel mode it's the full panel.  No child widget paints
its own background for the outer glass.
"""
from __future__ import annotations

import ctypes
import os

from PySide6.QtCore    import Qt, QRectF, QTimer
from PySide6.QtGui     import (QPainter, QPainterPath, QBrush, QKeySequence,
                               QShortcut, QIcon, QPixmap, QColor)
from PySide6.QtWidgets import (QMainWindow, QWidget, QStackedWidget,
                                QApplication, QSystemTrayIcon, QMenu)

from imla_ui.colors              import C
from imla_ui.app_state           import AppState
from imla_ui.audio_worker        import AudioWorker
from imla_ui.widgets.panel_view  import PanelView
from imla_ui.widgets.pill_view   import PillView

# ── Window geometry constants ─────────────────────────────────────────────────
PANEL_W   = 900    # TUNE
PANEL_H   = 580    # TUNE
PANEL_R   =  20    # TUNE: panel corner radius

PILL_W    = 300    # TUNE: window width in pill mode
PILL_H     =  72   # TUNE: window height in pill mode
# Corner radius in pill mode: half of height → stadium / fully-rounded ends
PILL_R    = PILL_H // 2

# Windows API
_user32 = ctypes.WinDLL("User32.dll", use_last_error=True)


class MainWindow(QMainWindow):
    """Frameless translucent host.  Starts in pill mode."""

    def __init__(self):
        super().__init__()

        # ── Window flags ──────────────────────────────────────────────────────
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool          # no taskbar entry
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # ── State & worker ────────────────────────────────────────────────────
        self._state  = AppState(self)
        self._worker = AudioWorker(self)
        self._worker_ready = False   # True once model_ready fires
        self._worker.set_journal_fn(lambda: self._state.journal_mode)

        # ── Stack: panel (0) and pill (1) ─────────────────────────────────────
        self._stack       = QStackedWidget(self)
        self._stack.setAutoFillBackground(False)   # don't let the stack paint over the pill shape
        self._panel_view  = PanelView(self._state, self._stack)
        self._pill_view   = PillView(self._state, self._stack)
        self._stack.addWidget(self._panel_view)   # index 0
        self._stack.addWidget(self._pill_view)    # index 1
        # QStackedWidget's sizeHint is the max of ALL children (even hidden ones).
        # Setting minimum to zero lets setFixedSize win when we shrink to pill.
        self._stack.setMinimumSize(0, 0)
        self.setCentralWidget(self._stack)

        # ── Wire all signals ──────────────────────────────────────────────────
        self._wire_worker()
        self._wire_panel()
        self._wire_pill()
        self._setup_shortcuts()
        self._setup_tray()
        self._setup_focus_tracker()

        # ── Start worker (Whisper loads in background on the QThread) ─────────
        self._worker.start()

        # ── Start in pill mode ────────────────────────────────────────────────
        # MUST call _to_pill() — not _apply_pill_geometry() — so the
        # QStackedWidget switches to index 1 (PillView) before the window
        # is shown.  Calling only _apply_pill_geometry() left the stack on
        # index 0 (PanelView), which was then clipped into the pill-sized frame.
        self._to_pill()

    # ── paintEvent — glass background ─────────────────────────────────────────

    def paintEvent(self, event):
        """Panel-mode glass fill only. Pill shape is painted by PillView itself."""
        if self._state.mode != "panel":
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), PANEL_R, PANEL_R)
        painter.fillPath(path, QBrush(C.BG_WINDOW))

    # ── Worker signal wiring ──────────────────────────────────────────────────

    def _wire_worker(self):
        """
        All worker → state connections.
        Qt creates queued connections automatically because worker lives on a
        different thread, so every emit is safe no matter which thread fires it.
        """
        w = self._worker
        s = self._state

        w.model_ready.connect(self._on_model_ready)
        w.model_load_error.connect(self._on_model_error)
        w.status_changed.connect(s.set_engine_status)
        w.recording_changed.connect(s.set_is_recording)
        w.amplitude_ready.connect(s.set_amplitude)
        w.amplitude_ready.connect(self._panel_view.set_web_amplitude)
        w.recording_changed.connect(
            lambda rec: self._panel_view.set_web_idle() if not rec else None
        )
        w.interim_ready.connect(s.set_interim_text)
        w.transcript_ready.connect(s.append_final_text)

    def _on_model_ready(self):
        self._worker_ready = True
        print("[MainWindow] Whisper ready.")

    def _on_model_error(self, msg: str):
        print(f"[MainWindow] Model load error: {msg}")

    # ── Panel / pill signal wiring ────────────────────────────────────────────

    def _wire_panel(self):
        p = self._panel_view
        p.to_pill_clicked.connect(self._to_pill)
        p.minimize_clicked.connect(self.showMinimized)
        p.close_clicked.connect(self._on_close)
        p.copy_clicked.connect(self._on_copy)
        p.insert_clicked.connect(self._on_insert)
        p.clear_clicked.connect(self._on_clear)
        p.mic_clicked.connect(self._toggle_recording)

    def _wire_pill(self):
        p = self._pill_view
        p.expand_requested.connect(self._to_panel)
        p.mic_clicked.connect(self._toggle_recording)

    # ── Keyboard shortcuts ────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(self._on_copy)
        QShortcut(QKeySequence("Ctrl+I"), self).activated.connect(self._on_insert)
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self._on_clear)
        QShortcut(QKeySequence("Ctrl+J"), self).activated.connect(self._on_toggle_journal)

    def _on_toggle_journal(self):
        self._state.set_journal_mode(not self._state.journal_mode)

    # ── System tray ───────────────────────────────────────────────────────────

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(self._make_tray_icon())
        self._tray.setToolTip("IMLA Dictate")

        menu = QMenu()

        # Show/hide toggle
        self._show_action = menu.addAction("Show panel")
        self._show_action.triggered.connect(self._tray_toggle_view)

        menu.addSeparator()

        # AI cleanup toggle
        import config
        self._cleanup_action = menu.addAction("AI Cleanup")
        self._cleanup_action.setCheckable(True)
        self._cleanup_action.setChecked(config.DICTATION_AI_CLEANUP)
        self._cleanup_action.toggled.connect(self._on_toggle_cleanup)

        menu.addSeparator()
        menu.addAction("Quit", self._on_close)

        self._tray.setContextMenu(menu)

        # Left-click: toggle pill ↔ panel
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._tray_toggle_view()

    def _tray_toggle_view(self):
        if self._state.mode == "pill":
            self._to_panel()
        else:
            self._to_pill()
        self._update_tray_menu()

    def _update_tray_menu(self):
        if self._state.mode == "pill":
            self._show_action.setText("Show panel")
        else:
            self._show_action.setText("Minimise to pill")

    def _on_toggle_cleanup(self, checked: bool):
        import config
        config.DICTATION_AI_CLEANUP = checked
        print(f"[Tray] AI Cleanup: {'ON' if checked else 'OFF'}")

    @staticmethod
    def _make_tray_icon() -> QIcon:
        """Draw a simple mic-in-circle icon if assets/mic.ico isn't available."""
        ico_path = os.path.join(
            os.path.dirname(__file__), "..", "assets", "mic.ico")
        if os.path.exists(ico_path):
            return QIcon(ico_path)
        # Fallback: paint a blue circle
        pix = QPixmap(32, 32)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(C.BLUE))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(2, 2, 28, 28)
        p.end()
        return QIcon(pix)

    # ── Focus tracker (100 ms QTimer, GUI thread) ─────────────────────────────

    def _setup_focus_tracker(self):
        """
        Poll GetForegroundWindow() every 100 ms.
        Store any HWND that isn't our own into worker.last_focus_hwnd.
        This is what lets insert_text() paste into the correct application
        even after the user clicked the IMLA orb button.
        """
        self._our_hwnd: int = 0   # resolved on first poll after window is shown
        self._focus_timer = QTimer(self)
        self._focus_timer.setInterval(100)
        self._focus_timer.timeout.connect(self._poll_focus)
        self._focus_timer.start()

    def _poll_focus(self):
        # Lazily resolve our own HWND (not available before the window is shown)
        if self._our_hwnd == 0:
            try:
                self._our_hwnd = int(self.winId())
            except Exception:
                return

        hwnd = _user32.GetForegroundWindow()
        if hwnd and hwnd != self._our_hwnd:
            self._worker.last_focus_hwnd = hwnd

    # ── Panel ↔ pill switching ────────────────────────────────────────────────

    def _to_pill(self):
        self._state.set_mode("pill")
        self._stack.setCurrentIndex(1)
        self._apply_pill_geometry()
        self._update_tray_menu()

    def _to_panel(self):
        self._state.set_mode("panel")
        self._stack.setCurrentIndex(0)
        self._apply_panel_geometry()
        self._update_tray_menu()

    def _apply_pill_geometry(self):
        self.setFixedSize(PILL_W, PILL_H)
        screen = QApplication.primaryScreen().availableGeometry()
        # Bottom-right corner, above the taskbar
        self.move(screen.width() - PILL_W - 20,
                  screen.height() - PILL_H - 80)

    def _apply_panel_geometry(self):
        self.setFixedSize(PANEL_W, PANEL_H)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width()  - PANEL_W) // 2,
                  (screen.height() - PANEL_H) // 2)

    # ── Recording toggle ──────────────────────────────────────────────────────

    def _toggle_recording(self):
        """Called from orb click (panel) or mic click (pill).  GUI thread."""
        if not self._worker_ready:
            return   # still loading — ignore
        self._worker.toggle_recording()

    # ── Action handlers ───────────────────────────────────────────────────────

    def _on_copy(self):
        QApplication.clipboard().setText(self._state.final_text)

    def _on_insert(self):
        """Re-insert last transcript into focused window."""
        text = self._state.final_text
        if text.strip() and self._worker_ready:
            # Run on worker to get the same focus-restore + timing path
            import threading
            t = threading.Thread(
                target=self._worker._run_insert_only,
                args=(text,), daemon=True)
            t.start()

    def _on_clear(self):
        self._state.clear_transcript()

    def _on_close(self):
        self._focus_timer.stop()
        self._worker.stop_worker()
        self._tray.hide()
        self.close()

    def closeEvent(self, event):
        self._focus_timer.stop()
        self._worker.stop_worker()
        self._tray.hide()
        event.accept()
