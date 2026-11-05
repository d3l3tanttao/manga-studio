import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from studio.theme import STYLE
from studio.window import Window


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Manga Studio")
    app.setApplicationVersion("2.2")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = Window()
    window.show()
    if len(sys.argv) > 1:
        window.add_paths([Path(p) for p in sys.argv[1:]])
    while True:
        status = app.exec()
        if not window.restart_language:
            return status
        reopen = window.project
        window.deleteLater()
        window = Window()
        window.show()
        if reopen:
            window.load_project(reopen)


if __name__ == "__main__":
    sys.exit(main())
