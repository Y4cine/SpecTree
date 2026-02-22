from __future__ import annotations

import sys

from PyQt5.QtWidgets import QApplication

from app.ui_mainwindow import MainWindow

def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1200, 700)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    main()
