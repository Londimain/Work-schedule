# config.py
# -*- coding: utf-8 -*-
"""Общие константы, шрифт, иконка и настройка Kivy.

ВАЖНО: этот модуль должен импортироваться ПЕРВЫМ — он выставляет
параметры Kivy до импорта kivy.uix.* в других модулях.
"""
import os
import platform
import sys
import webbrowser

# --- Настройка Kivy ДО импорта kivy.uix.* --------------------------------
os.environ.setdefault('KIVY_NO_ARGS', '1')
from kivy.config import Config
Config.set('input', 'mouse', 'mouse,disable_multitouch')
Config.set('graphics', 'dpi', '96')
Config.set('graphics', 'multisamples', '0')

from kivy.core.text import LabelBase
from kivy.core.window import Window

# =========================================================================
# ШРИФТ
# =========================================================================
FONT_REG = r'C:\Windows\Fonts\arial.ttf'
FONT_BOLD = r'C:\Windows\Fonts\arialbd.ttf'
FONT_NAME = 'AppFont'

if not os.path.exists(FONT_REG):
    FONT_REG = 'Roboto'
    FONT_BOLD = 'Roboto'
    FONT_NAME = 'Roboto'

try:
    LabelBase.register(name=FONT_NAME,
                       fn_regular=FONT_REG,
                       fn_bold=FONT_BOLD)
except Exception as e:
    print("Ошибка регистрации шрифта:", e)
    FONT_NAME = 'Roboto'

# =========================================================================
# ОКНО
# =========================================================================
Window.size = (1500, 900)
Window.position = 'custom'

# =========================================================================
# ПУТИ
# =========================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "tabel_data.json")

ICON_PATH = os.path.join(BASE_DIR, "ico", "tabel.ico")
ICON_EMOJI = "📋"

# =========================================================================
# ДАННЫЕ ПО УМОЛЧАНИЮ
# =========================================================================
MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
          "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
YEARS = [str(y) for y in range(2024, 2036)]

WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

DEFAULT_POSITIONS = ["электромонтер", "оператор котельной"]
DEFAULT_DEPARTMENTS = ["ЭНЕРГОСЛУЖБА"]
DEFAULT_ORG = 'ОАО "Компания "МогНат"'

HOLIDAYS = {
    (1, 1), (1, 7), (2, 23), (3, 8), (5, 1),
    (5, 9), (7, 3), (11, 7), (12, 25),
}

# =========================================================================
# ЦВЕТА
# =========================================================================
WEEKEND_BG   = (1.00, 0.82, 0.82, 1)
WEEKEND_FG   = (0.55, 0.05, 0.05, 1)
HOLIDAY_BG   = (1.00, 0.94, 0.70, 1)
HOLIDAY_FG   = (0.55, 0.35, 0.00, 1)
WORKDAY_BG   = (1.00, 1.00, 1.00, 1)
WORKDAY_FG   = (0.05, 0.05, 0.05, 1)
HEADER_BG    = (0.88, 0.88, 0.88, 1)
HEADER_FG    = (0.05, 0.05, 0.05, 1)

DEPT_BAR_BG  = (0.20, 0.30, 0.55, 1)
DEPT_BAR_FG  = (1.00, 1.00, 1.00, 1)

LABEL_LIGHT  = (0.95, 0.95, 0.95, 1)
LABEL_DARK   = (0.05, 0.05, 0.05, 1)

VHEADER_BG   = (0.85, 0.88, 0.92, 1)
VHEADER_FG   = (0.05, 0.05, 0.05, 1)

DIVIDER_COLOR = (0.55, 0.55, 0.55, 1)
HEADER_DIVIDER = (0.00, 0.00, 0.00, 1)

SPINNER_BG   = (0.20, 0.30, 0.55, 1)
SPINNER_FG   = (1.00, 1.00, 1.00, 1)

# =========================================================================
# КОЛОНКИ ИТОГОВ И КОДЫ
# =========================================================================
RIGHT_COLUMNS = [
    ("Факт.работы",                 "явки",              44),
    ("Целосмен. простои",           "целосмен_простои",  40),
    ("Трудовой отпуск",             "отп",               40),
    ("Отп. по родам",               "отп_роды",          44),
    ("Болезнь",                     "бол",               36),
    ("Проч. неявки",                "проч_неявки",       48),
    ("Отпуск без з/п",              "за_свой",           44),
    ("Прогул",                      "прогул",            36),
    ("Выходной",                    "вых",               36),
    ("Текущий простой",             "текущий_простой",   40),
    ("Опоздания",                   "опозд",             44),
    ("Всего",                       "часы",              52),
    ("сверхурочные",                "сверхурочные",      50),
    ("ночные",                      "ночные",            46),
    ("праздничные",                 "праздничные",       50),
]

CODES = {
    'В': 'вых', 'О': 'отп', 'Б': 'бол', 'А': 'за_свой',
    'Р': 'отп_роды', 'Н': 'проч_неявки', 'П': 'прогул',
    'Т': 'текущий_простой', 'Ц': 'целосмен_простои', 'У': 'опозд',
}

# =========================================================================
# ИКОНКА
# =========================================================================
def icon_exists():
    return os.path.isfile(ICON_PATH)


def decorate_title(title):
    """Добавляет эмодзи в заголовок, если иконки нет."""
    if icon_exists():
        return title
    return f"{ICON_EMOJI} {title}"


def _apply_icon_windows(window_title):
    """Ставит иконку окна и панели задач на Windows через WinAPI."""
    if platform.system() != 'Windows':
        return
    if not icon_exists():
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32

        hwnd = user32.FindWindowW(None, window_title)
        if not hwnd:
            return

        IMAGE_ICON      = 1
        LR_LOADFROMFILE = 0x00000010
        LR_DEFAULTSIZE  = 0x00000040
        WM_SETICON      = 0x0080
        ICON_SMALL      = 0
        ICON_BIG        = 1

        hicon_big = user32.LoadImageW(
            0, ICON_PATH, IMAGE_ICON, 0, 0,
            LR_LOADFROMFILE | LR_DEFAULTSIZE)
        hicon_small = user32.LoadImageW(
            0, ICON_PATH, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

        if hicon_big:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
        if hicon_small:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
    except Exception as e:
        print("Не удалось установить иконку (WinAPI):", e)


def _apply_icon_kivy():
    if not icon_exists():
        return
    try:
        Window.set_icon(ICON_PATH)
    except Exception as e:
        print("Kivy не смог установить иконку:", e)


def apply_app_icon(window_title):
    _apply_icon_kivy()
    _apply_icon_windows(window_title)