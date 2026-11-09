# excel_export.py
# -*- coding: utf-8 -*-
"""Экспорт в Excel."""
import os
import webbrowser
import math
from calendar import monthrange
from datetime import date, datetime

try:
    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
    OPENPYXL_ERR = ""
except Exception as _e:
    HAS_OPENPYXL = False
    OPENPYXL_ERR = f"{type(_e).__name__}: {_e}"
    import traceback
    OPENPYXL_ERR += "\n\n" + traceback.format_exc()

from config import (MONTHS, RIGHT_COLUMNS, RIGHT_COLUMN_GROUPS,
                    WEEKDAYS_SHORT, DEFAULT_ORG, BASE_DIR, DEFAULT_DIRECTOR)
from data_calc import classify_day, analyze_row, apply_overtime, fmt_hours, calc_norm_hours
from data_storage import get_local_signers, get_visible_right_columns

EXCEL_FONT = 'Times New Roman'

# --- Константы для вертикальных заголовков (row_h2 в полной выгрузке) ---
VERT_HEADER_MIN_H = 90
VERT_CHAR_WIDTH_PT = 6.0
VERT_PADDING_PT = 8.0

def _excel_visual_width(txt):
    """Оценивает визуальную ширину текста в единицах колонки Excel.
    Учитывает, что разные кириллические буквы и символы имеют разную ширину.
    """
    if not txt:
        return 0.0

    WIDE_UPPER = set('МЖШЩЮФ')
    w = 0.0
    for ch in str(txt):
        if ch.isdigit() or ch in ' .,+-':
            w += 0.55      # цифры, точки, запятые, минусы
        elif ch == '/':
            w += 0.65      # слэши чуть шире
        elif ch in WIDE_UPPER:
            w += 1.35      # широкие заглавные: М, Ж, Ш, Щ, Ю, Ф
        elif ch.isupper():
            w += 1.15      # остальные заглавные
        elif ch.isalpha():
            w += 0.85      # строчные буквы
        else:
            w += 0.65
    return w

def _estimate_wrap_lines(text, max_chars=19):
    """Точная эмуляция переноса строк в Excel (с учетом пробелов и дефисов)."""
    if not text:
        return 1
    lines = 0
    for paragraph in str(text).replace('\r', '').split('\n'):
        if not paragraph:
            lines += 1
            continue
        current_line_len = 0
        for word in paragraph.split(' '):
            if not word:
                continue
            parts = word.split('-')
            for i, part in enumerate(parts):
                if i < len(parts) - 1:
                    part += '-'
                if not part:
                    continue
                if current_line_len == 0:
                    current_line_len = len(part)
                    lines += 1
                elif current_line_len + 1 + len(part) <= max_chars:
                    current_line_len += 1 + len(part)
                else:
                    lines += 1
                    current_line_len = len(part)
                
                while current_line_len > max_chars:
                    current_line_len -= max_chars
                    lines += 1
    return max(1, lines)

def format_name(name):
    if not name:
        return ''
    parts = str(name).split()
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1][0]}.{parts[2][0]}."
    elif len(parts) == 2:
        if len(parts[1]) > 1 and not parts[1].endswith('.'):
            return f"{parts[0]} {parts[1][0]}."
    return str(name)


def _draw_legend(ws, row, total_cols, border, header_fill):
    ws.merge_cells(start_row=row, start_column=1,
                   end_row=row + 1, end_column=total_cols)
    c = ws.cell(row=row, column=1,
                value="Условные обозначения (вводятся так же, как на странице «Табель»):")
    c.font = Font(name=EXCEL_FONT, size=23, bold=True)
    c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    for r_header in (row, row + 1):
        for col in range(1, total_cols + 1):
            ws.cell(row=r_header, column=col).border = border
            ws.cell(row=r_header, column=col).fill = header_fill
    row += 2

    hints = [
        ('В',    'выходной'),
        ('О',    'трудовой отпуск'),
        ('Б',    'больничный'),
        ('А',    'за свой счёт'),
        ('РО',   'отпуск по родам'),
        ('К',    'командировка'),
        ('МК',   'мед. комиссия'),
        ('СР',   'оплата по среднему'),
        ('Р',    'ремонт'),
        ('ТО',   'тех. обслуживание'),
        ('КД',   'кол. договор'),
        ('Н',    'прочие неявки'),
        ('ДМ',   'день матери'),
        ('П',    'прогул'),
        ('Т',    'текущий простой'),
        ('Ц',    'целосменный простой'),
        ('У',    'опоздание'),
        ('8д',   'часы без ночных (8 тоже)'),
        ('8//N', 'часы // смена (и /)'),
    ]

    blocks = 3
    block_width = max(1, total_cols // blocks)
    start_row_hints = row

    for i, (code, desc) in enumerate(hints):
        r = start_row_hints + (i // blocks)
        b = i % blocks
        c_start = b * block_width + 1
        c_end = (b + 1) * block_width if b < blocks - 1 else total_cols
        if c_end < c_start:
            continue
        c_code_start = c_start
        c_code_end = min(c_start + 2, c_end)
        ws.merge_cells(start_row=r, start_column=c_code_start,
                       end_row=r, end_column=c_code_end)
        cell_code = ws.cell(row=r, column=c_code_start, value=code)
        cell_code.font = Font(name=EXCEL_FONT, size=16, bold=True, color="000000")
        cell_code.alignment = Alignment(horizontal='center', vertical='center')

        c_dash = c_code_end + 1
        if c_dash <= c_end:
            cell_dash = ws.cell(row=r, column=c_dash, value="—")
            cell_dash.font = Font(name=EXCEL_FONT, size=16, color="888888")
            cell_dash.alignment = Alignment(horizontal='center', vertical='center')

        c_desc_start = c_dash + 1
        if c_desc_start <= c_end:
            ws.merge_cells(start_row=r, start_column=c_desc_start,
                           end_row=r, end_column=c_end)
            cell_desc = ws.cell(row=r, column=c_desc_start, value=desc)
            cell_desc.font = Font(name=EXCEL_FONT, size=16)
            cell_desc.alignment = Alignment(horizontal='left', vertical='center')

        for col in range(c_start, c_end + 1):
            ws.cell(row=r, column=col).border = border

    last_r = start_row_hints + (len(hints) - 1) // blocks
    for r in range(start_row_hints, last_r + 1):
        for b in range(blocks):
            c_start = b * block_width + 1
            c_end = (b + 1) * block_width if b < blocks - 1 else total_cols
            if c_end < c_start:
                continue
            has_data = any(
                start_row_hints + (i // blocks) == r and (i % blocks) == b
                for i in range(len(hints))
            )
            if not has_data:
                ws.merge_cells(start_row=r, start_column=c_start,
                               end_row=r, end_column=c_end)
                for col in range(c_start, c_end + 1):
                    ws.cell(row=r, column=col).border = border
    return last_r + 1

def export_full_excel(tab, *args, force_dept=None, save_dir=None, force_year=None, force_month=None):
    if not HAS_OPENPYXL:
        tab._show_openpyxl_error(OPENPYXL_ERR)
        return

    # --- Видимые колонки ---
    visible_columns = get_visible_right_columns()
    if not visible_columns:
        visible_columns = list(RIGHT_COLUMNS)
    visible_keys = [c[1] for c in visible_columns]
    visible_set = set(visible_keys)

    # --- Период ---
    if force_year is not None and force_month is not None:
        y, m = int(force_year), int(force_month)
    else:
        y = int(tab.year_spinner.text)
        m = MONTHS.index(tab.month_spinner.text) + 1

    key = f"{y}-{m:02d}"
    days_in_month = monthrange(y, m)[1]
    ts = tab.app.data['timesheets'].get(key, {})
    
    # --- Сбор сотрудников и отдела ---
    if force_dept is not None:
        dept = force_dept
        emps = []
        for emp in tab.app.data['employees']:
            if emp.get('department', '') == dept:
                if emp.get('id') in ts or emp.get('show_in_timesheet', False):
                    emps.append(emp)
        
        month_dict = tab.app.data.get('extra_employees', {}).get(key, {})
        if isinstance(month_dict, dict):
            extra = month_dict.get(dept, [])
            for e in extra:
                e['is_extra'] = True
            emps += extra
        employees = emps
    else:
        dept = tab._get_dept()
        employees = tab._employees_for_report()

    if not dept and employees:
        for e in employees:
            d = e.get('department', '')
            if d:
                dept = d
                break

    night_flags = tab.app.data.get('night_flags', {})
    overtime_flags = tab.app.data.get('overtime_flags', {})
    no_weekends_flags = tab.app.data.get('no_weekends_flags', {})
    org = tab.app.data.get('organization', DEFAULT_ORG)
    signer_pos, signer_name = tab._get_signer(dept)
    director_name = tab.app.data.get('director_name', DEFAULT_DIRECTOR)
    day_types = [classify_day(y, m, d) for d in range(1, days_in_month + 1)]
    norm_hours, work_days, pre_count = calc_norm_hours(y, m)
    overrides_all = tab.app.data.get('result_overrides', {}).get(key, {})

    # --- Стили ---
    thin = Side(border_style="thin", color="333333")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    center_nowrap = Alignment(horizontal='center', vertical='center', wrap_text=False)
    left_wrap = Alignment(horizontal='left', vertical='center', wrap_text=True)
    left_nowrap = Alignment(horizontal='left', vertical='center', wrap_text=False)
    vert = Alignment(horizontal='center', vertical='bottom', text_rotation=90, wrap_text=False)
    
    header_fill = PatternFill("solid", fgColor="E8E8E8")
    weekend_fill = PatternFill("solid", fgColor="FFDEDE")
    holiday_fill = PatternFill("solid", fgColor="FFF3CC")
    total_fill = PatternFill("solid", fgColor="D0D0D0")

    f_title = Font(name=EXCEL_FONT, size=14, bold=True, italic=True)
    f_date_bold = Font(name=EXCEL_FONT, size=12, bold=True)
    f_italic = Font(name=EXCEL_FONT, size=11, italic=True)
    f_head = Font(name=EXCEL_FONT, size=11, bold=True)
    f_vert = Font(name=EXCEL_FONT, size=11)
    f_cell = Font(name=EXCEL_FONT, size=11)
    f_sig = Font(name=EXCEL_FONT, size=13)
    f_sig_bold = Font(name=EXCEL_FONT, size=13, bold=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{MONTHS[m-1]} {y}"

    # --- РАЗМЕТКА ---
    start_days = 4
    end_days = start_days + days_in_month - 1
    total_cols = end_days + len(visible_columns)
    
    title_end = min(end_days, 11)  # <--- УМЕНЬШЕНО ДО 11 (на 4 меньше)
    date_start = title_end + 1
    
    approve_col = max(end_days + 2, total_cols - 12) - 9
    director_col = approve_col - 1
    name_col = min(director_col + 5, total_cols)

    # ---------- Строка 1 ----------
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=title_end)
    c = ws.cell(row=1, column=1, value="табель учета использования рабочего времени")
    c.font = f_title
    c.alignment = left_nowrap  # <--- ВЫРАВНИВАНИЕ ПО ЛЕВОМУ КРАЮ

    if end_days >= date_start:
        date_end = min(end_days, approve_col - 1)
        if date_start <= date_end:
            ws.merge_cells(start_row=1, start_column=date_start, end_row=1, end_column=date_end)
            c = ws.cell(row=1, column=date_start, value=f"{y}, {MONTHS[m-1].lower()} ({days_in_month} календарных дней)")
            c.font = f_date_bold
            c.alignment = center_nowrap  # <--- ИСПРАВЛЕНО (без переноса)

    if approve_col <= total_cols:
        ws.merge_cells(start_row=1, start_column=approve_col, end_row=1, end_column=total_cols)
        c = ws.cell(row=1, column=approve_col, value="Утверждаю:")
        c.font = f_sig
        c.alignment = Alignment(horizontal='left', vertical='center', indent=1)

    # ---------- Строка 2 ----------
    ws.merge_cells('A2:C2')
    c = ws.cell(row=2, column=1, value="Предприятие")
    c.font = f_italic
    c.alignment = center
    
    org_end = min(end_days, director_col - 1)
    if org_end >= 4:
        ws.merge_cells(start_row=2, start_column=4, end_row=2, end_column=org_end)
        c = ws.cell(row=2, column=4, value=org)
        c.font = f_italic
        c.alignment = Alignment(horizontal='left', vertical='center', indent=1)

    if approve_col <= total_cols:
        ws.merge_cells(start_row=2, start_column=director_col, end_row=2, end_column=max(director_col, name_col - 1))
        c = ws.cell(row=2, column=director_col, value="Директор")
        c.font = f_sig
        c.alignment = Alignment(horizontal='right', vertical='center')

        ws.merge_cells(start_row=2, start_column=name_col, end_row=2, end_column=total_cols)
        c = ws.cell(row=2, column=name_col, value=director_name)
        c.font = f_sig
        c.alignment = Alignment(horizontal='right', vertical='center', indent=1)

    # ---------- Строка 3 ----------
    ws.merge_cells('A3:C3')
    c = ws.cell(row=3, column=1, value="Отдел, цех, участок")
    c.font = f_italic
    c.alignment = center
    
    ws.merge_cells(start_row=3, start_column=4, end_row=3, end_column=end_days)
    c = ws.cell(row=3, column=4, value=dept)
    c.font = f_italic
    c.alignment = Alignment(horizontal='left', vertical='center', indent=1)

    # ---------- Шапка таблицы ----------
    row_h1, row_h2 = 5, 6
    for col, label in [(1, "№"), (2, "Фамилия И.О."), (3, "Должность")]:
        c = ws.cell(row=row_h1, column=col, value=label)
        c.font = f_head
        c.alignment = center
        c.fill = header_fill
        ws.merge_cells(start_row=row_h1, start_column=col, end_row=row_h2, end_column=col)

    ws.merge_cells(start_row=row_h1, start_column=start_days, end_row=row_h1, end_column=end_days)
    c = ws.cell(row=row_h1, column=start_days, value="Числа месяца")
    c.font = f_head
    c.alignment = center
    c.fill = header_fill

    # Группы
    start_r = end_days + 1
    for gname, gkeys in RIGHT_COLUMN_GROUPS:
        gvis_count = sum(1 for k in gkeys if k in visible_set)
        if gvis_count == 0:
            continue
        ws.merge_cells(start_row=row_h1, start_column=start_r, end_row=row_h1, end_column=start_r + gvis_count - 1)
        c = ws.cell(row=row_h1, column=start_r, value=gname)
        c.font = f_head
        c.alignment = center
        c.fill = header_fill
        start_r += gvis_count

    # Дни
    for i, dt in enumerate(day_types):
        col = start_days + i
        wd = WEEKDAYS_SHORT[date(y, m, i + 1).weekday()]
        c = ws.cell(row=row_h2, column=col, value=f"{i + 1}\n{wd}")
        c.font = f_cell
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.fill = weekend_fill if dt == 'weekend' else holiday_fill if dt == 'holiday' else header_fill

    # Правые заголовки
    start_r = end_days + 1
    for label, key_, _w in visible_columns:
        c = ws.cell(row=row_h2, column=start_r, value=label)
        c.font = f_vert
        c.alignment = vert
        c.fill = header_fill
        start_r += 1

    for r in (row_h1, row_h2):
        for col in range(1, total_cols + 1):
            ws.cell(row=r, column=col).border = border

    # ---------- Данные ----------
    row = row_h2 + 1
    grand = {k: 0 for _, k, _ in RIGHT_COLUMNS}
    grand.update({'часы': 0.0, 'сверхурочные': 0.0, 'ночные': 0.0, 'праздничные': 0.0})
    max_col_len = {k: 0 for k in visible_keys}
    max_day_w = {i: 1.0 for i in range(days_in_month)}
    max_name_len, max_pos_len = 0, 0

    for idx, emp in enumerate(employees):
        emp_id = emp['id']
        day_data = ts.get(emp_id, {})
        values = [day_data.get(str(d), '') for d in range(1, days_in_month + 1)]
        
        name_text = format_name(emp.get('name', ''))
        pos_text = emp.get('position', '').replace('\n', ' ').strip()
        max_name_len = max(max_name_len, len(name_text))
        max_pos_len = max(max_pos_len, len(pos_text))

        pos_name = emp.get('position', '')
        res = analyze_row(values, day_types, bool(night_flags.get(pos_name, False)), bool(no_weekends_flags.get(pos_name, False)))
        if bool(overtime_flags.get(pos_name, False)):
            apply_overtime(res, norm_hours)
        else:
            res['сверхурочные'] = 0.0
            
        emp_over = overrides_all.get(emp_id, {})
        for k in grand:
            if k in emp_over:
                try: grand[k] += float(str(emp_over[k]).replace(',', '.'))
                except (ValueError, TypeError): pass
            else:
                grand[k] += res.get(k, 0)

        ws.cell(row=row, column=1, value=idx + 1).font = f_cell
        ws.cell(row=row, column=1).alignment = center

        c_name = ws.cell(row=row, column=2, value=name_text)
        c_name.font = f_cell
        c_name.alignment = left_nowrap  # <--- ФАМИЛИЯ БЕЗ ПЕРЕНОСА

        c_pos = ws.cell(row=row, column=3, value=pos_text)
        c_pos.font = f_cell
        c_pos.alignment = left_wrap     # <--- ДОЛЖНОСТЬ С ПЕРЕНОСОМ

        for i, v in enumerate(values):
            col = start_days + i
            if str(v).strip() == '0': v = None
            c = ws.cell(row=row, column=col, value=v)
            c.font = f_cell
            c.alignment = center
            if v is not None:
                w = _excel_visual_width(v)
                if w > max_day_w[i]:
                    max_day_w[i] = w
            if day_types[i] == 'weekend': c.fill = weekend_fill
            elif day_types[i] == 'holiday': c.fill = holiday_fill

        start_r = end_days + 1
        for _, key_, _w in visible_columns:
            val = emp_over.get(key_, res.get(key_, 0))
            if key_ in ('часы', 'сверхурочные', 'ночные', 'праздничные', 'выходные_часы'):
                val = fmt_hours(val)
            if str(val).strip() in ('0', '0.0', '0.00'): val = None
            c = ws.cell(row=row, column=start_r, value=val)
            if val is not None: max_col_len[key_] = max(max_col_len[key_], len(str(val)))
            c.font = f_cell
            c.alignment = center
            start_r += 1

        est_lines_pos = _estimate_wrap_lines(pos_text, max_chars=19)
        ws.row_dimensions[row].height = max(16, est_lines_pos * 17)
        for col in range(1, total_cols + 1):
            ws.cell(row=row, column=col).border = border
        row += 1

    # ---------- ИТОГО ----------
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
    c = ws.cell(row=row, column=1, value="ИТОГО")
    c.font = f_head
    c.alignment = center
    for col in range(1, 4):
        ws.cell(row=row, column=col).border = border
        ws.cell(row=row, column=col).fill = total_fill

    ws.merge_cells(start_row=row, start_column=start_days, end_row=row, end_column=end_days)
    for col in range(start_days, end_days + 1):
        ws.cell(row=row, column=col).border = border
        ws.cell(row=row, column=col).fill = total_fill

    start_r = end_days + 1
    for _, key_, _w in visible_columns:
        v = grand.get(key_, 0)
        val = fmt_hours(v) if key_ in ('часы', 'сверхурочные', 'ночные', 'праздничные', 'выходные_часы') else v
        if str(val).strip() in ('0', '0.0', '0.00'): val = None
        c = ws.cell(row=row, column=start_r, value=val)
        if val is not None: max_col_len[key_] = max(max_col_len[key_], len(str(val)))
        c.font = f_head
        c.alignment = center
        c.border = border
        c.fill = total_fill
        start_r += 1
    ws.row_dimensions[row].height = 20

    # ---------- Численность ----------
    spis_count = sum(1 for emp in employees if emp.get('is_contract', True))
    total_days = sum(grand[k] for k in grand if k not in ('часы', 'сверхурочные', 'ночные', 'праздничные'))
    avg_count = total_days / days_in_month if days_in_month > 0 else 0

    row += 2
    ws.row_dimensions[row].height = 24
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
    c = ws.cell(row=row, column=1, value="Норма рабочего времени:")
    c.font = f_sig
    c.alignment = Alignment(horizontal='left', vertical='center')
    c2 = ws.cell(row=row, column=4, value=f"{fmt_hours(norm_hours)} ч")
    c2.font = f_sig_bold
    c2.alignment = Alignment(horizontal='left', vertical='center')

    row += 1
    ws.row_dimensions[row].height = 24
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
    c = ws.cell(row=row, column=1, value="Списочная численность:")
    c.font = f_sig
    c.alignment = Alignment(horizontal='left', vertical='center')
    c2 = ws.cell(row=row, column=4, value=spis_count)
    c2.font = f_sig_bold
    c2.alignment = Alignment(horizontal='left', vertical='center')

    row += 1
    ws.row_dimensions[row].height = 24
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
    c = ws.cell(row=row, column=1, value="Среднесписочная численность:")
    c.font = f_sig
    c.alignment = Alignment(horizontal='left', vertical='center')
    val_avg = round(avg_count, 2)
    if val_avg == int(val_avg): val_avg = int(val_avg)
    c2 = ws.cell(row=row, column=4, value=val_avg)
    c2.font = f_sig_bold
    c2.alignment = Alignment(horizontal='left', vertical='center')

    # ---------- ШИРИНЫ СТОЛБЦОВ ----------
    EXCEL_OFFSET = 5.0 / 7.0

    # № — минимум 2.57, расширяем если номеров много
    max_num = max(1, len(employees))
    num_digits = len(str(max_num))
    num_visual = max(2.57, num_digits * 0.8 + 0.4)
    ws.column_dimensions['A'].width = num_visual + EXCEL_OFFSET

    # Фамилия — жесткий минимум 16.0 (в единицах Excel) + запас 1.0 к самой длинной фамилии
    max_name_visual = max((_excel_visual_width(format_name(emp.get('name', ''))) for emp in employees), default=0.0)
    name_visual = max(16.0, max_name_visual + 1.0)
    ws.column_dimensions['B'].width = name_visual + EXCEL_OFFSET

    # Должность — реальная визуальная ширина + минимальный отступ
    max_pos_visual = max((_excel_visual_width(emp.get('position', '').replace('\n', ' ').strip()) for emp in employees), default=0.0)
    pos_visual = max(12.5, min(21.0, max_pos_visual + 0.5))
    ws.column_dimensions['C'].width = pos_visual + EXCEL_OFFSET

    # Дни — минимум 2.57, + 0.5 к реальной ширине
    for i in range(days_in_month):
        day_visual = max(2.57, max_day_w[i] + 0.5)
        ws.column_dimensions[get_column_letter(start_days + i)].width = day_visual + EXCEL_OFFSET

    # Правые колонки (Итоги) — используем 0.55 на символ (цифры узкие) + 0.5 на отступы
    col_widths = {}
    for _, key_, _w in visible_columns:
        content_visual = max_col_len[key_] * 0.55 + 0.5
        visual_min = max(2.57, content_visual)
        col_widths[key_] = visual_min + EXCEL_OFFSET

    # Групповые минимумы (в визуальных единицах!)
    GROUP_MINS_VISUAL = {
        "Дни явок": 5.0,
        "Дни неявок": 8.0,
        "Отработано часов": 12.43,
    }
    for gname, gkeys in RIGHT_COLUMN_GROUPS:
        gvis = [k for k in gkeys if k in visible_set]
        if not gvis:
            continue
        target_visual = GROUP_MINS_VISUAL.get(gname, 0)
        if target_visual <= 0:
            continue
        target_openpyxl = target_visual + EXCEL_OFFSET
        current_sum = sum(col_widths[k] for k in gvis)
        if current_sum < target_openpyxl:
            diff = target_openpyxl - current_sum
            per_col = diff / len(gvis)
            for k in gvis:
                col_widths[k] += per_col

    for i, (_, key_, _w) in enumerate(visible_columns):
        col_letter = get_column_letter(end_days + 1 + i)
        ws.column_dimensions[col_letter].width = col_widths[key_]

    ws.row_dimensions[row_h1].height = 35

    max_vert_len = max((len(str(label)) for label, _k, _w in visible_columns), default=0)
    required_vert_h = max_vert_len * VERT_CHAR_WIDTH_PT + VERT_PADDING_PT
    ws.row_dimensions[row_h2].height = max(VERT_HEADER_MIN_H, required_vert_h)

    # ---------- Подписи ----------
    row += 4
    LEFT_COL = 3
    sig_row = row + 2

    c = ws.cell(row=sig_row, column=LEFT_COL, value=signer_pos)
    c.font = f_sig
    c.alignment = Alignment(horizontal='left', vertical='center')
    sig_name_col = min(LEFT_COL + 25, total_cols)
    c = ws.cell(row=sig_row, column=sig_name_col, value=signer_name)
    c.font = f_sig
    c.alignment = Alignment(horizontal='left', vertical='center')

    if force_dept is not None:
        additional_signers = tab.app.data.get('shared_signers', [])
    else:
        additional_signers = get_local_signers()

    for s in additional_signers:
        if s.get('active', True): 
            sig_row += 4
            c = ws.cell(row=sig_row, column=LEFT_COL, value=s.get('position', ''))
            c.font = f_sig
            c.alignment = Alignment(horizontal='left', vertical='center')
            c = ws.cell(row=sig_row, column=sig_name_col, value=s.get('name', ''))
            c.font = f_sig
            c.alignment = Alignment(horizontal='left', vertical='center')

    last_print_row = sig_row + 2

    if tab.legend_cb.active:
        legend_start_row = sig_row + 3
        last_print_row = _draw_legend(ws, legend_start_row, total_cols, border, header_fill)

    # --- Настройки страницы ---
    ws.page_margins.left = 0.2
    ws.page_margins.right = 0.2
    ws.page_margins.top = 0.2
    ws.page_margins.bottom = 0.2

    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    try:
        ws.print_area = f"A1:{get_column_letter(total_cols)}{last_print_row}"
    except Exception:
        pass

    _save_and_open(ws, wb, y, dept, key, "_full", custom_dir=save_dir)


def export_short_excel(tab, *args):
    if not HAS_OPENPYXL:
        tab._show_openpyxl_error(OPENPYXL_ERR)
        return

    y = int(tab.year_spinner.text)
    m = MONTHS.index(tab.month_spinner.text) + 1
    key = f"{y}-{m:02d}"
    days_in_month = monthrange(y, m)[1]
    ts = tab.app.data['timesheets'].get(key, {})
    employees = tab._employees_for_report()
    night_flags = tab.app.data.get('night_flags', {})
    no_weekends_flags = tab.app.data.get('no_weekends_flags', {})
    org = tab.app.data.get('organization', DEFAULT_ORG)
    dept = tab._get_dept()
    
    if not dept and employees:
        for e in employees:
            d = e.get('department', '')
            if d:
                dept = d
                break

    overrides_all = tab.app.data.get('result_overrides', {}).get(key, {})
    day_types = [classify_day(y, m, d) for d in range(1, days_in_month + 1)]
    norm_hours, work_days, pre_count = calc_norm_hours(y, m)

    thin = Side(border_style="thin", color="333333")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    center_nowrap = Alignment(horizontal='center', vertical='center', wrap_text=False)
    left_wrap = Alignment(horizontal='left', vertical='center', wrap_text=True)
    left_nowrap = Alignment(horizontal='left', vertical='center', wrap_text=False)
    
    header_fill = PatternFill("solid", fgColor="E8E8E8")
    weekend_fill = PatternFill("solid", fgColor="FFDEDE")
    holiday_fill = PatternFill("solid", fgColor="FFF3CC")
    total_fill = PatternFill("solid", fgColor="D0D0D0")
    
    f_title = Font(name=EXCEL_FONT, size=14, bold=True, italic=True)
    f_date_bold = Font(name=EXCEL_FONT, size=12, bold=True)
    f_italic = Font(name=EXCEL_FONT, size=11, italic=True)
    f_head = Font(name=EXCEL_FONT, size=11, bold=True)
    f_cell = Font(name=EXCEL_FONT, size=11)
    f_sig = Font(name=EXCEL_FONT, size=13)
    f_sig_bold = Font(name=EXCEL_FONT, size=13, bold=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{MONTHS[m-1]} {y}"
    
    start_days = 4
    end_days = start_days + days_in_month - 1
    total_cols = end_days + 2
    
    col_hours = end_days + 1
    col_off = end_days + 2

    title_end = min(end_days, 11)  # <--- УМЕНЬШЕНО ДО 11
    date_start = title_end + 1

    # Строка 1
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=title_end)
    c = ws.cell(row=1, column=1, value="табель учета использования рабочего времени")
    c.font = f_title
    c.alignment = left_nowrap  # <--- ВЫРАВНИВАНИЕ ПО ЛЕВОМУ КРАЮ
    
    if end_days >= date_start:
        ws.merge_cells(start_row=1, start_column=date_start, end_row=1, end_column=end_days)
        c = ws.cell(row=1, column=date_start, value=f"{y}, {MONTHS[m-1].lower()} ({days_in_month} календарных дней)")
        c.font = f_date_bold
        c.alignment = center_nowrap  # <--- ИСПРАВЛЕНО (без переноса)

    # Строка 2
    ws.merge_cells('A2:C2')
    c = ws.cell(row=2, column=1, value="Предприятие")
    c.font = f_italic
    c.alignment = center
    
    ws.merge_cells(start_row=2, start_column=start_days, end_row=2, end_column=end_days)
    c = ws.cell(row=2, column=start_days, value=org)
    c.font = f_italic
    c.alignment = Alignment(horizontal='left', vertical='center', indent=1)

    # Строка 3
    ws.merge_cells('A3:C3')
    c = ws.cell(row=3, column=1, value="Отдел, цех, участок")
    c.font = f_italic
    c.alignment = center
    
    ws.merge_cells(start_row=3, start_column=start_days, end_row=3, end_column=end_days)
    c = ws.cell(row=3, column=start_days, value=dept)
    c.font = f_italic
    c.alignment = Alignment(horizontal='left', vertical='center', indent=1)

    # Шапка (строки 5 и 6)
    row_h1, row_h2 = 5, 6
    c = ws.cell(row=row_h1, column=1, value="№")
    c.font = f_head
    c.alignment = center
    c.fill = header_fill
    ws.merge_cells(start_row=row_h1, start_column=1, end_row=row_h2, end_column=1)
    
    c = ws.cell(row=row_h1, column=2, value="Фамилия И.О.")
    c.font = f_head
    c.alignment = center
    c.fill = header_fill
    ws.merge_cells(start_row=row_h1, start_column=2, end_row=row_h2, end_column=2)

    c = ws.cell(row=row_h1, column=3, value="Должность")
    c.font = f_head
    c.alignment = center
    c.fill = header_fill
    ws.merge_cells(start_row=row_h1, start_column=3, end_row=row_h2, end_column=3)

    ws.merge_cells(start_row=row_h1, start_column=start_days, end_row=row_h1, end_column=end_days)
    c = ws.cell(row=row_h1, column=start_days, value="Числа месяца")
    c.font = f_head
    c.alignment = center
    c.fill = header_fill

    vert_short = Alignment(horizontal='center', vertical='bottom', text_rotation=90, wrap_text=False)

    c = ws.cell(row=row_h1, column=col_hours, value="Всего")
    c.font = f_head
    c.alignment = vert_short
    c.fill = header_fill
    ws.merge_cells(start_row=row_h1, start_column=col_hours, end_row=row_h2, end_column=col_hours)
    
    c = ws.cell(row=row_h1, column=col_off, value="Выходные")
    c.font = f_head
    c.alignment = vert_short
    c.fill = header_fill
    ws.merge_cells(start_row=row_h1, start_column=col_off, end_row=row_h2, end_column=col_off)

    for i, dt in enumerate(day_types):
        col = start_days + i
        wd = WEEKDAYS_SHORT[date(y, m, i + 1).weekday()]
        c = ws.cell(row=row_h2, column=col, value=f"{i + 1}\n{wd}")
        c.font = f_cell
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.fill = weekend_fill if dt == 'weekend' else holiday_fill if dt == 'holiday' else header_fill

    for r in (row_h1, row_h2):
        for col in range(1, total_cols + 1):
            ws.cell(row=r, column=col).border = border

    row = row_h2 + 1
    grand = {'часы': 0.0, 'вых': 0}
    max_col_len = {'часы': 2, 'вых': 2}
    max_day_w = {i: 1.0 for i in range(days_in_month)}
    max_name_len, max_pos_len = 0, 0

    for idx, emp in enumerate(employees):
        emp_id = emp['id']
        day_data = ts.get(emp_id, {})
        values = [day_data.get(str(d), '') for d in range(1, days_in_month + 1)]
        
        name_text = format_name(emp.get('name', ''))
        pos_text = emp.get('position', '').replace('\n', ' ').strip()
        max_name_len = max(max_name_len, len(name_text))
        max_pos_len = max(max_pos_len, len(pos_text))

        pos_name = emp.get('position', '')
        res = analyze_row(values, day_types, bool(night_flags.get(pos_name, False)), bool(no_weekends_flags.get(pos_name, False)))
        emp_over = overrides_all.get(emp_id, {})

        hours_val = float(str(emp_over.get('часы', res.get('часы', 0.0))).replace(',', '.'))
        off_val = int(float(str(emp_over.get('вых', res.get('вых', 0))).replace(',', '.')))
        grand['часы'] += hours_val
        grand['вых'] += off_val

        ws.cell(row=row, column=1, value=idx + 1).font = f_cell
        ws.cell(row=row, column=1).alignment = center
        c_name = ws.cell(row=row, column=2, value=name_text)
        c_name.font = f_cell
        c_name.alignment = left_nowrap  # <--- ФАМИЛИЯ БЕЗ ПЕРЕНОСА

        c_pos = ws.cell(row=row, column=3, value=pos_text)
        c_pos.font = f_cell
        c_pos.alignment = left_wrap     # <--- ДОЛЖНОСТЬ С ПЕРЕНОСОМ

        for i, v in enumerate(values):
            col = start_days + i
            if str(v).strip() == '0': v = None
            c = ws.cell(row=row, column=col, value=v)
            c.font = f_cell
            c.alignment = center
            if v is not None:
                w = _excel_visual_width(v)
                if w > max_day_w[i]:
                    max_day_w[i] = w
            if day_types[i] == 'weekend': c.fill = weekend_fill
            elif day_types[i] == 'holiday': c.fill = holiday_fill

        hours_val_fmt = fmt_hours(hours_val)
        if str(hours_val_fmt).strip() in ('0', '0.0'): hours_val_fmt = None
        c = ws.cell(row=row, column=col_hours, value=hours_val_fmt)
        if hours_val_fmt is not None: max_col_len['часы'] = max(max_col_len['часы'], len(str(hours_val_fmt)))
        c.font = f_cell
        c.alignment = center

        off_val_fmt = off_val if off_val != 0 else None
        c = ws.cell(row=row, column=col_off, value=off_val_fmt)
        if off_val_fmt is not None: max_col_len['вых'] = max(max_col_len['вых'], len(str(off_val_fmt)))
        c.font = f_cell
        c.alignment = center

        est_lines_pos = _estimate_wrap_lines(pos_text, max_chars=19)
        ws.row_dimensions[row].height = max(16, est_lines_pos * 17)

        for col in range(1, total_cols + 1):
            ws.cell(row=row, column=col).border = border
        row += 1

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
    c = ws.cell(row=row, column=1, value="ИТОГО")
    c.font = f_head
    c.alignment = center
    for col in range(1, 4):
        ws.cell(row=row, column=col).border = border
        ws.cell(row=row, column=col).fill = total_fill

    ws.merge_cells(start_row=row, start_column=start_days, end_row=row, end_column=end_days)
    for col in range(start_days, end_days + 1):
        ws.cell(row=row, column=col).border = border
        ws.cell(row=row, column=col).fill = total_fill

    grand_hours_fmt = fmt_hours(grand['часы'])
    c = ws.cell(row=row, column=col_hours, value=grand_hours_fmt if str(grand_hours_fmt) not in ('0', '0.0') else None)
    c.font = f_head
    c.alignment = center
    c.border = border
    c.fill = total_fill

    c = ws.cell(row=row, column=col_off, value=grand['вых'] if grand['вых'] != 0 else None)
    c.font = f_head
    c.alignment = center
    c.border = border
    c.fill = total_fill
    ws.row_dimensions[row].height = 20

    row += 2
    ws.row_dimensions[row].height = 24
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
    c = ws.cell(row=row, column=1, value="Норма рабочего времени:")
    c.font = f_sig
    c.alignment = Alignment(horizontal='left', vertical='center')
    c2 = ws.cell(row=row, column=start_days, value=f"{fmt_hours(norm_hours)} ч")
    c2.font = f_sig_bold
    c2.alignment = Alignment(horizontal='left', vertical='center')

    # --- ШИРИНЫ ---
    EXCEL_OFFSET = 5.0 / 7.0

    max_num = max(1, len(employees))
    num_digits = len(str(max_num))
    num_visual = max(2.57, num_digits * 0.8 + 0.4)
    ws.column_dimensions['A'].width = num_visual + EXCEL_OFFSET

    # Фамилия — жесткий минимум 16.0 (в единицах Excel) + запас 1.0 к самой длинной фамилии
    max_name_visual = max((_excel_visual_width(format_name(emp.get('name', ''))) for emp in employees), default=0.0)
    name_visual = max(16.0, max_name_visual + 1.0)
    ws.column_dimensions['B'].width = name_visual + EXCEL_OFFSET

    max_pos_visual = max((_excel_visual_width(emp.get('position', '').replace('\n', ' ').strip()) for emp in employees), default=0.0)
    pos_visual = max(12.5, min(21.0, max_pos_visual + 0.5))
    ws.column_dimensions['C'].width = pos_visual + EXCEL_OFFSET

    for i in range(days_in_month):
        day_visual = max(2.57, max_day_w[i] + 0.5)
        ws.column_dimensions[get_column_letter(start_days + i)].width = day_visual + EXCEL_OFFSET

    ws.column_dimensions[get_column_letter(col_hours)].width = (
        max(2.57, max_col_len['часы'] * 0.55 + 0.5) + EXCEL_OFFSET
    )
    ws.column_dimensions[get_column_letter(col_off)].width = (
        max(2.57, max_col_len['вых'] * 0.55 + 0.5) + EXCEL_OFFSET
    )

    ws.row_dimensions[1].height = 35
    ws.row_dimensions[2].height = 25
    ws.row_dimensions[3].height = 25
    ws.row_dimensions[4].height = 10
    ws.row_dimensions[row_h1].height = 20
    ws.row_dimensions[row_h2].height = 50

    if tab.legend_cb.active:
        row += 4
        row = _draw_legend(ws, row, total_cols, border, header_fill)

    ws.page_margins.left = 0.2
    ws.page_margins.right = 0.2
    ws.page_margins.top = 0.2
    ws.page_margins.bottom = 0.2

    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    try:
        ws.print_area = f"A1:{get_column_letter(total_cols)}{row}"
    except Exception:
        pass

    _save_and_open(ws, wb, y, dept, key, "_short")

def _save_and_open(ws, wb, y, dept, key, suffix, custom_dir=None):
    def _sanitize_folder(name):
        bad = '\\/:*?"<>|'
        for ch in bad:
            name = name.replace(ch, '_')
        return name.strip() or 'Без отдела'

    dept_folder = _sanitize_folder(dept)
    
    if custom_dir:
        out_dir = os.path.join(custom_dir, dept_folder, str(y))
    else:
        out_dir = os.path.join(BASE_DIR, "Табель", dept_folder, str(y))
        
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception as e:
        print("Не удалось создать папку:", e)

    path = os.path.join(out_dir, f"tabel_{key}{suffix}.xlsx")
    try:
        ws.page_margins.left = 0.3
        ws.page_margins.right = 0.3
        ws.page_margins.top = 0.4
        ws.page_margins.bottom = 0.4
        wb.save(path)
    except Exception as e:
        print("Ошибка сохранения Excel:", e)
        return
        
    if not custom_dir:
        try:
            os.startfile(path)
        except Exception:
            try:
                webbrowser.open(f"file://{path}")
            except Exception:
                pass