"""Экстренная горячая клавиша — снимает блокировку немедленно, без
подтверждения, работает даже когда окно Focus Guard не в фокусе.

Требует пакет `keyboard`. На Linux низкоуровневый хук клавиатуры обычно
требует root или членства в группе `input` — если хоткей не срабатывает,
единственный оставшийся способ снять блокировку — вручную отредактировать
hosts-файл (см. README), это всегда работает независимо от данного модуля.

ВАЖНО: колбэк `keyboard` вызывается из отдельного потока, не из потока
Qt-event-loop. Вызывающая сторона обязана передавать сюда только
потокобезопасный callback (например, emit сигнала PyQt — Qt сам
корректно поставит его в очередь на GUI-поток)."""

_hotkey_hooked = None


def register_emergency_hotkey(combo: str, callback) -> bool:
    global _hotkey_hooked
    try:
        import keyboard
    except ImportError:
        print(
            "[focus_guard] Пакет 'keyboard' не установлен — экстренная "
            "горячая клавиша недоступна. Аварийный способ снять блокировку: "
            "вручную отредактировать hosts-файл (см. README)."
        )
        return False

    try:
        keyboard.add_hotkey(combo, callback)
        _hotkey_hooked = combo
        return True
    except Exception as e:
        print(f"[focus_guard] Не удалось зарегистрировать горячую клавишу: {e}")
        return False


def unregister_emergency_hotkey():
    global _hotkey_hooked
    if _hotkey_hooked is None:
        return
    try:
        import keyboard
        keyboard.remove_hotkey(_hotkey_hooked)
    except Exception:
        pass
    _hotkey_hooked = None
