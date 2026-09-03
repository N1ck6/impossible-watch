"""Виджет сетки привычек: квадраты-дни, зелёное свечение по длине стрика."""

from datetime import date, timedelta

from PyQt6.QtWidgets import QWidget, QLabel, QGridLayout, QVBoxLayout, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from config import *
from storage import streak_for


class _DayCell(QLabel):
    """Одна клетка-день. Клик эмитит свою ISO-дату через callback."""

    def __init__(self, iso_date: str, on_click):
        super().__init__("\u2588")
        self.iso_date = iso_date
        self._on_click = on_click
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        effect = QGraphicsDropShadowEffect()
        effect.setColor(QColor(COLOR_GREEN))
        effect.setBlurRadius(10)
        effect.setOffset(0, 0)
        effect.setEnabled(False)
        self.setGraphicsEffect(effect)
        self._glow = effect

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click(self.iso_date)
        super().mousePressEvent(event)


class HabitGrid(QWidget):
    day_clicked = pyqtSignal(str)  # ISO-дата

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cells = []   # [[_DayCell,...], ...] по строкам
        self.dates = []   # ISO-дата для каждой ячейки, по порядку (row-major)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        outer.addWidget(self.status_label)

        grid_holder = QWidget()
        self.grid_layout = QGridLayout(grid_holder)
        self.grid_layout.setSpacing(2)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(grid_holder)

        today = date.today()
        start = today - timedelta(days=GRID_DAYS - 1)

        idx = 0
        for r in range(GRID_ROWS):
            row_cells = []
            for c in range(GRID_COLS):
                d = start + timedelta(days=idx)
                iso = d.isoformat()
                cell = _DayCell(iso, self._on_cell_click)
                self.grid_layout.addWidget(cell, r, c)
                row_cells.append(cell)
                self.dates.append(iso)
                idx += 1
            self.cells.append(row_cells)

        self._apply_status_style()

    def _on_cell_click(self, iso_date: str):
        self.day_clicked.emit(iso_date)

    def _apply_status_style(self):
        font = QFont(FONT_FAMILY, FONT_SIZE)
        self.status_label.setFont(font)
        self.status_label.setStyleSheet(
            f"color: {COLOR_GREEN}; background: transparent; border: none;"
        )

    def set_status(self, habit_name: str, streak: int):
        if habit_name:
            self.status_label.setText(f"> {habit_name}  streak:{streak}")
        else:
            self.status_label.setText("> no habits — press \u2699 to add")

    def render(self, done_dates):
        """done_dates — коллекция ISO-дат, когда текущая привычка выполнена."""
        done = set(done_dates)
        today_iso = date.today().isoformat()

        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                idx = r * GRID_COLS + c
                iso = self.dates[idx]
                cell = self.cells[r][c]
                is_today = iso == today_iso
                is_done = iso in done

                if is_done:
                    streak = streak_for(done, date.fromisoformat(iso))
                    if streak >= 7:
                        color = COLOR_GREEN
                        cell._glow.setEnabled(True)
                    elif streak >= 3:
                        color = COLOR_GREEN_MED
                        cell._glow.setEnabled(False)
                    else:
                        color = COLOR_TEXT_DIM
                        cell._glow.setEnabled(False)
                    cell.setText("\u2588")
                else:
                    color = COLOR_GREEN_DIM
                    cell._glow.setEnabled(False)
                    cell.setText("\u2591" if is_today else "\u00b7")

                border = f"1px solid {COLOR_GREEN}" if is_today else "1px solid transparent"
                cell.setStyleSheet(
                    f"color: {color}; background: transparent; border: {border};"
                )

    def set_scale(self, w: int, h: int):
        self.setFixedSize(w, h)
        status_h = max(14, int(h * 0.06))
        cell_w = w / GRID_COLS
        cell_h = max(1, (h - status_h - 4)) / GRID_ROWS
        size = max(8, int(min(cell_w, cell_h)))

        font = QFont(FONT_FAMILY, max(8, int(size * 0.55)))
        for row in self.cells:
            for cell in row:
                cell.setFixedSize(int(cell_w), int(cell_h))
                cell.setFont(font)
                cell._glow.setBlurRadius(max(4, int(size * 0.4)))

        status_font = QFont(FONT_FAMILY, max(8, int(status_h * 0.6)))
        self.status_label.setFont(status_font)
