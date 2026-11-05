# tab_report.py
# -*- coding: utf-8 -*-
"""Вкладка «Отчёт и печать» и экспорт в Excel."""
import config  # noqa: F401

import os
import webbrowser
import math
from calendar import monthrange
from datetime import datetime, date
from ui_helpers import NoOverscrollEffect

from kivy.metrics import dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from ui_widgets import HoverButton as Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget
from kivy.uix.checkbox import CheckBox
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock
from ui_widgets import CenteredField, LightSpinnerOption

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

from config import (FONT_NAME, LABEL_LIGHT, MONTHS, YEARS,
                    SPINNER_BG, SPINNER_FG, RIGHT_COLUMNS,
                    WEEKDAYS_SHORT, DEFAULT_ORG, BASE_DIR,
                    DEFAULT_ENERGETIC, DEFAULT_DIRECTOR)
from data_utils import (save_data, classify_day, analyze_row,
                        apply_overtime, fmt_hours, calc_norm_hours,
                        set_local_show_legend, get_local_show_legend)
from ui_widgets import CenteredField

# Базовый шрифт для Excel
EXCEL_FONT = 'Times New Roman'


def format_name(name):
    """Приводит 'Фамилия Имя Отчество' к виду 'Фамилия И.О.'"""
    if not name:
        return ''
    parts = str(name).split()
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1][0]}.{parts[2][0]}."
    elif len(parts) == 2:
        if len(parts[1]) > 1 and not parts[1].endswith('.'):
            return f"{parts[0]} {parts[1][0]}."
    return str(name)


class ReportTab(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app

        with self.canvas.before:
            Color(*config.TABLE_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda i, v: setattr(self._bg, 'pos', v),
                  size=lambda i, v: setattr(self._bg, 'size', v))

        self._build()
        Clock.schedule_once(lambda *a: self.update_preview(), 0.3)

    def _build(self):
        top = BoxLayout(size_hint_y=None, height=dp(52), spacing=5, padding=5)

        top.add_widget(Label(text="Месяц:", size_hint_x=None, width=dp(70),
                             color=LABEL_LIGHT, font_name=FONT_NAME,
                             font_size=dp(15)))
        self.month_spinner = Spinner(text=MONTHS[datetime.now().month - 1],
                                     values=MONTHS, size_hint_x=None, width=dp(150),
                                     font_name=FONT_NAME,
                                     background_color=SPINNER_BG, color=SPINNER_FG,
                                     option_cls=LightSpinnerOption) # <--- ДОБАВИТЬ ЭТО
        top.add_widget(self.month_spinner)

        top.add_widget(Label(text="Год:", size_hint_x=None, width=dp(50),
                             color=LABEL_LIGHT, font_name=FONT_NAME,
                             font_size=dp(15)))
        self.year_spinner = Spinner(text=str(datetime.now().year),
                                    values=YEARS, size_hint_x=None, width=dp(100),
                                    font_name=FONT_NAME,
                                    background_color=SPINNER_BG, color=SPINNER_FG,
                                    option_cls=LightSpinnerOption) # <--- ДОБАВИТЬ ЭТО
        top.add_widget(self.year_spinner)

        # Распорка, которая отодвигает чекбокс и кнопки к правому краю
        top.add_widget(Widget())

        # Чекбокс для условных обозначений (расположен прямо перед кнопками)
        legend_box = BoxLayout(size_hint_x=None, width=dp(220), spacing=dp(4), padding=(0, 0, dp(10), 0))
        
        # Берем сохраненное значение из локальных настроек
        is_legend_on = get_local_show_legend()
        self.legend_cb = CheckBox(active=is_legend_on, size_hint_x=None, width=dp(30), color=(1, 1, 1, 1))
        
        # При клике сохраняем новое значение в local.json
        self.legend_cb.bind(active=lambda inst, val: set_local_show_legend(val))
        
        legend_lbl = Label(text="Условные обозначения", color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(14))
        legend_box.add_widget(self.legend_cb)
        legend_box.add_widget(legend_lbl)
        top.add_widget(legend_box)

        excel_btn = Button(text="Сохранить в Excel",
                           size_hint_x=None, width=dp(200),
                           font_name=FONT_NAME, font_size=dp(15), bold=True,
                           background_color=(0.25, 0.55, 0.30, 1),
                           color=(1, 1, 1, 1))
        excel_btn.bind(on_press=self.save_excel)
        top.add_widget(excel_btn)

        excel_short_btn = Button(text="Кратко в Excel",
                                 size_hint_x=None, width=dp(170),
                                 font_name=FONT_NAME, font_size=dp(15), bold=True,
                                 background_color=(0.20, 0.45, 0.55, 1),
                                 color=(1, 1, 1, 1))
        excel_short_btn.bind(on_press=self.save_excel_short)
        top.add_widget(excel_short_btn)

        self.add_widget(top)

        self.month_spinner.bind(text=lambda *a: self.update_preview())
        self.year_spinner.bind(text=lambda *a: self.update_preview())

        line = Widget(size_hint_y=None, height=dp(2))
        with line.canvas:
            Color(0.5, 0.5, 0.5, 1)
            line._rect = Rectangle(pos=line.pos, size=line.size)
        line.bind(pos=lambda i, v: setattr(i._rect, 'pos', v),
                  size=lambda i, v: setattr(i._rect, 'size', v))
        self.add_widget(line)

        scroll = ScrollView(scroll_type=['bars'],
                            effect_cls=NoOverscrollEffect)
        self.preview = Label(text="", size_hint_y=None, halign='left',
                              valign='top', padding=(20, 20),
                              font_name=FONT_NAME,
                              font_size=dp(13), color=config.TABLE_FG)
        self.preview.bind(width=lambda *a: setattr(
            self.preview, 'text_size', (self.preview.width - 40, None)))
        self.preview.bind(texture_size=self.preview.setter('size'))
        scroll.add_widget(self.preview)
        self.add_widget(scroll)

    def _get_signer(self, dept):
        signers = self.app.data.get('department_signer', {}) or {}
        entry = signers.get(dept)
        if entry and entry.get('name'):
            return (entry.get('position') or 'Энергетик',
                    entry.get('name'))
        em = self.app.data.get('department_energetic', {}) or {}
        name = em.get(dept) or self.app.data.get('energetic_name',
                                                 DEFAULT_ENERGETIC)
        return ('Энергетик', name)

    def _employees_for_report(self):
        y = int(self.year_spinner.text)
        m = MONTHS.index(self.month_spinner.text) + 1
        key = f"{y}-{m:02d}"

        emps = [emp for emp in self.app.data['employees'] if emp.get('show_in_timesheet', False)]
        dept = emps[0].get('department', '') if emps else ''

        month_dict = self.app.data.get('extra_employees', {}).get(key, {})
        if isinstance(month_dict, list):
            month_dict = {'': month_dict}

        extra = month_dict.get(dept, [])

        for e in extra:
            e['is_extra'] = True
        return emps + extra

    def _get_dept(self):
        emps = self._employees_for_report()
        if emps:
            return emps[0].get('department', '')
        return ''

    def _calc_grand(self):
        y = int(self.year_spinner.text)
        m = MONTHS.index(self.month_spinner.text) + 1
        key = f"{y}-{m:02d}"
        days_in_month = monthrange(y, m)[1]
        ts = self.app.data['timesheets'].get(key, {})
        employees = self._employees_for_report()
        night_flags = self.app.data.get('night_flags', {})
        overtime_flags = self.app.data.get('overtime_flags', {})
        no_weekends_flags = self.app.data.get('no_weekends_flags', {})
        day_types = [classify_day(y, m, d)
                     for d in range(1, days_in_month + 1)]
        # Норма с учётом предпраздничных дней (−1 час за каждый)
        norm_hours, work_days, pre_count = calc_norm_hours(y, m)
        overrides_all = self.app.data.get('result_overrides', {}).get(key, {})

        grand = {k: 0 for _, k, _ in RIGHT_COLUMNS}
        grand['часы'] = 0.0
        grand['сверхурочные'] = 0.0
        grand['ночные'] = 0.0
        grand['праздничные'] = 0.0

        for emp in employees:
            emp_id = emp['id']
            day_data = ts.get(emp_id, {})
            values = [day_data.get(str(d), '')
                      for d in range(1, days_in_month + 1)]
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
        return grand, days_in_month, work_days, norm_hours, pre_count, key

    def update_preview(self):
        y = int(self.year_spinner.text)
        m = MONTHS.index(self.month_spinner.text) + 1
        key = f"{y}-{m:02d}"
        days_in_month = monthrange(y, m)[1]
        ts = self.app.data['timesheets'].get(key, {})
        employees = self._employees_for_report()
        night_flags = self.app.data.get('night_flags', {})
        overtime_flags = self.app.data.get('overtime_flags', {})
        no_weekends_flags = self.app.data.get('no_weekends_flags', {})
        org = self.app.data.get('organization', DEFAULT_ORG)
        dept = self._get_dept()
        signer_pos, signer_name = self._get_signer(dept)
        director_name = self.app.data.get('director_name', DEFAULT_DIRECTOR)

        if not employees:
            self.preview.text = "Нет сотрудников, отмеченных «В табель»."
            return

        grand, days_in_month, work_days, norm_hours, pre_count, key = \
            self._calc_grand()

        spis_count = sum(1 for emp in employees if emp.get('is_contract', True))
        total_days = sum(grand[k] for k in grand
                         if k not in ('часы', 'сверхурочные', 'ночные',
                                      'праздничные'))
        avg_count = total_days / days_in_month if days_in_month > 0 else 0

        if pre_count > 0:
            norm_line = (f"  Норма: {work_days} будних × 8 − "
                         f"{pre_count} предпраздн. = "
                         f"{fmt_hours(norm_hours)} ч")
        else:
            norm_line = (f"  Норма: {work_days} будних × 8 = "
                         f"{fmt_hours(norm_hours)} ч")

        sep = "─" * 90
        lines = [
            "  ТАБЕЛЬ УЧЁТА РАБОЧЕГО ВРЕМЕНИ",
            f"  Период: {MONTHS[m-1]} {y}   ({days_in_month} календарных дней)",
            f"  Организация: {org}",
            f"  Отдел: {dept}",
            norm_line,
            sep,
            f"  Сотрудников: {len(employees)}",
            f"  Списочная численность: {spis_count}",
            f"  Среднесписочная численность: {avg_count:.2f}",
            f"  Факт. работы: {grand.get('явки', 0)}    "
            f"Выходных: {grand.get('вых', 0)}    "
            f"Труд. отпуск: {grand.get('отп', 0)}    "
            f"Болезнь: {grand.get('бол', 0)}    "
            f"За свой счёт: {grand.get('за_свой', 0)}",
            f"  Прогул: {grand.get('прогул', 0)}    "
            f"Текущий простой: {grand.get('текущий_простой', 0)}    "
            f"Опоздания: {grand.get('опозд', 0)}    "
            f"Целосмен.простой: {grand.get('целосмен_простой', 0)}",
            f"  Роды: {grand.get('отп_роды', 0)}    "
            f"Проч.неявки: {grand.get('проч_неявки', 0)}",
            f"  Всего часов: {fmt_hours(grand.get('часы', 0))}    "
            f"Сверхурочные: {fmt_hours(grand.get('сверхурочные', 0))}    "
            f"Ночные: {fmt_hours(grand.get('ночные', 0))}    "
            f"Праздничные: {fmt_hours(grand.get('праздничные', 0))}",
            f"  Подписи: {signer_pos} — {signer_name}    "
            f"Директор — {director_name}",
            sep,
            "",
            "  По сотрудникам:",
        ]

        name_w = 26
        day_types = [classify_day(y, m, d)
                     for d in range(1, days_in_month + 1)]
        for idx, emp in enumerate(employees):
            emp_id = emp['id']
            day_data = ts.get(emp_id, {})
            values = [day_data.get(str(d), '')
                      for d in range(1, days_in_month + 1)]
            pos_name = emp.get('position', '')
            night_on = bool(night_flags.get(pos_name, False))
            overtime_on = bool(overtime_flags.get(pos_name, False))
            no_weekends_on = bool(no_weekends_flags.get(pos_name, False))
            res = analyze_row(values, day_types, night_on, no_weekends_on)
            if overtime_on:
                apply_overtime(res, norm_hours)
            else:
                res['сверхурочные'] = 0.0
            nm = (format_name(emp.get('name', '') or ''))[:name_w].ljust(name_w)
            lines.append(
                f"   {idx + 1:>2}. {nm} "
                f"явок {res['явки']:>2}  часов {fmt_hours(res['часы']):>7}  "
                f"сверхур {fmt_hours(res['сверхурочные']):>5}  "
                f"празд {fmt_hours(res['праздничные']):>5}  "
                f"В {res['вых']:>2}  О {res['отп']:>2}  Б {res['бол']:>2}"
            )

        lines += ["", sep,
                  "  Нажмите «Сохранить в Excel», чтобы получить файл .xlsx"]
        self.preview.text = "\n".join(lines)

    def _draw_legend(self, ws, row, total_cols, border, header_fill):
        """Рисует блок условных обозначений и возвращает номер следующей строки."""
        ws.merge_cells(start_row=row, start_column=1, end_row=row + 1, end_column=total_cols)
        c = ws.cell(row=row, column=1, value="Условные обозначения (вводятся так же, как на странице «Табель»):")
        c.font = Font(name=EXCEL_FONT, size=23, bold=True)
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

        for r_header in (row, row + 1):
            for col in range(1, total_cols + 1):
                ws.cell(row=r_header, column=col).border = border
                ws.cell(row=r_header, column=col).fill = header_fill

        row += 2

        hints = [
            ('В', 'выходной'), ('О', 'трудовой отпуск'), ('Б', 'больничный'),
            ('А', 'за свой счёт'), ('Р', 'отпуск по родам'), ('Н', 'прочие неявки'),
            ('ДМ', 'день матери'), ('П', 'прогул'), ('Т', 'текущий простой'),
            ('Ц', 'целосменный простой'), ('У', 'опоздание'), ('8д', 'часы без ночных (8 тоже)'),
            ('8//N', 'часы // смена (и /)')
        ]

        blocks = 3
        block_width = total_cols // blocks
        start_row_hints = row

        for i, (code, desc) in enumerate(hints):
            r = start_row_hints + (i // blocks)
            b = i % blocks

            c_start = b * block_width + 1
            c_end = (b + 1) * block_width if b < blocks - 1 else total_cols

            c_code_start = c_start
            c_code_end = min(c_start + 2, c_end)
            ws.merge_cells(start_row=r, start_column=c_code_start, end_row=r, end_column=c_code_end)
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
                ws.merge_cells(start_row=r, start_column=c_desc_start, end_row=r, end_column=c_end)
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

                has_data = False
                for i in range(len(hints)):
                    if start_row_hints + (i // blocks) == r and (i % blocks) == b:
                        has_data = True
                        break

                if not has_data:
                    ws.merge_cells(start_row=r, start_column=c_start, end_row=r, end_column=c_end)
                    for col in range(c_start, c_end + 1):
                        ws.cell(row=r, column=col).border = border

        return last_r + 1

    def save_excel(self, *a):
        if not HAS_OPENPYXL:
            from kivy.uix.scrollview import ScrollView as _SV
            msg = ("Не удалось загрузить openpyxl в собранной программе.\n\n"
                   "Техническая информация:\n"
                   f"{OPENPYXL_ERR}")
            inner = BoxLayout(orientation='vertical', spacing=8, padding=8)
            sv = _SV()
            lbl = Label(text=msg, color=LABEL_LIGHT, halign='left',
                        valign='top', font_name=FONT_NAME, font_size=dp(13))
            lbl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
            lbl.bind(texture_size=lbl.setter('size'))
            sv.add_widget(lbl)
            inner.add_widget(sv)
            ok_btn = Button(text="OK", size_hint_y=None, height=dp(40),
                            font_name=FONT_NAME, font_size=dp(16), bold=True,
                            background_color=(0.3, 0.7, 0.3, 1),
                            color=(1, 1, 1, 1))
            inner.add_widget(ok_btn)
            popup = Popup(title="Нужен openpyxl", content=inner,
                          size_hint=(0.85, 0.55),
                          title_color=LABEL_LIGHT, title_font=FONT_NAME,
                          auto_dismiss=False)
            ok_btn.bind(on_press=popup.dismiss)
            popup.open()
            return

        y = int(self.year_spinner.text)
        m = MONTHS.index(self.month_spinner.text) + 1
        key = f"{y}-{m:02d}"
        days_in_month = monthrange(y, m)[1]
        ts = self.app.data['timesheets'].get(key, {})
        employees = self._employees_for_report()
        night_flags = self.app.data.get('night_flags', {})
        overtime_flags = self.app.data.get('overtime_flags', {})
        no_weekends_flags = self.app.data.get('no_weekends_flags', {})
        org = self.app.data.get('organization', DEFAULT_ORG)
        dept = self._get_dept()
        signer_pos, signer_name = self._get_signer(dept)
        director_name = self.app.data.get('director_name', DEFAULT_DIRECTOR)

        day_types = [classify_day(y, m, d)
                     for d in range(1, days_in_month + 1)]
        # Норма с учётом предпраздничных дней
        norm_hours, work_days, pre_count = calc_norm_hours(y, m)
        overrides_all = self.app.data.get('result_overrides', {}).get(key, {})

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

        # ШРИФТЫ (Times New Roman)
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

        total_cols = 3 + days_in_month + len(RIGHT_COLUMNS)

        # ВЕРХНЯЯ ШАПКА (жесткие границы, сдвинуто влево)
        right_anchor = total_cols
        approve_col = right_anchor - 17

        title_end = 13   
        date_start = 14  
        date_end = 21    
        days_start = 23  
        days_end = approve_col - 1 

        # Название
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=title_end)
        c = ws.cell(row=1, column=1, value="табель учета использования рабочего времени")
        c.font = f_title
        c.alignment = Alignment(horizontal='left', vertical='center')

        # Дата
        ws.merge_cells(start_row=1, start_column=date_start, end_row=1, end_column=date_end)
        c = ws.cell(row=1, column=date_start, value=f"{y}, {MONTHS[m-1].lower()}")
        c.font = f_date_bold
        c.alignment = Alignment(horizontal='center', vertical='center')

        # Календарные дни
        ws.merge_cells(start_row=1, start_column=days_start, end_row=1, end_column=days_end)
        c = ws.cell(row=1, column=days_start, value=f"({days_in_month} календарных дней)")
        c.font = f_date_norm
        c.alignment = Alignment(horizontal='center', vertical='center')

        # ВОССТАНОВЛЕННЫЕ НАДПИСИ
        # Предприятие
        ws.merge_cells('A2:C2')
        c = ws.cell(row=2, column=1, value="Предприятие")
        c.font = f_italic
        c.alignment = Alignment(horizontal='left', vertical='center')

        ws.merge_cells(start_row=2, start_column=4, end_row=2, end_column=title_end + 3)
        c = ws.cell(row=2, column=4, value=org)
        c.font = f_italic_ul
        c.alignment = Alignment(horizontal='left', vertical='center', indent=2)

        # Отдел
        ws.merge_cells('A3:C3')
        c = ws.cell(row=3, column=1, value="Отдел, цех, участок")
        c.font = f_italic
        c.alignment = Alignment(horizontal='left', vertical='center')

        ws.merge_cells(start_row=3, start_column=4, end_row=3, end_column=title_end + 3)
        c = ws.cell(row=3, column=4, value=dept)
        c.font = f_italic_ul
        c.alignment = Alignment(horizontal='left', vertical='center', indent=2)

        # Утверждаю
        ws.merge_cells(start_row=1, start_column=approve_col, end_row=1, end_column=approve_col + 4)
        c = ws.cell(row=1, column=approve_col, value="Утверждаю:")
        c.font = f_sig
        c.alignment = Alignment(horizontal='center', vertical='center')

        # Директор
        director_col = right_anchor - 17
        ws.merge_cells(start_row=2, start_column=director_col, end_row=2, end_column=director_col + 4)
        c = ws.cell(row=2, column=director_col, value="Директор")
        c.font = f_sig
        c.alignment = Alignment(horizontal='center', vertical='center')

        # ФИО директора
        name_col = right_anchor - 9
        ws.merge_cells(start_row=2, start_column=name_col, end_row=2, end_column=right_anchor)
        c = ws.cell(row=2, column=name_col, value=director_name)
        c.font = f_sig
        c.alignment = Alignment(horizontal='center', vertical='center')

        # Заголовки таблицы
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

        start_r = end_days + 1
        # 5 колонок для "Отработано часов"
        for span, title in [(2, "Дни явок"), (9, "Дни неявок"), (5, "Отработано часов")]:
            ws.merge_cells(start_row=row_h1, start_column=start_r,
                           end_row=row_h1, end_column=start_r + span - 1)
            c = ws.cell(row=row_h1, column=start_r, value=title)
            c.font = f_head
            c.alignment = center
            c.fill = header_fill
            start_r += span

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

        start_r = end_days + 1
        for label, key_, _ in RIGHT_COLUMNS:
            c = ws.cell(row=row_h2, column=start_r, value=label)
            c.font = f_vert
            c.alignment = vert
            c.fill = header_fill
            start_r += 1

        for r in (row_h1, row_h2):
            for col in range(1, total_cols + 1):
                ws.cell(row=r, column=col).border = border

        row = row_h2 + 1
        grand = {k: 0 for _, k, _ in RIGHT_COLUMNS}
        grand['часы'] = 0.0
        grand['сверхурочные'] = 0.0
        grand['ночные'] = 0.0
        grand['праздничные'] = 0.0

        max_col_len = {k: 0 for _, k, _ in RIGHT_COLUMNS}

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
            c_pos.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)

            for i, v in enumerate(values):
                col = start_days + i
                if str(v).strip() == '0':
                    v = None
                c = ws.cell(row=row, column=col, value=v)
                c.font = f_cell
                c.alignment = Alignment(horizontal='center', vertical='center', shrink_to_fit=True)
                if day_types[i] == 'weekend':
                    c.fill = weekend_fill
                elif day_types[i] == 'holiday':
                    c.fill = holiday_fill

            # --- ВЫВОД ЗНАЧЕНИЙ В ПРАВЫЕ КОЛОНКИ ---
            start_r = end_days + 1
            for _, key_, _ in RIGHT_COLUMNS:
                if key_ in emp_over:
                    val = emp_over[key_]
                else:
                    v = res.get(key_, 0)
                    val = (fmt_hours(v) if key_ in ('часы', 'сверхурочные', 'ночные', 'праздничные', 'выходные_часы') else v)

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

        # --- СТРОКА "ИТОГО" ---
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
        for _, key_, _ in RIGHT_COLUMNS:
            v = grand.get(key_, 0)
            val = (fmt_hours(v) if key_ in ('часы', 'сверхурочные', 'ночные', 'праздничные', 'выходные_часы') else v)

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

        spis_count = sum(1 for emp in employees if emp.get('is_contract', True))
        total_days = sum(grand[k] for k in grand
                         if k not in ('часы', 'сверхурочные', 'ночные',
                                      'праздничные'))
        avg_count = total_days / days_in_month if days_in_month > 0 else 0

        row += 2

        # Норма рабочего времени
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

        # Списочная численность
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

        # Ширины колонок (оптимизированы)
        ws.column_dimensions['A'].width = 5
        
        max_name_len = max((len(format_name(emp.get('name', '') or ''))
                            for emp in employees), default=15)
        ws.column_dimensions['B'].width = max(20, max_name_len * 1.2 + 5)
        
        max_pos_len = max((len(emp.get('position', '') or '')
                           for emp in employees), default=15)
        ws.column_dimensions['C'].width = max(16, min(max_pos_len * 1.2 + 5, 35))
        
        for i in range(days_in_month):
            ws.column_dimensions[get_column_letter(start_days + i)].width = 5.0

        for i, (_, key_, _) in enumerate(RIGHT_COLUMNS):
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

        # Уменьшаем отступ перед подписями
        row += 1

        LEFT_COL = 3
        sig_row = row + 2

        c = ws.cell(row=sig_row, column=LEFT_COL, value=signer_pos)
        c.font = f_sig
        c.alignment = Alignment(horizontal='left', vertical='center')

        c = ws.cell(row=sig_row, column=LEFT_COL + 29, value=signer_name)
        c.font = f_sig
        c.alignment = Alignment(horizontal='left', vertical='center')

        last_print_row = sig_row + 2

        # Добавляем условные обозначения, если стоит галочка
        if self.legend_cb.active:
            legend_start_row = sig_row + 4
            last_print_row = self._draw_legend(ws, legend_start_row, total_cols, border, header_fill)

        ws.page_setup.orientation = 'landscape'
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True

        try:
            ws.print_area = f"A1:{get_column_letter(total_cols)}{last_print_row}"
        except Exception:
            pass

        def _sanitize_folder(name):
            bad = '\\/:*?"<>|'
            for ch in bad:
                name = name.replace(ch, '_')
            name = name.strip()
            return name or 'Без отдела'

        dept_folder = _sanitize_folder(dept)
        out_dir = os.path.join(BASE_DIR, "Табель", dept_folder, str(y))
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception as e:
            print("Не удалось создать папку:", e)

        path = os.path.join(out_dir, f"tabel_{key}.xlsx")

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

    def save_excel_short(self, *a):
        if not HAS_OPENPYXL:
            from kivy.uix.scrollview import ScrollView as _SV
            msg = ("Не удалось загрузить openpyxl в собранной программе.\n\n"
                   "Техническая информация:\n"
                   f"{OPENPYXL_ERR}")
            inner = BoxLayout(orientation='vertical', spacing=8, padding=8)
            sv = _SV()
            lbl = Label(text=msg, color=LABEL_LIGHT, halign='left',
                        valign='top', font_name=FONT_NAME, font_size=dp(13))
            lbl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
            lbl.bind(texture_size=lbl.setter('size'))
            sv.add_widget(lbl)
            inner.add_widget(sv)
            ok_btn = Button(text="OK", size_hint_y=None, height=dp(40),
                            font_name=FONT_NAME, font_size=dp(16), bold=True,
                            background_color=(0.3, 0.7, 0.3, 1),
                            color=(1, 1, 1, 1))
            inner.add_widget(ok_btn)
            popup = Popup(title="Нужен openpyxl", content=inner,
                          size_hint=(0.85, 0.55),
                          title_color=LABEL_LIGHT, title_font=FONT_NAME,
                          auto_dismiss=False)
            ok_btn.bind(on_press=popup.dismiss)
            popup.open()
            return

        y = int(self.year_spinner.text)
        m = MONTHS.index(self.month_spinner.text) + 1
        key = f"{y}-{m:02d}"
        days_in_month = monthrange(y, m)[1]
        ts = self.app.data['timesheets'].get(key, {})
        employees = self._employees_for_report()
        night_flags = self.app.data.get('night_flags', {})
        no_weekends_flags = self.app.data.get('no_weekends_flags', {})
        org = self.app.data.get('organization', DEFAULT_ORG)
        dept = self._get_dept()
        overrides_all = self.app.data.get('result_overrides', {}).get(key, {})

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

        # ШРИФТЫ (Times New Roman) — 23 размер
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

        # ВЕРХНЯЯ ШАПКА (сдвинуто и расширено)
        title_end = 16   # Заголовку добавили 1 колонку справа
        date_start = 18  # Начинаем дату с 18-й (17-я будет пустой для отступа)
        date_end = 24    # Дате добавили 1 колонку справа (теперь 7 колонок вместо 6)
        days_start = 26  # Начинаем дни с 26-й (25-я пустая для отступа)
        days_end = total_cols

        # Название
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=title_end)
        c = ws.cell(row=1, column=1, value="табель учета использования рабочего времени")
        c.font = f_title
        c.alignment = Alignment(horizontal='left', vertical='center')

        # Дата
        ws.merge_cells(start_row=1, start_column=date_start, end_row=1, end_column=date_end)
        c = ws.cell(row=1, column=date_start, value=f"{y}, {MONTHS[m-1].lower()}")
        c.font = f_date_bold
        c.alignment = Alignment(horizontal='center', vertical='center')

        # Календарные дни
        ws.merge_cells(start_row=1, start_column=days_start, end_row=1, end_column=days_end)
        c = ws.cell(row=1, column=days_start, value=f"({days_in_month} календарных дней)")
        c.font = f_date_norm
        c.alignment = Alignment(horizontal='center', vertical='center')

        # Предприятие (расширено до A2:E2)
        ws.merge_cells('A2:E2')
        c = ws.cell(row=2, column=1, value="Предприятие")
        c.font = f_italic
        c.alignment = Alignment(horizontal='left', vertical='center')

        ws.merge_cells(start_row=2, start_column=6, end_row=2, end_column=title_end + 3)
        c = ws.cell(row=2, column=6, value=org)
        c.font = f_italic_ul
        c.alignment = Alignment(horizontal='left', vertical='center', indent=2)

        # Отдел (расширено до A3:E3)
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
        ws.merge_cells(start_row=row_h1, start_column=start_days, end_row=row_h1, end_column=end_days)
        c = ws.cell(row=row_h1, column=start_days, value="Числа месяца")
        c.font = f_head
        c.alignment = center
        c.fill = header_fill

        col_hours = end_days + 1
        c = ws.cell(row=row_h1, column=col_hours, value="Всего")
        c.font = f_head
        c.alignment = center
        c.fill = header_fill
        ws.merge_cells(start_row=row_h1, start_column=col_hours, end_row=row_h2, end_column=col_hours)

        col_off = end_days + 2
        c = ws.cell(row=row_h1, column=col_off, value="Выходные")
        c.font = f_head
        c.alignment = center
        c.fill = header_fill
        ws.merge_cells(start_row=row_h1, start_column=col_off, end_row=row_h2, end_column=col_off)

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

        # Инициализируем длину с учётом заголовков, чтобы они не обрезались!
        max_col_len = {'часы': len("Всего"), 'вых': len("Выходные")}

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
                try: hours_val = float(str(emp_over['часы']).replace(',', '.'))
                except: hours_val = res.get('часы', 0.0)
            else: hours_val = res.get('часы', 0.0)

            if 'вых' in emp_over:
                try: off_val = int(float(str(emp_over['вых']).replace(',', '.')))
                except: off_val = res.get('вых', 0)
            else: off_val = res.get('вых', 0)

            grand['часы'] += hours_val
            grand['вых'] += off_val

            ws.cell(row=row, column=1, value=idx + 1).font = f_cell
            ws.cell(row=row, column=1).alignment = center

            c_name = ws.cell(row=row, column=2,
                             value=format_name(emp.get('name', '')))
            c_name.font = f_cell
            c_name.alignment = left

            for i, v in enumerate(values):
                col = start_days + i
                if str(v).strip() == '0':
                    v = None
                c = ws.cell(row=row, column=col, value=v)
                c.font = f_cell
                c.alignment = Alignment(horizontal='center', vertical='center', shrink_to_fit=True)
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

        ws.merge_cells(start_row=row, start_column=start_days, end_row=row, end_column=end_days)
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

        # Убираем лишние отступы
        row += 1

        # Норма рабочего времени (label non-bold, value bold)
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
        max_name_len = max((len(format_name(emp.get('name', '') or ''))
                            for emp in employees), default=15)
        ws.column_dimensions['B'].width = max(20, max_name_len * 1.2 + 5)
        
        for i in range(days_in_month):
            ws.column_dimensions[get_column_letter(start_days + i)].width = 5.0

        # Динамическая ширина для колонок "Всего" и "Выходные"
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

        # Легенда ниже нормы (только если стоит галочка)
        if self.legend_cb.active:
            row += 4
            row = self._draw_legend(ws, row, total_cols, border, header_fill)

        ws.page_setup.orientation = 'landscape'
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True

        try:
            ws.print_area = f"A1:{get_column_letter(total_cols)}{row}"
        except Exception:
            pass

        def _sanitize_folder(name):
            bad = '\\/:*?"<>|'
            for ch in bad:
                name = name.replace(ch, '_')
            name = name.strip()
            return name or 'Без отдела'

        dept_folder = _sanitize_folder(dept)
        out_dir = os.path.join(BASE_DIR, "Табель", dept_folder, str(y))
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception as e:
            print("Не удалось создать папку:", e)

        path = os.path.join(out_dir, f"tabel_{key}_кратко.xlsx")

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