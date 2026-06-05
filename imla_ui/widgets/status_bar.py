"""
imla_ui/widgets/status_bar.py
──────────────────────────────
Bottom status row with three pill widgets.

Left pill   — [● Listening…]  or [● Idle]   (tracks engine_status)
Centre pill — [☁ ● Connected]              (tracks engine_status)
Right pill  — [00:01:24]                   (tracks elapsed_seconds)

Each pill is a self-painting QWidget.  The StatusBar arranges them
in a QHBoxLayout.  No business logic; no state writes.
"""
from __future__ import annotations

from PySide6.QtCore    import Qt, QRectF, QPointF
from PySide6.QtGui     import (QPainter, QPainterPath, QColor, QPen,
                               QBrush, QFont)
from PySide6.QtWidgets import QWidget, QHBoxLayout, QSizePolicy

from imla_ui.colors    import C
from imla_ui.app_state import AppState

PILL_H   = 32    # TUNE: pill height
PILL_R   = PILL_H / 2   # fully-rounded pill
PAD_H    = 16    # TUNE: outer horizontal margin
DOT_R    =  4    # TUNE: status dot radius


class StatusBar(QWidget):
    """Horizontal row: left status pill | stretch | connected pill + timer pill."""

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)    # TUNE
        self.setAutoFillBackground(False)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(PAD_H, 9, PAD_H, 9)
        lay.setSpacing(8)

        self._status_pill    = _StatusPill(state)
        self._connected_pill = _ConnectedPill(state)
        self._timer_pill     = _TimerPill(state)

        lay.addWidget(self._status_pill)
        lay.addStretch()
        lay.addWidget(self._connected_pill)
        lay.addWidget(self._timer_pill)


# ── Individual pill widgets ────────────────────────────────────────────────────

class _BasePill(QWidget):
    """Shared painting utilities for all pills."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(PILL_H)
        self.setAutoFillBackground(False)

    def _paint_pill_bg(self, painter: QPainter, w: int, h: int,
                       bg: QColor, border: QColor | None = None):
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), PILL_R, PILL_R)
        painter.fillPath(path, QBrush(bg))
        if border:
            painter.setPen(QPen(border, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

    def _paint_dot(self, painter: QPainter, x: float, y: float, color: QColor):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(x, y), DOT_R, DOT_R)


class _StatusPill(_BasePill):
    """Left pill: coloured dot + engine status label."""

    _STATUS_LABELS = {
        "loading":    "Loading...",
        "idle":       "Idle",
        "listening":  "Listening...",
        "processing": "Processing...",
        "error":      "Error",
    }
    _STATUS_COLORS = {
        "loading":    QColor(90, 110, 155),
        "idle":       QColor(90, 110, 155),
        "listening":  C.GREEN,
        "processing": C.BLUE,
        "error":      C.RED,
    }

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setFixedWidth(140)    # TUNE
        state.engine_status_changed.connect(self.update)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        self._paint_pill_bg(painter, w, h, C.BG_PILL_L)

        status = self._state.engine_status
        dot_c  = self._STATUS_COLORS.get(status, C.GREEN)
        label  = self._STATUS_LABELS.get(status, status.capitalize())

        # Dot
        self._paint_dot(painter, DOT_R + 10, h / 2, dot_c)

        # Label
        font = QFont("Segoe UI", 10)    # TUNE
        painter.setFont(font)
        painter.setPen(QPen(C.TEXT_LABEL))
        painter.drawText(
            QRectF(DOT_R * 2 + 16, 0, w - DOT_R * 2 - 20, h),
            Qt.AlignmentFlag.AlignVCenter,
            label,
        )


class _ConnectedPill(_BasePill):
    """Centre pill: cloud icon + green dot + 'Connected'."""

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setFixedWidth(140)    # TUNE
        state.engine_status_changed.connect(self.update)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        connected = self._state.engine_status != "error"
        bg = C.BG_PILL_C if connected else QColor(28, 12, 12)
        self._paint_pill_bg(painter, w, h, bg)

        # Cloud icon (simplified)
        self._draw_cloud(painter, 16, h / 2,
                         C.GREEN if connected else C.RED)

        # Status dot
        dot_c = C.GREEN if connected else C.RED
        self._paint_dot(painter, 34, h / 2, dot_c)

        # Label
        font = QFont("Segoe UI", 10)
        painter.setFont(font)
        painter.setPen(QPen(C.GREEN if connected else C.RED))
        painter.drawText(
            QRectF(44, 0, w - 50, h),
            Qt.AlignmentFlag.AlignVCenter,
            "Connected" if connected else "Offline",
        )

    def _draw_cloud(self, painter: QPainter, cx: float, cy: float,
                    color: QColor):
        """Tiny cloud silhouette using arcs."""
        pen = QPen(color, 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Three overlapping arcs to suggest a cloud shape
        painter.drawArc(QRectF(cx - 7, cy - 5, 7, 7), 30 * 16, 210 * 16)
        painter.drawArc(QRectF(cx - 3, cy - 7, 8, 8), 0 * 16, 180 * 16)
        painter.drawArc(QRectF(cx + 1, cy - 5, 6, 6), 0 * 16, 150 * 16)
        painter.drawLine(QPointF(cx - 7, cy + 2), QPointF(cx + 7, cy + 2))


class _TimerPill(_BasePill):
    """Right pill: elapsed time display."""

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setFixedWidth(88)    # TUNE
        state.elapsed_seconds_changed.connect(self.update)
        state.is_recording_changed.connect(self.update)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        self._paint_pill_bg(painter, w, h, C.BG_PILL_T)

        secs  = self._state.elapsed_seconds
        mm    = secs // 60
        ss    = secs % 60
        label = f"{mm:02d}:{ss:02d}"

        font = QFont("Segoe UI", 10, QFont.Weight.Medium)    # TUNE
        painter.setFont(font)
        painter.setPen(QPen(C.TEXT_LABEL))
        painter.drawText(
            QRectF(0, 0, w, h),
            Qt.AlignmentFlag.AlignCenter,
            label,
        )
