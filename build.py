#!/usr/bin/env python3
"""Сборка исполняемых файлов: Word Clock (модуль) + Module Manager"""

import PyInstaller.__main__


def build_clock():
    """Собирает модуль часов в dist/WordClock/"""
    PyInstaller.__main__.run([
        'clock/main.py',
        '--name=WordClock',
        '--noconfirm',
        '--clean',
        '--windowed',
        '--onedir',
    ])


def build_manager():
    """Собирает менеджер модулей в dist/ModuleManager/"""
    PyInstaller.__main__.run([
        'module_manager.py',
        '--name=ModuleManager',
        '--noconfirm',
        '--clean',
        '--windowed',
        '--onedir',
    ])


if __name__ == "__main__":
    build_clock()
    build_manager()
    print(
        "\nГотово: dist/WordClock/ и dist/ModuleManager/.\n"
        "Не забудьте положить modules.json рядом с ModuleManager.exe "
        "и при необходимости обновить в нём путь \"script\" на "
        "собранный WordClock (например dist/WordClock/WordClock.exe)."
    )
