"""Сворачивание окон заблокированных приложений.

Best-effort и платформозависимо: на Windows нужен pywin32+psutil, на
Linux — установленный wmctrl, на macOS — доступ Accessibility для
System Events. Если зависимость отсутствует — тихо ничего не делает
(сайты при этом всё равно остаются заблокированы через hosts, это
независимый уровень защиты)."""

import sys
import subprocess


def minimize_matching(app_names):
    names_lower = [n.strip().lower() for n in app_names if n and n.strip()]
    if not names_lower:
        return

    if sys.platform.startswith("win"):
        _minimize_windows(names_lower)
    elif sys.platform.startswith("linux"):
        _minimize_linux(names_lower)
    elif sys.platform == "darwin":
        _minimize_macos(names_lower)


def _minimize_windows(names_lower):
    try:
        import win32gui
        import win32process
        import win32con
        import psutil
    except ImportError:
        return

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd).lower()
        proc_name = ""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc_name = psutil.Process(pid).name().lower()
        except Exception:
            pass
        if any(n in title or n in proc_name for n in names_lower):
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        return True

    try:
        win32gui.EnumWindows(callback, None)
    except Exception:
        pass


def _minimize_linux(names_lower):
    try:
        out = subprocess.run(
            ["wmctrl", "-l"], capture_output=True, text=True, timeout=2
        ).stdout
    except Exception:
        return

    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        win_id, title = parts[0], parts[3].lower()
        if any(n in title for n in names_lower):
            try:
                subprocess.run(
                    ["wmctrl", "-ic", win_id, "-b", "add,hidden"],
                    timeout=2, capture_output=True,
                )
            except Exception:
                pass


def _minimize_macos(names_lower):
    for name in names_lower:
        safe_name = name.replace('"', "")
        script = f'''
        tell application "System Events"
            set procList to (name of every process whose name contains "{safe_name}")
        end tell
        repeat with procName in procList
            tell application "System Events" to set visible of process procName to false
        end repeat
        '''
        try:
            subprocess.run(["osascript", "-e", script], timeout=3, capture_output=True)
        except Exception:
            pass
