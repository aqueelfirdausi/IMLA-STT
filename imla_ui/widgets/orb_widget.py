"""
imla_ui/widgets/orb_widget.py
──────────────────────────────
The central mic orb.

Visual structure (outermost → innermost)
─────────────────────────────────────────
  ① Outer faint halo ring           (large, 1 px, very low alpha)
  ② Soft-glow concentric rings      (3 rings, decreasing radius/alpha)
  ③ Dark filled circle              (radial gradient, near-black)
  ④ Bright main ring                (2.5 px stroke, BLUE or RED for error)
  ⑤ White mic icon                  (capsule + stand arc + pole + base)
  ⑥ Status label below orb         ("Listening…", "Idle", etc.)

Architecture rules
──────────────────
• No business logic here — state is READ from AppState signals.
• All painting happens in paintEvent; geometry constants are at module level.
• Step 5 will add QPropertyAnimation for pulsing rings / glow.
  The geometry is already sized to accommodate animated rings.
"""
from PySide6.QtCore    import Qt, QRectF, QPointF, Signal
from PySide6.QtGui     import (QPainter, QPainterPath, QColor, QPen, QBrush,
                               QRadialGradient, QFont)
from PySide6.QtWidgets import QWidget, QSizePolicy

from imla_ui.colors    import C
from imla_ui.app_state import AppState

# ── Geometry constants ────────────────────────────────────────────────────────
ORB_SIZE   = 140     # TUNE: total widget bounding box (px)
FILL_R     =  54     # TUNE: dark-fill circle radius
RING_R     =  60     # TUNE: main ring radius
HALO_R     =  68     # TUNE: outer faint halo radius
GLOW_STEPS = [        # (radius_offset, alpha) for the soft-glow rings  # TUNE
    ( 7, 18),
    ( 4, 32),
    ( 1, 50),
]
LABEL_GAP  =  8      # TUNE: px below orb to the status label

# Mic icon sizes (all relative to orb centre = 0,0)
MIC_BW     = 10      # TUNE: half-width of mic capsule
MIC_TOP    = -20     # TUNE: y of top of capsule relative to orb centre
MIC_BOT    =  -4     # TUNE: y of bottom of capsule
MIC_STAND  = 14      # TUNE: half-width of stand arc
MIC_ARC_T  = -2      # TUNE: y of top of arc bbox
MIC_ARC_H  = 18      # TUNE: height of arc bbox
MIC_POLE_B = 22      # TUNE: y of bottom of pole
MIC_BASE_W = 10      # TUNE: half-width of base line


class OrbWidget(QWidget):
    """Central glowing mic orb.  Fixed size; parent positions it centred."""

    # Emitted when the user clicks within the ring area — starts/stops recording.
    clicked = Signal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setFixedSize(ORB_SIZE, ORB_SIZE)
        self.setAutoFillBackground(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # React to state changes
        state.engine_status_changed.connect(self.update)
        state.is_recording_changed.connect(self.update)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Only fire if the click lands within the visible ring
            cx = self.width()  / 2.0
            cy = self.height() / 2.0
            import math
            dist = math.hypot(event.position().x() - cx,
                              event.position().y() - cy)
            if dist <= HALO_R:   # generous hit area includes glow zone
                self.clicked.emit()

    # ── paintEvent — drawing only ─────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width()  / 2.0
        cy = self.height() / 2.0

        status    = self._state.engine_status
        recording = self._state.is_recording
        ring_col  = C.RED if status == "error" else C.ORB_RING

        # ── ① Outer halo ring ──────────────────────────────────────────────
        painter.setPen(QPen(C.ORB_GLOW, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), HALO_R, HALO_R)

        # ── ② Soft glow (concentric rings) ────────────────────────────────
        for dr, alpha in GLOW_STEPS:
            r = RING_R + dr
            glow_color = QColor(ring_col.red(), ring_col.green(),
                                ring_col.blue(), alpha)
            painter.setPen(QPen(glow_color, 1))
            painter.drawEllipse(QPointF(cx, cy), r, r)

        # ── ③ Fill circle — lit from upper-left for 3D sphere look ──────────
        fill_grad = QRadialGradient(cx, cy, FILL_R, cx - 18, cy - 18)
        fill_grad.setColorAt(0.0, QColor(40,  90, 170))   # blue-lit highlight  # TUNE
        fill_grad.setColorAt(0.4, QColor(15,  25,  60))   # mid navy             # TUNE
        fill_grad.setColorAt(1.0, QColor( 6,   9,  20))   # deep near-black edge # TUNE
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(fill_grad))
        painter.drawEllipse(QPointF(cx, cy), FILL_R, FILL_R)

        # ── ③b Specular glint (glass-sphere highlight, upper-left) ───────────
        glint_grad = QRadialGradient(cx - 18, cy - 20, 13)
        glint_grad.setColorAt(0.0, QColor(180, 210, 255, 75))   # TUNE: alpha
        glint_grad.setColorAt(1.0, QColor(180, 210, 255,  0))
        painter.setBrush(QBrush(glint_grad))
        painter.drawEllipse(QPointF(cx - 18, cy - 20), 13, 13)

        # ── ④ Main ring ───────────────────────────────────────────────────
        ring_alpha = 255 if recording else 160    # TUNE: dimmer when idle
        final_ring = QColor(ring_col.red(), ring_col.green(),
                            ring_col.blue(), ring_alpha)
        painter.setPen(QPen(final_ring, 2.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), RING_R, RING_R)

        # ── ⑤ Mic icon ────────────────────────────────────────────────────
        self._draw_mic(painter, cx, cy)

    def _draw_mic(self, painter: QPainter, cx: float, cy: float):
        """Paint a white microphone icon centred at (cx, cy)."""
        mic_color = QColor(205, 225, 255)   # soft white-blue  # TUNE
        cap_r     = MIC_BW                   # corner radius for capsule

        # Capsule body (rounded rectangle)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(mic_color))
        body = QRectF(cx - MIC_BW, cy + MIC_TOP,
                      MIC_BW * 2, MIC_BOT - MIC_TOP)
        painter.drawRoundedRect(body, cap_r, cap_r)

        # Stand arc (U-shape below capsule)
        arc_pen = QPen(mic_color, 2.2)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        arc_rect = QRectF(cx - MIC_STAND, cy + MIC_ARC_T,
                          MIC_STAND * 2, MIC_ARC_H)
        # drawArc: angles in 1/16 degree. 0=3 o'clock; -180*16 = clockwise half
        painter.drawArc(arc_rect, 0 * 16, -180 * 16)

        # Pole
        pole_top = QPointF(cx, cy + MIC_ARC_T + MIC_ARC_H)
        pole_bot = QPointF(cx, cy + MIC_POLE_B)
        painter.drawLine(pole_top, pole_bot)

        # Base
        base_l = QPointF(cx - MIC_BASE_W, cy + MIC_POLE_B)
        base_r = QPointF(cx + MIC_BASE_W, cy + MIC_POLE_B)
        painter.drawLine(base_l, base_r)
