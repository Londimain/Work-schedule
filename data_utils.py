# data_utils.py
# -*- coding: utf-8 -*-
"""Загрузка/сохранение данных и пересчёт итогов."""
import os
import json
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


def set_show_in_timesheet(emp_id, value):
    """Сохраняет галочку «В таблицу» только для этого компьютера."""
    if not emp_id:
        return
    local = load_local()
    local.setdefault('show_in_timesheet', {})[emp_id] = bool(value)
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
                data.setdefault('holiday_flags', {})
                data.setdefault('departments', list(DEFAULT_DEPARTMENTS))
                data.setdefault('organization', DEFAULT_ORG)
                data.setdefault('energetic_name', DEFAULT_ENERGETIC)
                data.setdefault('director_name', DEFAULT_DIRECTOR)
                data.setdefault('department_energetic', {})
                data.setdefault('signer_positions', ['Энергетик'])
                for emp in data['employees']:
                    emp.setdefault('department', '')
                    emp.setdefault('show_in_timesheet', False)
                    emp.setdefault('is_contract', True)   # <— ДОБАВИТЬ
                data = apply_local_overrides(data)
                data = apply_local_order(data)      # <— ДОБАВЛЕНО
                return data
        except Exception:
            pass
    data = {
        "employees": [], "timesheets": {},
        "positions": list(DEFAULT_POSITIONS),
        "night_flags": {},
        "overtime_flags": {},
        "holiday_flags": {},
        "departments": list(DEFAULT_DEPARTMENTS),
        "organization": DEFAULT_ORG,
        "energetic_name": DEFAULT_ENERGETIC,
        "department_energetic": {},
        "signer_positions": ['Энергетик'],
        "director_name": DEFAULT_DIRECTOR,
    }
    data = apply_local_overrides(data)
    data = apply_local_order(data)                  # <— ДОБАВЛЕНО
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

def analyze_row(values, day_types, night_enabled=False):
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
            
            # Если ввели часы в выходной или праздник — суммируем в праздничные
            if dt in ('weekend', 'holiday'):
                res['праздничные'] += h

            # В любом случае (и в будни, и в выходные) это явка и отработанные часы
            res['явки'] += 1
            res['часы'] += h
            
            if night_enabled:
                res['ночные'] += calc_night_hours(h)
    return res

def apply_overtime(res, norm_hours):
    # Часы, отработанные в выходные и праздники, оплачиваются отдельно 
    # (как минимум в двойном размере). Поэтому они НЕ должны участвовать 
    # в расчёте сверхурочных, чтобы не было двойной оплаты.
    
    # Получаем "чистые" часы, отработанные только в рабочие дни:
    work_hours = res.get('часы', 0.0) - res.get('праздничные', 0.0)
    
    over = work_hours - norm_hours
    res['сверхурочные'] = over if over > 0 else 0.0
    return res


def fmt_hours(h):
    if h == int(h):
        return str(int(h))
    return f"{h:.2f}".rstrip('0').rstrip('.')