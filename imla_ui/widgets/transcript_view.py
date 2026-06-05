"""
imla_ui/widgets/transcript_view.py
────────────────────────────────────
Transcript display card.

Two-tier text
─────────────
• Final text   — full white, confirmed speech, never changes once appended.
• Interim text — dimmer colour, current in-progress recognition, replaced
  each update.  Shown as a continuation of the final text (inline append).

Mini eq-bars
────────────
A small animated equaliser in the bottom-right corner shows when recording.
It uses a separate 30fps QTimer that drives 7 bars.  Bar heights are
pre-computed in _compute_bars(); paintEvent only draws the stored values.

The card paints its own rounded-rectangle background (no stylesheet hacks).
"""
from __future__ import annotations
import math

from PySide6.QtCore    import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui     import (QPainter, QColor, QPen, QBrush,
                               QPainterPath, QFont, QFontMetrics)
from PySide6.QtWidgets import QWidget

from imla_ui.colors    import C
from imla_ui.app_state import AppState

# ── Layout ────────────────────────────────────────────────────────────────────
PAD        = 16    # TUNE: inner padding (px)
CORNER_R   = 10    # TUNE: card corner radius
LINE_H     = 26    # TUNE: text line height

# Mini equaliser
EQ_N       =  7    # TUNE: number of bars
EQ_W       =  4    # TUNE: bar width (px)
EQ_GAP     =  3    # TUNE: gap between bars
EQ_MAX_H   = 16    # TUNE: max bar height (px)
EQ_MIN_H   =  3    # TUNE: min bar height (px)
EQ_MARGIN  = 10    # TUNE: right/bottom margin from card edge
FPS        = 30


class TranscriptView(QWidget):
    """Transcript card with two-tier text and an animated mini equaliser."""

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setAutoFillBackground(False)

        # Cached text (kept in sync with AppState)
        self._final_text   = ""
        self._interim_text = ""

        # Mini eq bars — pre-computed list of heights
        self._eq_phase  = 0.0
        self._eq_bars: list[int] = [EQ_MIN_H] * EQ_N
        self._eq_timer  = QTimer(self)
        self._eq_timer.setInterval(1000 // FPS)
        self._eq_timer.timeout.connect(self._compute_bars)

        # Scroll offset (for long transcripts)
        self._scroll_y = 0

        # State connections
        state.final_text_changed.connect(self._on_final)
        state.interim_text_changed.connect(self._on_interim)
        state.is_recording_changed.connect(self._on_recording)

    # ── State handlers ────────────────────────────────────────────────────────

    def _on_final(self, text: str):
        self._final_text = text
        self._scroll_to_bottom()
        self.update()

    def _on_interim(self, text: str):
        self._interim_text = text
        self.update()

    def _on_recording(self, recording: bool):
        if recording:
            self._eq_timer.start()
        else:
            self._eq_timer.stop()
            self._eq_bars = [EQ_MIN_H] * EQ_N
            self.update()

    # ── Pre-computation ───────────────────────────────────────────────────────

    def _compute_bars(self):
        """Update mini-eq bar heights — no drawing."""
        self._eq_phase += 0.18    # TUNE
        amp = self._state.amplitude
        for i in range(EQ_N):
            wave = 0.5 + 0.5 * math.sin(self._eq_phase * (1.0 + i * 0.35) + i * 0.6)
            h = EQ_MIN_H + int((EQ_MAX_H - EQ_MIN_H) * amp * wave)
            self._eq_bars[i] = max(EQ_MIN_H, min(EQ_MAX_H, h))
        self.update()

    def _scroll_to_bottom(self):
        """Compute scroll_y so the latest text is visible."""
        # Approximate: one line per 60 characters of final text  # TUNE
        lines = max(0, len(self._final_text) // 60)
        content_h = lines * LINE_H
        visible_h = self.height() - PAD * 2
        self._scroll_y = max(0, content_h - visible_h)

    # ── paintEvent — drawing only ─────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # ── Card background ────────────────────────────────────────────────
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), CORNER_R, CORNER_R)
        painter.fillPath(path, QBrush(C.BG_CARD))

        # Card border
        painter.setPen(QPen(C.CARD_BORDER, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # ── Clip to card interior ─────────────────────────────────────────
        painter.setClipPath(path)

        # ── Text ──────────────────────────────────────────────────────────
        font = QFont("Segoe UI", 12)   # TUNE: font size
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)

        fm          = QFontMetrics(font)
        text_w      = w - PAD * 2
        text_x      = PAD
        text_y      = PAD - self._scroll_y
        cursor_char = "│"    # blinking cursor placeholder  # TUNE

        # Final text (white)
        painter.setPen(QPen(C.TEXT_PRI))
        combined = self._final_text
        if self._interim_text:
            combined += " " + self._interim_text

        # Word-wrap
        words = (combined + (" " + cursor_char if self._state.is_recording else "")).split(" ")
        line  = ""
        for word in words:
            test = (line + " " + word).strip()
            if fm.horizontalAdvance(test) > text_w:
                if text_y + LINE_H > 0:   # only draw visible lines
                    # Determine if this line contains interim text
                    is_interim_line = self._final_text and line.strip() not in self._final_text
                    painter.setPen(QPen(C.TEXT_DIM if is_interim_line else C.TEXT_PRI))
                    painter.drawText(int(text_x), int(text_y + fm.ascent()), line.strip())
                text_y += LINE_H
                line = word
            else:
                line = test
        if line.strip():
            is_interim_last = (
                self._interim_text
                and line.strip().startswith(self._interim_text.split()[0])
                if self._interim_text else False
            )
            painter.setPen(QPen(C.TEXT_DIM if is_interim_last else C.TEXT_PRI))
            painter.drawText(int(text_x), int(text_y + fm.ascent()), line.strip())

        # ── Mini eq bars (bottom-right) ────────────────────────────────────
        if self._state.is_recording or any(b > EQ_MIN_H for b in self._eq_bars):
            eq_total_w = EQ_N * (EQ_W + EQ_GAP) - EQ_GAP
            bx = w - EQ_MARGIN - eq_total_w
            by = h - EQ_MARGIN

            bar_color = QColor(C.BLUE.red(), C.BLUE.green(), C.BLUE.blue(), 160)  # TUNE
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bar_color))
            for i, bar_h in enumerate(self._eq_bars):
                bxi = bx + i * (EQ_W + EQ_GAP)
                painter.drawRoundedRect(
                    QRectF(bxi, by - bar_h, EQ_W, bar_h), 1.5, 1.5)

        painter.setClipping(False)
