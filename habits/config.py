"""Конфигурация трекера привычек — тёмный хакерский стиль (терминал/matrix)."""

IPC_SOCKET_NAME = "wordclock_module_habits"

COLOR_BG = "#000000"
COLOR_GREEN = "#00ff41"        # яркий "matrix" зелёный — длинный стрик
COLOR_GREEN_MED = "#12b83a"    # средний стрик
COLOR_GREEN_DIM = "#0a3d0a"    # неактивная клетка
COLOR_TEXT_DIM = "#0f7a24"     # короткий стрик (1-2 дня)
COLOR_FRAME = "#00ff41"
COLOR_FRAME_DIM = "#123d16"

FONT_FAMILY = "Consolas, 'Courier New', monospace"
FONT_SIZE = 12

GRID_COLS = 10
GRID_ROWS = 7
GRID_DAYS = GRID_COLS * GRID_ROWS  # 70 дней истории, от старых к today (bottom-right)

BASE_SIZE = 320
WINDOW_PADDING = 12
BUTTON_SIZE = 14
BUTTON_MARGIN = 4
RESIZE_HANDLE_SIZE = 12
MIN_SIZE = 240
MAX_SIZE = 640
FRAME_BORDER_WIDTH = 2
FRAME_RADIUS = 3
CLICK_MOVE_THRESHOLD = 4

DATA_FILE = "habits_data.json"
