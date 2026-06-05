"""
imla_ui/widgets/action_bar.py
──────────────────────────────
Three equal-width action buttons: Copy · Insert · Clear.

Each button:
  [ ICON  Label         Shortcut ]
  icon + bold label (left-aligned) + dim shortcut key (right-aligned)

Buttons paint their own dark rounded-rect background and react to
hover / press via QWidget mouse events (no QSS hover tricks needed for
accurate control of the translucent look).

Signals emitted (connected by MainWindow to business logic):
  copy_clicked, insert_clicked, clear_clicked
"""
from __future__ import annotations

from PySide6.QtCore    import Qt, QRectF, QPointF, Signal
from PySide6.QtGui     import (QPainter, QPainterPath, QColor, QPen,
                               QBrush, QFont, QFontMetrics, QLinearGradient)
from PySide6.QtWidgets import QWidget, QHBoxLayout, QSizePolicy

from imla_ui.colors    import C

CORNER_R   =  8      # TUNE: button corner radius
BTN_HEIGHT = 56      # TUNE: button height
BTN_GAP    = 10      # TUNE: gap between buttons
PAD_H      = 16      # TUNE: left/right outer padding


class ActionBar(QWidget):
    """Row of three action buttons."""

    copy_clicked   = Signal()
    insert_clicked = Signal()
    clear_clicked  = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(BTN_HEIGHT + 16)   # TUNE: top/bottom margin
        self.setAutoFillBackground(False)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(PAD_H, 8, PAD_H, 8)
        lay.setSpacing(BTN_GAP)

        self._copy_btn   = _ActionButton("Copy",   "Ctrl+C", _IconType.COPY)
        self._insert_btn = _ActionButton("Insert", "Ctrl+I", _IconType.INSERT)
        self._clear_btn  = _ActionButton("Clear",  "Ctrl+K", _IconType.CLEAR)

        for btn in (self._copy_btn, self._insert_btn, self._clear_btn):
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            lay.addWidget(btn)

        self._copy_btn.clicked_sig.connect(self.copy_clicked)
        self._insert_btn.clicked_sig.connect(self.insert_clicked)
        self._clear_btn.clicked_sig.connect(self.clear_clicked)


class _IconType:
    COPY   = "copy"
    INSERT = "insert"
    CLEAR  = "clear"


class _ActionButton(QWidget):
    """Single action button with custom painting."""

    clicked_sig = Signal()

    def __init__(self, label: str, shortcut: str, icon: str, parent=None):
        super().__init__(parent)
        self._label    = label
        self._shortcut = shortcut
        self._icon     = icon
        self._hovered  = False
        self._pressed  = False
        self.setFixedHeight(BTN_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ── Mouse events ──────────────────────────────────────────────────────────

    def enterEvent(self, event):
        self._hovered = True;  self.update()

    def leaveEvent(self, event):
        self._hovered = False; self._pressed = False; self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True;  self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._hovered:
            self._pressed = False
            self.clicked_sig.emit()
            self.update()

    # ── paintEvent — drawing only ─────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background
        if self._pressed:
            bg = QColor(15, 20, 38)       # TUNE: press
        elif self._hovered:
            bg = C.BG_BTN_HOV
        else:
            bg = C.BG_BTN

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), CORNER_R, CORNER_R)
        painter.fillPath(path, QBrush(bg))

        # Subtle top-edge highlight
        hl = QColor(255, 255, 255, 8 if not self._hovered else 14)   # TUNE
        painter.setPen(QPen(hl, 1))
        painter.drawLine(QPointF(CORNER_R, 0.5), QPointF(w - CORNER_R, 0.5))

        # ── Icon (left) ───────────────────────────────────────────────────
        icon_x = 18    # TUNE: left margin for icon
        icon_y = h / 2
        self._draw_icon(painter, icon_x, icon_y)

        # ── Label (centre-left) ───────────────────────────────────────────
        font_lbl = QFont("Segoe UI", 12, QFont.Weight.Bold)   # TUNE
        painter.setFont(font_lbl)
        painter.setPen(QPen(C.TEXT_PRI))
        lbl_x = icon_x + 28    # TUNE: space after icon
        painter.drawText(
            QRectF(lbl_x, 0, w - lbl_x - 70, h),
            Qt.AlignmentFlag.AlignVCenter,
            self._label,
        )

        # ── Shortcut (right-aligned, dim) ─────────────────────────────────
        font_sc = QFont("Segoe UI", 10)   # TUNE
        painter.setFont(font_sc)
        painter.setPen(QPen(C.TEXT_DIM))
        painter.drawText(
            QRectF(0, 0, w - 14, h),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            self._shortcut,
        )

    def _draw_icon(self, painter: QPainter, cx: float, cy: float):
        """Minimal geometric icon for each button type."""
        col  = QColor(C.BLUE.red(), C.BLUE.green(), C.BLUE.blue(), 220)
        pen  = QPen(col, 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self._icon == _IconType.COPY:
            # Two overlapping pages
            painter.drawRoundedRect(QRectF(cx - 6, cy - 9, 12, 14), 2, 2)
            painter.fillRect(QRectF(cx - 9, cy - 6, 12, 14),
                             QBrush(C.BG_BTN if not self._hovered else C.BG_BTN_HOV))
            painter.drawRoundedRect(QRectF(cx - 9, cy - 6, 12, 14), 2, 2)

        elif self._icon == _IconType.INSERT:
            # Arrow pointing down into a tray
            painter.drawLine(QPointF(cx, cy - 8), QPointF(cx, cy + 5))
            painter.drawLine(QPointF(cx - 5, cy), QPointF(cx, cy + 5))
            painter.drawLine(QPointF(cx + 5, cy), QPointF(cx, cy + 5))
            painter.drawLine(QPointF(cx - 7, cy + 8), QPointF(cx + 7, cy + 8))

        elif self._icon == _IconType.CLEAR:
            # Trash can outline
            # Lid
            painter.drawLine(QPointF(cx - 8, cy - 7), QPointF(cx + 8, cy - 7))
            # Handle on lid
            painter.drawRoundedRect(QRectF(cx - 3, cy - 10, 6, 4), 1, 1)
            # Body
            painter.drawRoundedRect(QRectF(cx - 6, cy - 6, 12, 14), 1, 1)
            # Lines inside
            painter.drawLine(QPointF(cx - 2, cy - 3), QPointF(cx - 2, cy + 5))
            painter.drawLine(QPointF(cx + 2, cy - 3), QPointF(cx + 2, cy + 5))
