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


def export_full_excel(tab, *args):
    if not HAS_OPENPYXL:
        tab._show_openpyxl_error(OPENPYXL_ERR)
        return

    # --- Видимые колонки этого пользователя ---
    visible_columns = get_visible_right_columns()
    if not visible_columns:
        visible_columns = list(RIGHT_COLUMNS)
    visible_keys = [c[1] for c in visible_columns]
    visible_set = set(visible_keys)

    y = int(tab.year_spinner.text)
    m = MONTHS.index(tab.month_spinner.text) + 1
    key = f"{y}-{m:02d}"
    days_in_month = monthrange(y, m)[1]
    ts = tab.app.data['timesheets'].get(key, {})
    employees = tab._employees_for_report()
    night_flags = tab.app.data.get('night_flags', {})
    overtime_flags = tab.app.data.get('overtime_flags', {})
    no_weekends_flags = tab.app.data.get('no_weekends_flags', {})
    org = tab.app.data.get('organization', DEFAULT_ORG)
    dept = tab._get_dept()
    signer_pos, signer_name = tab._get_signer(dept)
    director_name = tab.app.data.get('director_name', DEFAULT_DIRECTOR)
    day_types = [classify_day(y, m, d) for d in range(1, days_in_month + 1)]
    norm_hours, work_days, pre_count = calc_norm_hours(y, m)
    overrides_all = tab.app.data.get('result_overrides', {}).get(key, {})

    thin = Side(border_style="thin", color="333333")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal='center', vertical='center')
    left = Alignment(horizontal='left', vertical='center')
    vert = Alignment(horizontal='center', vertical='center',
                     text_rotation=90, wrap_text=False)
    header_fill = PatternFill("solid", fgColor="E8E8E8")
    weekend_fill = PatternFill("solid", fgColor="FFDEDE")
    holiday_fill = PatternFill("solid", fgColor="FFF3CC")
    total_fill = PatternFill("solid", fgColor="D0D0D0")

    f_title = Font(name=EXCEL_FONT, size=25, bold=True, italic=True)
    f_date_bold = Font(name=EXCEL_FONT, size=25, bold=True)
    f_date_norm = Font(name=EXCEL_FONT, size=23)
    f_italic = Font(name=EXCEL_FONT, size=25, italic=True)
    f_italic_ul = Font(name=EXCEL_FONT, size=25, italic=True, underline='single')
    f_head = Font(name=EXCEL_FONT, size=14, bold=True)
    f_vert = Font(name=EXCEL_FONT, size=14)
    f_cell = Font(name=EXCEL_FONT, size=14)
    f_sig = Font(name=EXCEL_FONT, size=25)
    f_sig_bold = Font(name=EXCEL_FONT, size=25, bold=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{MONTHS[m-1]} {y}"

    total_cols = 3 + days_in_month + len(visible_columns)
    right_anchor = total_cols
    title_end = 13
    date_start = 14
    date_end = 21
    days_start = 23

    # Позиция блока "Утверждаю" — безопасная для любого кол-ва видимых колонок
    approve_col = right_anchor - 17
    if approve_col < days_start + 1:
        approve_col = days_start + 1
    if approve_col + 14 > right_anchor:
        approve_col = max(days_start + 1, right_anchor - 14)
    days_end = max(days_start, approve_col - 1)

    # ---------- Строка 1: заголовки ----------
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=title_end)
    c = ws.cell(row=1, column=1, value="табель учета использования рабочего времени")
    c.font = f_title
    c.alignment = Alignment(horizontal='left', vertical='center')

    ws.merge_cells(start_row=1, start_column=date_start,
                   end_row=1, end_column=date_end)
    c = ws.cell(row=1, column=date_start, value=f"{y}, {MONTHS[m-1].lower()}")
    c.font = f_date_bold
    c.alignment = Alignment(horizontal='center', vertical='center')

    ws.merge_cells(start_row=1, start_column=days_start,
                   end_row=1, end_column=days_end)
    c = ws.cell(row=1, column=days_start, value=f"({days_in_month} календарных дней)")
    c.font = f_date_norm
    c.alignment = Alignment(horizontal='center', vertical='center')

    ws.merge_cells('A2:C2')
    c = ws.cell(row=2, column=1, value="Предприятие")
    c.font = f_italic
    c.alignment = Alignment(horizontal='left', vertical='center')
    ws.merge_cells(start_row=2, start_column=4, end_row=2, end_column=title_end + 3)
    c = ws.cell(row=2, column=4, value=org)
    c.font = f_italic_ul
    c.alignment = Alignment(horizontal='left', vertical='center', indent=2)

    ws.merge_cells('A3:C3')
    c = ws.cell(row=3, column=1, value="Отдел, цех, участок")
    c.font = f_italic
    c.alignment = Alignment(horizontal='left', vertical='center')
    ws.merge_cells(start_row=3, start_column=4, end_row=3, end_column=title_end + 3)
    c = ws.cell(row=3, column=4, value=dept)
    c.font = f_italic_ul
    c.alignment = Alignment(horizontal='left', vertical='center', indent=2)

    # ---------- Утверждаю / Директор / Фамилия ----------
    ws.merge_cells(start_row=1, start_column=approve_col,
                   end_row=1, end_column=approve_col + 4)
    c = ws.cell(row=1, column=approve_col, value="Утверждаю:")
    c.font = f_sig
    c.alignment = Alignment(horizontal='center', vertical='center')

    director_col = approve_col
    ws.merge_cells(start_row=2, start_column=director_col,
                   end_row=2, end_column=director_col + 4)
    c = ws.cell(row=2, column=director_col, value="Директор")
    c.font = f_sig
    c.alignment = Alignment(horizontal='center', vertical='center')

    name_col = max(director_col + 5, right_anchor - 9)
    if name_col > right_anchor:
        name_col = right_anchor
    if name_col <= right_anchor:
        ws.merge_cells(start_row=2, start_column=name_col,
                       end_row=2, end_column=right_anchor)
        c = ws.cell(row=2, column=name_col, value=director_name)
        c.font = f_sig
        c.alignment = Alignment(horizontal='center', vertical='center')

    # ---------- Шапка таблицы (row_h1, row_h2) ----------
    row_h1, row_h2 = 5, 6
    for col, label in [(1, "№"), (2, "Фамилия И.О."), (3, "Должность")]:
        c = ws.cell(row=row_h1, column=col, value=label)
        c.font = f_head
        c.alignment = center
        c.fill = header_fill
        ws.merge_cells(start_row=row_h1, start_column=col,
                       end_row=row_h2, end_column=col)

    start_days = 4
    end_days = start_days + days_in_month - 1
    ws.merge_cells(start_row=row_h1, start_column=start_days,
                   end_row=row_h1, end_column=end_days)
    c = ws.cell(row=row_h1, column=start_days, value="Числа месяца")
    c.font = f_head
    c.alignment = center
    c.fill = header_fill

    # Группы "Дни явок / Дни неявок / Отработано часов" — только по видимым
    start_r = end_days + 1
    for gname, gkeys in RIGHT_COLUMN_GROUPS:
        gvis_count = sum(1 for k in gkeys if k in visible_set)
        if gvis_count == 0:
            continue
        ws.merge_cells(start_row=row_h1, start_column=start_r,
                       end_row=row_h1, end_column=start_r + gvis_count - 1)
        c = ws.cell(row=row_h1, column=start_r, value=gname)
        c.font = f_head
        c.alignment = center
        c.fill = header_fill
        start_r += gvis_count

    # Заголовки дней месяца (row_h2)
    for i, dt in enumerate(day_types):
        col = start_days + i
        wd = WEEKDAYS_SHORT[date(y, m, i + 1).weekday()]
        c = ws.cell(row=row_h2, column=col, value=f"{i + 1}\n{wd}")
        c.font = f_cell
        c.alignment = Alignment(horizontal='center', vertical='top', wrap_text=True)
        if dt == 'weekend':
            c.fill = weekend_fill
        elif dt == 'holiday':
            c.fill = holiday_fill
        else:
            c.fill = header_fill

    # Заголовки правых колонок — только видимые
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
    # grand — по ВСЕМ колонкам (нужно для среднесписочной)
    grand = {k: 0 for _, k, _ in RIGHT_COLUMNS}
    grand['часы'] = 0.0
    grand['сверхурочные'] = 0.0
    grand['ночные'] = 0.0
    grand['праздничные'] = 0.0
    max_col_len = {k: 0 for k in visible_keys}
    max_day_len = {i: 1 for i in range(days_in_month)}

    for idx, emp in enumerate(employees):
        emp_id = emp['id']
        day_data = ts.get(emp_id, {})
        values = [day_data.get(str(d), '') for d in range(1, days_in_month + 1)]
        pos_name = emp.get('position', '')
        night_on = bool(night_flags.get(pos_name, False))
        overtime_on = bool(overtime_flags.get(pos_name, False))
        no_weekends_on = bool(no_weekends_flags.get(pos_name, False))
        res = analyze_row(values, day_types, night_on, no_weekends_on)
        if overtime_on:
            apply_overtime(res, norm_hours)
        else:
            res['сверхурочные'] = 0.0
        emp_over = overrides_all.get(emp_id, {})
        for k in grand:
            if k in emp_over:
                try:
                    grand[k] += float(str(emp_over[k]).replace(',', '.'))
                except (ValueError, TypeError):
                    pass
            else:
                grand[k] += res.get(k, 0)

        ws.cell(row=row, column=1, value=idx + 1).font = f_cell
        ws.cell(row=row, column=1).alignment = center

        c_name = ws.cell(row=row, column=2,
                         value=format_name(emp.get('name', '')))
        c_name.font = f_cell
        c_name.alignment = left

        pos_text = emp.get('position', '').replace('\n', ' ').strip()
        c_pos = ws.cell(row=row, column=3, value=pos_text)
        c_pos.font = f_cell
        c_pos.alignment = Alignment(horizontal='left', vertical='center',
                                    wrap_text=True)

        for i, v in enumerate(values):
            col = start_days + i
            if str(v).strip() == '0':
                v = None
            c = ws.cell(row=row, column=col, value=v)
            c.font = f_cell
            c.alignment = Alignment(horizontal='center', vertical='center')
            if v is not None:
                max_day_len[i] = max(max_day_len[i], len(str(v)))
            if day_types[i] == 'weekend':
                c.fill = weekend_fill
            elif day_types[i] == 'holiday':
                c.fill = holiday_fill

        start_r = end_days + 1
        for _, key_, _w in visible_columns:
            if key_ in emp_over:
                val = emp_over[key_]
            else:
                v = res.get(key_, 0)
                val = (fmt_hours(v)
                       if key_ in ('часы', 'сверхурочные', 'ночные',
                                   'праздничные', 'выходные_часы')
                       else v)
            if str(val).strip() in ('0', '0.0', '0.00'):
                val = None
            c = ws.cell(row=row, column=start_r, value=val)
            if val is not None:
                max_col_len[key_] = max(max_col_len[key_], len(str(val)))
            c.font = f_cell
            c.alignment = center
            start_r += 1

        num_lines = max(1, math.ceil(len(pos_text) / 20))
        ws.row_dimensions[row].height = max(45, num_lines * 20)
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

    ws.merge_cells(start_row=row, start_column=start_days,
                   end_row=row, end_column=end_days)
    for col in range(start_days, end_days + 1):
        ws.cell(row=row, column=col).border = border
        ws.cell(row=row, column=col).fill = total_fill

    start_r = end_days + 1
    for _, key_, _w in visible_columns:
        v = grand.get(key_, 0)
        val = (fmt_hours(v)
               if key_ in ('часы', 'сверхурочные', 'ночные',
                           'праздничные', 'выходные_часы')
               else v)
        if str(val).strip() in ('0', '0.0', '0.00'):
            val = None
        c = ws.cell(row=row, column=start_r, value=val)
        if val is not None:
            max_col_len[key_] = max(max_col_len[key_], len(str(val)))
        c.font = f_head
        c.alignment = center
        c.border = border
        c.fill = total_fill
        start_r += 1
    ws.row_dimensions[row].height = 28

    # ---------- Численность ----------
    spis_count = sum(1 for emp in employees if emp.get('is_contract', True))
    total_days = sum(grand[k] for k in grand
                     if k not in ('часы', 'сверхурочные', 'ночные', 'праздничные'))
    avg_count = total_days / days_in_month if days_in_month > 0 else 0

    row += 2
    ws.row_dimensions[row].height = 38
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
    c = ws.cell(row=row, column=1, value="Норма рабочего времени:")
    c.font = f_sig
    c.alignment = Alignment(horizontal='left', vertical='center')
    ws.merge_cells(start_row=row, start_column=8, end_row=row, end_column=10)
    c2 = ws.cell(row=row, column=8, value=f"{fmt_hours(norm_hours)} ч")
    c2.font = f_sig_bold
    c2.alignment = Alignment(horizontal='left', vertical='center')

    row += 1
    ws.row_dimensions[row].height = 38
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
    c = ws.cell(row=row, column=1, value="Списочная численность:")
    c.font = f_sig
    c.alignment = Alignment(horizontal='left', vertical='center')
    ws.merge_cells(start_row=row, start_column=8, end_row=row, end_column=10)
    c2 = ws.cell(row=row, column=8, value=spis_count)
    c2.font = f_sig_bold
    c2.alignment = Alignment(horizontal='left', vertical='center')

    row += 1
    ws.row_dimensions[row].height = 38
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
    c = ws.cell(row=row, column=1, value="Среднесписочная численность:")
    c.font = f_sig
    c.alignment = Alignment(horizontal='left', vertical='center')
    val_avg = round(avg_count, 2)
    if val_avg == int(val_avg):
        val_avg = int(val_avg)
    ws.merge_cells(start_row=row, start_column=8, end_row=row, end_column=10)
    c2 = ws.cell(row=row, column=8, value=val_avg)
    c2.font = f_sig_bold
    c2.alignment = Alignment(horizontal='left', vertical='center')

    # ---------- Ширины столбцов ----------
    ws.column_dimensions['A'].width = 5
    max_name_len = max(
        (len(format_name(emp.get('name', '') or '')) for emp in employees),
        default=15)
    ws.column_dimensions['B'].width = max(20, max_name_len * 1.2 + 5)
    max_pos_len = max(
        (len(emp.get('position', '') or '') for emp in employees),
        default=15)
    ws.column_dimensions['C'].width = max(16, min(max_pos_len * 1.2 + 5, 35))
    
    # Авто-ширина для колонок дней месяца
    for i in range(days_in_month):
        w = max(4.5, max_day_len[i] * 1.2 + 2.0)
        ws.column_dimensions[get_column_letter(start_days + i)].width = w

    for i, (_, key_, _w) in enumerate(visible_columns):
        col_letter = get_column_letter(end_days + 1 + i)
        calc_width = max(6.5, max_col_len[key_] * 1.2 + 2.0)
        if key_ in ('явки', 'целосмен_простой'):
            calc_width = max(calc_width, 7.5)
        ws.column_dimensions[col_letter].width = calc_width

    ws.row_dimensions[1].height = 45
    ws.row_dimensions[2].height = 35
    ws.row_dimensions[3].height = 35
    ws.row_dimensions[4].height = 24
    ws.row_dimensions[row_h1].height = 30
    ws.row_dimensions[row_h2].height = 150

    # ---------- Подписи ----------
    row += 1
    LEFT_COL = 3
    sig_row = row + 2

    c = ws.cell(row=sig_row, column=LEFT_COL, value=signer_pos)
    c.font = f_sig
    c.alignment = Alignment(horizontal='left', vertical='center')
    sig_name_col = min(LEFT_COL + 29, total_cols)
    c = ws.cell(row=sig_row, column=sig_name_col, value=signer_name)
    c.font = f_sig
    c.alignment = Alignment(horizontal='left', vertical='center')

    additional_signers = get_local_signers()
    active_add = [s for s in additional_signers if s.get('active', True)]
    for s in active_add:
        sig_row += 7
        c = ws.cell(row=sig_row, column=LEFT_COL, value=s.get('position', ''))
        c.font = f_sig
        c.alignment = Alignment(horizontal='left', vertical='center')
        c = ws.cell(row=sig_row, column=sig_name_col, value=s.get('name', ''))
        c.font = f_sig
        c.alignment = Alignment(horizontal='left', vertical='center')

    last_print_row = sig_row + 2

    if tab.legend_cb.active:
        legend_start_row = sig_row + 4
        last_print_row = _draw_legend(ws, legend_start_row, total_cols,
                                      border, header_fill)

    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    try:
        ws.print_area = f"A1:{get_column_letter(total_cols)}{last_print_row}"
    except Exception:
        pass

    _save_and_open(ws, wb, y, dept, key, "_full")


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
    overrides_all = tab.app.data.get('result_overrides', {}).get(key, {})

    day_types = [classify_day(y, m, d) for d in range(1, days_in_month + 1)]
    norm_hours, work_days, pre_count = calc_norm_hours(y, m)

    thin = Side(border_style="thin", color="333333")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal='center', vertical='center')
    left = Alignment(horizontal='left', vertical='center')
    header_fill = PatternFill("solid", fgColor="E8E8E8")
    weekend_fill = PatternFill("solid", fgColor="FFDEDE")
    holiday_fill = PatternFill("solid", fgColor="FFF3CC")
    total_fill = PatternFill("solid", fgColor="D0D0D0")
    f_title = Font(name=EXCEL_FONT, size=23, bold=True, italic=True)
    f_date_bold = Font(name=EXCEL_FONT, size=23, bold=True)
    f_date_norm = Font(name=EXCEL_FONT, size=23)
    f_italic = Font(name=EXCEL_FONT, size=23, italic=True)
    f_italic_ul = Font(name=EXCEL_FONT, size=23, italic=True, underline='single')
    f_head = Font(name=EXCEL_FONT, size=12, bold=True)
    f_cell = Font(name=EXCEL_FONT, size=12)
    f_norm_lbl = Font(name=EXCEL_FONT, size=23)
    f_norm_val = Font(name=EXCEL_FONT, size=23, bold=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{MONTHS[m-1]} {y}"
    total_cols = 2 + days_in_month + 2
    title_end = 16
    date_start = 18
    date_end = 24
    days_start = 26
    days_end = total_cols

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=title_end)
    c = ws.cell(row=1, column=1, value="табель учета использования рабочего времени")
    c.font = f_title
    c.alignment = Alignment(horizontal='left', vertical='center')
    ws.merge_cells(start_row=1, start_column=date_start,
                   end_row=1, end_column=date_end)
    c = ws.cell(row=1, column=date_start, value=f"{y}, {MONTHS[m-1].lower()}")
    c.font = f_date_bold
    c.alignment = Alignment(horizontal='center', vertical='center')
    ws.merge_cells(start_row=1, start_column=days_start,
                   end_row=1, end_column=days_end)
    c = ws.cell(row=1, column=days_start, value=f"({days_in_month} календарных дней)")
    c.font = f_date_norm
    c.alignment = Alignment(horizontal='center', vertical='center')

    ws.merge_cells('A2:E2')
    c = ws.cell(row=2, column=1, value="Предприятие")
    c.font = f_italic
    c.alignment = Alignment(horizontal='left', vertical='center')
    ws.merge_cells(start_row=2, start_column=6, end_row=2, end_column=title_end + 3)
    c = ws.cell(row=2, column=6, value=org)
    c.font = f_italic_ul
    c.alignment = Alignment(horizontal='left', vertical='center', indent=2)
    ws.merge_cells('A3:E3')
    c = ws.cell(row=3, column=1, value="Отдел, цех, участок")
    c.font = f_italic
    c.alignment = Alignment(horizontal='left', vertical='center')
    ws.merge_cells(start_row=3, start_column=6, end_row=3, end_column=title_end + 3)
    c = ws.cell(row=3, column=6, value=dept)
    c.font = f_italic_ul
    c.alignment = Alignment(horizontal='left', vertical='center', indent=2)

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

    start_days = 3
    end_days = start_days + days_in_month - 1
    ws.merge_cells(start_row=row_h1, start_column=start_days,
                   end_row=row_h1, end_column=end_days)
    c = ws.cell(row=row_h1, column=start_days, value="Числа месяца")
    c.font = f_head
    c.alignment = center
    c.fill = header_fill

    col_hours = end_days + 1
    c = ws.cell(row=row_h1, column=col_hours, value="Всего")
    c.font = f_head
    c.alignment = center
    c.fill = header_fill
    ws.merge_cells(start_row=row_h1, start_column=col_hours,
                   end_row=row_h2, end_column=col_hours)
    col_off = end_days + 2
    c = ws.cell(row=row_h1, column=col_off, value="Выходные")
    c.font = f_head
    c.alignment = center
    c.fill = header_fill
    ws.merge_cells(start_row=row_h1, start_column=col_off,
                   end_row=row_h2, end_column=col_off)

    for i, dt in enumerate(day_types):
        col = start_days + i
        wd = WEEKDAYS_SHORT[date(y, m, i + 1).weekday()]
        c = ws.cell(row=row_h2, column=col, value=f"{i + 1}\n{wd}")
        c.font = f_cell
        c.alignment = Alignment(horizontal='center', vertical='top', wrap_text=True)
        if dt == 'weekend':
            c.fill = weekend_fill
        elif dt == 'holiday':
            c.fill = holiday_fill
        else:
            c.fill = header_fill

    for r in (row_h1, row_h2):
        for col in range(1, total_cols + 1):
            ws.cell(row=r, column=col).border = border

    row = row_h2 + 1
    grand = {'часы': 0.0, 'вых': 0}
    max_col_len = {'часы': len("Всего"), 'вых': len("Выходные")}
    max_day_len = {i: 1 for i in range(days_in_month)}

    for idx, emp in enumerate(employees):
        emp_id = emp['id']
        day_data = ts.get(emp_id, {})
        values = [day_data.get(str(d), '') for d in range(1, days_in_month + 1)]
        pos_name = emp.get('position', '')
        night_on = bool(night_flags.get(pos_name, False))
        no_weekends_on = bool(no_weekends_flags.get(pos_name, False))
        res = analyze_row(values, day_types, night_on, no_weekends_on)
        emp_over = overrides_all.get(emp_id, {})

        if 'часы' in emp_over:
            try:
                hours_val = float(str(emp_over['часы']).replace(',', '.'))
            except Exception:
                hours_val = res.get('часы', 0.0)
        else:
            hours_val = res.get('часы', 0.0)

        if 'вых' in emp_over:
            try:
                off_val = int(float(str(emp_over['вых']).replace(',', '.')))
            except Exception:
                off_val = res.get('вых', 0)
        else:
            off_val = res.get('вых', 0)

        grand['часы'] += hours_val
        grand['вых'] += off_val

        ws.cell(row=row, column=1, value=idx + 1).font = f_cell
        ws.cell(row=row, column=1).alignment = center
        c_name = ws.cell(row=row, column=2, value=format_name(emp.get('name', '')))
        c_name.font = f_cell
        c_name.alignment = left

        for i, v in enumerate(values):
            col = start_days + i
            if str(v).strip() == '0':
                v = None
            c = ws.cell(row=row, column=col, value=v)
            c.font = f_cell
            c.alignment = Alignment(horizontal='center', vertical='center')
            if v is not None:
                max_day_len[i] = max(max_day_len[i], len(str(v)))
            if day_types[i] == 'weekend':
                c.fill = weekend_fill
            elif day_types[i] == 'holiday':
                c.fill = holiday_fill

        hours_val_fmt = fmt_hours(hours_val)
        if str(hours_val_fmt).strip() in ('0', '0.0'):
            hours_val_fmt = None
        c = ws.cell(row=row, column=col_hours, value=hours_val_fmt)
        if hours_val_fmt is not None:
            max_col_len['часы'] = max(max_col_len['часы'], len(str(hours_val_fmt)))
        c.font = f_cell
        c.alignment = center

        off_val_fmt = off_val
        if str(off_val_fmt).strip() in ('0', '0.0'):
            off_val_fmt = None
        c = ws.cell(row=row, column=col_off, value=off_val_fmt)
        if off_val_fmt is not None:
            max_col_len['вых'] = max(max_col_len['вых'], len(str(off_val_fmt)))
        c.font = f_cell
        c.alignment = center

        ws.row_dimensions[row].height = 32
        for col in range(1, total_cols + 1):
            ws.cell(row=row, column=col).border = border
        row += 1

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    c = ws.cell(row=row, column=1, value="ИТОГО")
    c.font = f_head
    c.alignment = center
    for col in range(1, 3):
        ws.cell(row=row, column=col).border = border
        ws.cell(row=row, column=col).fill = total_fill
    ws.merge_cells(start_row=row, start_column=start_days,
                   end_row=row, end_column=end_days)
    for col in range(start_days, end_days + 1):
        ws.cell(row=row, column=col).border = border
        ws.cell(row=row, column=col).fill = total_fill

    grand_hours_fmt = fmt_hours(grand['часы'])
    if str(grand_hours_fmt).strip() in ('0', '0.0'):
        grand_hours_fmt = None
    c = ws.cell(row=row, column=col_hours, value=grand_hours_fmt)
    if grand_hours_fmt is not None:
        max_col_len['часы'] = max(max_col_len['часы'], len(str(grand_hours_fmt)))
    c.font = f_head
    c.alignment = center
    c.border = border
    c.fill = total_fill

    grand_off_fmt = grand['вых']
    if str(grand_off_fmt).strip() in ('0', '0.0'):
        grand_off_fmt = None
    c = ws.cell(row=row, column=col_off, value=grand_off_fmt)
    if grand_off_fmt is not None:
        max_col_len['вых'] = max(max_col_len['вых'], len(str(grand_off_fmt)))
    c.font = f_head
    c.alignment = center
    c.border = border
    c.fill = total_fill
    ws.row_dimensions[row].height = 28

    row += 1
    ws.row_dimensions[row].height = 32
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
    c = ws.cell(row=row, column=1, value="Норма рабочего времени:")
    c.font = f_norm_lbl
    c.alignment = Alignment(horizontal='left', vertical='center')
    ws.merge_cells(start_row=row, start_column=8, end_row=row, end_column=10)
    c2 = ws.cell(row=row, column=8, value=f"{fmt_hours(norm_hours)} ч")
    c2.font = f_norm_val
    c2.alignment = Alignment(horizontal='left', vertical='center')

    ws.column_dimensions['A'].width = 5
    max_name_len = max(
        (len(format_name(emp.get('name', '') or '')) for emp in employees),
        default=15)
    ws.column_dimensions['B'].width = max(20, max_name_len * 1.2 + 5)
    
    # Авто-ширина для колонок дней месяца
    for i in range(days_in_month):
        w = max(4.5, max_day_len[i] * 1.2 + 1.0)
        ws.column_dimensions[get_column_letter(start_days + i)].width = w
        
    col_h = get_column_letter(col_hours)
    ws.column_dimensions[col_h].width = max(7.5, max_col_len['часы'] * 1.2 + 2.0)
    col_o = get_column_letter(col_off)
    ws.column_dimensions[col_o].width = max(9.5, max_col_len['вых'] * 1.2 + 2.0)

    ws.row_dimensions[1].height = 45
    ws.row_dimensions[2].height = 30
    ws.row_dimensions[3].height = 30
    ws.row_dimensions[4].height = 24
    ws.row_dimensions[row_h1].height = 30
    ws.row_dimensions[row_h2].height = 50

    if tab.legend_cb.active:
        row += 4
        row = _draw_legend(ws, row, total_cols, border, header_fill)

    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    try:
        ws.print_area = f"A1:{get_column_letter(total_cols)}{row}"
    except Exception:
        pass

    _save_and_open(ws, wb, y, dept, key, "_short")


def _save_and_open(ws, wb, y, dept, key, suffix):
    def _sanitize_folder(name):
        bad = '\\/:*?"<>|'
        for ch in bad:
            name = name.replace(ch, '_')
        return name.strip() or 'Без отдела'

    dept_folder = _sanitize_folder(dept)
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
    try:
        os.startfile(path)
    except Exception:
        try:
            webbrowser.open(f"file://{path}")
        except Exception:
            pass