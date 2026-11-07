# data_storage.py
# -*- coding: utf-8 -*-
"""Сохранение и загрузка данных."""
import os
import json
# Измените импорт в начале файла:
from config import (DATA_FILE, LOCAL_FILE, DEFAULT_POSITIONS,
                    DEFAULT_DEPARTMENTS, DEFAULT_ORG, DEFAULT_ENERGETIC,
                    DEFAULT_DIRECTOR, RIGHT_COLUMNS)

_LAST_MTIME = 0.0

def get_last_mtime(): return _LAST_MTIME
def set_last_mtime(value):
    global _LAST_MTIME
    _LAST_MTIME = value

def load_local():
    if os.path.exists(LOCAL_FILE):
        try:
            with open(LOCAL_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception: pass
    return {"show_in_timesheet": {}}

def save_local(local):
    try:
        d = os.path.dirname(LOCAL_FILE)
        if d: os.makedirs(d, exist_ok=True)
        with open(LOCAL_FILE, 'w', encoding='utf-8') as f:
            json.dump(local, f, ensure_ascii=False, indent=2)
    except Exception as e: print("Ошибка сохранения локальных настроек:", e)

def set_local_show_legend(value):
    local = load_local(); local['show_legend'] = bool(value); save_local(local)

def get_local_show_legend():
    return bool(load_local().get('show_legend', False))

def set_local_results_hidden(value):
    local = load_local(); local['results_hidden'] = bool(value); save_local(local)

def get_local_results_hidden():
    return bool(load_local().get('results_hidden', False))

def set_show_in_timesheet(emp_id, value):
    if not emp_id: return
    local = load_local()
    local.setdefault('show_in_timesheet', {})[emp_id] = bool(value)
    save_local(local)

def set_theme(theme_name):
    local = load_local(); local['theme'] = theme_name; save_local(local)

def save_local_order(departments, employees):
    local = load_local()
    local['departments_order'] = list(departments or [])
    local['employees_order'] = [e.get('id') for e in (employees or []) if e.get('id')]
    save_local(local)

def get_local_collapsed_depts():
    return load_local().get('collapsed_depts', [])

def save_local_collapsed_depts(depts):
    local = load_local(); local['collapsed_depts'] = list(depts); save_local(local)
    
def apply_local_overrides(data):
    first_run = not os.path.exists(LOCAL_FILE)
    local = load_local()
    sel = local.setdefault('show_in_timesheet', {})
    if first_run: save_local(local)
    for emp in data.get('employees', []):
        emp_id = emp.get('id')
        if not emp_id:
            emp['show_in_timesheet'] = False
            continue
        emp['show_in_timesheet'] = bool(sel.get(emp_id, False))
    return data

def apply_local_order(data):
    local = load_local()
    changed = False
    dept_order = local.get('departments_order')
    if dept_order:
        current = list(data.get('departments', []))
        known = [d for d in dept_order if d in current]
        unknown = [d for d in current if d not in dept_order]
        data['departments'] = known + unknown
    else:
        local['departments_order'] = list(data.get('departments', []))
        changed = True

    emp_order = local.get('employees_order')
    current_emps = list(data.get('employees', []))
    if emp_order:
        by_id = {}
        for e in current_emps:
            eid = e.get('id')
            if eid: by_id[eid] = e
        new_list = []
        for eid in emp_order:
            if eid in by_id: new_list.append(by_id.pop(eid))
        for e in current_emps:
            eid = e.get('id')
            if eid and eid in by_id: new_list.append(by_id.pop(eid))
            elif not eid: new_list.append(e)
        data['employees'] = new_list
    else:
        local['employees_order'] = [e.get('id') for e in current_emps if e.get('id')]
        changed = True
    if changed: save_local(local)
    return data

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
                data.setdefault('shared_signers', [])
                for emp in data['employees']:
                    emp.setdefault('department', '')
                    emp.setdefault('show_in_timesheet', False)
                    emp.setdefault('is_contract', True)
                    
                # --- МИГРАЦИЯ ---
                if _migrate_r_to_ro(data):
                    save_data(data)
                    
                data = apply_local_overrides(data)
                data = apply_local_order(data)
                return data
        except Exception: pass
    data = {
        "employees": [], "timesheets": {},
        "positions": list(DEFAULT_POSITIONS), "night_flags": {}, "overtime_flags": {}, "no_weekends_flags": {},
        "departments": list(DEFAULT_DEPARTMENTS), "organization": DEFAULT_ORG,
        "energetic_name": DEFAULT_ENERGETIC, "department_energetic": {},
        "signer_positions": ['Энергетик'], "director_name": DEFAULT_DIRECTOR, "extra_employees": {},
        "shared_signers": [],
    }
    data = apply_local_overrides(data)
    data = apply_local_order(data)
    return data

def save_data(data):
    global _LAST_MTIME
    popped = []
    for emp in data.get('employees', []):
        if 'show_in_timesheet' in emp:
            popped.append((emp, emp.pop('show_in_timesheet')))
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        try: _LAST_MTIME = os.path.getmtime(DATA_FILE)
        except Exception: pass
    except Exception as e: print("Ошибка сохранения:", e)
    finally:
        for emp, val in popped: emp['show_in_timesheet'] = val

def get_local_signers():
    local = load_local()
    return local.get('additional_signers', [])

def set_local_signers(signers):
    local = load_local()
    local['additional_signers'] = list(signers)
    save_local(local)
    
# =========================================================================
# ВИДИМОСТЬ КОЛОНОК (per-user)
# =========================================================================
def get_local_visible_columns():
    """Возвращает список ключей видимых колонок, или None = показать все."""
    local = load_local()
    v = local.get('visible_columns')
    return list(v) if v is not None else None

def set_local_visible_columns(keys):
    local = load_local()
    local['visible_columns'] = list(keys)
    save_local(local)

def get_visible_right_columns():
    """Возвращает отфильтрованный список кортежей (label, key, width)."""
    visible = get_local_visible_columns()
    if visible is None:
        return list(RIGHT_COLUMNS)
    vset = set(visible)
    return [col for col in RIGHT_COLUMNS if col[1] in vset]

# =========================================================================
# МИГРАЦИЯ ДАННЫХ: 'Р' → 'РО' (отпуск по родам → новое обозначение)
# =========================================================================
def _migrate_r_to_ro(data):
    """Возвращает True, если данные были изменены (или помечены как мигрированные)."""
    if data.get('_migr_ro_v2'):
        return False
    for _mkey, month_ts in data.get('timesheets', {}).items():
        if not isinstance(month_ts, dict):
            continue
        for _eid, days in month_ts.items():
            if not isinstance(days, dict):
                continue
            for d, v in list(days.items()):
                if isinstance(v, str) and v.strip().upper() == 'Р':
                    days[d] = 'РО'
    data['_migr_ro_v2'] = True
    return True