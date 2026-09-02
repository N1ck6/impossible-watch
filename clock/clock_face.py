"""Виджет циферблата с сеткой букв (v3)"""

from PyQt6.QtWidgets import QWidget, QLabel, QGridLayout, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

from datetime import datetime
from time_logic import get_text_time_coords, get_digit_time_coords, GRID
from config import *


class ClockFace(QWidget):
    """Циферблат с масштабируемой сеткой букв"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels = []
        self._init_ui()

        # Состояние отображения
        self.text_mode = True
        self.show_minutes = False
        self.show_seconds = False
        self.digit_submode = "hours"
        self.use_12h = True
        self.show_ampm = True

        # Таймер обновления букв (останавливается при паузе — см. ClockWindow)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_display)
        self.timer.start(1000)

        # Применяем базовый масштаб (квадрат BASE_SIZE x BASE_SIZE)
        self.set_scale(BASE_SIZE, BASE_SIZE)
        self.update_display()

    def _init_ui(self):
        self.layout = QGridLayout(self)
        self.layout.setSpacing(0)   # Плотная сетка без промежутков
        self.layout.setContentsMargins(0, 0, 0, 0)

        font = QFont(FONT_FAMILY, FONT_SIZE)
        font.setWeight(int(FONT_WEIGHT))

        for row in range(GRID_ROWS):
            row_labels = []
            for col in range(GRID_COLS):
                lbl = QLabel(GRID[row][col])
                lbl.setFont(font)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet(self._inactive_style())

                # Свечение активных букв — QGraphicsDropShadowEffect вместо
                # CSS text-shadow (Qt QSS его не поддерживает и спамит
                # в консоль "Unknown property text-shadow").
                #
                # ВАЖНО: эффект прикрепляется к лейблу ОДИН РАЗ и остаётся
                # прикреплённым навсегда — переключаем только setEnabled().
                # setGraphicsEffect(None) удаляет C++-объект эффекта
                # (виджет им владеет), и повторная попытка переиспользовать
                # тот же Python-объект эффекта приводит к падению
                # приложения при следующей активации этой же буквы.
                effect = QGraphicsDropShadowEffect()
                effect.setColor(QColor(COLOR_ACTIVE_GLOW))
                effect.setBlurRadius(16)
                effect.setOffset(0, 0)
                effect.setEnabled(False)
                lbl.setGraphicsEffect(effect)
                lbl._glow_effect = effect

                self.layout.addWidget(lbl, row, col)
                row_labels.append(lbl)
            self.labels.append(row_labels)

    def _inactive_style(self):
        return f"color: {COLOR_INACTIVE}; background: transparent; border: none;"

    def _active_style(self):
        return f"color: {COLOR_ACTIVE}; background: transparent; border: none;"

    def set_scale(self, target_w: int, target_h: int):
        """Масштабирование сетки под заданный размер.
        Сетка 11x10 не квадратная, поэтому ширина и высота ячейки
        считаются отдельно, чтобы итоговый виджет был точным квадратом
        (target_w == target_h вызывающей стороной)."""
        cell_w = target_w / GRID_COLS
        cell_h = target_h / GRID_ROWS

        font_size = max(6, int(min(cell_w, cell_h) * FONT_SIZE_RATIO))
        font = QFont(FONT_FAMILY, font_size)
        font.setWeight(int(FONT_WEIGHT))

        glow_radius = max(6, int(min(cell_w, cell_h) * 0.55))

        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                lbl = self.labels[row][col]
                lbl.setFont(font)
                lbl.setFixedSize(round(cell_w), round(cell_h))
                lbl._glow_effect.setBlurRadius(glow_radius)

        self.setFixedSize(round(target_w), round(target_h))

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
                is_active = (row, col) in active
                if is_active:
                    lbl.setStyleSheet(self._active_style())
                else:
                    lbl.setStyleSheet(self._inactive_style())
                lbl._glow_effect.setEnabled(is_active)

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
