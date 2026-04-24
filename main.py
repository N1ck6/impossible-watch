#!/usr/bin/env python3
"""Точка входа Word Clock"""

import sys
from PyQt6.QtWidgets import QApplication
from clock_window import ClockWindow


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    window = ClockWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
