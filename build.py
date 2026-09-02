#!/usr/bin/env python3
"""Скрипт сборки исполняемого файла через PyInstaller"""

import PyInstaller.__main__


def build():
    """Собирает приложение в папку dist/WordClock/"""
    PyInstaller.__main__.run([
        'main.py',
        '--name=WordClock',
        '--noconfirm',
        '--clean',
        '--windowed',
        '--onedir',
    ])


if __name__ == "__main__":
    build()
