"""Панель настроек Pomodoro-таймера (v4).

Заменяет циферблат, пока пользователь настраивает длительность
рабочей сессии, перерыва и количество повторов, перед запуском таймера.
Стилистически — тёмный фон + золото + тот же шрифт, что и весь циферблат
(НЕ пиксельная иконка-стилистика референса — только состав настроек)."""

from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QCursor

from config import (
    FONT_FAMILY, COLOR_ACTIVE, COLOR_BG, COLOR_FRAME_GOLD,
    COLOR_BUTTON_INACTIVE,
    POMO_DEFAULT_SESSION_MIN, POMO_DEFAULT_BREAK_MIN, POMO_DEFAULT_REPEATS,
    POMO_SESSION_MIN_MIN, POMO_SESSION_MIN_MAX, POMO_SESSION_STEP,
    POMO_BREAK_MIN_MIN, POMO_BREAK_MIN_MAX, POMO_BREAK_STEP,
    POMO_REPEATS_MIN, POMO_REPEATS_MAX, POMO_REPEATS_STEP,
)


class _StepperRow(QWidget):
    """Одна строка настройки: название — значение — [-] [+]"""

    changed = pyqtSignal()

    def __init__(self, label_text: str, value: int, minimum: int, maximum: int,
                 step: int, suffix: str, parent=None):
        super().__init__(parent)
        self.value = value
        self.minimum = minimum
        self.maximum = maximum
        self.step = step
        self.suffix = suffix

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        self.name_label = QLabel(label_text)
        self.value_label = QLabel()
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.minus_btn = QPushButton("\u2212")
        self.plus_btn = QPushButton("+")

        for b in (self.minus_btn, self.plus_btn):
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        row.addWidget(self.name_label)
        row.addStretch(1)
        row.addWidget(self.minus_btn)
        row.addWidget(self.value_label)
        row.addWidget(self.plus_btn)

        self.minus_btn.clicked.connect(self._dec)
        self.plus_btn.clicked.connect(self._inc)

        self._apply_styles()
        self._refresh()

    def _dec(self):
        self.value = max(self.minimum, self.value - self.step)
        self._refresh()
        self.changed.emit()

    def _inc(self):
        self.value = min(self.maximum, self.value + self.step)
        self._refresh()
        self.changed.emit()

    def _refresh(self):
        self.value_label.setText(f"{self.value}{self.suffix}")

    def _apply_styles(self):
        self.name_label.setStyleSheet(
            f"color: {COLOR_ACTIVE}; background: transparent; border: none;"
        )
        self.value_label.setStyleSheet(
            f"color: {COLOR_FRAME_GOLD}; background: transparent; border: none; font-weight: 600;"
        )
        btn_style = f"""
            QPushButton {{
                background-color: {COLOR_BUTTON_INACTIVE};
                color: {COLOR_ACTIVE};
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #555555;
            }}
        """
        self.minus_btn.setStyleSheet(btn_style)
        self.plus_btn.setStyleSheet(btn_style)

    def set_scale(self, px: int, btn_size: int, value_w: int):
        font = QFont(FONT_FAMILY)
        font.setPixelSize(px)
        self.name_label.setFont(font)
        self.value_label.setFont(font)
        self.value_label.setFixedWidth(value_w)

        btn_font = QFont(FONT_FAMILY)
        btn_font.setPixelSize(max(9, int(px * 0.95)))
        btn_font.setBold(True)
        for b in (self.minus_btn, self.plus_btn):
            b.setFixedSize(btn_size, btn_size)
            b.setFont(btn_font)


class PomodoroSettingsPanel(QWidget):
    """Настройки: Session / Break / Repeat + кнопка Start."""

    start_requested = pyqtSignal(int, int, int)  # session_min, break_min, repeats

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self.session_row = _StepperRow(
            "Session", POMO_DEFAULT_SESSION_MIN,
            POMO_SESSION_MIN_MIN, POMO_SESSION_MIN_MAX, POMO_SESSION_STEP, " мин",
        )
        self.break_row = _StepperRow(
            "Break", POMO_DEFAULT_BREAK_MIN,
            POMO_BREAK_MIN_MIN, POMO_BREAK_MIN_MAX, POMO_BREAK_STEP, " мин",
        )
        self.repeat_row = _StepperRow(
            "Repeat", POMO_DEFAULT_REPEATS,
            POMO_REPEATS_MIN, POMO_REPEATS_MAX, POMO_REPEATS_STEP, "\u00d7",
        )

        layout.addWidget(self.session_row)
        layout.addWidget(self.break_row)
        layout.addWidget(self.repeat_row)
        layout.addStretch(1)

        self.start_btn = QPushButton("Start")
        self.start_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.start_btn.clicked.connect(self._emit_start)
        layout.addWidget(self.start_btn)

        self._apply_start_style()

    def _apply_start_style(self):
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_FRAME_GOLD};
                color: {COLOR_BG};
                border: none;
                border-radius: 4px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #ffffff;
            }}
        """)

    def _emit_start(self):
        self.start_requested.emit(
            self.session_row.value, self.break_row.value, self.repeat_row.value
        )

    def values(self):
        """Текущие настроенные значения (session_min, break_min, repeats)"""
        return self.session_row.value, self.break_row.value, self.repeat_row.value

    def set_values(self, session_min: int, break_min: int, repeats: int):
        self.session_row.value = max(self.session_row.minimum, min(self.session_row.maximum, session_min))
        self.break_row.value = max(self.break_row.minimum, min(self.break_row.maximum, break_min))
        self.repeat_row.value = max(self.repeat_row.minimum, min(self.repeat_row.maximum, repeats))
        self.session_row._refresh()
        self.break_row._refresh()
        self.repeat_row._refresh()

    def set_scale(self, w: int, h: int):
        self.setFixedSize(w, h)
        px = max(9, int(min(w, h) * 0.062))
        btn_size = max(14, int(min(w, h) * 0.09))
        value_w = max(30, int(min(w, h) * 0.2))

        for row in (self.session_row, self.break_row, self.repeat_row):
            row.set_scale(px, btn_size, value_w)

        start_font = QFont(FONT_FAMILY)
        start_font.setPixelSize(max(10, int(px * 1.05)))
        start_font.setBold(True)
        self.start_btn.setFont(start_font)
        self.start_btn.setFixedHeight(max(22, int(h * 0.14)))
