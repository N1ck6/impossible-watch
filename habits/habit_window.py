"""Главное окно трекера привычек."""

from PyQt6.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QLineEdit, QApplication,
)
from PyQt6.QtCore import Qt, QPoint, QRect, QSettings
from PyQt6.QtGui import QCursor, QFont, QKeySequence, QShortcut

from habit_grid import HabitGrid
from config import *
from storage import load_data, save_data, streak_for


class _SettingsPanel(QWidget):
    """Добавление/удаление привычек — простой список со строкой ввода."""

    def __init__(self, on_add, on_remove, parent=None):
        super().__init__(parent)
        self._on_add = on_add
        self._on_remove = on_remove

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        add_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("новая привычка...")
        self.input.returnPressed.connect(self._add)
        self.add_btn = QPushButton("+")
        self.add_btn.clicked.connect(self._add)
        add_row.addWidget(self.input)
        add_row.addWidget(self.add_btn)
        layout.addLayout(add_row)

        self.list_holder = QVBoxLayout()
        layout.addLayout(self.list_holder)
        layout.addStretch(1)

        self._apply_styles()

    def _add(self):
        text = self.input.text().strip()
        if text:
            self._on_add(text)
            self.input.clear()

    def _apply_styles(self):
        self.input.setStyleSheet(
            f"background: {COLOR_BG}; color: {COLOR_GREEN}; "
            f"border: 1px solid {COLOR_FRAME_DIM}; padding: 3px; font-family: {FONT_FAMILY};"
        )
        self.add_btn.setStyleSheet(
            f"background: {COLOR_FRAME_DIM}; color: {COLOR_GREEN}; border: none; padding: 3px 8px;"
        )

    def rebuild_list(self, habits):
        while self.list_holder.count():
            item = self.list_holder.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                _clear_layout(item.layout())

        for name in habits:
            row = QHBoxLayout()
            lbl = QLabel(name)
            lbl.setStyleSheet(
                f"color: {COLOR_GREEN}; background: transparent; border: none; font-family: {FONT_FAMILY};"
            )
            del_btn = QPushButton("\u00d7")
            del_btn.setFixedWidth(22)
            del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            del_btn.setStyleSheet("background: transparent; color: #ff4444; border: none;")
            del_btn.clicked.connect(lambda checked, n=name: self._on_remove(n))
            row.addWidget(lbl)
            row.addStretch(1)
            row.addWidget(del_btn)
            self.list_holder.addLayout(row)

    def set_scale(self, w, h):
        self.setFixedSize(w, h)


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()


class HabitWindow(QMainWindow):
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
        self._view = "grid"

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.central = QWidget()
        self.central.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_BG};
                border: {FRAME_BORDER_WIDTH}px solid {COLOR_FRAME};
                border-radius: {FRAME_RADIUS}px;
            }}
        """)
        self.setCentralWidget(self.central)

        layout = QVBoxLayout(self.central)
        layout.setContentsMargins(WINDOW_PADDING, WINDOW_PADDING, WINDOW_PADDING, WINDOW_PADDING)
        layout.setSpacing(0)

        self.grid = HabitGrid()
        self.grid.day_clicked.connect(self._toggle_day)
        layout.addWidget(self.grid)

        self.settings_panel = _SettingsPanel(self._add_habit, self._remove_habit)
        layout.addWidget(self.settings_panel)
        self.settings_panel.hide()

        self.setFixedSize(
            self.grid.width() + WINDOW_PADDING * 2,
            self.grid.height() + WINDOW_PADDING * 2,
        )

        self.btn_next = self._create_dot("\u25b8", "Следующая привычка")
        self.btn_settings = self._create_dot("\u2699", "Управление привычками")
        self.btn_next.clicked.connect(self._next_habit)
        self.btn_settings.clicked.connect(self._toggle_settings)

        self._position_buttons()
        self._init_shortcuts()
        self._enable_mouse_tracking_recursive(self)
        self._refresh()
        self._load_window_settings()

    # ═══════════════════════════════════════════════════════════
    def _create_dot(self, glyph, tooltip):
        btn = QPushButton(glyph, self)
        btn.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setToolTip(tooltip)
        font = QFont(FONT_FAMILY)
        font.setPixelSize(9)
        btn.setFont(font)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_FRAME_DIM};
                color: {COLOR_GREEN};
                border-radius: 3px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #1a5c1a;
            }}
        """)
        return btn

    def _position_buttons(self):
        m = BUTTON_MARGIN
        self.btn_next.move(m, m)
        self.btn_settings.move(self.width() - BUTTON_SIZE - m, m)

    def _init_shortcuts(self):
        sc = QShortcut(QKeySequence("Ctrl+Q"), self)
        sc.activated.connect(self._quit)

    def _enable_mouse_tracking_recursive(self, widget):
        widget.setMouseTracking(True)
        for c in widget.findChildren(QWidget):
            c.setMouseTracking(True)

    # ═══════════════════════════════════════════════════════════
    # ДАННЫЕ
    # ═══════════════════════════════════════════════════════════
    def _current_habit(self):
        habits = self.data["habits"]
        if not habits:
            return None
        idx = self.data.get("current_index", 0) % len(habits)
        return habits[idx]

    def _refresh(self):
        habit = self._current_habit()
        done = set(self.data["log"].get(habit, [])) if habit else set()
        streak = streak_for(done) if habit else 0
        self.grid.set_status(habit, streak)
        self.grid.render(done)

    def _toggle_day(self, iso_date):
        habit = self._current_habit()
        if not habit:
            return
        log = self.data["log"].setdefault(habit, [])
        if iso_date in log:
            log.remove(iso_date)
        else:
            log.append(iso_date)
        save_data(self.data)
        self._refresh()

    def _next_habit(self):
        habits = self.data["habits"]
        if not habits:
            return
        self.data["current_index"] = (self.data.get("current_index", 0) + 1) % len(habits)
        save_data(self.data)
        self._refresh()

    def _add_habit(self, name):
        if name not in self.data["habits"]:
            self.data["habits"].append(name)
            self.data["log"].setdefault(name, [])
            save_data(self.data)
        self.settings_panel.rebuild_list(self.data["habits"])
        self._refresh()

    def _remove_habit(self, name):
        if name in self.data["habits"]:
            self.data["habits"].remove(name)
            self.data["log"].pop(name, None)
            if self.data.get("current_index", 0) >= len(self.data["habits"]):
                self.data["current_index"] = 0
            save_data(self.data)
        self.settings_panel.rebuild_list(self.data["habits"])
        self._refresh()

    def _toggle_settings(self):
        if self._view == "grid":
            self._view = "settings"
            self.grid.hide()
            self.btn_next.hide()
            self.settings_panel.rebuild_list(self.data["habits"])
            self.settings_panel.show()
        else:
            self._view = "grid"
            self.settings_panel.hide()
            self.grid.show()
            self.btn_next.show()
            self._refresh()

    # ═══════════════════════════════════════════════════════════
    # ГЕОМЕТРИЯ / РЕСАЙЗ / DRAG (тот же паттерн, что в часах)
    # ═══════════════════════════════════════════════════════════
    def _apply_scale(self):
        inner = max(1, self.width() - WINDOW_PADDING * 2)
        self.grid.set_scale(inner, inner)
        self.settings_panel.set_scale(inner, inner)

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
        for btn in (self.btn_next, self.btn_settings):
            if btn.geometry().contains(event.pos()):
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
            if not self._moved:
                delta = event.pos() - self._press_pos
                if abs(delta.x()) > CLICK_MOVE_THRESHOLD or abs(delta.y()) > CLICK_MOVE_THRESHOLD:
                    self._moved = True
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()
            return
        self._update_cursor(event.pos())

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            self._apply_scale()
            self._save_window_settings()
        self.drag_pos = None
        self._moved = False

    def _do_resize(self, global_pos):
        delta = global_pos - self._resize_start
        geom = QRect(self._resize_geom)
        old = geom.width()
        if self._resize_dir == "br":
            d = max(delta.x(), delta.y())
            s = max(MIN_SIZE, min(MAX_SIZE, old + d))
            self.setFixedSize(s, s)
        elif self._resize_dir == "bl":
            d = max(-delta.x(), delta.y())
            s = max(MIN_SIZE, min(MAX_SIZE, old + d))
            self.setFixedSize(s, s)
            self.move(geom.right() - s + 1, geom.y())
        elif self._resize_dir == "tr":
            d = max(delta.x(), -delta.y())
            s = max(MIN_SIZE, min(MAX_SIZE, old + d))
            self.setFixedSize(s, s)
            self.move(geom.x(), geom.bottom() - s + 1)
        elif self._resize_dir == "tl":
            d = max(-delta.x(), -delta.y())
            s = max(MIN_SIZE, min(MAX_SIZE, old + d))
            self.setFixedSize(s, s)
            self.move(geom.right() - s + 1, geom.bottom() - s + 1)
        self._position_buttons()
        self._apply_scale()

    def _load_window_settings(self):
        settings = QSettings("WordClock", "HabitsSettings")
        try:
            pos = settings.value("pos", QPoint(150, 150))
            if pos:
                self.move(pos)
            if settings.contains("size"):
                s = max(MIN_SIZE, min(MAX_SIZE, int(settings.value("size"))))
                self.setFixedSize(s, s)
                self._position_buttons()
                self._apply_scale()
        except Exception:
            pass

    def _save_window_settings(self):
        settings = QSettings("WordClock", "HabitsSettings")
        settings.setValue("pos", self.pos())
        settings.setValue("size", self.width())

    def _quit(self):
        self._save_window_settings()
        QApplication.instance().quit()

    def closeEvent(self, event):
        self._save_window_settings()
        event.accept()

    # ═══════════════════════════════════════════════════════════
    # ПУБЛИЧНЫЙ API ДЛЯ IPC
    # ═══════════════════════════════════════════════════════════
    def request_close(self):
        self._quit()

    def bring_to_front(self):
        self.show()
        self.raise_()
        self.activateWindow()
