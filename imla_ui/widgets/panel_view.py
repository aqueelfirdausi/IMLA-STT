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
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtWebEngineWidgets import QWebEngineView

from imla_ui.app_state              import AppState
from imla_ui.widgets.title_bar      import TitleBar
from imla_ui.widgets.waveform_widget import WaveformWidget
from imla_ui.widgets.orb_widget     import OrbWidget, ORB_SIZE
from imla_ui.widgets.transcript_view import TranscriptView
from imla_ui.widgets.action_bar     import ActionBar
from imla_ui.widgets.status_bar     import StatusBar
from imla_ui.colors                 import C

# ── Layout constants ──────────────────────────────────────────────────────────
ORB_ZONE_H     = 248    # TUNE: height of orb + waveform area
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

        # 3. Transcript card (with side margins via a wrapper)
        self._transcript = TranscriptView(self._state, self)
        self._transcript.setFixedHeight(TRANSCRIPT_H)
        self._layout_with_margin(root, self._transcript, SIDE_MARGIN)

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
        self._action_bar.copy_clicked.connect(self.copy_clicked)
        self._action_bar.insert_clicked.connect(self.insert_clicked)
        self._action_bar.clear_clicked.connect(self.clear_clicked)
        self._orb_zone.mic_clicked.connect(self.mic_clicked)

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
        js = f"ampTarget = {value:.4f}; autoOsc = false;"
        self._waveform.page().runJavaScript(js)

    def set_web_idle(self):
        self._waveform.page().runJavaScript("autoOsc = true;")

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setAutoFillBackground(False)

        # QWebEngineView — fills the entire zone, loads the HTML waveform prototype
        self._waveform = QWebEngineView(self)
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
        }
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
