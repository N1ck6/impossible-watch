"""Главное окно приложения (v3 — production)"""

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
        self._paused = False
        self._glyph_anim = None

        # Флаги окна
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Центральный виджет — фон + золотая обводка/прогресс-бар
        self.central = FrameWidget()
        self.setCentralWidget(self.central)

        layout = QVBoxLayout(self.central)
        layout.setContentsMargins(WINDOW_PADDING, WINDOW_PADDING, WINDOW_PADDING, WINDOW_PADDING)
        layout.setSpacing(0)

        # Циферблат
        self.clock = ClockFace()
        layout.addWidget(self.clock)

        # Оверлей паузы/воспроизведения (клик по циферблату)
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

        # Кнопки-точки по углам
        self.btn_lt = self._create_corner_button("Текст / цифры (Space)")
        self.btn_lb = self._create_corner_button("Следующий режим: часы → минуты → секунды")
        self.btn_rt = self._create_corner_button("12ч / 24ч формат")
        self.btn_rb = self._create_corner_button("Предыдущий режим: секунды → минуты → часы")

        self._position_buttons()

        # Сигналы
        self.btn_lt.clicked.connect(self._toggle_text_mode)
        self.btn_lb.clicked.connect(lambda: self._cycle_digit_mode(+1))
        self.btn_rt.clicked.connect(self._toggle_format)
        self.btn_rb.clicked.connect(lambda: self._cycle_digit_mode(-1))

        # Начальное состояние
        self._update_buttons()

        # Горячие клавиши
        self._init_shortcuts()

        # Курсор ресайза должен появляться при наведении даже без
        # зажатой кнопки мыши — для этого нужен mouse tracking везде.
        self._enable_mouse_tracking_recursive(self)

        # Таймер прогресс-бара золотой обводки (чаще, чем обновление букв,
        # чтобы анимация "стирания" выглядела плавной)
        self._border_timer = QTimer(self)
        self._border_timer.timeout.connect(self._update_border_progress)
        self._border_timer.start(BORDER_TICK_MS)

        # Настройки (позиция, размер, режим отображения)
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

    def _position_buttons(self):
        m = BUTTON_MARGIN
        self.btn_lt.move(m, m)
        self.btn_lb.move(m, self.height() - BUTTON_SIZE - m)
        self.btn_rt.move(self.width() - BUTTON_SIZE - m, m)
        self.btn_rb.move(self.width() - BUTTON_SIZE - m, self.height() - BUTTON_SIZE - m)

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

    def _apply_scale(self):
        """Пересчёт масштаба сетки под текущий (квадратный) размер окна"""
        inner = max(1, self.width() - WINDOW_PADDING * 2)
        self.clock.set_scale(inner, inner)
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
    # ОБРАБОТКА КНОПОК
    # ═══════════════════════════════════════════════════════════
    def _toggle_text_mode(self):
        self.clock.text_mode = not self.clock.text_mode
        self._update_buttons()
        self.clock.update_display()

    def _cycle_digit_mode(self, direction: int):
        """Циклическое переключение часы→минуты→секунды (или назад).
        Заменяет старые независимые toggle-кнопки, из-за которых легко
        было пропустить нужное состояние."""
        if self.clock.text_mode:
            return
        idx = DIGIT_SUBMODES.index(self.clock.digit_submode)
        idx = (idx + direction) % len(DIGIT_SUBMODES)
        self.clock.digit_submode = DIGIT_SUBMODES[idx]
        self.clock.show_minutes = self.clock.digit_submode == "minutes"
        self.clock.show_seconds = self.clock.digit_submode == "seconds"
        self._update_buttons()
        self.clock.update_display()

    def _toggle_format(self):
        self.clock.use_12h = not self.clock.use_12h
        self.clock.show_ampm = self.clock.use_12h  # AM/PM только в 12ч режиме
        self._update_buttons()
        self.clock.update_display()

    def _update_buttons(self):
        # ЛВ: горит в текстовом режиме
        self._set_btn_state(self.btn_lt, self.clock.text_mode)

        # ЛН/ПН: кнопки цикла режима — просто вкл/выкл в зависимости от
        # текст/цифры; текущий режим показывает буква H/M/S на циферблате
        enabled = not self.clock.text_mode
        self._set_btn_state(self.btn_lb, False, enabled)
        self._set_btn_state(self.btn_rb, False, enabled)

        # ПВ: горит в 12-часовом формате
        self._set_btn_state(self.btn_rt, self.clock.use_12h)

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

    # ═══════════════════════════════════════════════════════════
    # ПАУЗА / ВОСПРОИЗВЕДЕНИЕ (клик по циферблату)
    # ═══════════════════════════════════════════════════════════
    def _toggle_pause(self):
        self._paused = not self._paused
        if self._paused:
            self.clock.timer.stop()
            self._show_glyph("pause")
        else:
            self.clock.timer.start(1000)
            self.clock.update_display()
            self._show_glyph("play")

    def _show_glyph(self, kind: str):
        symbol = "⏸" if kind == "pause" else "▶"
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
    # ЗОЛОТАЯ ОБВОДКА КАК ПРОГРЕСС-БАР (полный оборот = 1 минута)
    # ═══════════════════════════════════════════════════════════
    def _update_border_progress(self):
        if self._paused:
            return
        now = datetime.now()
        erased_fraction = (now.second + now.microsecond / 1_000_000) / 60.0
        lit_fraction = 1.0 - erased_fraction
        self.central.set_progress(lit_fraction)

    # ═══════════════════════════════════════════════════════════
    # MOUSE EVENTS: drag + resize + клик (пауза)
    # ═══════════════════════════════════════════════════════════
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Игнорируем клики по кнопкам
        for btn in (self.btn_lt, self.btn_lb, self.btn_rt, self.btn_rb):
            if btn.geometry().contains(event.pos()):
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

        # Drag/click: за любую часть окна (рамка + сетка)
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
            # Мышь не сдвинулась дальше порога -> это клик, а не drag
            if self.clock.geometry().contains(event.pos()):
                self._toggle_pause()

        self.drag_pos = None
        self._moved = False

    def _do_resize(self, global_pos):
        """Выполняет ресайз окна за угол — форма всегда остаётся квадратом,
        буквы масштабируются в реальном времени (ещё во время движения мыши)"""
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
        self._apply_scale()  # живое масштабирование букв прямо во время ресайза

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
            lbl.setGraphicsEffect(None)
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
