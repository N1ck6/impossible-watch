#!/usr/bin/env python3
"""
Универсальный менеджер модулей продуктивности.

CLI (одноразовые команды, вызываются извне — например из основного
приложения продуктивности):
    python module_manager.py <module> start    # открыть модуль (или поднять уже открытое окно наверх)
    python module_manager.py <module> stop     # закрыть модуль (с анимацией, если модуль это умеет)
    python module_manager.py <module> status   # проверить, запущен ли модуль
    python module_manager.py <module> toggle   # открыть/закрыть в зависимости от текущего состояния

Фоновый трей (ручной fallback для включения/выключения модулей без
основного приложения):
    python module_manager.py
    python module_manager.py tray

Модули описываются в modules.json рядом с этим файлом:
    {
      "clock": {
        "label": "Word Clock",
        "script": "clock/main.py",
        "socket_name": "wordclock_module_clock"
      }
    }

Чтобы добавить новый модуль с той же системой запуска/остановки —
допишите его сюда и реализуйте в самом модуле приём команд "stop"/
"focus" через QLocalServer на имени сокета из конфига (см. clock/main.py
как референс).
"""

import sys
import os
import json
import argparse
import subprocess
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QTimer
from PyQt6.QtNetwork import QLocalSocket

if getattr(sys, "frozen", False):
    # Собранный PyInstaller-экзешник — modules.json должен лежать рядом с ним
    ROOT_DIR = Path(sys.executable).resolve().parent
else:
    ROOT_DIR = Path(__file__).resolve().parent

CONFIG_PATH = ROOT_DIR / "modules.json"
IPC_TIMEOUT_MS = 800


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"[module_manager] Конфиг не найден: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _ensure_qcore_app():
    """QLocalSocket требует существующий экземпляр QCoreApplication,
    даже в чисто консольном одноразовом вызове."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)
    return app


def is_running(socket_name: str) -> bool:
    _ensure_qcore_app()
    sock = QLocalSocket()
    sock.connectToServer(socket_name)
    ok = sock.waitForConnected(IPC_TIMEOUT_MS)
    if ok:
        sock.disconnectFromServer()
    return ok


def send_command(socket_name: str, command: str) -> bool:
    _ensure_qcore_app()
    sock = QLocalSocket()
    sock.connectToServer(socket_name)
    if not sock.waitForConnected(IPC_TIMEOUT_MS):
        return False
    sock.write(command.encode("utf-8"))
    sock.waitForBytesWritten(IPC_TIMEOUT_MS)

    # disconnectFromServer() часто завершается синхронно (сокет уже
    # переходит в UnconnectedState), и последующий waitForDisconnected()
    # на уже отключённом сокете печатает предупреждение Qt в консоль.
    # Ждём только если сокет реально ещё подключен.
    if sock.state() != QLocalSocket.LocalSocketState.UnconnectedState:
        sock.disconnectFromServer()
        if sock.state() != QLocalSocket.LocalSocketState.UnconnectedState:
            sock.waitForDisconnected(IPC_TIMEOUT_MS)
    return True


def spawn_module(module_cfg: dict):
    script = ROOT_DIR / module_cfg["script"]

    if script.suffix == ".py":
        python_exe = module_cfg.get("python") or sys.executable
        cmd = [python_exe, str(script)]
    else:
        # Путь указывает на собранный исполняемый файл модуля
        cmd = [str(script)]

    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        kwargs["start_new_session"] = True

    subprocess.Popen(
        cmd,
        cwd=str(script.parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )


def start_module(name: str, cfg: dict):
    m = cfg[name]
    if is_running(m["socket_name"]):
        send_command(m["socket_name"], "focus")
        print(f"[{name}] уже запущен — окно поднято наверх")
        return
    spawn_module(m)
    print(f"[{name}] запущен")


def stop_module(name: str, cfg: dict):
    m = cfg[name]
    if is_running(m["socket_name"]):
        send_command(m["socket_name"], "stop")
        print(f"[{name}] отправлена команда закрытия")
    else:
        print(f"[{name}] уже не запущен")


def status_module(name: str, cfg: dict) -> bool:
    m = cfg[name]
    running = is_running(m["socket_name"])
    print(f"[{name}] {'запущен' if running else 'остановлен'}")
    return running


def toggle_module(name: str, cfg: dict):
    m = cfg[name]
    if is_running(m["socket_name"]):
        stop_module(name, cfg)
    else:
        start_module(name, cfg)


# ═══════════════════════════════════════════════════════════
# ТРЕЙ — фоновый fallback для ручного управления модулями
# ═══════════════════════════════════════════════════════════
def run_tray(cfg: dict):
    from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
    from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QBrush, QColor
    from PyQt6.QtCore import Qt

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    def make_icon() -> QIcon:
        px = QPixmap(64, 64)
        px.fill(Qt.GlobalColor.transparent)
        painter = QPainter(px)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#d4af37")))
        painter.drawEllipse(8, 8, 48, 48)
        painter.end()
        return QIcon(px)

    tray = QSystemTrayIcon(make_icon())
    tray.setToolTip("Модули продуктивности")
    menu = QMenu()
    actions = {}

    def refresh_menu():
        for name, m in cfg.items():
            running = is_running(m["socket_name"])
            actions[name].setChecked(running)

    for name, m in cfg.items():
        act = QAction(m.get("label", name), menu)
        act.setCheckable(True)
        act.setChecked(is_running(m["socket_name"]))
        act.triggered.connect(lambda checked, n=name: toggle_module(n, cfg))
        menu.addAction(act)
        actions[name] = act

    menu.addSeparator()
    exit_action = QAction("Выход из менеджера", menu)
    exit_action.triggered.connect(app.quit)
    menu.addAction(exit_action)

    menu.aboutToShow.connect(refresh_menu)
    tray.setContextMenu(menu)
    tray.show()

    refresh_timer = QTimer()
    refresh_timer.timeout.connect(refresh_menu)
    refresh_timer.start(3000)

    sys.exit(app.exec())


def main():
    cfg = load_config()

    parser = argparse.ArgumentParser(description="Менеджер модулей продуктивности")
    parser.add_argument("module", nargs="?", help="Имя модуля из modules.json, либо 'tray'")
    parser.add_argument("action", nargs="?", choices=["start", "stop", "status", "toggle"])
    args = parser.parse_args()

    if args.module in (None, "tray"):
        run_tray(cfg)
        return

    if args.module not in cfg:
        print(f"Неизвестный модуль: {args.module}. Доступны: {', '.join(cfg)}", file=sys.stderr)
        sys.exit(1)

    if not args.action:
        print("Не указано действие: start|stop|status|toggle", file=sys.stderr)
        sys.exit(1)

    actions = {
        "start": start_module,
        "stop": stop_module,
        "status": status_module,
        "toggle": toggle_module,
    }
    actions[args.action](args.module, cfg)


if __name__ == "__main__":
    main()
