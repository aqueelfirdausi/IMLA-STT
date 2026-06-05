"""
imla_ui/widgets/pill_view.py
─────────────────────────────
Minimised compact pill view.

Background is NOT painted here — MainWindow.paintEvent handles it so the
glass pill shape is consistent across panel and pill modes.

Interactions
────────────
• Click the mini orb (left circle) → mic_clicked  (start/stop dictation)
• Double-click anywhere else       → expand_requested  (switch to panel)
• Drag anywhere except the orb     → move the window

Mockup reference (top-right inset):
  [ (mic orb) | ▪▪▪▪▪▪▪  00:01:24 ]
"""
from __future__ import annotations
import math

from PySide6.QtCore    import Qt, QPointF, QRectF, Signal
from PySide6.QtGui     import (QPainter, QPainterPath, QColor, QPen, QBrush, QFont)
from PySide6.QtWidgets import QWidget

from imla_ui.colors    import C
from imla_ui.app_state import AppState

# ── Geometry ──────────────────────────────────────────────────────────────────
ORB_CX  = 38    # TUNE: mini orb centre x
ORB_R   = 22    # TUNE: mini orb radius (clickable + visual)
BAR_X0  = 76    # TUNE: start x of mini eq bars
N_BARS  =  8    # TUNE
BAR_W   =  5    # TUNE
BAR_GAP =  4    # TUNE


class PillView(QWidget):
    """
    Compact pill.  Shown when the panel is minimised.
    Background is transparent; MainWindow.paintEvent draws the pill glass rect.
    """

    expand_requested = Signal()   # double-click → back to panel
    mic_clicked      = Signal()   # orb click → start/stop dictation

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self._state    = state
        self._drag_pos: QPointF | None = None

        self.setAutoFillBackground(False)

        state.elapsed_seconds_changed.connect(self.update)
        state.is_recording_changed.connect(self.update)
        state.amplitude_changed.connect(self.update)
        state.engine_status_changed.connect(self.update)

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # ── Pill background (stadium shape) ────────────────────────────────
        r = h / 2.0
        bg_path = QPainterPath()
        bg_path.addRoundedRect(QRectF(0, 0, w, h), r, r)
        painter.fillPath(bg_path, QBrush(C.BG_WINDOW))

        recording = self._state.is_recording
        status    = self._state.engine_status

        # ── Mini orb (left) ────────────────────────────────────────────────
        cx, cy = float(ORB_CX), h / 2.0
        ring_col = C.RED if recording else (C.RED if status == "error" else C.BLUE)

        # Subtle outer glow
        painter.setPen(QPen(QColor(ring_col.red(), ring_col.green(),
                                   ring_col.blue(), 30), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), ORB_R + 5, ORB_R + 5)

        # Dark fill
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(C.ORB_CORE))
        painter.drawEllipse(QPointF(cx, cy), ORB_R, ORB_R)

        # Ring
        ring_alpha = 255 if recording else 180
        painter.setPen(QPen(QColor(ring_col.red(), ring_col.green(),
                                   ring_col.blue(), ring_alpha), 2.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), ORB_R, ORB_R)

        # Tiny mic dot
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(200, 220, 255, 220 if recording else 160)))
        painter.drawEllipse(QPointF(cx, cy - 3), 5, 7)   # TUNE: stub mic

        # ── Mini eq bars (centre) ──────────────────────────────────────────
        amp = self._state.amplitude if recording else 0.0
        import math, time
        t = time.monotonic()

        bar_color = QColor(C.BLUE.red(), C.BLUE.green(), C.BLUE.blue(),
                           180 if recording else 80)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bar_color))

        for i in range(N_BARS):
            if recording:
                bh = 4 + int(12 * amp * abs(math.sin(t * 4 + i * 0.7)))
            else:
                bh = 3 + (i % 3)    # static decorative heights
            bx = BAR_X0 + i * (BAR_W + BAR_GAP)
            painter.drawRoundedRect(
                QRectF(bx, cy - bh / 2, BAR_W, bh), 2, 2)

        # ── Timer / status text (right) ────────────────────────────────────
        secs  = self._state.elapsed_seconds
        if recording:
            label = f"{secs // 60:02d}:{secs % 60:02d}"
            text_color = C.TEXT_LABEL
        else:
            label      = self._state.engine_status.capitalize()
            text_color = QColor(80, 100, 150)

        font = QFont("Segoe UI", 10, QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(QPen(text_color))

        # Blue dot before timer when recording
        if recording:
            painter.setBrush(QBrush(C.BLUE))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(w - 78, cy), 4, 4)   # TUNE
            painter.setPen(QPen(text_color))

        painter.drawText(QRectF(w - 70, 0, 60, h),    # TUNE
                         Qt.AlignmentFlag.AlignVCenter, label)

    # ── Interactions ──────────────────────────────────────────────────────────

    def _is_on_orb(self, x: float, y: float) -> bool:
        return math.hypot(x - ORB_CX, y - self.height() / 2) <= ORB_R

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_on_orb(event.position().x(), event.position().y()):
                self.mic_clicked.emit()
            else:
                self._drag_pos = event.globalPosition() - QPointF(self.pos())

    def mouseMoveEvent(self, event):
        if (event.buttons() == Qt.MouseButton.LeftButton
                and self._drag_pos is not None):
            self.window().move(
                (event.globalPosition() - self._drag_pos).toPoint())

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        if not self._is_on_orb(event.position().x(), event.position().y()):
            self.expand_requested.emit()
