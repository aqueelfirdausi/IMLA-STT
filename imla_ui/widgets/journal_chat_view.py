"""
imla_ui/widgets/journal_chat_view.py
─────────────────────────────────────
JournalChatView — the "ask your journal" surface.

Sits in the same panel slot as TranscriptView (same fixed height + margin).
Two parts, top → bottom:
  - answer area  (read-only QTextEdit, same card styling as TranscriptView)
  - question row (single-line QLineEdit; Enter sends)

Calls journal_reader.answer() on a background thread so the UI never
freezes during the Groq call. Pure view — owns no app state.
"""
from __future__ import annotations

from PySide6.QtCore    import Qt, QThread, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLineEdit

from imla_ui.colors import C
from imla_ui import journal_reader


class _AnswerWorker(QThread):
    """Runs the blocking Groq answer() call off the UI thread."""
    done = Signal(str)

    def __init__(self, question: str, parent=None):
        super().__init__(parent)
        self._question = question

    def run(self):
        try:
            result = journal_reader.answer(self._question)
        except Exception as exc:
            result = f"Couldn't answer ({exc})."
        self.done.emit(result)


class JournalChatView(QWidget):
    """Ask-your-journal view. Self-contained; calls journal_reader.answer()."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        self._worker: _AnswerWorker | None = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # Answer area — read-only, same card look as TranscriptView
        self._answer = QTextEdit(self)
        self._answer.setReadOnly(True)
        self._answer.setPlaceholderText("Ask a question about your journal below.")
        self._answer.setStyleSheet(f"""
            QTextEdit {{
                background: {C.BG_CARD.name()};
                border: 1px solid {C.CARD_BORDER.name()};
                border-radius: 10px;
                padding: 14px;
                color: {C.TEXT_PRI.name()};
                font-family: "Segoe UI";
                font-size: 12pt;
                selection-background-color: rgb(27, 80, 160);
            }}
            QScrollBar:vertical {{
                width: 6px; background: {C.BG_CARD.name()};
            }}
            QScrollBar::handle:vertical {{
                background: rgb(40, 60, 100); border-radius: 3px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        root.addWidget(self._answer, stretch=1)

        # Question input — single line, Enter sends
        self._input = QLineEdit(self)
        self._input.setPlaceholderText("Ask your journal…  (Enter to send)")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {C.BG_CARD.name()};
                border: 1px solid {C.CARD_BORDER.name()};
                border-radius: 10px;
                padding: 8px 14px;
                color: {C.TEXT_PRI.name()};
                font-family: "Segoe UI";
                font-size: 12pt;
                selection-background-color: rgb(27, 80, 160);
            }}
            QLineEdit:focus {{
                border: 1px solid {C.BLUE.name()};
            }}
        """)
        self._input.returnPressed.connect(self._on_send)
        root.addWidget(self._input)

    def _on_send(self):
        question = self._input.text().strip()
        if not question:
            return
        # Don't fire a second call while one is in flight.
        if self._worker is not None and self._worker.isRunning():
            return
        self._answer.setText("Thinking…")
        self._input.clear()
        self._input.setEnabled(False)

        self._worker = _AnswerWorker(question, self)
        self._worker.done.connect(self._on_answer)
        self._worker.start()

    def _on_answer(self, text: str):
        self._answer.setText(text)
        self._input.setEnabled(True)
        self._input.setFocus()
