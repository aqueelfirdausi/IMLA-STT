"""
imla_ui/widgets/transcript_view.py
────────────────────────────────────
Editable transcript box (QTextEdit) that keeps AppState as the source of truth.

Flow
────
• AppState.final_text_changed → box.setPlainText() (guarded to avoid feedback)
• AppState.interim_text_changed → appended in grey after final text (read-only suffix)
• User edits → on focusOut → AppState.set_final_text() writes back
• Copy / Insert / Clear all still read AppState, not the widget, so they get edits.

TranscriptViewLegacy (the original hand-painted widget) is kept below for reference.
"""
from __future__ import annotations
import math

from PySide6.QtCore    import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui     import (QPainter, QColor, QPen, QBrush,
                               QPainterPath, QFont, QFontMetrics,
                               QTextCharFormat, QTextCursor)
from PySide6.QtWidgets import QWidget, QTextEdit

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


class TranscriptView(QTextEdit):
    """
    Editable transcript box.  AppState is the source of truth; this widget
    reflects it and writes user edits back on focus-out.

    Focus-out chosen over debounce because:
    • Streaming append_final_text fires during dictation — committing on every
      keystroke would fight those writes. Focus-out lets the user finish a
      correction before it races against incoming chunks.
    • Debounce would need a QTimer and still has the same race on short delays.

    Interim text (in-progress recognition) is appended after the confirmed text
    in grey, read-only. It is replaced on each interim_text_changed signal and
    is never committed to AppState.
    """

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self._state = state
        self._updating = False   # guard: suppress write-back while we're setting text

        # ── Appearance ────────────────────────────────────────────────────────
        bg   = C.BG_CARD
        text = C.TEXT_PRI

        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: rgb({bg.red()}, {bg.green()}, {bg.blue()});
                color: rgb({text.red()}, {text.green()}, {text.blue()});
                border: 1px solid rgb({C.CARD_BORDER.red()}, {C.CARD_BORDER.green()}, {C.CARD_BORDER.blue()});
                border-radius: 10px;
                padding: 14px;
                font-family: "Segoe UI";
                font-size: 12pt;
                selection-background-color: rgb(27, 80, 160);
            }}
            QScrollBar:vertical {{
                background: rgb({bg.red()}, {bg.green()}, {bg.blue()});
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: rgb(40, 60, 100);
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWordWrapMode(self.wordWrapMode())   # keep default word wrap

        # ── State connections ─────────────────────────────────────────────────
        state.final_text_changed.connect(self._on_final)
        state.interim_text_changed.connect(self._on_interim)

    # ── State → widget ────────────────────────────────────────────────────────

    def _on_final(self, text: str):
        if self._updating:
            return
        self._updating = True
        # Preserve cursor position if the user is in the box
        cursor_at_end = self.textCursor().atEnd()
        self.setPlainText(text)
        if cursor_at_end:
            self.moveCursor(QTextCursor.MoveOperation.End)
        self._updating = False

    def _on_interim(self, text: str):
        # Re-render: final in white, interim appended in grey (not editable here,
        # but QTextEdit lets the user click past it — acceptable for now).
        if self._updating:
            return
        self._updating = True
        final = self._state.final_text
        if text:
            # Build rich text: final normal, interim dimmed
            cursor = QTextCursor(self.document())
            self.setPlainText(final)
            cursor.movePosition(QTextCursor.MoveOperation.End)
            fmt = QTextCharFormat()
            fmt.setForeground(C.TEXT_DIM)
            cursor.insertText(" " + text, fmt)
        else:
            self.setPlainText(final)
        self.moveCursor(QTextCursor.MoveOperation.End)
        self._updating = False

    # ── Widget → AppState (write-back on focus-out) ───────────────────────────

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if not self._updating:
            self._state.set_final_text(self.toPlainText())


# ── Legacy painted widget (kept as fallback) ──────────────────────────────────

class TranscriptViewLegacy(QWidget):
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
