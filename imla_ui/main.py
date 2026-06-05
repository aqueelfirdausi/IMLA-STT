"""
imla_ui/main.py
────────────────
Application entry point.

Usage
─────
    cd IMLA-STT
    python -m imla_ui.main
    # or:
    python imla_ui/main.py
"""
import atexit
import signal
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore    import Qt
from imla_ui.main_window import MainWindow


def main():
    # Enable high-DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("IMLA")
    app.setOrganizationName("IMLA Project")

    window = MainWindow()

    # ── Clean exit on any path (Ctrl+C, kill, crash) ─────────────────────────
    def _on_exit():
        try:
            window._worker.stop_worker()
        except Exception:
            pass

    atexit.register(_on_exit)

    def _signal_handler(signum, frame):
        _on_exit()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    # ─────────────────────────────────────────────────────────────────────────

    # Centre on screen
    screen_geo = app.primaryScreen().availableGeometry()
    window.move(
        (screen_geo.width()  - window.width())  // 2,
        (screen_geo.height() - window.height()) // 2,
    )
    window.show()

    try:
        exit_code = app.exec()
    finally:
        _emergency_hotkey_cleanup()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
