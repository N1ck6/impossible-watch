"""Логика отображения времени на сетке букв (v3)"""

from datetime import datetime
from typing import List, Tuple, Set
from config import GRID

# ═══════════════════════════════════════════════════════════
# КООРДИНАТЫ СЛОВ (row, col) — сетка ITISHMSAMPM + остальные строки
#
# Проверено построчно относительно строк GRID из config.py.
# Исправлены 3 бага исходной версии:
#   - AM светила как "MP" (было (0,8),(0,9)) -> теперь верно "AM"
#   - QUARTER светила как "CQUARTE" без последней R (было со сдвигом
#     на 1 колонку влево) -> теперь верно "QUARTER"
#   - TO светила как "FTO" с лишней буквой F -> теперь верно "TO"
# Буквы H/M/S в верхней строке больше не подсвечиваются как индикатор
# режима (режим теперь показывают кнопки H/M/S, см. clock_window.py) —
# в WORDS они и не нужны.
# ═══════════════════════════════════════════════════════════
WORDS = {
    'IT': [(0, 0), (0, 1)],
    'IS': [(0, 2), (0, 3)],
    'AM': [(0, 7), (0, 8)],
    'PM': [(0, 9), (0, 10)],
    'FIVE_MIN': [(2, 6), (2, 7), (2, 8), (2, 9)],
    'TEN_MIN': [(3, 5), (3, 6), (3, 7)],
    'QUARTER': [(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8)],
    'TWENTY': [(2, 0), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5)],
    'HALF': [(3, 0), (3, 1), (3, 2), (3, 3)],
    'PAST': [(4, 0), (4, 1), (4, 2), (4, 3)],
    'TO': [(3, 9), (3, 10)],
    'ONE': [(5, 0), (5, 1), (5, 2)],
    'TWO': [(6, 8), (6, 9), (6, 10)],
    'THREE': [(5, 6), (5, 7), (5, 8), (5, 9), (5, 10)],
    'FOUR': [(6, 0), (6, 1), (6, 2), (6, 3)],
    'FIVE_HOUR': [(6, 4), (6, 5), (6, 6), (6, 7)],
    'SIX': [(5, 3), (5, 4), (5, 5)],
    'SEVEN': [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4)],
    'EIGHT': [(7, 0), (7, 1), (7, 2), (7, 3), (7, 4)],
    'NINE': [(4, 7), (4, 8), (4, 9), (4, 10)],
    'TEN_HOUR': [(9, 0), (9, 1), (9, 2)],
    'ELEVEN': [(7, 5), (7, 6), (7, 7), (7, 8), (7, 9), (7, 10)],
    'TWELVE': [(8, 5), (8, 6), (8, 7), (8, 8), (8, 9), (8, 10)],
    'OCLOCK': [(9, 5), (9, 6), (9, 7), (9, 8), (9, 9), (9, 10)],
}

# ═══════════════════════════════════════════════════════════
# ПАТТЕРНЫ ЦИФР 5×7 (для сетки 11×10)
# Размещаем цифры начиная с row=1, col=0
# Две цифры: первая col=0, вторая col=6 (ширина 5 + зазор 1)
# ═══════════════════════════════════════════════════════════
DIGIT_PATTERNS_5x7 = {
    0: [
        (0,1),(0,2),(0,3),
        (1,0),       (1,4),
        (2,0),       (2,4),
        (3,0),       (3,4),
        (4,0),       (4,4),
        (5,0),       (5,4),
        (6,1),(6,2),(6,3),
    ],
    1: [
              (0,2),
        (1,1),(1,2),
              (2,2),
              (3,2),
              (4,2),
              (5,2),
        (6,1),(6,2),(6,3),
    ],
    2: [
        (0,1),(0,2),(0,3),
        (1,0),       (1,4),
                     (2,4),
              (3,2),(3,3),
        (4,1),
        (5,0),
        (6,0),(6,1),(6,2),(6,3),(6,4),
    ],
    3: [
        (0,1),(0,2),(0,3),
        (1,0),       (1,4),
                     (2,4),
              (3,2),(3,3),
                     (4,4),
        (5,0),       (5,4),
        (6,1),(6,2),(6,3),
    ],
    4: [
              (0,3),
        (1,2),(1,3),
        (2,1),(2,3),
        (3,0),(3,3),
        (4,0),(4,1),(4,2),(4,3),(4,4),
                     (5,3),
                     (6,3),
    ],
    5: [
        (0,0),(0,1),(0,2),(0,3),(0,4),
        (1,0),
        (2,0),(2,1),(2,2),(2,3),
                     (3,4),
                     (4,4),
        (5,0),       (5,4),
        (6,1),(6,2),(6,3),
    ],
    6: [
              (0,2),(0,3),
        (1,1),
        (2,0),
        (3,0),(3,1),(3,2),(3,3),
        (4,0),       (4,4),
        (5,0),       (5,4),
        (6,1),(6,2),(6,3),
    ],
    7: [
        (0,0),(0,1),(0,2),(0,3),(0,4),
                     (1,4),
                    (2,3),
              (3,2),
              (4,2),
              (5,2),
              (6,2),
    ],
    8: [
        (0,1),(0,2),(0,3),
        (1,0),       (1,4),
        (2,0),       (2,4),
              (3,2),
        (4,0),       (4,4),
        (5,0),       (5,4),
        (6,1),(6,2),(6,3),
    ],
    9: [
        (0,1),(0,2),(0,3),
        (1,0),       (1,4),
        (2,0),       (2,4),
        (3,1),(3,2),(3,3),(3,4),
                     (4,4),
              (5,3),
        (6,1),(6,2),
    ],
}


def get_digit_coords(digit: int, base_row: int, base_col: int) -> List[Tuple[int, int]]:
    """Абсолютные координаты для одной цифры 5×7"""
    return [(base_row + r, base_col + c) for r, c in DIGIT_PATTERNS_5x7[digit]]


def get_number_coords(number: int, base_row: int, base_col: int, always_two: bool = False) -> List[Tuple[int, int]]:
    """Координаты для двузначного числа на сетке 11×10.
    Первая цифра: col=0, вторая: col=6 (ширина 5 + зазор 1)"""
    tens = number // 10
    ones = number % 10
    coords = []
    if always_two or tens != 0:
        coords.extend(get_digit_coords(tens, base_row, base_col))
    coords.extend(get_digit_coords(ones, base_row, base_col + 6))
    return coords


def get_text_time_coords(dt: datetime, show_ampm: bool = True) -> Set[Tuple[int, int]]:
    """Возвращает координаты букв для текстового отображения"""
    coords = set()
    coords.update(WORDS['IT'])
    coords.update(WORDS['IS'])

    hour = dt.hour
    minute = dt.minute

    # AM/PM (только если включен 12-часовой формат)
    if show_ampm:
        if hour >= 12:
            coords.update(WORDS['PM'])
        else:
            coords.update(WORDS['AM'])

    # 12-часовой формат для отображения
    display_hour = hour % 12
    if display_hour == 0:
        display_hour = 12

    # Округление до ближайших 5 минут
    rounded = ((minute + 2) // 5) * 5
    if rounded == 60:
        rounded = 0
        display_hour = display_hour + 1 if display_hour < 12 else 1

    if rounded == 0:
        coords.update(WORDS['OCLOCK'])
    elif rounded <= 30:
        coords.update(WORDS['PAST'])
    else:
        coords.update(WORDS['TO'])
        rounded = 60 - rounded
        display_hour = display_hour + 1 if display_hour < 12 else 1

    # Минуты словами
    if rounded == 5:
        coords.update(WORDS['FIVE_MIN'])
    elif rounded == 10:
        coords.update(WORDS['TEN_MIN'])
    elif rounded == 15:
        coords.update(WORDS['QUARTER'])
    elif rounded == 20:
        coords.update(WORDS['TWENTY'])
    elif rounded == 25:
        coords.update(WORDS['TWENTY'])
        coords.update(WORDS['FIVE_MIN'])
    elif rounded == 30:
        coords.update(WORDS['HALF'])

    # Час словом
    hour_map = {
        1: 'ONE', 2: 'TWO', 3: 'THREE', 4: 'FOUR',
        5: 'FIVE_HOUR', 6: 'SIX', 7: 'SEVEN', 8: 'EIGHT',
        9: 'NINE', 10: 'TEN_HOUR', 11: 'ELEVEN', 12: 'TWELVE'
    }
    coords.update(WORDS[hour_map[display_hour]])

    return coords


def get_digit_time_coords(
    dt: datetime,
    show_minutes: bool = False,
    show_seconds: bool = False,
    use_12h: bool = True
) -> Set[Tuple[int, int]]:
    """Возвращает координаты букв для цифрового отображения.
    Текущий режим (часы/минуты/секунды) теперь показывают кнопки H/M/S,
    поэтому буквы-индикаторы на самом циферблате больше не подсвечиваются."""
    coords = set()

    if show_seconds:
        val = dt.second
        coords.update(get_number_coords(val, 1, 0, always_two=True))
    elif show_minutes:
        val = dt.minute
        coords.update(get_number_coords(val, 1, 0, always_two=True))
    else:
        val = dt.hour
        if use_12h:
            val = val % 12
            if val == 0:
                val = 12
            if val < 10:
                # Одна цифра по центру: col=3 (центрируем в 11 колонках)
                coords.update(get_digit_coords(val, 1, 3))
            else:
                coords.update(get_number_coords(val, 1, 0, always_two=True))
        else:
            coords.update(get_number_coords(val, 1, 0, always_two=True))

    return coords
