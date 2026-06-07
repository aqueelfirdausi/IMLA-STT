"""
imla_ui/widgets/title_bar.py
─────────────────────────────
Custom frameless title bar.

Responsibilities
────────────────
• Drag-to-move the parent window (any mouse-press + move on the bar itself,
  excluding the button widgets).
• "Pill" circle button (left) – emits to_pill_clicked to minimise the panel.
• App name label.
• Bell icon, OS-style minimise (—) and close (×) on the right.

No business logic.  No state writes.  Pure UI events → signals.
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore    import Qt, QPoint, Signal
from PySide6.QtGui     import QPainter, QColor, QFont


class TitleBar(QWidget):
    """Draggable title bar with pill / minimise / close controls."""

    to_pill_clicked  = Signal()   # minimise → pill view
    minimize_clicked = Signal()   # OS minimize (taskbar)
    close_clicked    = Signal()   # quit
    ask_clicked      = Signal()   # toggle journal chat view

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)       # TUNE
        self.setAutoFillBackground(False)
        self._drag_start: QPoint | None = None
        self._build_layout()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(10)

        # Left: pill-circle button
        self._pill_btn = _CircleButton("–")
        self._pill_btn.setToolTip("Minimise to pill")
        self._pill_btn.clicked.connect(self.to_pill_clicked)

        # App name
        self._name_lbl = QLabel("IMLA")
        self._name_lbl.setStyleSheet(
            "color: #DCE9FF; font: bold 15px 'Segoe UI', Arial; background: transparent;"
        )

        lay.addWidget(self._pill_btn)
        lay.addWidget(self._name_lbl)
        lay.addStretch()

        # Right: ask-journal, bell, minimise, close
        self._ask_btn   = _GhostButton("💬")   # speech balloon
        self._ask_btn.setToolTip("Ask your journal")
        self._ask_btn.clicked.connect(self.ask_clicked)

        self._bell_btn  = _GhostButton("🔔")
        self._bell_btn.setToolTip("Notifications")

        self._min_btn   = _GhostButton("–")
        self._min_btn.setToolTip("Minimise")
        self._min_btn.clicked.connect(self.minimize_clicked)

        self._close_btn = _GhostButton("✕")
        self._close_btn.setToolTip("Close")
        self._close_btn.setStyleSheet(
            "QPushButton{"
            "  color:#5870A4; background:transparent; border:none;"
            "  font:16px 'Segoe UI'; padding:0;"
            "}"
            "QPushButton:hover{color:#FF5555;}"
        )
        self._close_btn.clicked.connect(self.close_clicked)

        lay.addWidget(self._ask_btn)
        lay.addWidget(self._bell_btn)
        lay.addSpacing(6)
        lay.addWidget(self._min_btn)
        lay.addWidget(self._close_btn)

    # ── Drag-to-move ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if (event.buttons() == Qt.MouseButton.LeftButton
                and self._drag_start is not None):
            self.window().move(
                event.globalPosition().toPoint() - self._drag_start
            )

    def mouseReleaseEvent(self, event):
        self._drag_start = None


# ── Private helper buttons ────────────────────────────────────────────────────

class _CircleButton(QPushButton):
    """Left-side pill-toggle button: dark circle with a "–" glyph."""

    _SS = (
        "QPushButton{"
        "  color:#8AAAD0; background:#151E33; border:1px solid #243050;"
        "  border-radius:16px; font:bold 15px 'Segoe UI'; padding:0;"
        "}"
        "QPushButton:hover{background:#1E2D48; color:#DCE9FF;}"
        "QPushButton:pressed{background:#111828;}"
    )

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(32, 32)
        self.setStyleSheet(self._SS)


class _GhostButton(QPushButton):
    """Right-side icon button: no background, hover-brightens."""

    _SS = (
        "QPushButton{"
        "  color:#5870A4; background:transparent; border:none;"
        "  font:16px 'Segoe UI'; padding:0;"
        "}"
        "QPushButton:hover{color:#DCE9FF;}"
    )

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(28, 28)
        self.setStyleSheet(self._SS)
