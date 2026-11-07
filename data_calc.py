# data_calc.py
# -*- coding: utf-8 -*-
"""Расчеты табеля."""
from calendar import monthrange
from datetime import date
from config import RIGHT_COLUMNS, CODES, HOLIDAYS

def classify_day(y, m, d):
    if (m, d) in HOLIDAYS:
        return 'holiday'
    if date(y, m, d).weekday() >= 5:
        return 'weekend'
    return 'work'

def get_pre_holiday_days(y, m):
    days_in_month = monthrange(y, m)[1]
    result = []
    for d in range(1, days_in_month + 1):
        if classify_day(y, m, d) != 'work':
            continue
        if d < days_in_month:
            ny, nm, nd = y, m, d + 1
        elif m == 12:
            ny, nm, nd = y + 1, 1, 1
        else:
            ny, nm, nd = y, m + 1, 1
        if (nm, nd) in HOLIDAYS:
            result.append(d)
    return result

def calc_norm_hours(y, m):
    days_in_month = monthrange(y, m)[1]
    work_days = sum(1 for d in range(1, days_in_month + 1)
                    if classify_day(y, m, d) == 'work')
    pre_days = get_pre_holiday_days(y, m)
    norm = work_days * 8.0 - len(pre_days)
    return norm, work_days, len(pre_days)

def calc_night_hours(h):
    try:
        n = int(round(h))
    except Exception:
        return 0
    if n == 4: return 1
    if n == 5: return 2
    if n == 6: return 3
    if 7 <= n <= 11: return 6
    return 0

def analyze_row(values, day_types, night_enabled=False, no_weekends=False, *args, **kwargs):
    res = {key: 0 for _, key, _ in RIGHT_COLUMNS}
    res['часы'] = 0.0
    res['сверхурочные'] = 0.0
    res['ночные'] = 0.0
    res['праздничные'] = 0.0
    res['выходные_часы'] = 0.0
    res['_выходные_часы'] = 0.0

    for i, v in enumerate(values):
        if v is None or str(v).strip() == '': continue
        s = str(v).strip().upper()

        if s in CODES:
            res[CODES[s]] += 1
            continue

        has_day_suffix = s.endswith('Д') and len(s) > 1
        if has_day_suffix: s = s[:-1].strip()

        shift = None
        s_hours = s
        sep = None
        if '//' in s: sep = '//'
        elif '/' in s: sep = '/'
        
        if sep:
            parts = s.split(sep, 1)
            s_hours = parts[0].strip()
            if len(parts) > 1:
                try: shift = int(parts[1].strip())
                except (ValueError, IndexError): shift = None

        try: h = float(s_hours.replace(',', '.'))
        except ValueError: continue

        dt = day_types[i] if i < len(day_types) else 'work'
        if dt == 'holiday':
            res['праздничные'] += h
        elif dt == 'weekend':
            if not no_weekends:
                res['_выходные_часы'] += h
                res['выходные_часы'] += h
            
        res['явки'] += 1
        res['часы'] += h

        if not has_day_suffix:
            if shift is not None:
                if shift == 1: night_h = 0
                elif shift == 2:
                    if   h == 8:  night_h = 1
                    elif h == 9:  night_h = 2
                    elif h == 10: night_h = 3
                    elif h == 11: night_h = 4
                    elif h == 12: night_h = 8
                    elif h == 13: night_h = 8
                    elif h == 14: night_h = 8
                    elif h == 15: night_h = 8
                    else:         night_h = calc_night_hours(h)
                else: night_h = calc_night_hours(h)
                res['ночные'] += night_h
            else:
                if night_enabled and h != 8.0:
                    res['ночные'] += calc_night_hours(h)
    return res

def apply_overtime(res, norm_hours):
    weekend_h = res.get('_выходные_часы', 0.0)
    work_hours = res.get('часы', 0.0) - res.get('праздничные', 0.0) - weekend_h
    over = work_hours - norm_hours
    res['сверхурочные'] = over if over > 0 else 0.0
    return res

def fmt_hours(h):
    if h == int(h): return str(int(h))
    return f"{h:.2f}".rstrip('0').rstrip('.')