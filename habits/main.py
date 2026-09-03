#!/usr/bin/env python3
"""Точка входа Habit Tracker. Обычно запускается через:
    python module_manager.py habits start
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtNetwork import QLocalServer

from habit_window import HabitWindow
from config import IPC_SOCKET_NAME

_active_sockets = []


def _setup_ipc_server(window: HabitWindow) -> QLocalServer:
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

    window = HabitWindow()
    window.show()

    server = _setup_ipc_server(window)  # noqa: F841

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
