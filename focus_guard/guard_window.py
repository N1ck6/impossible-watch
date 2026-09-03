"""Главное окно Focus Guard."""

from PyQt6.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QLineEdit, QApplication,
)
from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, QSettings, QObject, pyqtSignal
from PyQt6.QtGui import QCursor, QFont, QKeySequence, QShortcut

from config import *
import hosts_blocker
import app_minimizer
import hotkey
from storage import load_data, save_data


class _HotkeyBridge(QObject):
    """Мост из потока `keyboard` в Qt-поток: сигналы PyQt автоматически
    становятся потокобезопасной очередью при кросс-тредовом emit."""
    triggered = pyqtSignal()


class _StepperRow(QWidget):
    def __init__(self, label, value, minimum, maximum, step, suffix, parent=None):
        super().__init__(parent)
        self.value, self.minimum, self.maximum, self.step, self.suffix = (
            value, minimum, maximum, step, suffix
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.name_label = QLabel(label)
        self.value_label = QLabel()
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setFixedWidth(48)
        self.minus_btn = QPushButton("\u2212")
        self.plus_btn = QPushButton("+")
        for b in (self.minus_btn, self.plus_btn):
            b.setFixedSize(20, 20)
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        row.addWidget(self.name_label)
        row.addStretch(1)
        row.addWidget(self.minus_btn)
        row.addWidget(self.value_label)
        row.addWidget(self.plus_btn)
        self.minus_btn.clicked.connect(self._dec)
        self.plus_btn.clicked.connect(self._inc)
        self._style()
        self._refresh()

    def _dec(self):
        self.value = max(self.minimum, self.value - self.step)
        self._refresh()

    def _inc(self):
        self.value = min(self.maximum, self.value + self.step)
        self._refresh()

    def _refresh(self):
        self.value_label.setText(f"{self.value}{self.suffix}")

    def _style(self):
        self.name_label.setStyleSheet(f"color: {COLOR_TEXT}; background: transparent; border: none;")
        self.value_label.setStyleSheet(f"color: {COLOR_ORANGE}; background: transparent; border: none; font-weight: 600;")
        btn_style = f"""
            QPushButton {{ background-color: {COLOR_BTN}; color: {COLOR_TEXT}; border: none; border-radius: 3px; }}
            QPushButton:hover {{ background-color: #442a2a; }}
        """
        self.minus_btn.setStyleSheet(btn_style)
        self.plus_btn.setStyleSheet(btn_style)


class _ListSection(QWidget):
    """Заголовок + строка добавления + список элементов с удалением."""

    def __init__(self, title, placeholder, on_add, on_remove, parent=None):
        super().__init__(parent)
        self._on_add = on_add
        self._on_remove = on_remove

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; background: transparent; border: none; font-weight: 600;")
        layout.addWidget(title_lbl)

        add_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.returnPressed.connect(self._add)
        self.add_btn = QPushButton("+")
        self.add_btn.setFixedWidth(24)
        self.add_btn.clicked.connect(self._add)
        add_row.addWidget(self.input)
        add_row.addWidget(self.add_btn)
        layout.addLayout(add_row)

        self.list_holder = QVBoxLayout()
        self.list_holder.setSpacing(2)
        layout.addLayout(self.list_holder)

        self.input.setStyleSheet(
            f"background: {COLOR_INPUT_BG}; color: {COLOR_TEXT}; border: 1px solid #333; padding: 3px;"
        )
        self.add_btn.setStyleSheet(f"background: {COLOR_BTN}; color: {COLOR_TEXT}; border: none;")

    def _add(self):
        text = self.input.text().strip()
        if text:
            self._on_add(text)
            self.input.clear()

    def rebuild(self, items):
        while self.list_holder.count():
            item = self.list_holder.takeAt(0)
            if item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        for name in items:
            row = QHBoxLayout()
            lbl = QLabel(name)
            lbl.setStyleSheet(f"color: {COLOR_TEXT}; background: transparent; border: none;")
            del_btn = QPushButton("\u00d7")
            del_btn.setFixedWidth(20)
            del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            del_btn.setStyleSheet("background: transparent; color: #ff4444; border: none;")
            del_btn.clicked.connect(lambda checked, n=name: self._on_remove(n))
            row.addWidget(lbl)
            row.addStretch(1)
            row.addWidget(del_btn)
            self.list_holder.addLayout(row)

    def set_enabled(self, enabled: bool):
        self.input.setEnabled(enabled)
        self.add_btn.setEnabled(enabled)


class GuardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data = load_data()

        self.drag_pos = None
        self._press_pos = QPoint()
        self._moved = False
        self._resizing = False
        self._resize_dir = None
        self._resize_start = None
        self._resize_geom = None

        self._active = False
        self._session_seconds_left = None   # None = бессрочно (восстановлено после сбоя)
        self._stop_armed = False
        self._stop_remaining = 0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.central = QWidget()
        self.setCentralWidget(self.central)
        self._apply_central_style()

        layout = QVBoxLayout(self.central)
        layout.setContentsMargins(WINDOW_PADDING, WINDOW_PADDING, WINDOW_PADDING, WINDOW_PADDING)
        layout.setSpacing(8)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.sites_section = _ListSection("SITES", "example.com", self._add_site, self._remove_site)
        self.apps_section = _ListSection("APPS", "discord", self._add_app, self._remove_app)
        layout.addWidget(self.sites_section)
        layout.addWidget(self.apps_section)

        self.duration_row = _StepperRow(
            "Session", self.data.get("session_min", DEFAULT_SESSION_MIN),
            SESSION_MIN_MIN, SESSION_MIN_MAX, SESSION_STEP, " мин",
        )
        layout.addWidget(self.duration_row)

        layout.addStretch(1)

        self.main_btn = QPushButton("Start")
        self.main_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.main_btn.clicked.connect(self._on_main_button)
        layout.addWidget(self.main_btn)

        self.resize(BASE_W, BASE_H)

        self._init_shortcuts()
        self._enable_mouse_tracking_recursive(self)

        self.sites_section.rebuild(self.data["sites"])
        self.apps_section.rebuild(self.data["apps"])

        self._app_timer = QTimer(self)
        self._app_timer.timeout.connect(self._poll_apps)
        self._app_timer.setInterval(APP_POLL_INTERVAL_MS)

        self._session_timer = QTimer(self)
        self._session_timer.timeout.connect(self._tick_session)
        self._session_timer.setInterval(1000)

        self._stop_countdown_timer = QTimer(self)
        self._stop_countdown_timer.timeout.connect(self._tick_stop_countdown)
        self._stop_countdown_timer.setInterval(1000)

        # ── эмерджди-хоткей: колбэк из чужого потока -> сигнал Qt -> GUI-поток ──
        self._hotkey_bridge = _HotkeyBridge()
        self._hotkey_bridge.triggered.connect(self._emergency_stop)
        hotkey.register_emergency_hotkey(EMERGENCY_HOTKEY, self._hotkey_bridge.triggered.emit)

        self._load_window_settings()
        self._recover_after_crash()
        self._refresh_ui()

    # ═══════════════════════════════════════════════════════════
    def _apply_central_style(self):
        border_color = COLOR_RED if self._active else COLOR_FRAME_IDLE
        self.central.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_BG};
                border: {FRAME_BORDER_WIDTH}px solid {border_color};
                border-radius: {FRAME_RADIUS}px;
            }}
        """)

    def _init_shortcuts(self):
        sc = QShortcut(QKeySequence("Ctrl+Q"), self)
        sc.activated.connect(self._quit)

    def _enable_mouse_tracking_recursive(self, widget):
        widget.setMouseTracking(True)
        for c in widget.findChildren(QWidget):
            c.setMouseTracking(True)

    # ═══════════════════════════════════════════════════════════
    # СПИСКИ САЙТОВ/ПРИЛОЖЕНИЙ (менять можно только когда не активно —
    # иначе можно было бы обойти защиту, удалив домен из списка и
    # тут же "переприменив" блок без него)
    # ═══════════════════════════════════════════════════════════
    def _add_site(self, name):
        if self._active:
            return
        if name not in self.data["sites"]:
            self.data["sites"].append(name)
            save_data(self.data)
        self.sites_section.rebuild(self.data["sites"])

    def _remove_site(self, name):
        if self._active:
            return
        if name in self.data["sites"]:
            self.data["sites"].remove(name)
            save_data(self.data)
        self.sites_section.rebuild(self.data["sites"])

    def _add_app(self, name):
        if self._active:
            return
        if name not in self.data["apps"]:
            self.data["apps"].append(name)
            save_data(self.data)
        self.apps_section.rebuild(self.data["apps"])

    def _remove_app(self, name):
        if self._active:
            return
        if name in self.data["apps"]:
            self.data["apps"].remove(name)
            save_data(self.data)
        self.apps_section.rebuild(self.data["apps"])

    # ═══════════════════════════════════════════════════════════
    # СТАРТ / АНТИСОФТБЛОК-СТОП / АВАРИЙНАЯ ОСТАНОВКА
    # ═══════════════════════════════════════════════════════════
    def _on_main_button(self):
        if not self._active:
            self._start_session()
            return

        if not self._stop_armed:
            self._arm_stop()
        elif self._stop_remaining <= 0:
            self._end_session(force=True)
        # если armed, но countdown ещё не истёк — кнопка неактивна,
        # сюда попасть нельзя штатно

    def _start_session(self):
        if not self.data["sites"] and not self.data["apps"]:
            self.status_label.setText("Добавьте хотя бы один сайт или приложение")
            return

        try:
            hosts_blocker.apply_block(self.data["sites"])
        except hosts_blocker.HostsBlockError as e:
            self.status_label.setText(str(e))
            return

        self.data["session_min"] = self.duration_row.value
        save_data(self.data)

        self._active = True
        self._session_seconds_left = self.duration_row.value * 60
        self._stop_armed = False

        self._app_timer.start()
        self._session_timer.start()
        self._refresh_ui()
        self._save_window_settings()

    def _tick_session(self):
        if self._session_seconds_left is None:
            return
        self._session_seconds_left -= 1
        if self._session_seconds_left <= 0:
            self._end_session(force=True)
        else:
            self._refresh_ui()

    def _poll_apps(self):
        app_minimizer.minimize_matching(self.data["apps"])

    def _arm_stop(self):
        self._stop_armed = True
        self._stop_remaining = STOP_CONFIRM_SECONDS
        self._stop_countdown_timer.start()
        self._refresh_ui()

    def _tick_stop_countdown(self):
        self._stop_remaining -= 1
        if self._stop_remaining <= 0:
            self._stop_countdown_timer.stop()
            self._stop_remaining = 0
        self._refresh_ui()

    def _cancel_arm(self):
        self._stop_armed = False
        self._stop_countdown_timer.stop()
        self._refresh_ui()

    def _end_session(self, force=False):
        try:
            hosts_blocker.remove_block()
        except hosts_blocker.HostsBlockError as e:
            self.status_label.setText(str(e))
            if not force:
                return

        self._active = False
        self._session_seconds_left = None
        self._stop_armed = False
        self._stop_countdown_timer.stop()
        self._app_timer.stop()
        self._session_timer.stop()
        self._refresh_ui()
        self._save_window_settings()

    def _emergency_stop(self):
        """Вызывается из _hotkey_bridge — уже на GUI-потоке. Снимает
        блокировку немедленно, без подтверждения, вне зависимости от
        текущего состояния (даже если окно свёрнуто/не в фокусе)."""
        if self._active:
            self._end_session(force=True)
            self.status_label.setText("Снято аварийной горячей клавишей")

    def _recover_after_crash(self):
        """Если процесс упал во время блокировки, hosts-файл остаётся
        заблокированным (это не баг — иначе просто kill процесса снимал
        бы блок). При повторном запуске обнаруживаем это и продолжаем
        мониторинг приложений, но без исходной длительности (бессрочно,
        до ручного подтверждения или хоткея)."""
        if hosts_blocker.is_blocked():
            self._active = True
            self._session_seconds_left = None
            self._app_timer.start()
            self.status_label.setText("Восстановлено после сбоя — сессия активна")

    # ═══════════════════════════════════════════════════════════
    def _refresh_ui(self):
        self._apply_central_style()
        can_edit = not self._active
        self.sites_section.set_enabled(can_edit)
        self.apps_section.set_enabled(can_edit)
        self.duration_row.setEnabled(can_edit)

        if not self._active:
            self.status_label.setText("\u25cf IDLE")
            self.status_label.setStyleSheet(f"color: {COLOR_TEXT_DIM}; background: transparent; border: none; font-weight: 600;")
            self.main_btn.setText("Start")
            self.main_btn.setEnabled(True)
            self._style_main_btn(COLOR_RED)
            return

        if self._session_seconds_left is None:
            time_text = "неизвестно (после сбоя)"
        else:
            m, s = divmod(max(0, self._session_seconds_left), 60)
            time_text = f"{m:02d}:{s:02d}"
        self.status_label.setText(f"\u25cf ACTIVE — {time_text}")
        self.status_label.setStyleSheet(f"color: {COLOR_RED}; background: transparent; border: none; font-weight: 600;")

        if not self._stop_armed:
            self.main_btn.setText("Стоп")
            self.main_btn.setEnabled(True)
            self._style_main_btn(COLOR_BTN)
        elif self._stop_remaining > 0:
            self.main_btn.setText(f"Подождите {self._stop_remaining}с...")
            self.main_btn.setEnabled(False)
            self._style_main_btn(COLOR_BTN)
        else:
            self.main_btn.setText("Подтвердить остановку")
            self.main_btn.setEnabled(True)
            self._style_main_btn(COLOR_ORANGE)

    def _style_main_btn(self, color):
        self.main_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: {COLOR_TEXT if color != COLOR_ORANGE else "#1a0f00"};
                border: none; border-radius: 4px; font-weight: 700; padding: 8px 0;
            }}
            QPushButton:disabled {{ color: #888888; }}
        """)

    # ═══════════════════════════════════════════════════════════
    # ГЕОМЕТРИЯ / РЕСАЙЗ / DRAG (прямоугольник — не квадрат, независимые
    # ширина/высота, т.к. под списки удобнее вертикальная форма)
    # ═══════════════════════════════════════════════════════════
    def _get_resize_dir(self, pos):
        rs = RESIZE_HANDLE_SIZE
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        left, right = x < rs, x > w - rs
        top, bottom = y < rs, y > h - rs
        if top and left: return "tl"
        if top and right: return "tr"
        if bottom and left: return "bl"
        if bottom and right: return "br"
        return None

    def _update_cursor(self, pos):
        d = self._get_resize_dir(pos)
        if d in ("tl", "br"):
            self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        elif d in ("tr", "bl"):
            self.setCursor(QCursor(Qt.CursorShape.SizeBDiagCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        d = self._get_resize_dir(event.pos())
        if d:
            self._resizing = True
            self._resize_dir = d
            self._resize_start = event.globalPosition().toPoint()
            self._resize_geom = self.geometry()
            event.accept()
            return
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
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()
            return
        self._update_cursor(event.pos())

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            self._save_window_settings()
        self.drag_pos = None
        self._moved = False

    def _do_resize(self, global_pos):
        delta = global_pos - self._resize_start
        geom = QRect(self._resize_geom)

        if self._resize_dir in ("br", "tr"):
            new_w = max(MIN_W, min(MAX_W, geom.width() + delta.x()))
        else:
            new_w = max(MIN_W, min(MAX_W, geom.width() - delta.x()))

        if self._resize_dir in ("br", "bl"):
            new_h = max(MIN_H, min(MAX_H, geom.height() + delta.y()))
        else:
            new_h = max(MIN_H, min(MAX_H, geom.height() - delta.y()))

        self.resize(new_w, new_h)

        if self._resize_dir in ("bl", "tl"):
            self.move(geom.right() - new_w + 1, self.y())
        if self._resize_dir in ("tl", "tr"):
            self.move(self.x(), geom.bottom() - new_h + 1)

    def _load_window_settings(self):
        settings = QSettings("WordClock", "FocusGuardSettings")
        try:
            pos = settings.value("pos", QPoint(200, 150))
            if pos:
                self.move(pos)
            w = settings.value("w", type=int)
            h = settings.value("h", type=int)
            if w and h:
                self.resize(max(MIN_W, min(MAX_W, w)), max(MIN_H, min(MAX_H, h)))
        except Exception:
            pass

    def _save_window_settings(self):
        settings = QSettings("WordClock", "FocusGuardSettings")
        settings.setValue("pos", self.pos())
        settings.setValue("w", self.width())
        settings.setValue("h", self.height())

    def _quit(self):
        self._save_window_settings()
        hotkey.unregister_emergency_hotkey()
        QApplication.instance().quit()

    def closeEvent(self, event):
        self._save_window_settings()
        event.accept()

    # ═══════════════════════════════════════════════════════════
    # ПУБЛИЧНЫЙ API ДЛЯ IPC
    # Пока блокировка активна, "stop" НЕ снимает её мгновенно — иначе
    # это был бы тривиальный обход антисофтблока через командную строку
    # ("module_manager.py focus_guard stop"). Вместо этого окно просто
    # поднимается наверх, и пользователь проходит обычный флоу
    # подтверждения. Настоящий безусловный выход — только хоткей.
    # ═══════════════════════════════════════════════════════════
    def request_close(self):
        if self._active:
            self.bring_to_front()
            self.status_label.setText("Остановка — только через кнопку в окне или хоткей")
        else:
            self._quit()

    def bring_to_front(self):
        self.show()
        self.raise_()
        self.activateWindow()
