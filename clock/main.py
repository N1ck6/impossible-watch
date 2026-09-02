#!/usr/bin/env python3
"""Точка входа Word Clock v3.

Обычно запускается не напрямую, а через module_manager.py:
    python module_manager.py clock start

Слушает локальный сокет (см. config.IPC_SOCKET_NAME) и принимает от
менеджера две команды:
    "stop"  — закрыть окно с анимацией (module_manager.py clock stop)
    "focus" — поднять уже открытое окно наверх (повторный "start")
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtNetwork import QLocalServer

from clock_window import ClockWindow
from config import IPC_SOCKET_NAME

# Держим ссылки на активные соединения, чтобы Python не собрал их
# сборщиком мусора до обработки readyRead.
_active_sockets = []


def _setup_ipc_server(window: ClockWindow) -> QLocalServer:
    # Чистим "зависший" сокет, если предыдущий процесс упал без корректного закрытия
    QLocalServer.removeServer(IPC_SOCKET_NAME)

    server = QLocalServer()
    server.listen(IPC_SOCKET_NAME)

    def handle_connection():
        socket = server.nextPendingConnection()
        if socket is None:
            return
        _active_sockets.append(socket)

        def on_ready():
            data = bytes(socket.readAll()).decode("utf-8", errors="ignore").strip()
            if data == "stop":
                window.request_close()
            elif data == "focus":
                window.bring_to_front()
            socket.disconnectFromServer()

        def cleanup():
            if socket in _active_sockets:
                _active_sockets.remove(socket)

        socket.readyRead.connect(on_ready)
        socket.disconnected.connect(cleanup)

    server.newConnection.connect(handle_connection)
    return server


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    window = ClockWindow()
    window.show()

    server = _setup_ipc_server(window)  # noqa: F841 — держим ссылку живой

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
