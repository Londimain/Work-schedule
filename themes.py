# themes.py
# -*- coding: utf-8 -*-
"""Темы оформления приложения."""
import json as _json
import os
from config import LOCAL_FILE

_THEME_COLORS = {
    'standard': {
        'WEEKEND_BG': (1.00, 0.82, 0.82, 1), 'WEEKEND_FG': (0.55, 0.05, 0.05, 1),
        'HOLIDAY_BG': (1.00, 0.94, 0.70, 1), 'HOLIDAY_FG': (0.55, 0.35, 0.00, 1),
        'WORKDAY_BG': (1.00, 1.00, 1.00, 1), 'WORKDAY_FG': (0.05, 0.05, 0.05, 1),
        'HEADER_BG': (0.88, 0.88, 0.88, 1), 'HEADER_FG': (0.05, 0.05, 0.05, 1),
        'DEPT_BAR_BG': (0.20, 0.30, 0.55, 1), 'DEPT_BAR_FG': (1.00, 1.00, 1.00, 1),
        'VHEADER_BG': (0.85, 0.88, 0.92, 1), 'VHEADER_FG': (0.05, 0.05, 0.05, 1),
        'HEADER_DIVIDER': (0.00, 0.00, 0.00, 1),
        'SPINNER_BG': (0.20, 0.30, 0.55, 1), 'SPINNER_FG': (1.00, 1.00, 1.00, 1),
        'TOPBAR_BG': (0.11, 0.12, 0.15, 1), 'WINDOW_BG': (0.15, 0.15, 0.15, 1),
        'TABLE_BG': (0.15, 0.15, 0.15, 1), 'EXIT_BG': (0.20, 0.30, 0.55, 1),
        'TABLE_FG': (0.95, 0.95, 0.95, 1), 'SELECTED_ROW_BG': (0.22, 0.28, 0.38, 1),
    },
    'blue': {
        'WEEKEND_BG': (0.82, 0.88, 1.00, 1), 'WEEKEND_FG': (0.10, 0.20, 0.60, 1),
        'HOLIDAY_BG': (0.82, 0.92, 1.00, 1), 'HOLIDAY_FG': (0.10, 0.30, 0.60, 1),
        'WORKDAY_BG': (0.96, 0.98, 1.00, 1), 'WORKDAY_FG': (0.05, 0.10, 0.25, 1),
        'HEADER_BG': (0.78, 0.85, 0.96, 1), 'HEADER_FG': (0.05, 0.15, 0.40, 1),
        'DEPT_BAR_BG': (0.10, 0.25, 0.60, 1), 'DEPT_BAR_FG': (1.00, 1.00, 1.00, 1),
        'VHEADER_BG': (0.78, 0.85, 0.96, 1), 'VHEADER_FG': (0.05, 0.10, 0.30, 1),
        'HEADER_DIVIDER': (0.10, 0.20, 0.40, 1),
        'SPINNER_BG': (0.25, 0.55, 0.95, 1), 'SPINNER_FG': (1.00, 1.00, 1.00, 1),
        'TOPBAR_BG': (0.10, 0.15, 0.25, 1), 'WINDOW_BG': (0.08, 0.12, 0.20, 1),
        'TABLE_BG': (0.08, 0.12, 0.20, 1), 'EXIT_BG': (0.20, 0.45, 0.80, 1),
        'TABLE_FG': (0.95, 0.95, 0.95, 1), 'SELECTED_ROW_BG': (0.22, 0.28, 0.38, 1),
    },
    'green': {
        'WEEKEND_BG': (0.85, 1.00, 0.88, 1), 'WEEKEND_FG': (0.10, 0.45, 0.15, 1),
        'HOLIDAY_BG': (0.92, 1.00, 0.85, 1), 'HOLIDAY_FG': (0.25, 0.50, 0.10, 1),
        'WORKDAY_BG': (0.96, 1.00, 0.96, 1), 'WORKDAY_FG': (0.05, 0.20, 0.10, 1),
        'HEADER_BG': (0.82, 0.94, 0.85, 1), 'HEADER_FG': (0.05, 0.30, 0.15, 1),
        'DEPT_BAR_BG': (0.15, 0.45, 0.25, 1), 'DEPT_BAR_FG': (1.00, 1.00, 1.00, 1),
        'VHEADER_BG': (0.82, 0.94, 0.85, 1), 'VHEADER_FG': (0.05, 0.25, 0.10, 1),
        'HEADER_DIVIDER': (0.10, 0.30, 0.15, 1),
        'SPINNER_BG': (0.20, 0.65, 0.35, 1), 'SPINNER_FG': (1.00, 1.00, 1.00, 1),
        'TOPBAR_BG': (0.10, 0.20, 0.10, 1), 'WINDOW_BG': (0.08, 0.15, 0.08, 1),
        'TABLE_BG': (0.08, 0.15, 0.08, 1), 'EXIT_BG': (0.15, 0.55, 0.25, 1),
        'TABLE_FG': (0.95, 0.95, 0.95, 1), 'SELECTED_ROW_BG': (0.22, 0.28, 0.38, 1),
    },
    'warm': {
        'WEEKEND_BG': (1.00, 0.88, 0.80, 1), 'WEEKEND_FG': (0.55, 0.20, 0.05, 1),
        'HOLIDAY_BG': (1.00, 0.95, 0.75, 1), 'HOLIDAY_FG': (0.55, 0.30, 0.00, 1),
        'WORKDAY_BG': (1.00, 0.98, 0.94, 1), 'WORKDAY_FG': (0.20, 0.10, 0.05, 1),
        'HEADER_BG': (0.96, 0.88, 0.80, 1), 'HEADER_FG': (0.35, 0.15, 0.05, 1),
        'DEPT_BAR_BG': (0.55, 0.30, 0.15, 1), 'DEPT_BAR_FG': (1.00, 1.00, 1.00, 1),
        'VHEADER_BG': (0.96, 0.88, 0.80, 1), 'VHEADER_FG': (0.25, 0.10, 0.05, 1),
        'HEADER_DIVIDER': (0.30, 0.15, 0.05, 1),
        'SPINNER_BG': (0.85, 0.45, 0.15, 1), 'SPINNER_FG': (1.00, 1.00, 1.00, 1),
        'TOPBAR_BG': (0.25, 0.15, 0.10, 1), 'WINDOW_BG': (0.18, 0.10, 0.08, 1),
        'TABLE_BG': (0.18, 0.10, 0.08, 1), 'EXIT_BG': (0.70, 0.30, 0.10, 1),
        'TABLE_FG': (0.95, 0.95, 0.95, 1), 'SELECTED_ROW_BG': (0.22, 0.28, 0.38, 1),
    },
    'light': {
        'WEEKEND_BG': (0.95, 0.85, 0.85, 1), 'WEEKEND_FG': (0.60, 0.10, 0.10, 1),
        'HOLIDAY_BG': (0.95, 0.95, 0.75, 1), 'HOLIDAY_FG': (0.50, 0.40, 0.00, 1),
        'WORKDAY_BG': (1.00, 1.00, 1.00, 1), 'WORKDAY_FG': (0.10, 0.10, 0.10, 1),
        'HEADER_BG': (0.85, 0.85, 0.85, 1), 'HEADER_FG': (0.10, 0.10, 0.10, 1),
        'DEPT_BAR_BG': (0.30, 0.40, 0.60, 1), 'DEPT_BAR_FG': (1.00, 1.00, 1.00, 1),
        'VHEADER_BG': (0.85, 0.85, 0.85, 1), 'VHEADER_FG': (0.10, 0.10, 0.10, 1),
        'HEADER_DIVIDER': (0.50, 0.50, 0.50, 1),
        'SPINNER_BG': (0.40, 0.50, 0.70, 1), 'SPINNER_FG': (1.00, 1.00, 1.00, 1),
        'TOPBAR_BG': (0.35, 0.35, 0.35, 1), 'WINDOW_BG': (0.92, 0.92, 0.92, 1),
        'TABLE_BG': (0.92, 0.92, 0.92, 1), 'EXIT_BG': (0.45, 0.55, 0.70, 1),
        'TABLE_FG': (0.10, 0.10, 0.10, 1), 'SELECTED_ROW_BG': (0.22, 0.28, 0.38, 1),
    },
}

THEME_LABELS = {
    'standard': 'Стандартная',
    'blue':     'Синяя',
    'green':    'Зелёная',
    'warm':     'Тёплая',
    'light':    'Светлая',
}

CURRENT_THEME = 'standard'

def apply_theme(name):
    """Подменяет переменные цветов в модуле config значениями из палитры."""
    global CURRENT_THEME
    if name not in _THEME_COLORS:
        name = 'standard'
    CURRENT_THEME = name
    import config
    g = config.__dict__
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