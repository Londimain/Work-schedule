# data_utils.py
# -*- coding: utf-8 -*-
"""Загрузка/сохранение данных и пересчёт итогов."""
import os
import json
from datetime import date

from config import (DATA_FILE, RIGHT_COLUMNS, CODES,
                    DEFAULT_POSITIONS, DEFAULT_DEPARTMENTS,
                    DEFAULT_ORG, HOLIDAYS,
                    DEFAULT_ENERGETIC, DEFAULT_DIRECTOR)
_LAST_MTIME = 0.0


def get_last_mtime():
    return _LAST_MTIME


def set_last_mtime(value):
    global _LAST_MTIME
    _LAST_MTIME = value


# ---------------------------------------------------------------------------
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data.setdefault('employees', [])
                data.setdefault('timesheets', {})
                data.setdefault('positions', list(DEFAULT_POSITIONS))
                data.setdefault('night_flags', {})
                data.setdefault('overtime_flags', {})
                data.setdefault('holiday_flags', {})
                data.setdefault('departments', list(DEFAULT_DEPARTMENTS))
                data.setdefault('organization', DEFAULT_ORG)
                data.setdefault('energetic_name', DEFAULT_ENERGETIC)
                data.setdefault('director_name', DEFAULT_DIRECTOR)
                for emp in data['employees']:
                    emp.setdefault('department', '')
                    emp.setdefault('show_in_timesheet', True)
                return data
        except Exception:
            pass
    return {"employees": [], "timesheets": {},
            "positions": list(DEFAULT_POSITIONS),
            "night_flags": {},
            "overtime_flags": {},
            "holiday_flags": {},
            "departments": list(DEFAULT_DEPARTMENTS),
            "organization": DEFAULT_ORG,
            "energetic_name": DEFAULT_ENERGETIC,
            "director_name": DEFAULT_DIRECTOR}

def save_data(data):
    global _LAST_MTIME
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        try:
            _LAST_MTIME = os.path.getmtime(DATA_FILE)
        except Exception:
            pass
    except Exception as e:
        print("Ошибка сохранения:", e)


def classify_day(y, m, d):
    if (m, d) in HOLIDAYS:
        return 'holiday'
    if date(y, m, d).weekday() >= 5:
        return 'weekend'
    return 'work'


def calc_night_hours(h):
    try:
        n = int(round(h))
    except Exception:
        return 0
    if n == 4:
        return 1
    if n == 5:
        return 2
    if n == 6:
        return 3
    if 7 <= n <= 11:
        return 6
    return 0


def analyze_row(values, day_types, night_enabled=False, holiday_enabled=False):
    res = {key: 0 for _, key, _ in RIGHT_COLUMNS}
    res['часы'] = 0.0
    res['сверхурочные'] = 0.0
    res['ночные'] = 0.0
    res['праздничные'] = 0.0

    for i, v in enumerate(values):
        if v is None or str(v).strip() == '':
            continue
        s = str(v).strip().upper()
        if s in CODES:
            res[CODES[s]] += 1
        else:
            try:
                h = float(s.replace(',', '.'))
            except ValueError:
                continue
            dt = day_types[i] if i < len(day_types) else 'work'
            if dt in ('weekend', 'holiday') and holiday_enabled:
                res['праздничные'] += h
            else:
                res['явки'] += 1
                res['часы'] += h
                if night_enabled:
                    res['ночные'] += calc_night_hours(h)
    return res


def apply_overtime(res, norm_hours):
    over = res.get('часы', 0.0) - norm_hours
    res['сверхурочные'] = over if over > 0 else 0.0
    return res


def fmt_hours(h):
    if h == int(h):
        return str(int(h))
    return f"{h:.2f}".rstrip('0').rstrip('.')