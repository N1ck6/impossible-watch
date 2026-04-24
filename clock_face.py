"""Виджет циферблата с сеткой букв"""

from PyQt6 import *
from PyQt6.QtWidgets import QWidget, QLabel, QGridLayout
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from datetime import datetime
from time_logic import get_text_time_coords, get_digit_time_coords, GRID
from config import *


class ClockFace(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels = []
        self._init_ui()

        # Состояние отображения
        self.text_mode = True
        self.show_minutes = False
        self.show_seconds = False
        self.use_12h = True

        # Таймер обновления
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_display)
        self.timer.start(1000)
        self.update_display()

    def _init_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(8, 8, 8, 8)

        font = QFont(FONT_FAMILY, FONT_SIZE)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)

        for row in range(GRID_ROWS):
            row_labels = []
            for col in range(GRID_COLS):
                lbl = QLabel(GRID[row][col])
                lbl.setFont(font)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setFixedSize(CELL_SIZE, CELL_SIZE)
                lbl.setStyleSheet(f"color: {COLOR_INACTIVE}; background: transparent;")
                layout.addWidget(lbl, row, col)
                row_labels.append(lbl)
            self.labels.append(row_labels)

        self.setFixedSize(GRID_WIDTH + 16, GRID_HEIGHT + 16)

    def update_display(self):
        now = datetime.now()

        if self.text_mode:
            active = get_text_time_coords(now)
        else:
            active = get_digit_time_coords(
                now, self.show_minutes, self.show_seconds, self.use_12h
            )

        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                lbl = self.labels[row][col]
                color = COLOR_ACTIVE if (row, col) in active else COLOR_INACTIVE
                lbl.setStyleSheet(f"color: {color}; background: transparent;")

    def set_mode(self, text_mode=None, minutes=None, seconds=None, format_12h=None):
        if text_mode is not None:
            self.text_mode = text_mode
        if minutes is not None:
            self.show_minutes = minutes
        if seconds is not None:
            self.show_seconds = seconds
        if format_12h is not None:
            self.use_12h = format_12h
        self.update_display()
