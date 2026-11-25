# data_calc.py
# -*- coding: utf-8 -*-
"""Расчеты табеля."""
import math
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

def analyze_row(values, day_types, night_enabled=False, no_weekends=False,
                highlighted_days=None, *args, **kwargs):
    res = {key: 0 for _, key, _ in RIGHT_COLUMNS}
    res['часы'] = 0.0
    res['сверхурочные'] = 0.0
    res['ночные'] = 0.0
    res['праздничные'] = 0.0
    res['выходные_часы'] = 0.0
    res['_выходные_часы'] = 0.0

    hl = set(highlighted_days or ())
    hl_int_sum = 0      # Сумма целых частей выделенных ячеек
    hl_frac_sum = 0.0   # Сумма дробных частей выделенных ячеек

    for i, v in enumerate(values):
        if v is None or str(v).strip() == '':
            continue
        s = str(v).strip().upper()

        if s in CODES:
            res[CODES[s]] += 1
            continue

        has_day_suffix = s.endswith('Д') and len(s) > 1
        if has_day_suffix:
            s = s[:-1].strip()

        # Пометка ячейки (1-based индекс)
        is_highlighted = (i + 1) in hl

        # Пометка ячейки = принудительная 2-я смена (если не указана явно)
        is_forced_shift2 = is_highlighted and not has_day_suffix and '/' not in s

        shift = None
        s_hours = s
        sep = None

        if is_forced_shift2:
            shift = 2
        else:
            if '//' in s:
                sep = '//'
            elif '/' in s:
                sep = '/'

            if sep:
                parts = s.split(sep, 1)
                s_hours = parts[0].strip()
                if len(parts) > 1:
                    try:
                        shift = int(parts[1].strip())
                    except (ValueError, IndexError):
                        shift = None

        try:
            h = float(s_hours.replace(',', '.'))
        except ValueError:
            continue

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
            h_int = int(round(h))
            frac = h - int(h)
            
            if is_highlighted:
                # НОВАЯ ЛОГИКА ДЛЯ ВЫДЕЛЕННЫХ ЯЧЕЕК
                if 8 <= h <= 15:
                    base_val = h - 6.8
                elif h >= 16:
                    base_val = 8.2
                else:
                    base_val = 0.0

                # Защита от ошибок округления float (например, 1.2000000001)
                base_val = round(base_val, 2)
                
                # Раскладываем на целую и дробную части
                hl_int_sum += int(base_val)
                hl_frac_sum += base_val - int(base_val)
            else:
                # СТАРАЯ ЛОГИКА ДЛЯ ОБЫЧНЫХ ЯЧЕЕК
                if shift == 1:
                    night_h = 0.0
                elif shift == 2:
                    if h_int <= 7:
                        night_h = 0.0
                    elif h_int == 8:
                        night_h = 1.0 + frac
                    elif 9 <= h_int <= 16:
                        night_h = 2.0 + frac
                    else:
                        night_h = 0.0
                else:
                    # Без смены
                    if night_enabled and h != 8.0:
                        nh = float(calc_night_hours(h))
                        if nh > 0 and frac > 0:
                            nh += frac
                        night_h = nh
                    else:
                        night_h = 0.0
                
                res['ночные'] += night_h

    # Применяем накопленные суммы для выделенных ячеек
    if hl_frac_sum > 0 or hl_int_sum > 0:
        # Округляем сумму дробных частей до 2 знаков, чтобы убрать ошибки float (0.599999 -> 0.6)
        hl_frac_sum = round(hl_frac_sum, 2)
        
        # Считаем, сколько целых часов даст сумма дробных частей (каждые 0.6 = +1)
        carry = int(hl_frac_sum / 0.6)
        # Остаток дробной части
        remainder = round(hl_frac_sum % 0.6, 2)
        
        res['ночные'] += hl_int_sum + carry + remainder

    # Округляем итоговый результат до 1 знака после запятой для красоты
    res['ночные'] = round(res['ночные'], 1)

    return res

def apply_overtime(res, norm_hours):
    weekend_h = res.get('_выходные_часы', 0.0)
    work_hours = res.get('часы', 0.0) - res.get('праздничные', 0.0) - weekend_h
    over = work_hours - norm_hours
    res['сверхурочные'] = over if over > 0 else 0.0
    return res

def fmt_hours(h):
    """Безопасное форматирование часов (защита от строк и None)."""
    try:
        if isinstance(h, str):
            h = float(h.replace(',', '.').strip())
        if h == int(h):
            return str(int(h))
        return f"{h:.2f}".rstrip('0').rstrip('.')
    except Exception:
        return str(h) if h is not None else ''