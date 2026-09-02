"""Главное окно приложения (v2)"""

from PyQt6.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QWidget,
    QSystemTrayIcon, QMenu, QApplication, QToolTip
)
from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QAction, QCursor, QIcon, QPixmap, QPainter, QBrush, QKeySequence, QShortcut

from clock_face import ClockFace
from config import *


class ClockWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.drag_pos = None
        self._resizing = False
        self._resize_dir = None
        self._resize_start = None
        self._resize_geom = None

        # Флаги окна
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Центральный виджет
        self.central = QWidget()
        self.central.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_BG};
                border: 1px solid {COLOR_FRAME};
                border-radius: 2px;
            }}
        """)
        self.setCentralWidget(self.central)

        layout = QVBoxLayout(self.central)
        layout.setContentsMargins(WINDOW_PADDING, WINDOW_PADDING, WINDOW_PADDING, WINDOW_PADDING)
        layout.setSpacing(0)

        # Циферблат
        self.clock = ClockFace()
        layout.addWidget(self.clock)

        # Размер окна
        self.setFixedSize(
            self.clock.width() + WINDOW_PADDING * 2,
            self.clock.height() + WINDOW_PADDING * 2
        )

        # Кнопки-точки по углам
        self.btn_lt = self._create_corner_button("Toggle text/digital mode")
        self.btn_lb = self._create_corner_button("Toggle minutes (digital mode)")
        self.btn_rt = self._create_corner_button("Toggle 12/24h format")
        self.btn_rb = self._create_corner_button("Toggle seconds (digital mode)")

        self._position_buttons()

        # Сигналы
        self.btn_lt.clicked.connect(self._toggle_text_mode)
        self.btn_lb.clicked.connect(self._toggle_minutes)
        self.btn_rt.clicked.connect(self._toggle_format)
        self.btn_rb.clicked.connect(self._toggle_seconds)

        # Начальное состояние
        self._update_buttons()

        # Системный трей
        self._init_tray()

        # Горячие клавиши
        self._init_shortcuts()

        # Настройки (позиция, размер)
        self._load_settings()

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

    def _init_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip("Word Clock")
        self.tray.setIcon(self._create_tray_icon())

        menu = QMenu()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self._start_exit_animation)
        menu.addAction(exit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _create_tray_icon(self):
        px = QPixmap(64, 64)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setBrush(QBrush(Qt.GlobalColor.cyan))
        p.drawEllipse(8, 8, 48, 48)
        p.end()
        return QIcon(px)

    def _init_shortcuts(self):
        # Ctrl+Q — выход с анимацией
        shortcut_exit = QShortcut(QKeySequence("Ctrl+Q"), self)
        shortcut_exit.activated.connect(self._start_exit_animation)

        # Пробел — переключение текст/цифры
        shortcut_mode = QShortcut(QKeySequence("Space"), self)
        shortcut_mode.activated.connect(self._toggle_text_mode)

    def _load_settings(self):
        from PyQt6.QtCore import QSettings
        settings = QSettings("WordClock", "Settings")
        pos = settings.value("pos", QPoint(100, 100))
        size = settings.value("size", None)
        self.move(pos)
        if size:
            self.resize(size)
            self._apply_scale()

    def _save_settings(self):
        from PyQt6.QtCore import QSettings
        settings = QSettings("WordClock", "Settings")
        settings.setValue("pos", self.pos())
        settings.setValue("size", self.size())

    def _apply_scale(self):
        """Пересчёт масштаба сетки относительно базового размера"""
        base_w = BASE_GRID_WIDTH + WINDOW_PADDING * 2
        base_h = BASE_GRID_HEIGHT + WINDOW_PADDING * 2
        scale_w = self.width() / base_w
        scale_h = self.height() / base_h
        scale = min(scale_w, scale_h)
        self.clock.set_scale(scale)

    # ═══════════════════════════════════════════════════════════
    # РЕСАЙЗ ЗА УГЛЫ
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
        if self.clock.text_mode:
            self.clock.show_minutes = False
            self.clock.show_seconds = False
        self._update_buttons()
        self.clock.update_display()

    def _toggle_minutes(self):
        if self.clock.text_mode:
            return
        # Toggle: если уже показываем минуты — выключаем и показываем часы
        if self.clock.show_minutes:
            self.clock.show_minutes = False
            self.clock.show_seconds = False
        else:
            self.clock.show_minutes = True
            self.clock.show_seconds = False
        self._update_buttons()
        self.clock.update_display()

    def _toggle_format(self):
        self.clock.use_12h = not self.clock.use_12h
        self.clock.show_ampm = self.clock.use_12h  # AM/PM только в 12ч режиме
        self._update_buttons()
        self.clock.update_display()

    def _toggle_seconds(self):
        if self.clock.text_mode:
            return
        # Toggle: если уже показываем секунды — выключаем и показываем часы
        if self.clock.show_seconds:
            self.clock.show_seconds = False
            self.clock.show_minutes = False
        else:
            self.clock.show_seconds = True
            self.clock.show_minutes = False
        self._update_buttons()
        self.clock.update_display()

    def _update_buttons(self):
        # ЛВ: горит в текстовом режиме
        self._set_btn_state(self.btn_lt, self.clock.text_mode)

        # ЛН: горит когда показываем минуты (только в цифровом)
        active = not self.clock.text_mode and self.clock.show_minutes
        enabled = not self.clock.text_mode
        self._set_btn_state(self.btn_lb, active, enabled)

        # ПВ: горит в 12-часовом формате
        self._set_btn_state(self.btn_rt, self.clock.use_12h)

        # ПН: горит когда показываем секунды (только в цифровом)
        active = not self.clock.text_mode and self.clock.show_seconds
        enabled = not self.clock.text_mode
        self._set_btn_state(self.btn_rb, active, enabled)

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
    # MOUSE EVENTS: drag + resize
    # ═══════════════════════════════════════════════════════════
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Игнорируем клики по кнопкам
        for btn in (self.btn_lt, self.btn_lb, self.btn_rt, self.btn_rb):
            if btn.geometry().contains(event.pos()):
                return

        # Проверяем ресайз (приоритет над drag)
        resize_dir = self._get_resize_dir(event.pos())
        if resize_dir:
            self._resizing = True
            self._resize_dir = resize_dir
            self._resize_start = event.globalPosition().toPoint()
            self._resize_geom = self.geometry()
            event.accept()
            return

        # Drag: за любую часть окна (рамки + сетка), но не за прозрачный фон
        # Проверяем, что клик внутри central widget
        if self.central.geometry().contains(event.pos()):
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._resizing and event.buttons() == Qt.MouseButton.LeftButton:
            self._do_resize(event.globalPosition().toPoint())
            event.accept()
            return

        if self.drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()
            return

        # Обновляем курсор при наведении
        self._update_cursor(event.pos())

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            self._resize_dir = None
            self._apply_scale()
            self._save_settings()
        self.drag_pos = None

    def _do_resize(self, global_pos):
        """Выполняет ресайз окна за угол"""
        delta = global_pos - self._resize_start
        geom = QRect(self._resize_geom)

        if self._resize_dir == "br":  # bottom-right
            new_w = max(MIN_WIDTH, min(MAX_WIDTH, geom.width() + delta.x()))
            new_h = max(MIN_HEIGHT, min(MAX_HEIGHT, geom.height() + delta.y()))
            self.setFixedSize(new_w, new_h)
        elif self._resize_dir == "bl":  # bottom-left
            new_w = max(MIN_WIDTH, min(MAX_WIDTH, geom.width() - delta.x()))
            new_h = max(MIN_HEIGHT, min(MAX_HEIGHT, geom.height() + delta.y()))
            if new_w != geom.width():
                self.setFixedSize(new_w, new_h)
                self.move(geom.right() - new_w + 1, geom.y())
            else:
                self.setFixedSize(new_w, new_h)
        elif self._resize_dir == "tr":  # top-right
            new_w = max(MIN_WIDTH, min(MAX_WIDTH, geom.width() + delta.x()))
            new_h = max(MIN_HEIGHT, min(MAX_HEIGHT, geom.height() - delta.y()))
            if new_h != geom.height():
                self.setFixedSize(new_w, new_h)
                self.move(geom.x(), geom.bottom() - new_h + 1)
            else:
                self.setFixedSize(new_w, new_h)
        elif self._resize_dir == "tl":  # top-left
            new_w = max(MIN_WIDTH, min(MAX_WIDTH, geom.width() - delta.x()))
            new_h = max(MIN_HEIGHT, min(MAX_HEIGHT, geom.height() - delta.y()))
            self.setFixedSize(new_w, new_h)
            self.move(geom.right() - new_w + 1, geom.bottom() - new_h + 1)

        self._position_buttons()

    # ═══════════════════════════════════════════════════════════
    # АНИМАЦИЯ ВЫХОДА
    # ═══════════════════════════════════════════════════════════
    def _start_exit_animation(self):
        """Запускает анимацию выхода: поэтапное затухание букв"""
        # Останавливаем таймер обновления
        self.clock.timer.stop()

        # Получаем все активные буквы
        active_labels = self.clock.get_active_labels()
        import random
        random.shuffle(active_labels)

        # Этап 1: поочерёдное затухание активных букв
        self._exit_step = 0
        self._exit_labels = active_labels
        self._exit_timer = QTimer(self)
        self._exit_timer.timeout.connect(self._exit_fade_letter)
        self._exit_timer.start(EXIT_ANIMATION_DURATION // FADE_STEPS)

    def _exit_fade_letter(self):
        if self._exit_labels:
            lbl = self._exit_labels.pop(0)
            lbl.setStyleSheet(self.clock._inactive_style())
        else:
            self._exit_timer.stop()
            # Этап 2: fade-out всего окна
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

    def _tray_activated(self, reason):
        """Показать/скрыть окно при клике по иконке трея"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
                self.activateWindow()

    def _quit_app(self):
        self._save_settings()
        self.tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event):
        self._save_settings()
        event.accept()
