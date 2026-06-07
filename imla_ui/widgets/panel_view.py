"""
imla_ui/widgets/panel_view.py
──────────────────────────────
PanelView — the full expanded panel.

Assembles (top → bottom):
  TitleBar
  _OrbZone  (WaveformWidget + OrbWidget overlaid + status label)
  TranscriptView
  ActionBar
  StatusBar

_OrbZone is a private helper that sizes WaveformWidget to fill the zone
and keeps OrbWidget centred on top.  OrbWidget has setAutoFillBackground(False)
so the waveform behind it remains visible.

This widget is transparent; MainWindow paints the glass background beneath it.
"""
from pathlib import Path

from PySide6.QtCore    import Qt, Signal, QPointF, QUrl
from PySide6.QtGui     import QPainter, QColor, QFont, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QStackedWidget
from PySide6.QtWebEngineWidgets import QWebEngineView

from imla_ui.app_state              import AppState
from imla_ui.widgets.title_bar      import TitleBar
from imla_ui.widgets.waveform_widget import WaveformWidget
from imla_ui.widgets.orb_widget     import OrbWidget, ORB_SIZE
from imla_ui.widgets.transcript_view import TranscriptView
from imla_ui.widgets.journal_chat_view import JournalChatView
from imla_ui.widgets.action_bar     import ActionBar
from imla_ui.widgets.status_bar     import StatusBar
from imla_ui.colors                 import C

# ── Layout constants ──────────────────────────────────────────────────────────
ORB_ZONE_H     = 248    # TUNE: height of orb + waveform area

# --- Web waveform amplitude mapping (tune by eye) ---
# Raw RMS arrives ~0.0002 (silence) to ~0.19 (loud speech peaks).
# The web waveform only reads as "active" from ~0.30 up, so map the
# speech band into the visible band. Clamped to [0,1].
AMP_IN_MIN = 0.02    # below this = treated as silence
AMP_IN_MAX = 0.18    # at/above this = full output
AMP_OUT_MIN = 0.25   # output floor when just barely speaking
AMP_OUT_MAX = 1.0    # output ceiling at loud speech
TRANSCRIPT_H   = 158    # TUNE: transcript card height
SIDE_MARGIN    =  16    # TUNE: left/right margin for card + buttons



class PanelView(QWidget):
    """
    Full panel.  Transparent background — MainWindow paints the glass rect.

    Signals forwarded upward to MainWindow:
      to_pill_clicked    – title bar pill button
      minimize_clicked   – title bar OS-minimise
      close_clicked      – title bar close
      copy_clicked       – action bar Copy
      insert_clicked     – action bar Insert
      clear_clicked      – action bar Clear
    """

    to_pill_clicked  = Signal()
    minimize_clicked = Signal()
    close_clicked    = Signal()
    copy_clicked     = Signal()
    insert_clicked   = Signal()
    clear_clicked    = Signal()
    mic_clicked      = Signal()   # orb button → start/stop recording

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setAutoFillBackground(False)
        self._build_layout()
        self._connect_signals()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. Title bar (full width, no margins)
        self._title_bar = TitleBar(self)
        root.addWidget(self._title_bar)

        # 2. Orb zone (full width)
        self._orb_zone = _OrbZone(self._state, self)
        self._orb_zone.setFixedHeight(ORB_ZONE_H)
        root.addWidget(self._orb_zone)

        # 3. Transcript / journal-chat stack (with side margins via a wrapper)
        self._transcript = TranscriptView(self._state, self)
        self._journal_chat = JournalChatView(self)
        self._center_stack = QStackedWidget(self)
        self._center_stack.addWidget(self._transcript)    # index 0
        self._center_stack.addWidget(self._journal_chat)  # index 1
        self._center_stack.setFixedHeight(TRANSCRIPT_H)
        self._layout_with_margin(root, self._center_stack, SIDE_MARGIN)

        # 4. Action bar (with side margins)
        self._action_bar = ActionBar(self)
        self._layout_with_margin(root, self._action_bar, SIDE_MARGIN)

        # 5. Status bar (full width)
        self._status_bar = StatusBar(self._state, self)
        root.addWidget(self._status_bar)

    def _layout_with_margin(self, vbox: QVBoxLayout, widget: QWidget,
                            margin: int):
        """Wrap widget in a container with left/right margins."""
        from PySide6.QtWidgets import QHBoxLayout
        container = QWidget(self)
        container.setAutoFillBackground(False)
        hl = QHBoxLayout(container)
        hl.setContentsMargins(margin, 0, margin, 0)
        hl.setSpacing(0)
        hl.addWidget(widget)
        vbox.addWidget(container)

    def _connect_signals(self):
        self._title_bar.to_pill_clicked.connect(self.to_pill_clicked)
        self._title_bar.minimize_clicked.connect(self.minimize_clicked)
        self._title_bar.close_clicked.connect(self.close_clicked)
        self._title_bar.ask_clicked.connect(self._toggle_journal_chat)
        self._action_bar.copy_clicked.connect(self.copy_clicked)
        self._action_bar.insert_clicked.connect(self.insert_clicked)
        self._action_bar.clear_clicked.connect(self.clear_clicked)
        self._orb_zone.mic_clicked.connect(self.mic_clicked)

    # ── Journal chat toggle ───────────────────────────────────────────────────

    def _toggle_journal_chat(self):
        """Flip the centre slot between the transcript (0) and chat view (1)."""
        idx = self._center_stack.currentIndex()
        self._center_stack.setCurrentIndex(0 if idx == 1 else 1)

    # ── Web waveform bridge (passthroughs into _OrbZone) ─────────────────────

    def set_web_amplitude(self, value: float):
        self._orb_zone.set_web_amplitude(value)

    def set_web_idle(self):
        self._orb_zone.set_web_idle()


# ── Private helper ────────────────────────────────────────────────────────────

class _OrbZone(QWidget):
    """
    Full-width zone that hosts WaveformWidget (background) and OrbWidget
    (centred on top) plus the status label beneath the orb.

    Resizing keeps the orb centred and the waveform filling the zone.
    """

    mic_clicked = Signal()   # forwarded from OrbWidget.clicked

    def set_web_amplitude(self, value: float):
        if value <= AMP_IN_MIN:
            mapped = 0.0
        elif value >= AMP_IN_MAX:
            mapped = AMP_OUT_MAX
        else:
            t = (value - AMP_IN_MIN) / (AMP_IN_MAX - AMP_IN_MIN)
            mapped = AMP_OUT_MIN + t * (AMP_OUT_MAX - AMP_OUT_MIN)
        js = f"ampTarget = {mapped:.4f}; autoOsc = false;"
        self._waveform.page().runJavaScript(js)

    def set_web_idle(self):
        self._waveform.page().runJavaScript("autoOsc = true;")

    def _on_wf_loaded(self, ok: bool):
        self._wf_loaded = True
        # Page is now live — resize canvas to match the current real zone width.
        self._waveform.page().runJavaScript("if (typeof resize === 'function') resize();")

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setAutoFillBackground(False)

        # QWebEngineView — fills the entire zone, loads the HTML waveform prototype
        self._wf_loaded = False
        self._waveform = QWebEngineView(self)
        self._waveform.loadFinished.connect(self._on_wf_loaded)
        _html = (Path(__file__).resolve().parents[2] / "prototypes" / "waveform_web.html")
        self._waveform.load(QUrl.fromLocalFile(str(_html)))

        # OrbWidget — centred on top
        self._orb = OrbWidget(state, self)
        self._orb.clicked.connect(self.mic_clicked)

        # Status label — below the orb  ("● Listening…")
        self._status_lbl = _StatusLabel(state, self)

    def resizeEvent(self, event):
        w = self.width()
        h = self.height()

        # Waveform fills zone
        self._waveform.setGeometry(0, 0, w, h)
        if self._wf_loaded:
            self._waveform.page().runJavaScript("if (typeof resize === 'function') resize();")

        # Orb centred
        ox = (w - ORB_SIZE) // 2
        oy = (h - ORB_SIZE) // 2 - 12   # TUNE: shift up slightly for label
        self._orb.setGeometry(ox, oy, ORB_SIZE, ORB_SIZE)
        self._orb.raise_()

        # Status label centred below orb
        lbl_y = oy + ORB_SIZE + 8    # TUNE: gap between orb bottom and label
        lbl_w = 160                  # TUNE
        lbl_h = 24                   # TUNE
        self._status_lbl.setGeometry((w - lbl_w) // 2, lbl_y, lbl_w, lbl_h)
        self._status_lbl.raise_()


class _StatusLabel(QWidget):
    """
    "● Listening…" label shown beneath the orb.
    Transparent background; paints a coloured dot + text.
    """

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setAutoFillBackground(False)
        state.engine_status_changed.connect(self.update)
        state.is_recording_changed.connect(self.update)
        state.journal_mode_changed.connect(self.update)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        status = self._state.engine_status

        _STATUS_MAP = {
            "loading":    ("Loading...",    QColor(90, 110, 155)),
            "idle":       ("Idle",          QColor(90, 110, 155)),
            "listening":  ("Listening...",  C.BLUE),
            "processing": ("Processing...", C.CYAN),
            "error":      ("Error",         C.RED),
            "journal":    ("Journal",       QColor(160, 100, 220)),
        }
        if self._state.journal_mode and status == "idle":
            status = "journal"
        label, color = _STATUS_MAP.get(status, ("Idle", QColor(90, 110, 155)))

        # Dot
        dot_x = w / 2 - 40    # TUNE: approximate centre offset
        dot_y = h / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 255))
        painter.drawEllipse(
            int(dot_x - 4), int(dot_y - 4), 8, 8)

        # Text
        font = QFont("Segoe UI", 10)   # TUNE
        painter.setFont(font)
        painter.setPen(QPen(color))
        from PySide6.QtCore import QRectF, Qt as _Qt
        painter.drawText(
            QRectF(dot_x + 10, 0, w - dot_x - 10, h),
            _Qt.AlignmentFlag.AlignVCenter,
            label,
        )
