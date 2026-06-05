"""
imla_ui/widgets/waveform_widget.py
───────────────────────────────────
30 FPS waveform background that spans the full orb zone.

Architecture rules enforced here
─────────────────────────────────
• All geometry is PRE-COMPUTED in _compute_frame() (a QTimer slot).
• paintEvent() does ONLY drawing – zero maths, zero state mutations.
• Timer starts / stops with is_recording so CPU is idle when not in use.
• Amplitude comes from AppState.amplitude_changed signal.

Visual layers (painted in order)
─────────────────────────────────
1. Radial blue-glow background centred on the orb position.
2. Three overlapping sine-wave curves: cyan lead, blue mid, dark back.
   Each wave is a filled polygon + a stroked path on top.
   Amplitude envelope: gaussian centred at widget centre so waves peak
   directly behind the orb and fade near the window edges.
3. Scatter particles: small glowing dots that drift slowly.
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore    import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui     import (QPainter, QPainterPath, QLinearGradient,
                               QRadialGradient, QBrush, QPen, QColor)
from PySide6.QtWidgets import QWidget

from imla_ui.colors    import C
from imla_ui.app_state import AppState

# ── Tunable constants ─────────────────────────────────────────────────────────
FPS          = 30
FRAME_MS     = 1000 // FPS    # 33 ms

N_POINTS     = 120            # TUNE: horizontal resolution of each wave
MAX_AMP      = 56             # TUNE: peak wave height in px at full amplitude
GAUSSIAN_SIG = 0.28           # TUNE: width of the centre-weighted envelope (0–1)
IDLE_FADE    = 0.15           # static amplitude shown while not recording (no timer)

N_PARTICLES  = 22             # TUNE: number of sparkle dots
PART_SPEED   = 0.4            # TUNE: particle drift speed (px/frame)
PART_MAX_R   = 2.5            # TUNE: max particle radius in px


class WaveformWidget(QWidget):
    """Full-zone waveform canvas.  OrbWidget is overlaid on top by the parent."""

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)

        self._state    = state
        self._amp      = 0.0        # smoothed amplitude (0–1)
        self._phase    = 0.0        # animation phase (radians)
        self._fade     = 0.0        # fade-in/out multiplier (0–1)

        # Pre-computed per-frame geometry (written by _compute_frame, read by paintEvent)
        self._paths: list[tuple[QPainterPath, QPainterPath]] = []
        self._grads: list[QLinearGradient]                   = []
        self._particles: list[list[float]]                   = []   # [x, y, alpha, r]
        self._bg_grad: QRadialGradient | None                = None

        self._init_particles()

        # 30 FPS timer (runs only while recording)
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._compute_frame)

        # State connections
        state.is_recording_changed.connect(self._on_recording_changed)
        state.amplitude_changed.connect(self._on_amplitude)

        # Draw one static idle frame immediately
        self._compute_frame()

    # ── State handlers ────────────────────────────────────────────────────────

    def _on_recording_changed(self, recording: bool):
        if recording:
            self._timer.start()
        else:
            self._timer.stop()
            # Let the fade naturally decay to 0 over a few more static frames
            self._fade_out()

    def _on_amplitude(self, amp: float):
        self._amp = min(1.0, amp * 4.0)   # match dictate.py's proven scaling

    def _fade_out(self):
        """Paint a few more decaying frames after recording stops."""
        if self._fade > IDLE_FADE + 0.02:
            self._fade *= 0.75
            self._compute_frame()
            QTimer.singleShot(FRAME_MS, self._fade_out)
        else:
            self._fade = IDLE_FADE
            self._compute_frame()

    # ── Pre-computation (called by timer — NOT paintEvent) ────────────────────

    def _compute_frame(self):
        """Update all geometry that paintEvent will use.  No QPainter here."""
        self._phase += 0.10    # TUNE: phase advance per frame

        # Smooth the fade multiplier
        target_fade = self._amp if self._state.is_recording else IDLE_FADE
        self._fade  = self._fade * 0.82 + target_fade * 0.18   # TUNE: smoothing

        w = max(1, self.width())
        h = max(1, self.height())
        cy = h / 2.0

        # ── Radial background glow ────────────────────────────────────────────
        bg = QRadialGradient(w / 2.0, cy, w * 0.72)
        alpha = int(130 * self._fade)    # TUNE
        bg.setColorAt(0.0, QColor(18, 70, 160, alpha))
        bg.setColorAt(0.5, QColor( 8, 30,  90, alpha // 2))
        bg.setColorAt(1.0, QColor( 0,  0,   0, 0))
        self._bg_grad = bg

        # ── Wave layers ───────────────────────────────────────────────────────
        # Wave specs: (freq_mult, phase_offset, amplitude_frac, (stroke_R,G,B,A), fill_alpha_centre)
        wave_specs = [
            (2.3, 0.0,   1.0,  C.WAVE_CYAN, 55),   # cyan  – lead    # TUNE
            (3.1, 1.1,   0.70, C.WAVE_BLUE, 38),   # blue  – mid     # TUNE
            (4.5, 2.4,   0.45, C.WAVE_DARK, 22),   # dark  – back    # TUNE
        ]

        self._paths = []
        self._grads = []

        for freq, p_off, amp_frac, stroke_col, fill_ac in wave_specs:
            # Build point list
            pts: list[QPointF] = []
            for i in range(N_POINTS + 1):
                t  = i / N_POINTS                                   # 0..1
                px = t * w
                # Gaussian envelope (higher amplitude near centre)
                env = math.exp(-((t - 0.5) ** 2) / (2 * GAUSSIAN_SIG ** 2))
                py = cy + MAX_AMP * self._fade * amp_frac * env * math.sin(
                    2 * math.pi * t * freq + self._phase + p_off
                )
                pts.append(QPointF(px, py))

            # Stroke path
            stroke_path = QPainterPath()
            stroke_path.moveTo(pts[0])
            for pt in pts[1:]:
                stroke_path.lineTo(pt)

            # Filled polygon (wave + baseline)
            fill_path = QPainterPath()
            fill_path.moveTo(QPointF(0, cy))
            for pt in pts:
                fill_path.lineTo(pt)
            fill_path.lineTo(QPointF(w, cy))
            fill_path.closeSubpath()

            # Horizontal gradient for the fill
            grad = QLinearGradient(0, 0, w, 0)
            edge_alpha = max(0, fill_ac // 4)
            grad.setColorAt(0.0,  QColor(C.WAVE_FILL_E.red(), C.WAVE_FILL_E.green(), C.WAVE_FILL_E.blue(), edge_alpha))
            grad.setColorAt(0.35, QColor(C.WAVE_FILL_C.red(), C.WAVE_FILL_C.green(), C.WAVE_FILL_C.blue(), fill_ac // 2))
            grad.setColorAt(0.5,  QColor(stroke_col.red(), stroke_col.green(), stroke_col.blue(), fill_ac))
            grad.setColorAt(0.65, QColor(C.WAVE_FILL_C.red(), C.WAVE_FILL_C.green(), C.WAVE_FILL_C.blue(), fill_ac // 2))
            grad.setColorAt(1.0,  QColor(C.WAVE_FILL_E.red(), C.WAVE_FILL_E.green(), C.WAVE_FILL_E.blue(), edge_alpha))

            self._paths.append((fill_path, stroke_path))
            self._grads.append((grad, stroke_col))

        # ── Particles ─────────────────────────────────────────────────────────
        for p in self._particles:
            # Drift upward / sideways
            p[0] += (random.random() - 0.5) * PART_SPEED
            p[1] -= PART_SPEED * (0.4 + random.random() * 0.6)
            p[2] -= 0.015    # fade alpha
            # Reset when faded out or out of bounds
            if p[2] <= 0 or p[1] < 0:
                self._respawn_particle(p, w, h)
            # Scale visibility with fade
            p[3] = (0.5 + random.random() * 0.5) * self._fade

        self.update()   # schedule repaint

    # ── paintEvent — drawing only ─────────────────────────────────────────────

    def paintEvent(self, event):
        """Render pre-computed geometry.  No maths here."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # 1. Radial background glow
        if self._bg_grad is not None:
            painter.fillRect(0, 0, w, h, QBrush(self._bg_grad))

        # 2. Wave layers (back → front)
        for (fill_path, stroke_path), (fill_grad, stroke_color) in zip(
                reversed(self._paths), reversed(self._grads)):
            # Filled area
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(fill_grad))
            painter.drawPath(fill_path)

            # Stroke on top
            pen = QPen(stroke_color, 1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(stroke_path)

        # 3. Sparkle particles
        painter.setPen(Qt.PenStyle.NoPen)
        for p in self._particles:
            alpha = max(0, min(255, int(p[2] * 200 * p[3])))
            if alpha < 8:
                continue
            painter.setBrush(QBrush(QColor(100, 210, 255, alpha)))
            r = p[4]
            painter.drawEllipse(QRectF(p[0] - r, p[1] - r, r * 2, r * 2))

    # ── Particle helpers ──────────────────────────────────────────────────────

    def _init_particles(self):
        self._particles = []
        for _ in range(N_PARTICLES):
            self._particles.append([0.0, 0.0, 0.0, 0.0, 0.0])

    def _respawn_particle(self, p: list, w: int, h: int):
        p[0] = random.random() * w
        p[1] = h * (0.3 + random.random() * 0.4)
        p[2] = 0.6 + random.random() * 0.4   # alpha
        p[3] = 0.0                             # vis (set in compute)
        p[4] = PART_MAX_R * (0.4 + random.random() * 0.6)   # radius

    def resizeEvent(self, event):
        # Re-seed particles to the new size
        w, h = self.width(), self.height()
        for p in self._particles:
            self._respawn_particle(p, w, h)
        self._compute_frame()
