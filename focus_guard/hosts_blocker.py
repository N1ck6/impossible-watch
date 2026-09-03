"""Блокировка сайтов через hosts-файл.

Принцип безопасности: все изменения находятся строго между двумя
маркерами (HOSTS_MARK_START/END). Снятие блокировки — это удаление
всего между маркерами, а не восстановление файла из полной копии, что
исключает потерю посторонних правок пользователя и делает операцию
идемпотентной (можно звать apply/remove в любом порядке, сколько угодно
раз, без накопления дублей и без риска "затереть" не свои строки).

Требует прав администратора/root на запись hosts. Никакой автоматической
эскалации привилегий модуль не делает — при нехватке прав просто
поднимается понятная ошибка с инструкцией.
"""

import sys
import os
from pathlib import Path


def hosts_path() -> Path:
    if sys.platform.startswith("win"):
        root = os.environ.get("SystemRoot", r"C:\Windows")
        return Path(root) / "System32" / "drivers" / "etc" / "hosts"
    return Path("/etc/hosts")


class HostsBlockError(Exception):
    pass


def _read_hosts() -> str:
    try:
        return hosts_path().read_text(encoding="utf-8")
    except Exception as e:
        raise HostsBlockError(f"Не удалось прочитать hosts-файл: {e}")


def _write_hosts(content: str):
    try:
        hosts_path().write_text(content, encoding="utf-8")
    except PermissionError:
        raise HostsBlockError(
            "Нет прав на запись hosts-файла. Запустите модуль от имени "
            "администратора (Windows) или через sudo (Linux/macOS)."
        )
    except Exception as e:
        raise HostsBlockError(f"Не удалось записать hosts-файл: {e}")


def _strip_block(content: str) -> str:
    from config import HOSTS_MARK_START, HOSTS_MARK_END
    if HOSTS_MARK_START not in content:
        return content
    before, _, rest = content.partition(HOSTS_MARK_START)
    _, _, after = rest.partition(HOSTS_MARK_END)
    return before.rstrip("\n") + "\n" + after.lstrip("\n")


def is_blocked() -> bool:
    from config import HOSTS_MARK_START
    try:
        return HOSTS_MARK_START in _read_hosts()
    except HostsBlockError:
        return False


def apply_block(domains):
    """Идемпотентно добавляет маркированный блок редиректов."""
    from config import HOSTS_MARK_START, HOSTS_MARK_END, REDIRECT_IP
    content = _strip_block(_read_hosts())

    lines = [HOSTS_MARK_START]
    for d in domains:
        d = d.strip().lower()
        if not d:
            continue
        lines.append(f"{REDIRECT_IP} {d}")
        if not d.startswith("www."):
            lines.append(f"{REDIRECT_IP} www.{d}")
    lines.append(HOSTS_MARK_END)

    new_content = content.rstrip("\n") + "\n" + "\n".join(lines) + "\n"
    _write_hosts(new_content)


def remove_block():
    """Безопасно убирает блок редиректов (no-op, если блока нет)."""
    content = _read_hosts()
    new_content = _strip_block(content)
    if new_content != content:
        _write_hosts(new_content)
