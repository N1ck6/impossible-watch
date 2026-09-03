"""Главное окно приложения (v4 — Pomodoro)"""

import random
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel,
    QGraphicsOpacityEffect, QApplication,
)
from PyQt6.QtCore import (
    Qt, QPoint, QRect, QTimer, QPropertyAnimation, QEasingCurve,
    QSequentialAnimationGroup, QSettings,
)
from PyQt6.QtGui import QCursor, QKeySequence, QShortcut, QFont

from clock_face import ClockFace
from frame_widget import FrameWidget
from pomodoro_panel import PomodoroSettingsPanel
from config import *


class ClockWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.drag_pos = None
        self._press_pos = QPoint()
        self._moved = False
        self._resizing = False
        self._resize_dir = None
        self._resize_start = None
        self._resize_geom = None
        self._glyph_anim = None

        # ── Состояние вида: какой контент сейчас в квадрате ──
        # "clock"    — циферблат (обычные часы, либо запущенный Pomodoro)
        # "settings" — панель настроек Pomodoro
        self._view = "clock"

        # ── Состояние Pomodoro ──
        self._pomo_active = False      # идёт рабочая/перерывная стадия
        self._pomo_paused = False      # стадия на паузе (клик по циферблату)
        self._pomo_stage = None        # "work" | "break"
        self._pomo_cycle = 0           # сколько пар работа+перерыв уже завершено
        self._pomo_repeats = POMO_DEFAULT_REPEATS
        self._pomo_session_min = POMO_DEFAULT_SESSION_MIN
        self._pomo_break_min = POMO_DEFAULT_BREAK_MIN
        self._pomo_stage_duration = 0.0   # секунд
        self._pomo_stage_elapsed = 0.0    # секунд

        # Флаги окна
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Центральный виджет — фон + обводка/прогресс-бар (золото/лайм)
        self.central = FrameWidget()
        self.setCentralWidget(self.central)

        layout = QVBoxLayout(self.central)
        layout.setContentsMargins(WINDOW_PADDING, WINDOW_PADDING, WINDOW_PADDING, WINDOW_PADDING)
        layout.setSpacing(0)

        # Циферблат
        self.clock = ClockFace()
        layout.addWidget(self.clock)

        # Панель настроек Pomodoro — занимает то же место, видна только
        # когда self._view == "settings" (скрытый QWidget не влияет на
        # раскладку QVBoxLayout, поэтому оба виджета можно держать в
        # одном слое и просто скрывать ненужный)
        self.settings_panel = PomodoroSettingsPanel()
        layout.addWidget(self.settings_panel)
        self.settings_panel.hide()
        self.settings_panel.start_requested.connect(self._start_pomodoro)

        # Оверлей паузы/воспроизведения/завершения (клик по циферблату)
        self.pause_glyph = QLabel(self.central)
        self.pause_glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pause_glyph.setStyleSheet(
            f"color: {COLOR_FRAME_GOLD}; background: transparent; border: none;"
        )
        self.pause_glyph.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.pause_glyph.hide()

        # Размер окна (квадрат)
        self.setFixedSize(
            self.clock.width() + WINDOW_PADDING * 2,
            self.clock.height() + WINDOW_PADDING * 2,
        )

        # Кнопки-точки по углам (текст/цифры, 12/24ч)
        self.btn_lt = self._create_corner_button("Текст / цифры (Space)")
        self.btn_rt = self._create_corner_button("12ч / 24ч формат")

        # Кнопки прямого выбора режима цифрового отображения — H/M/S
        self.btn_h = self._create_submode_button("H", "Показать часы")
        self.btn_m = self._create_submode_button("M", "Показать минуты")
        self.btn_s = self._create_submode_button("S", "Показать секунды")

        # Кнопка "пропустить стадию" — заменяет H/M/S, пока идёт Pomodoro
        self.btn_skip = self._create_skip_button()
        self.btn_skip.hide()

        # Кнопка-иконка таймера (правый нижний угол): открыть настройки /
        # отменить настройку / остановить запущенный Pomodoro
        self.btn_timer = self._create_timer_button()

        self._position_buttons()

        # Сигналы
        self.btn_lt.clicked.connect(self._toggle_text_mode)
        self.btn_rt.clicked.connect(self._toggle_format)
        self.btn_h.clicked.connect(lambda: self._select_digit_mode("hours"))
        self.btn_m.clicked.connect(lambda: self._select_digit_mode("minutes"))
        self.btn_s.clicked.connect(lambda: self._select_digit_mode("seconds"))
        self.btn_skip.clicked.connect(self._skip_stage)
        self.btn_timer.clicked.connect(self._on_timer_button_clicked)

        # Начальное состояние
        self._update_buttons()

        # Горячие клавиши
        self._init_shortcuts()

        # Курсор ресайза должен появляться при наведении даже без
        # зажатой кнопки мыши — для этого нужен mouse tracking везде.
        self._enable_mouse_tracking_recursive(self)

        # Таймер прогресс-бара обводки (чаще, чем обновление букв,
        # чтобы анимация "стирания" выглядела плавной)
        self._border_timer = QTimer(self)
        self._border_timer.timeout.connect(self._update_border_progress)
        self._border_timer.start(BORDER_TICK_MS)

        # Настройки (позиция, размер, режим отображения, Pomodoro)
        self._load_settings()

    # ═══════════════════════════════════════════════════════════
    # ИНИЦИАЛИЗАЦИЯ
    # ═══════════════════════════════════════════════════════════
    def _create_corner_button(self, tooltip=""):
        btn = QPushButton(self)
        btn.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setToolTip(tooltip)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_BUTTON_INACTIVE};
                border-radius: {BUTTON_SIZE // 2}px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #555555;
            }}
        """)
        return btn

    def _create_submode_button(self, letter: str, tooltip: str) -> QPushButton:
        btn = QPushButton(letter, self)
        btn.setFixedSize(SUBMODE_BTN_W, SUBMODE_BTN_H)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setToolTip(tooltip)
        font = QFont(FONT_FAMILY)
        font.setPixelSize(SUBMODE_BTN_FONT_PX)
        font.setBold(True)
        btn.setFont(font)
        return btn

    def _create_skip_button(self) -> QPushButton:
        btn = QPushButton("\u23ed", self)  # ⏭
        w = 3 * SUBMODE_BTN_W + 2 * SUBMODE_BTN_SPACING
        btn.setFixedSize(w, SUBMODE_BTN_H)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setToolTip("Пропустить текущую стадию")
        font = QFont(FONT_FAMILY)
        font.setPixelSize(SKIP_BTN_FONT_PX)
        btn.setFont(font)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_BUTTON_INACTIVE};
                color: {COLOR_ACTIVE};
                border-radius: 2px;
                border: none;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: #555555;
            }}
        """)
        return btn

    def _create_timer_button(self) -> QPushButton:
        btn = QPushButton("\u23f1", self)  # ⏱
        btn.setFixedSize(TIMER_BTN_SIZE, TIMER_BTN_SIZE)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        font = QFont(FONT_FAMILY)
        font.setPixelSize(TIMER_BTN_FONT_PX)
        btn.setFont(font)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_BUTTON_INACTIVE};
                color: {COLOR_ACTIVE};
                border-radius: 3px;
                border: none;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: #555555;
            }}
        """)
        return btn

    def _position_buttons(self):
        m = BUTTON_MARGIN
        self.btn_lt.move(m, m)
        self.btn_rt.move(self.width() - BUTTON_SIZE - m, m)
        self.btn_timer.move(self.width() - TIMER_BTN_SIZE - m, self.height() - TIMER_BTN_SIZE - m)

        total_w = 3 * SUBMODE_BTN_W + 2 * SUBMODE_BTN_SPACING
        start_x = (self.width() - total_w) // 2
        y = self.height() - SUBMODE_BTN_H - m
        self.btn_h.move(start_x, y)
        self.btn_m.move(start_x + SUBMODE_BTN_W + SUBMODE_BTN_SPACING, y)
        self.btn_s.move(start_x + 2 * (SUBMODE_BTN_W + SUBMODE_BTN_SPACING), y)
        self.btn_skip.move(start_x, y)

    def _init_shortcuts(self):
        # Ctrl+Q — выход с анимацией (то же самое, что IPC-команда "stop")
        shortcut_exit = QShortcut(QKeySequence("Ctrl+Q"), self)
        shortcut_exit.activated.connect(self._start_exit_animation)

        # Пробел — переключение текст/цифры
        shortcut_mode = QShortcut(QKeySequence("Space"), self)
        shortcut_mode.activated.connect(self._toggle_text_mode)

    def _enable_mouse_tracking_recursive(self, widget: QWidget):
        """Без mouseTracking курсор-ресайз срабатывает только при
        зажатой кнопке мыши. Включаем трекинг на всём дереве виджетов,
        чтобы наведение на угол меняло курсор всегда."""
        widget.setMouseTracking(True)
        for child in widget.findChildren(QWidget):
            child.setMouseTracking(True)

    def _load_settings(self):
        settings = QSettings("WordClock", "Settings")
        try:
            pos = settings.value("pos", QPoint(100, 100))
            if pos:
                self.move(pos)

            if settings.contains("size"):
                raw = settings.value("size")
                size = int(raw)
                size = max(MIN_SIZE, min(MAX_SIZE, size))
                self.setFixedSize(size, size)
                self._position_buttons()
                self._apply_scale()

            text_mode = settings.value("text_mode", True, type=bool)
            use_12h = settings.value("use_12h", True, type=bool)
            digit_submode = settings.value("digit_submode", "hours", type=str)
            if digit_submode not in DIGIT_SUBMODES:
                digit_submode = "hours"

            self.clock.text_mode = text_mode
            self.clock.use_12h = use_12h
            self.clock.show_ampm = use_12h
            self.clock.digit_submode = digit_submode
            self.clock.show_minutes = digit_submode == "minutes"
            self.clock.show_seconds = digit_submode == "seconds"
            self.clock.update_display()

            session_min = settings.value("pomo_session_min", POMO_DEFAULT_SESSION_MIN, type=int)
            break_min = settings.value("pomo_break_min", POMO_DEFAULT_BREAK_MIN, type=int)
            repeats = settings.value("pomo_repeats", POMO_DEFAULT_REPEATS, type=int)
            self.settings_panel.set_values(session_min, break_min, repeats)

            self._update_buttons()
        except Exception:
            # Повреждённые/несовместимые настройки не должны ронять приложение
            pass

    def _save_settings(self):
        settings = QSettings("WordClock", "Settings")
        settings.setValue("pos", self.pos())
        settings.setValue("size", self.width())
        settings.setValue("text_mode", self.clock.text_mode)
        settings.setValue("use_12h", self.clock.use_12h)
        settings.setValue("digit_submode", self.clock.digit_submode)

        session_min, break_min, repeats = self.settings_panel.values()
        settings.setValue("pomo_session_min", session_min)
        settings.setValue("pomo_break_min", break_min)
        settings.setValue("pomo_repeats", repeats)

    def _apply_scale(self):
        """Пересчёт масштаба под текущий (квадратный) размер окна —
        и циферблата, и панели настроек (даже если она сейчас скрыта,
        чтобы быть готовой к показу без скачка размера)."""
        inner = max(1, self.width() - WINDOW_PADDING * 2)
        self.clock.set_scale(inner, inner)
        self.settings_panel.set_scale(inner, inner)
        self._scale_pause_glyph()

    def _scale_pause_glyph(self):
        font = QFont(FONT_FAMILY)
        font.setPointSize(max(14, int(self.clock.width() * 0.32)))
        self.pause_glyph.setFont(font)

    # ═══════════════════════════════════════════════════════════
    # РЕСАЙЗ ЗА УГЛЫ (всегда квадрат)
    # ═══════════════════════════════════════════════════════════
    def _get_resize_dir(self, pos: QPoint):
        """Определяет направление ресайза по позиции курсора"""
        rs = RESIZE_HANDLE_SIZE
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()

        left = x < rs
        right = x > w - rs
        top = y < rs
        bottom = y > h - rs

        if top and left: return "tl"
        if top and right: return "tr"
        if bottom and left: return "bl"
        if bottom and right: return "br"
        return None

    def _update_cursor(self, pos: QPoint):
        """Обновляет курсор в зависимости от зоны"""
        d = self._get_resize_dir(pos)
        if d in ("tl", "br"):
            self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        elif d in ("tr", "bl"):
            self.setCursor(QCursor(Qt.CursorShape.SizeBDiagCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    # ═══════════════════════════════════════════════════════════
    # ОБРАБОТКА КНОПОК ЦИФЕРБЛАТА
    # ═══════════════════════════════════════════════════════════
    def _toggle_text_mode(self):
        self.clock.text_mode = not self.clock.text_mode
        self._update_buttons()
        self.clock.update_display()

    def _select_digit_mode(self, mode: str):
        """Прямой выбор режима цифрового отображения по кнопке H/M/S."""
        if self.clock.text_mode:
            return
        self.clock.digit_submode = mode
        self.clock.show_minutes = mode == "minutes"
        self.clock.show_seconds = mode == "seconds"
        self._update_buttons()
        self.clock.update_display()

    def _toggle_format(self):
        self.clock.use_12h = not self.clock.use_12h
        self.clock.show_ampm = self.clock.use_12h  # AM/PM только в 12ч режиме
        self._update_buttons()
        self.clock.update_display()

    def _update_buttons(self):
        if self._view == "settings":
            return  # всё скрыто в _show_settings(), обновлять нечего

        # ЛВ: горит в текстовом режиме
        self._set_btn_state(self.btn_lt, self.clock.text_mode)
        # ПВ: горит в 12-часовом формате
        self._set_btn_state(self.btn_rt, self.clock.use_12h)

        if self._pomo_active:
            # Идёт Pomodoro: H/M/S скрыты, вместо них — кнопка "пропустить"
            self.btn_h.hide()
            self.btn_m.hide()
            self.btn_s.hide()
            self.btn_skip.show()
        else:
            self.btn_skip.hide()
            self.btn_h.show()
            self.btn_m.show()
            self.btn_s.show()
            enabled = not self.clock.text_mode
            self._set_submode_btn_state(self.btn_h, self.clock.digit_submode == "hours", enabled)
            self._set_submode_btn_state(self.btn_m, self.clock.digit_submode == "minutes", enabled)
            self._set_submode_btn_state(self.btn_s, self.clock.digit_submode == "seconds", enabled)

        self._update_timer_button_tooltip()

    def _set_btn_state(self, btn, active, enabled=True):
        if not enabled:
            color, hover = COLOR_BUTTON_DISABLED, COLOR_BUTTON_DISABLED
        elif active:
            color, hover = COLOR_BUTTON_ACTIVE, "#ffffff"
        else:
            color, hover = COLOR_BUTTON_INACTIVE, "#555555"

        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border-radius: {BUTTON_SIZE // 2}px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
        """)
        btn.setEnabled(enabled)

    def _set_submode_btn_state(self, btn, active, enabled=True):
        if not enabled:
            bg, fg, hover = COLOR_BUTTON_DISABLED, "#2a2a2a", COLOR_BUTTON_DISABLED
        elif active:
            bg, fg, hover = COLOR_BUTTON_ACTIVE, COLOR_BG, "#ffffff"
        else:
            bg, fg, hover = COLOR_BUTTON_INACTIVE, "#999999", "#555555"

        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border-radius: 2px;
                border: none;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
        """)
        btn.setEnabled(enabled)

    # ═══════════════════════════════════════════════════════════
    # POMODORO: переключение видов (часы <-> настройки)
    # ═══════════════════════════════════════════════════════════
    def _on_timer_button_clicked(self):
        if self._pomo_active:
            self._cancel_pomodoro()
        elif self._view == "clock":
            self._show_settings()
        else:
            self._show_clock()

    def _update_timer_button_tooltip(self):
        if self._pomo_active:
            self.btn_timer.setToolTip("Остановить Pomodoro-таймер")
        elif self._view == "settings":
            self.btn_timer.setToolTip("Отмена")
        else:
            self.btn_timer.setToolTip("Настроить Pomodoro-таймер")

    def _show_settings(self):
        self._view = "settings"
        self.clock.hide()
        self.settings_panel.show()
        self.btn_lt.hide()
        self.btn_rt.hide()
        self.btn_h.hide()
        self.btn_m.hide()
        self.btn_s.hide()
        self.btn_skip.hide()
        self._update_timer_button_tooltip()

    def _show_clock(self):
        self._view = "clock"
        self.settings_panel.hide()
        self.clock.show()
        self.btn_lt.show()
        self.btn_rt.show()
        self._update_buttons()

    # ═══════════════════════════════════════════════════════════
    # POMODORO: запуск / стадии / завершение
    # ═══════════════════════════════════════════════════════════
    def _start_pomodoro(self, session_min: int, break_min: int, repeats: int):
        self._pomo_session_min = session_min
        self._pomo_break_min = break_min
        self._pomo_repeats = max(1, repeats)
        self._pomo_cycle = 0
        self._show_clock()
        self._begin_stage("work")
        self._save_settings()

    def _begin_stage(self, stage: str):
        self._pomo_active = True
        self._pomo_paused = False
        self._pomo_stage = stage
        self._pomo_stage_elapsed = 0.0

        minutes = self._pomo_session_min if stage == "work" else self._pomo_break_min
        self._pomo_stage_duration = max(1, minutes) * 60.0

        if stage == "work":
            self.central.set_colors(COLOR_FRAME_GOLD, COLOR_FRAME_GOLD_DIM)
        else:
            self.central.set_colors(COLOR_FRAME_LIME, COLOR_FRAME_LIME_DIM)
        self.central.set_progress(1.0)

        self._update_buttons()

    def _advance_pomodoro_stage(self):
        """Стадия завершилась (само собой или по кнопке "пропустить")."""
        if self._pomo_stage == "work":
            self._begin_stage("break")
        else:
            self._pomo_cycle += 1
            if self._pomo_cycle >= self._pomo_repeats:
                self._finish_pomodoro()
            else:
                self._begin_stage("work")

    def _skip_stage(self):
        if not self._pomo_active:
            return
        self._advance_pomodoro_stage()

    def _finish_pomodoro(self):
        self._pomo_active = False
        self._pomo_paused = False
        self._pomo_stage = None
        self.central.set_colors(COLOR_FRAME_GOLD, COLOR_FRAME_GOLD_DIM)
        self.central.set_progress(1.0)
        self._update_buttons()
        self._show_glyph("done")

    def _cancel_pomodoro(self):
        self._pomo_active = False
        self._pomo_paused = False
        self._pomo_stage = None
        self.central.set_colors(COLOR_FRAME_GOLD, COLOR_FRAME_GOLD_DIM)
        self.central.set_progress(1.0)
        self._update_buttons()

    # ═══════════════════════════════════════════════════════════
    # ПАУЗА / ВОСПРОИЗВЕДЕНИЕ POMODORO (клик по циферблату)
    # Пауза имеет смысл только пока идёт рабочая/перерывная стадия —
    # в простом режиме часов клик по циферблату ничего не делает.
    # ═══════════════════════════════════════════════════════════
    def _toggle_pause(self):
        if not self._pomo_active:
            return
        self._pomo_paused = not self._pomo_paused
        if self._pomo_paused:
            self._show_glyph("pause")
        else:
            self._show_glyph("play")

    def _show_glyph(self, kind: str):
        symbol = {"pause": "\u23f8", "play": "\u25b6", "done": "\u2713"}.get(kind, "")
        self.pause_glyph.setText(symbol)
        self._scale_pause_glyph()
        self.pause_glyph.setGeometry(self.clock.geometry())
        self.pause_glyph.show()
        self.pause_glyph.raise_()

        effect = self.pause_glyph.graphicsEffect()
        if effect is None:
            effect = QGraphicsOpacityEffect(self.pause_glyph)
            self.pause_glyph.setGraphicsEffect(effect)
        effect.setOpacity(0.0)

        fade_in = QPropertyAnimation(effect, b"opacity", self)
        fade_in.setDuration(PAUSE_GLYPH_FADE_IN_MS)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)

        fade_out = QPropertyAnimation(effect, b"opacity", self)
        fade_out.setDuration(PAUSE_GLYPH_FADE_OUT_MS)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)

        group = QSequentialAnimationGroup(self)
        group.addAnimation(fade_in)
        group.addPause(PAUSE_GLYPH_HOLD_MS)
        group.addAnimation(fade_out)
        group.finished.connect(self.pause_glyph.hide)

        self._glyph_anim = group  # держим ссылку, чтобы группу не собрал GC
        group.start()

    # ═══════════════════════════════════════════════════════════
    # ОБВОДКА КАК ПРОГРЕСС-БАР POMODORO
    # (золото = работа, лайм = перерыв; 1 оборот = 100% стадии)
    # ═══════════════════════════════════════════════════════════
    def _update_border_progress(self):
        if not self._pomo_active or self._pomo_paused:
            return

        self._pomo_stage_elapsed += BORDER_TICK_MS / 1000.0
        if self._pomo_stage_elapsed >= self._pomo_stage_duration:
            self._advance_pomodoro_stage()
            return

        lit_fraction = 1.0 - (self._pomo_stage_elapsed / self._pomo_stage_duration)
        self.central.set_progress(lit_fraction)

    # ═══════════════════════════════════════════════════════════
    # MOUSE EVENTS: drag + resize + клик (пауза Pomodoro)
    # ═══════════════════════════════════════════════════════════
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Игнорируем клики по кнопкам
        for btn in (self.btn_lt, self.btn_rt, self.btn_h, self.btn_m, self.btn_s,
                    self.btn_skip, self.btn_timer):
            if btn.isVisible() and btn.geometry().contains(event.pos()):
                return

        # Проверяем ресайз (приоритет над drag/click)
        resize_dir = self._get_resize_dir(event.pos())
        if resize_dir:
            self._resizing = True
            self._resize_dir = resize_dir
            self._resize_start = event.globalPosition().toPoint()
            self._resize_geom = self.geometry()
            event.accept()
            return

        # Drag/click: за любую часть окна (рамка + сетка/панель настроек)
        if self.central.geometry().contains(event.pos()):
            self._moved = False
            self._press_pos = event.pos()
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._resizing and event.buttons() == Qt.MouseButton.LeftButton:
            self._do_resize(event.globalPosition().toPoint())
            event.accept()
            return

        if self.drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            if not self._moved:
                delta = event.pos() - self._press_pos
                if abs(delta.x()) > CLICK_MOVE_THRESHOLD or abs(delta.y()) > CLICK_MOVE_THRESHOLD:
                    self._moved = True
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()
            return

        # Обновляем курсор при наведении (работает благодаря mouseTracking)
        self._update_cursor(event.pos())

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            self._resize_dir = None
            self._apply_scale()
            self._save_settings()
        elif self.drag_pos is not None and not self._moved:
            # Мышь не сдвинулась дальше порога -> это клик, а не drag.
            # Пауза Pomodoro доступна только в виде "часы" (не в настройках).
            if self._view == "clock" and self.clock.geometry().contains(event.pos()):
                self._toggle_pause()

        self.drag_pos = None
        self._moved = False

    def _do_resize(self, global_pos):
        """Выполняет ресайз окна за угол — форма всегда остаётся квадратом,
        содержимое масштабируется в реальном времени (ещё во время движения мыши)"""
        delta = global_pos - self._resize_start
        geom = QRect(self._resize_geom)
        old_size = geom.width()  # width == height, окно всегда квадрат

        if self._resize_dir == "br":
            d = max(delta.x(), delta.y())
            new_size = max(MIN_SIZE, min(MAX_SIZE, old_size + d))
            self.setFixedSize(new_size, new_size)
        elif self._resize_dir == "bl":
            d = max(-delta.x(), delta.y())
            new_size = max(MIN_SIZE, min(MAX_SIZE, old_size + d))
            self.setFixedSize(new_size, new_size)
            self.move(geom.right() - new_size + 1, geom.y())
        elif self._resize_dir == "tr":
            d = max(delta.x(), -delta.y())
            new_size = max(MIN_SIZE, min(MAX_SIZE, old_size + d))
            self.setFixedSize(new_size, new_size)
            self.move(geom.x(), geom.bottom() - new_size + 1)
        elif self._resize_dir == "tl":
            d = max(-delta.x(), -delta.y())
            new_size = max(MIN_SIZE, min(MAX_SIZE, old_size + d))
            self.setFixedSize(new_size, new_size)
            self.move(geom.right() - new_size + 1, geom.bottom() - new_size + 1)

        self._position_buttons()
        self._apply_scale()  # живое масштабирование прямо во время ресайза

    # ═══════════════════════════════════════════════════════════
    # АНИМАЦИЯ ВЫХОДА
    # ═══════════════════════════════════════════════════════════
    def _start_exit_animation(self):
        """Запускает анимацию выхода: поэтапное затухание букв + fade-out окна.
        Используется и для Ctrl+Q, и для IPC-команды "stop" от менеджера."""
        self.clock.timer.stop()
        self._border_timer.stop()

        active_labels = self.clock.get_active_labels()
        random.shuffle(active_labels)

        self._exit_labels = active_labels
        self._exit_timer = QTimer(self)
        self._exit_timer.timeout.connect(self._exit_fade_letter)
        self._exit_timer.start(EXIT_ANIMATION_DURATION // max(1, FADE_STEPS))

    def _exit_fade_letter(self):
        if self._exit_labels:
            lbl = self._exit_labels.pop(0)
            lbl.setStyleSheet(self.clock._inactive_style())
            lbl._glow_effect.setEnabled(False)
        else:
            self._exit_timer.stop()
            self._fade_window()

    def _fade_window(self):
        """Плавное затухание всего окна"""
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(500)
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.animation.finished.connect(self._quit_app)
        self.animation.start()

    def _quit_app(self):
        self._save_settings()
        QApplication.instance().quit()

    def closeEvent(self, event):
        self._save_settings()
        event.accept()

    # ═══════════════════════════════════════════════════════════
    # ПУБЛИЧНЫЙ API ДЛЯ IPC (используется clock/main.py при командах
    # от module_manager.py)
    # ═══════════════════════════════════════════════════════════
    def request_close(self):
        """Команда "stop": закрыть с анимацией (как Ctrl+Q)"""
        self._start_exit_animation()

    def bring_to_front(self):
        """Команда "focus": поднять уже открытое окно наверх"""
        self.show()
        self.raise_()
        self.activateWindow()
