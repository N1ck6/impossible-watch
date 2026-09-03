#!/usr/bin/env python3
"""Сборка исполняемых файлов всех модулей + менеджера"""

import PyInstaller.__main__

MODULES = [
    ("clock/main.py", "WordClock"),
    ("habits/main.py", "HabitTracker"),
    ("focus_guard/main.py", "FocusGuard"),
]


def build_module(script, name):
    PyInstaller.__main__.run([
        script,
        f'--name={name}',
        '--noconfirm',
        '--clean',
        '--windowed',
        '--onedir',
    ])


def build_manager():
    PyInstaller.__main__.run([
        'module_manager.py',
        '--name=ModuleManager',
        '--noconfirm',
        '--clean',
        '--windowed',
        '--onedir',
    ])


if __name__ == "__main__":
    for script, name in MODULES:
        build_module(script, name)
    build_manager()
    print(
        "\nГотово: dist/WordClock/, dist/HabitTracker/, dist/FocusGuard/, "
        "dist/ModuleManager/.\n"
        "Не забудьте положить modules.json рядом с ModuleManager и обновить "
        "в нём пути \"script\" на собранные exe.\n"
        "FocusGuard для блокировки сайтов нужно запускать с правами "
        "администратора/root."
    )
