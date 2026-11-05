# data_utils.py
# -*- coding: utf-8 -*-
"""Загрузка/сохранение данных и пересчёт итогов."""
import os
import json
from calendar import monthrange
from datetime import date

from config import (DATA_FILE, RIGHT_COLUMNS, CODES,
                    DEFAULT_POSITIONS, DEFAULT_DEPARTMENTS,
                    DEFAULT_ORG, HOLIDAYS,
                    DEFAULT_ENERGETIC, DEFAULT_DIRECTOR,
                    LOCAL_FILE)

_LAST_MTIME = 0.0


def get_last_mtime():
    return _LAST_MTIME


def set_last_mtime(value):
    global _LAST_MTIME
    _LAST_MTIME = value


# ---------------------------------------------------------------------------
# ЛОКАЛЬНЫЕ (PER-MACHINE) НАСТРОЙКИ
# ---------------------------------------------------------------------------
def load_local():
    if os.path.exists(LOCAL_FILE):
        try:
            with open(LOCAL_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"show_in_timesheet": {}}


def save_local(local):
    try:
        d = os.path.dirname(LOCAL_FILE)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(LOCAL_FILE, 'w', encoding='utf-8') as f:
            json.dump(local, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Ошибка сохранения локальных настроек:", e)

def set_local_show_legend(value):
    """Сохраняет выбор отображения условных обозначений для этого компьютера."""
    local = load_local()
    local['show_legend'] = bool(value)
    save_local(local)

def get_local_show_legend():
    """Возвращает сохранённый выбор отображения условных обозначений."""
    local = load_local()
    return bool(local.get('show_legend', False))

def set_local_results_hidden(value):
    """Сохраняет состояние видимости итогов для этого компьютера."""
    local = load_local()
    local['results_hidden'] = bool(value)
    save_local(local)

def get_local_results_hidden():
    """Возвращает сохраненное состояние видимости итогов."""
    local = load_local()
    return bool(local.get('results_hidden', False))

def set_show_in_timesheet(emp_id, value):
    """Сохраняет галочку «В таблицу» только для этого компьютера."""
    if not emp_id:
        return
    local = load_local()
    local.setdefault('show_in_timesheet', {})[emp_id] = bool(value)
    save_local(local)

def set_theme(theme_name):
    """Сохраняет выбранную тему оформления для этого компьютера."""
    local = load_local()
    local['theme'] = theme_name
    save_local(local)

def save_local_order(departments, employees):
    """Сохраняет локальный порядок отделов и сотрудников.

    departments — список имён отделов в нужном порядке;
    employees   — список dict-ов сотрудников в нужном порядке.
    Хранятся только идентификаторы, чтобы остальные данные
    всегда брались из общего файла."""
    local = load_local()
    local['departments_order'] = list(departments or [])
    local['employees_order'] = [
        e.get('id') for e in (employees or []) if e.get('id')
    ]
    save_local(local)

def get_local_collapsed_depts():
    """Возвращает список свернутых отделов для этого компьютера."""
    local = load_local()
    return local.get('collapsed_depts', [])

def save_local_collapsed_depts(depts):
    """Сохраняет список свернутых отделов для этого компьютера."""
    local = load_local()
    local['collapsed_depts'] = list(depts)
    save_local(local)
    
def apply_local_overrides(data):
    """Накладывает локальный выбор «В таблицу» поверх общих данных."""
    first_run = not os.path.exists(LOCAL_FILE)
    local = load_local()
    sel = local.setdefault('show_in_timesheet', {})

    if first_run:
        save_local(local)

    for emp in data.get('employees', []):
        emp_id = emp.get('id')
        if not emp_id:
            emp['show_in_timesheet'] = False
            continue
        emp['show_in_timesheet'] = bool(sel.get(emp_id, False))
    return data


def apply_local_order(data):
    """Переупорядочивает отделы и сотрудников согласно local.json.

    Если в local.json ещё нет ключей departments_order / employees_order
    (первый запуск или апгрейд старой версии), они инициализируются
    текущим порядком из общего файла — так пользователь увидит
    привычную раскладку.

    Новые отделы/сотрудники, которых нет в локальном файле, идут в конец."""
    local = load_local()
    changed = False

    # --- порядок отделов ---
    dept_order = local.get('departments_order')
    if dept_order:
        current = list(data.get('departments', []))
        known = [d for d in dept_order if d in current]
        unknown = [d for d in current if d not in dept_order]
        data['departments'] = known + unknown
    else:
        local['departments_order'] = list(data.get('departments', []))
        changed = True

    # --- порядок сотрудников (по id) ---
    emp_order = local.get('employees_order')
    current_emps = list(data.get('employees', []))
    if emp_order:
        by_id = {}
        for e in current_emps:
            eid = e.get('id')
            if eid:
                by_id[eid] = e
        new_list = []
        for eid in emp_order:
            if eid in by_id:
                new_list.append(by_id.pop(eid))
        # Оставшиеся (новые сотрудники или без id) — в конец.
        for e in current_emps:
            eid = e.get('id')
            if eid and eid in by_id:
                new_list.append(by_id.pop(eid))
            elif not eid:
                new_list.append(e)
        data['employees'] = new_list
    else:
        local['employees_order'] = [
            e.get('id') for e in current_emps if e.get('id')
        ]
        changed = True

    if changed:
        save_local(local)

    return data


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
                data.setdefault('no_weekends_flags', {})
                data.setdefault('departments', list(DEFAULT_DEPARTMENTS))
                data.setdefault('organization', DEFAULT_ORG)
                data.setdefault('energetic_name', DEFAULT_ENERGETIC)
                data.setdefault('director_name', DEFAULT_DIRECTOR)
                data.setdefault('department_energetic', {})
                data.setdefault('signer_positions', ['Энергетик'])
                data.setdefault('extra_employees', {})
                for emp in data['employees']:
                    emp.setdefault('department', '')
                    emp.setdefault('show_in_timesheet', False)
                    emp.setdefault('is_contract', True)
                data = apply_local_overrides(data)
                data = apply_local_order(data)
                return data
        except Exception:
            pass
    data = {
        "employees": [], "timesheets": {},
        "positions": list(DEFAULT_POSITIONS),
        "night_flags": {},
        "overtime_flags": {},
        "no_weekends_flags": {},
        "departments": list(DEFAULT_DEPARTMENTS),
        "organization": DEFAULT_ORG,
        "energetic_name": DEFAULT_ENERGETIC,
        "department_energetic": {},
        "signer_positions": ['Энергетик'],
        "director_name": DEFAULT_DIRECTOR,
        "extra_employees": {},
    }
    data = apply_local_overrides(data)
    data = apply_local_order(data)
    return data


def save_data(data):
    global _LAST_MTIME
    # Поле show_in_timesheet — локальное, не пишем его в общий файл.
    popped = []
    for emp in data.get('employees', []):
        if 'show_in_timesheet' in emp:
            popped.append((emp, emp.pop('show_in_timesheet')))
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        try:
            _LAST_MTIME = os.path.getmtime(DATA_FILE)
        except Exception:
            pass
    except Exception as e:
        print("Ошибка сохранения:", e)
    finally:
        for emp, val in popped:
            emp['show_in_timesheet'] = val


def classify_day(y, m, d):
    if (m, d) in HOLIDAYS:
        return 'holiday'
    if date(y, m, d).weekday() >= 5:
        return 'weekend'
    return 'work'

def get_pre_holiday_days(y, m):
    """Возвращает список чисел месяца, которые являются предпраздничными
    рабочими днями (рабочий день непосредственно перед праздником).

    Каждый такой день сокращает норму месяца на 1 час.
    Например, если 8 марта — праздник, а 7 марта — рабочий день,
    то 7 марта попадёт в этот список.
    """
    days_in_month = monthrange(y, m)[1]
    result = []
    for d in range(1, days_in_month + 1):
        if classify_day(y, m, d) != 'work':
            continue
        # Следующий календарный день (с переходом через границу месяца/года)
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
    """Норма рабочего времени за месяц с учётом предпраздничных дней.

    Возвращает (norm_hours, work_days, pre_holiday_count):
      norm_hours       — итоговая норма (work_days * 8 − pre_holiday_count);
      work_days        — количество обычных рабочих дней;
      pre_holiday_count — количество предпраздничных рабочих дней.

    Праздничные дни в норму не входят вообще.
    """
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
    if n == 4:
        return 1
    if n == 5:
        return 2
    if n == 6:
        return 3
    if 7 <= n <= 11:
        return 6
    return 0

def analyze_row(values, day_types, night_enabled=False,
                no_weekends=False, *args, **kwargs):
    res = {key: 0 for _, key, _ in RIGHT_COLUMNS}
    res['часы'] = 0.0
    res['сверхурочные'] = 0.0
    res['ночные'] = 0.0
    res['праздничные'] = 0.0
    res['выходные_часы'] = 0.0
    res['_выходные_часы'] = 0.0

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

        shift = None
        s_hours = s
        sep = None
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

# data_utils.py (фрагмент функции analyze_row)
        dt = day_types[i] if i < len(day_types) else 'work'
        # Только реальные праздники дают часы в колонку «праздничные».
        if dt == 'holiday':
            res['праздничные'] += h
        elif dt == 'weekend':
            if not no_weekends:
                res['_выходные_часы'] += h   # исключаем из сверхурочных
                res['выходные_часы'] += h    # Для отображения в колонке
            
        res['явки'] += 1
        res['часы'] += h

        if not has_day_suffix:
            if shift is not None:
                if shift == 1:
                    night_h = 0
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
                else:
                    night_h = calc_night_hours(h)
                res['ночные'] += night_h
            else:
                if night_enabled and h != 8.0:
                    res['ночные'] += calc_night_hours(h)

    return res

def apply_overtime(res, norm_hours):
    # Часы, отработанные в выходные и праздники, оплачиваются отдельно
    # (как минимум в двойном размере). Поэтому они НЕ должны участвовать
    # в расчёте сверхурочных, чтобы не было двойной оплаты.
    weekend_h = res.get('_выходные_часы', 0.0)
    work_hours = res.get('часы', 0.0) - res.get('праздничные', 0.0) - weekend_h
    over = work_hours - norm_hours
    res['сверхурочные'] = over if over > 0 else 0.0
    return res


def fmt_hours(h):
    if h == int(h):
        return str(int(h))
    return f"{h:.2f}".rstrip('0').rstrip('.')