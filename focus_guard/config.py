"""Конфигурация Focus Guard — блокировщик отвлечений."""

IPC_SOCKET_NAME = "wordclock_module_focus_guard"

COLOR_BG = "#0d0808"
COLOR_RED = "#ff3b30"
COLOR_RED_DIM = "#4a1310"
COLOR_ORANGE = "#ff9500"
COLOR_TEXT = "#e8e8e8"
COLOR_TEXT_DIM = "#888888"
COLOR_FRAME_IDLE = "#555555"
COLOR_INPUT_BG = "#1a1414"
COLOR_BTN = "#2a1e1e"

FONT_FAMILY = "Segoe UI, Arial, sans-serif"
FONT_SIZE = 12

WINDOW_PADDING = 12
BUTTON_SIZE = 14
BUTTON_MARGIN = 4
RESIZE_HANDLE_SIZE = 12

MIN_W, MIN_H = 260, 340
MAX_W, MAX_H = 480, 640
BASE_W, BASE_H = 300, 400

FRAME_BORDER_WIDTH = 2
FRAME_RADIUS = 4
CLICK_MOVE_THRESHOLD = 4

DATA_FILE = "focus_guard_data.json"

# ── hosts-файл ──
HOSTS_MARK_START = "# === FocusGuard BLOCK START ==="
HOSTS_MARK_END = "# === FocusGuard BLOCK END ==="
REDIRECT_IP = "127.0.0.1"

# ── сворачивание приложений ──
APP_POLL_INTERVAL_MS = 1000

# ── антисофтблок: кнопка "Стоп" во время блокировки требует ожидания,
# прежде чем подтверждение станет доступно — защита от импульсивного
# самосаботажа ("я просто на секунду выключу и сразу обратно") ──
STOP_CONFIRM_SECONDS = 20

DEFAULT_SESSION_MIN = 60
SESSION_MIN_MIN, SESSION_MIN_MAX, SESSION_STEP = 5, 240, 5

# ── экстренная горячая клавиша: снимает блокировку МГНОВЕННО и БЕЗ
# подтверждения, работает даже когда окно не в фокусе. Это единственный
# способ обойти STOP_CONFIRM_SECONDS — сознательно, как аварийный выход. ──
EMERGENCY_HOTKEY = "ctrl+alt+shift+f12"
