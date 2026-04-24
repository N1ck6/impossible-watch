"""Главное окно приложения"""

from PyQt6.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QWidget,
    QSystemTrayIcon, QMenu, QApplication
)
from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QAction, QCursor, QIcon, QPixmap, QPainter, QBrush

from clock_face import ClockFace
from config import *


class ClockWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.drag_pos = None

        # Флаги окна: без рамки, поверх всех, не на панели задач
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Центральный виджет с рамкой
        central = QWidget()
        central.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_BG};
                border: 3px solid {COLOR_FRAME};
                border-radius: 6px;
            }}
        """)
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(WINDOW_PADDING, WINDOW_PADDING, WINDOW_PADDING, WINDOW_PADDING)

        # Циферблат
        self.clock = ClockFace()
        layout.addWidget(self.clock)

        # Размер окна
        self.setFixedSize(
            self.clock.width() + WINDOW_PADDING * 2,
            self.clock.height() + WINDOW_PADDING * 2
        )

        # Кнопки-точки по углам
        self.btn_lt = self._create_corner_button()  # Left Top
        self.btn_lb = self._create_corner_button()  # Left Bottom
        self.btn_rt = self._create_corner_button()  # Right Top
        self.btn_rb = self._create_corner_button()  # Right Bottom

        self._position_buttons()

        # Сигналы
        self.btn_lt.clicked.connect(self._toggle_text_mode)
        self.btn_lb.clicked.connect(self._toggle_minutes)
        self.btn_rt.clicked.connect(self._toggle_format)
        self.btn_rb.clicked.connect(self._toggle_seconds)

        # Начальное состояние кнопок
        self._update_buttons()

        # Системный трей
        self._init_tray()

    def _create_corner_button(self):
        btn = QPushButton(self)
        btn.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
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
        exit_action.triggered.connect(self._quit_app)
        menu.addAction(exit_action)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def _create_tray_icon(self):
        px = QPixmap(64, 64)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setBrush(QBrush(Qt.GlobalColor.cyan))
        p.drawEllipse(8, 8, 48, 48)
        p.end()
        return QIcon(px)

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
        self.clock.show_minutes = True
        self.clock.show_seconds = False
        self._update_buttons()
        self.clock.update_display()

    def _toggle_format(self):
        self.clock.use_12h = not self.clock.use_12h
        self._update_buttons()
        self.clock.update_display()

    def _toggle_seconds(self):
        if self.clock.text_mode:
            return
        self.clock.show_seconds = True
        self.clock.show_minutes = False
        self._update_buttons()
        self.clock.update_display()

    def _update_buttons(self):
        # ЛВ: горит в текстовом режиме
        self._set_btn_state(self.btn_lt, self.clock.text_mode)

        # ЛН: горит когда показываем минуты (только в цифровом режиме)
        active = not self.clock.text_mode and self.clock.show_minutes
        enabled = not self.clock.text_mode
        self._set_btn_state(self.btn_lb, active, enabled)

        # ПВ: горит в 12-часовом формате
        self._set_btn_state(self.btn_rt, self.clock.use_12h)

        # ПН: горит когда показываем секунды (только в цифровом режиме)
        active = not self.clock.text_mode and self.clock.show_seconds
        enabled = not self.clock.text_mode
        self._set_btn_state(self.btn_rb, active, enabled)

    def _set_btn_state(self, btn, active, enabled=True):
        if not enabled:
            color = COLOR_BUTTON_DISABLED
            hover = COLOR_BUTTON_DISABLED
        elif active:
            color = COLOR_BUTTON_ACTIVE
            hover = "#5eeeee"
        else:
            color = COLOR_BUTTON_INACTIVE
            hover = "#555555"

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

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Игнорируем клики по кнопкам
        for btn in (self.btn_lt, self.btn_lb, self.btn_rt, self.btn_rb):
            if btn.geometry().contains(event.pos()):
                return

        # Разрешаем перетаскивание только за область циферблата
        global_pos = self.clock.mapToGlobal(QPoint(0, 0))
        local_pos = self.mapFromGlobal(global_pos)
        clock_rect = QRect(local_pos, self.clock.size())

        if clock_rect.contains(event.pos()):
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def _quit_app(self):
        self.tray.hide()
        QApplication.instance().quit()
