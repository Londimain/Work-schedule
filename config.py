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
Config.set('graphics', 'window_state', 'maximized')
Config.set('kivy', 'keyboard_mode', 'system')
Config.set('kivy', 'scroll_timeout', '250')
Config.set('kivy', 'scroll_distance', '20')

from kivy.core.text import LabelBase
from kivy.core.window import Window

# =========================================================================
# ВЕРСИЯ
# =========================================================================
APP_VERSION = "1.0.0"

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
# Размер окна не задаём — он управляется строкой
# Config.set('graphics', 'window_state', 'maximized') выше.
# Если здесь написать Window.size, Kivy применит его уже после создания
# окна и отменит максимизацию.

# =========================================================================
# ПУТИ
# =========================================================================
def _data_dir():
    """Папка для tabel_data.json — рядом с .exe (frozen) или с .py (скрипт)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _assets_dir():
    """Папка с ресурсами: временная у PyInstaller, обычная у скрипта."""
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        return meipass
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _data_dir()
DATA_FILE = os.path.join(BASE_DIR, "tabel_data.json")

# Иконку ищем сначала внутри ресурсов PyInstaller, потом рядом с программой.
_icon_candidates = [
    os.path.join(_assets_dir(), "ico", "tabel.ico"),
    os.path.join(BASE_DIR, "ico", "tabel.ico"),
]
ICON_PATH = next(
    (p for p in _icon_candidates if os.path.isfile(p)),
    _icon_candidates[0],
)
ICON_EMOJI = "[T]"      # ASCII-маркер в заголовке, если нет ico/tabel.ico

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
DEFAULT_ENERGETIC = "Борщенков С.В."
DEFAULT_DIRECTOR = "Авчинников С. А."
DELETE_PASSWORD = "admins"      # пароль для подтверждения удаления

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
    ("Целосмен. простой",           "целосмен_простой",  40),
    ("Трудовой отпуск",             "отп",               40),
    ("Отп. по родам",               "отп_роды",          44),
    ("Болезнь",                     "бол",               36),
    ("Прочие неявки",               "проч_неявки",       48),
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
    'Т': 'текущий_простой', 'Ц': 'целосмен_простой', 'У': 'опозд',
    'ДМ': 'проч_неявки',
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
    
# =========================================================================
# ЛОКАЛЬНЫЕ (PER-MACHINE) НАСТРОЙКИ
# =========================================================================
def _local_dir():
    """Папка для локальных настроек этого компьютера.
    Лежит вне папки программы, поэтому не попадает в общую синхронизацию."""
    if platform.system() == 'Windows':
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
    else:
        base = (os.environ.get('XDG_CONFIG_HOME')
                or os.path.expanduser('~/.config'))
    d = os.path.join(base, 'TabelApp')
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d

LOCAL_DIR = _local_dir()
LOCAL_FILE = os.path.join(LOCAL_DIR, 'local.json')

# =========================================================================
# ТЕМЫ ОФОРМЛЕНИЯ
# =========================================================================
import json as _json

_THEME_COLORS = {
    'standard': {
        'WEEKEND_BG':     (1.00, 0.82, 0.82, 1),
        'WEEKEND_FG':     (0.55, 0.05, 0.05, 1),
        'HOLIDAY_BG':     (1.00, 0.94, 0.70, 1),
        'HOLIDAY_FG':     (0.55, 0.35, 0.00, 1),
        'WORKDAY_BG':     (1.00, 1.00, 1.00, 1),
        'WORKDAY_FG':     (0.05, 0.05, 0.05, 1),
        'HEADER_BG':      (0.88, 0.88, 0.88, 1),
        'HEADER_FG':      (0.05, 0.05, 0.05, 1),
        'DEPT_BAR_BG':    (0.20, 0.30, 0.55, 1),
        'DEPT_BAR_FG':    (1.00, 1.00, 1.00, 1),
        'VHEADER_BG':     (0.85, 0.88, 0.92, 1),
        'VHEADER_FG':     (0.05, 0.05, 0.05, 1),
        'HEADER_DIVIDER': (0.00, 0.00, 0.00, 1),
        'SPINNER_BG':     (0.20, 0.30, 0.55, 1),
        'SPINNER_FG':     (1.00, 1.00, 1.00, 1),
        'TOPBAR_BG':      (0.11, 0.12, 0.15, 1),
        'WINDOW_BG':      (0.15, 0.15, 0.15, 1), # Темный фон окна
        'TABLE_BG':       (0.15, 0.15, 0.15, 1), # Темный фон таблиц
        'EXIT_BG':        (0.20, 0.30, 0.55, 1),
        'TABLE_FG':       (0.95, 0.95, 0.95, 1), # Белый текст
    },
    'blue': {
        'WEEKEND_BG':     (0.82, 0.88, 1.00, 1),
        'WEEKEND_FG':     (0.10, 0.20, 0.60, 1),
        'HOLIDAY_BG':     (0.82, 0.92, 1.00, 1),
        'HOLIDAY_FG':     (0.10, 0.30, 0.60, 1),
        'WORKDAY_BG':     (0.96, 0.98, 1.00, 1),
        'WORKDAY_FG':     (0.05, 0.10, 0.25, 1),
        'HEADER_BG':      (0.78, 0.85, 0.96, 1),
        'HEADER_FG':      (0.05, 0.15, 0.40, 1),
        'DEPT_BAR_BG':    (0.10, 0.25, 0.60, 1),
        'DEPT_BAR_FG':    (1.00, 1.00, 1.00, 1),
        'VHEADER_BG':     (0.78, 0.85, 0.96, 1),
        'VHEADER_FG':     (0.05, 0.10, 0.30, 1),
        'HEADER_DIVIDER': (0.10, 0.20, 0.40, 1),
        'SPINNER_BG':     (0.15, 0.30, 0.60, 1),
        'SPINNER_FG':     (1.00, 1.00, 1.00, 1),
        'TOPBAR_BG':      (0.10, 0.15, 0.25, 1),
        'WINDOW_BG':      (0.08, 0.12, 0.20, 1), # Темно-синий
        'TABLE_BG':       (0.08, 0.12, 0.20, 1),
        'EXIT_BG':        (0.15, 0.25, 0.50, 1),
        'TABLE_FG':       (0.95, 0.95, 0.95, 1), # Белый текст
    },
    'green': {
        'WEEKEND_BG':     (0.85, 1.00, 0.88, 1),
        'WEEKEND_FG':     (0.10, 0.45, 0.15, 1),
        'HOLIDAY_BG':     (0.92, 1.00, 0.85, 1),
        'HOLIDAY_FG':     (0.25, 0.50, 0.10, 1),
        'WORKDAY_BG':     (0.96, 1.00, 0.96, 1),
        'WORKDAY_FG':     (0.05, 0.20, 0.10, 1),
        'HEADER_BG':      (0.82, 0.94, 0.85, 1),
        'HEADER_FG':      (0.05, 0.30, 0.15, 1),
        'DEPT_BAR_BG':    (0.15, 0.45, 0.25, 1),
        'DEPT_BAR_FG':    (1.00, 1.00, 1.00, 1),
        'VHEADER_BG':     (0.82, 0.94, 0.85, 1),
        'VHEADER_FG':     (0.05, 0.25, 0.10, 1),
        'HEADER_DIVIDER': (0.10, 0.30, 0.15, 1),
        'SPINNER_BG':     (0.20, 0.45, 0.25, 1),
        'SPINNER_FG':     (1.00, 1.00, 1.00, 1),
        'TOPBAR_BG':      (0.10, 0.20, 0.10, 1),
        'WINDOW_BG':      (0.08, 0.15, 0.08, 1), # Темно-зеленый
        'TABLE_BG':       (0.08, 0.15, 0.08, 1),
        'EXIT_BG':        (0.15, 0.45, 0.25, 1),
        'TABLE_FG':       (0.95, 0.95, 0.95, 1), # Белый текст
    },
    'warm': {
        'WEEKEND_BG':     (1.00, 0.88, 0.80, 1),
        'WEEKEND_FG':     (0.55, 0.20, 0.05, 1),
        'HOLIDAY_BG':     (1.00, 0.95, 0.75, 1),
        'HOLIDAY_FG':     (0.55, 0.30, 0.00, 1),
        'WORKDAY_BG':     (1.00, 0.98, 0.94, 1),
        'WORKDAY_FG':     (0.20, 0.10, 0.05, 1),
        'HEADER_BG':      (0.96, 0.88, 0.80, 1),
        'HEADER_FG':      (0.35, 0.15, 0.05, 1),
        'DEPT_BAR_BG':    (0.55, 0.30, 0.15, 1),
        'DEPT_BAR_FG':    (1.00, 1.00, 1.00, 1),
        'VHEADER_BG':     (0.96, 0.88, 0.80, 1),
        'VHEADER_FG':     (0.25, 0.10, 0.05, 1),
        'HEADER_DIVIDER': (0.30, 0.15, 0.05, 1),
        'SPINNER_BG':     (0.55, 0.30, 0.15, 1),
        'SPINNER_FG':     (1.00, 1.00, 1.00, 1),
        'TOPBAR_BG':      (0.25, 0.15, 0.10, 1),
        'WINDOW_BG':      (0.18, 0.10, 0.08, 1), # Темно-коричневый
        'TABLE_BG':       (0.18, 0.10, 0.08, 1),
        'EXIT_BG':        (0.50, 0.25, 0.15, 1),
        'TABLE_FG':       (0.95, 0.95, 0.95, 1), # Белый текст
    },
    'light': {
        'WEEKEND_BG':     (0.95, 0.85, 0.85, 1),
        'WEEKEND_FG':     (0.60, 0.10, 0.10, 1),
        'HOLIDAY_BG':     (0.95, 0.95, 0.75, 1),
        'HOLIDAY_FG':     (0.50, 0.40, 0.00, 1),
        'WORKDAY_BG':     (1.00, 1.00, 1.00, 1),
        'WORKDAY_FG':     (0.10, 0.10, 0.10, 1),
        'HEADER_BG':      (0.85, 0.85, 0.85, 1),
        'HEADER_FG':      (0.10, 0.10, 0.10, 1),
        'DEPT_BAR_BG':    (0.30, 0.40, 0.60, 1),
        'DEPT_BAR_FG':    (1.00, 1.00, 1.00, 1),
        'VHEADER_BG':     (0.85, 0.85, 0.85, 1),
        'VHEADER_FG':     (0.10, 0.10, 0.10, 1),
        'HEADER_DIVIDER': (0.50, 0.50, 0.50, 1),
        'SPINNER_BG':     (0.40, 0.50, 0.70, 1),
        'SPINNER_FG':     (1.00, 1.00, 1.00, 1),
        'TOPBAR_BG':      (0.35, 0.35, 0.35, 1),
        'WINDOW_BG':      (0.92, 0.92, 0.92, 1),
        'TABLE_BG':       (0.92, 0.92, 0.92, 1),
        'EXIT_BG':        (0.45, 0.55, 0.70, 1),
        'TABLE_FG':       (0.10, 0.10, 0.10, 1), # Белый текст
    },
}

THEME_LABELS = {
    'standard': 'Стандартная',
    'blue':     'Синяя',
    'green':    'Зелёная',
    'warm':     'Тёплая',
    'light':    'Светлая', # <--- ДОБАВИТЬ
}

CURRENT_THEME = 'standard'


def apply_theme(name):
    """Подменяет переменные цветов в модуле config значениями из палитры."""
    global CURRENT_THEME
    if name not in _THEME_COLORS:
        name = 'standard'
    CURRENT_THEME = name
    g = globals()
    for k, v in _THEME_COLORS[name].items():
        g[k] = v


def _load_saved_theme():
    try:
        if os.path.exists(LOCAL_FILE):
            with open(LOCAL_FILE, 'r', encoding='utf-8') as f:
                d = _json.load(f)
            return d.get('theme', 'standard')
    except Exception:
        pass
    return 'standard'


apply_theme(_load_saved_theme())