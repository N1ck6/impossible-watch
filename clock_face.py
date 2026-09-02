"""Виджет циферблата с сеткой букв (v2)"""

from PyQt6.QtWidgets import QWidget, QLabel, QGridLayout
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QFont, QColor

from datetime import datetime
from time_logic import get_text_time_coords, get_digit_time_coords, GRID
from config import *


class ClockFace(QWidget):
    """Циферблат с масштабируемой сеткой букв"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels = []
        self._scale = 1.0
        self._init_ui()

        # Состояние отображения
        self.text_mode = True
        self.show_minutes = False
        self.show_seconds = False
        self.use_12h = True
        self.show_ampm = True

        # Таймер обновления
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_display)
        self.timer.start(1000)
        self.update_display()

    def _init_ui(self):
        self.layout = QGridLayout(self)
        self.layout.setSpacing(0)   # Плотная сетка без промежутков (как на фото)
        self.layout.setContentsMargins(4, 4, 4, 4)

        font = QFont(FONT_FAMILY, FONT_SIZE)
        font.setWeight(int(FONT_WEIGHT))
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1)

        for row in range(GRID_ROWS):
            row_labels = []
            for col in range(GRID_COLS):
                lbl = QLabel(GRID[row][col])
                lbl.setFont(font)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setFixedSize(BASE_CELL_SIZE, BASE_CELL_SIZE)
                lbl.setStyleSheet(self._inactive_style())
                self.layout.addWidget(lbl, row, col)
                row_labels.append(lbl)
            self.labels.append(row_labels)

        self.setFixedSize(BASE_GRID_WIDTH + 8, BASE_GRID_HEIGHT + 8)

    def _inactive_style(self):
        return f"color: {COLOR_INACTIVE}; background: transparent; border: none;"

    def _active_style(self):
        # Glow-эффект через text-shadow
        return (f"color: {COLOR_ACTIVE}; background: transparent; border: none;"
                f"text-shadow: 0 0 8px {COLOR_ACTIVE_GLOW}, 0 0 16px {COLOR_ACTIVE_GLOW};")

    def set_scale(self, scale: float):
        """Масштабирование сетки при ресайзе окна"""
        self._scale = scale
        size = int(BASE_CELL_SIZE * scale)
        font_size = max(8, int(FONT_SIZE * scale))
        font = QFont(FONT_FAMILY, font_size)
        font.setWeight(int(FONT_WEIGHT))
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, max(0, int(scale)))

        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                lbl = self.labels[row][col]
                lbl.setFont(font)
                lbl.setFixedSize(size, size)

        self.setFixedSize(
            int((BASE_GRID_WIDTH + 8) * scale),
            int((BASE_GRID_HEIGHT + 8) * scale)
        )

    def update_display(self):
        now = datetime.now()

        if self.text_mode:
            active = get_text_time_coords(now, self.show_ampm)
        else:
            active = get_digit_time_coords(
                now, self.show_minutes, self.show_seconds, self.use_12h
            )

        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                lbl = self.labels[row][col]
                if (row, col) in active:
                    lbl.setStyleSheet(self._active_style())
                else:
                    lbl.setStyleSheet(self._inactive_style())

    def set_mode(self, text_mode=None, minutes=None, seconds=None, format_12h=None, ampm=None):
        if text_mode is not None:
            self.text_mode = text_mode
        if minutes is not None:
            self.show_minutes = minutes
        if seconds is not None:
            self.show_seconds = seconds
        if format_12h is not None:
            self.use_12h = format_12h
        if ampm is not None:
            self.show_ampm = ampm
        self.update_display()

    def get_active_labels(self):
        """Возвращает список QLabel, которые сейчас активны (подсвечены)"""
        result = []
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                lbl = self.labels[row][col]
                if COLOR_ACTIVE in lbl.styleSheet():
                    result.append(lbl)
        return result

    def get_all_labels(self):
        """Все QLabel в плоском списке"""
        return [lbl for row in self.labels for lbl in row]
