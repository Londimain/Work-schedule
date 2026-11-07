# tab_report.py
# -*- coding: utf-8 -*-
import config, webbrowser
from datetime import datetime
from calendar import monthrange

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget
from kivy.uix.checkbox import CheckBox
from kivy.uix.textinput import TextInput
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock

from config import (FONT_NAME, LABEL_LIGHT, MONTHS, YEARS, SPINNER_BG, SPINNER_FG, 
                    RIGHT_COLUMNS, DEFAULT_ORG, DEFAULT_ENERGETIC, DEFAULT_DIRECTOR)

# Импортируем напрямую из data_storage, чтобы VS Code не ругался
from data_storage import get_local_signers, set_local_signers
from data_utils import (classify_day, analyze_row, apply_overtime, fmt_hours, 
                        calc_norm_hours, set_local_show_legend, get_local_show_legend,
                        save_data)

from ui_helpers import (NoOverscrollEffect, add_top_border, add_bottom_border,
                        add_left_border, add_right_border, vsep)
from ui_widgets import HoverButton as Button, LightSpinnerOption
from excel_export import export_full_excel, export_short_excel

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

class ReportTab(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        self._org_save_ev = None
        self._dir_save_ev = None

        with self.canvas.before:
            Color(*config.TABLE_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda i, v: setattr(self._bg, 'pos', v),
                  size=lambda i, v: setattr(self._bg, 'size', v))

        self._build()
        Clock.schedule_once(lambda *a: self.update_preview(), 0.3)

    def _on_org_change(self, inst, value):
        self.app.data['organization'] = value
        if self._org_save_ev:
            self._org_save_ev.cancel()
        self._org_save_ev = Clock.schedule_once(lambda *a: save_data(self.app.data), 0.5)
        Clock.schedule_once(lambda *a: self.update_preview(), 0.1)

    def _on_dir_change(self, inst, value):
        self.app.data['director_name'] = value
        if self._dir_save_ev:
            self._dir_save_ev.cancel()
        self._dir_save_ev = Clock.schedule_once(lambda *a: save_data(self.app.data), 0.5)
        Clock.schedule_once(lambda *a: self.update_preview(), 0.1)

    def _build(self):
        # --- Строка 1: Период, Доп. подписанты, Условные обозначения, Экспорт ---
        top = BoxLayout(size_hint_y=None, height=dp(52), spacing=5, padding=5)

        top.add_widget(Label(text="Месяц:", size_hint_x=None, width=dp(70),
                             color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15)))
        self.month_spinner = Spinner(text=MONTHS[datetime.now().month - 1],
                                     values=MONTHS, size_hint_x=None, width=dp(150),
                                     font_name=FONT_NAME, background_color=SPINNER_BG, 
                                     color=SPINNER_FG, option_cls=LightSpinnerOption)
        top.add_widget(self.month_spinner)

        top.add_widget(Label(text="Год:", size_hint_x=None, width=dp(50),
                             color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15)))
        self.year_spinner = Spinner(text=str(datetime.now().year),
                                    values=YEARS, size_hint_x=None, width=dp(100),
                                    font_name=FONT_NAME, background_color=SPINNER_BG, 
                                    color=SPINNER_FG, option_cls=LightSpinnerOption)
        top.add_widget(self.year_spinner)

        top.add_widget(Widget())

        # Кнопка Доп. подписанты перенесена сюда
        signers_btn = Button(text="Доп. подписанты", size_hint_x=None, width=dp(180),
                             font_name=FONT_NAME, font_size=dp(14), bold=True,
                             background_color=(0.5, 0.4, 0.75, 1), color=(1, 1, 1, 1))
        signers_btn.bind(on_press=self.show_signers_popup)
        top.add_widget(signers_btn)

        top.add_widget(Widget(size_hint_x=None, width=dp(15))) # Отступ

        legend_box = BoxLayout(size_hint_x=None, width=dp(220), spacing=dp(4), padding=(0, 0, dp(10), 0))
        is_legend_on = get_local_show_legend()
        self.legend_cb = CheckBox(active=is_legend_on, size_hint_x=None, width=dp(30), color=(1, 1, 1, 1))
        self.legend_cb.bind(active=lambda inst, val: set_local_show_legend(val))
        legend_lbl = Label(text="Условные обозначения", color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(14))
        legend_box.add_widget(self.legend_cb)
        legend_box.add_widget(legend_lbl)
        top.add_widget(legend_box)

        excel_btn = Button(text="Сохранить в Excel", size_hint_x=None, width=dp(200),
                           font_name=FONT_NAME, font_size=dp(15), bold=True,
                           background_color=(0.25, 0.55, 0.30, 1), color=(1, 1, 1, 1))
        excel_btn.bind(on_press=lambda *a: export_full_excel(self))
        top.add_widget(excel_btn)

        excel_short_btn = Button(text="Кратко в Excel", size_hint_x=None, width=dp(170),
                                 font_name=FONT_NAME, font_size=dp(15), bold=True,
                                 background_color=(0.20, 0.45, 0.55, 1), color=(1, 1, 1, 1))
        excel_short_btn.bind(on_press=lambda *a: export_short_excel(self))
        top.add_widget(excel_short_btn)

        self.add_widget(top)

        # --- Строка 2: Организация и Директор ---
        row2 = BoxLayout(size_hint_y=None, height=dp(46), spacing=5, padding=(5, 0, 5, 5))
        
        row2.add_widget(Label(text="Организация:", size_hint_x=None, width=dp(95),
                             color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(14)))
        
        self.org_input = TextInput(
            text=self.app.data.get('organization', DEFAULT_ORG),
            multiline=False, font_size=dp(14), font_name=FONT_NAME,
            foreground_color=(0.05, 0.05, 0.05, 1), background_color=(1, 1, 1, 1),
            padding=[dp(8), dp(8), dp(8), dp(8)],
            size_hint=(None, None), size=(dp(250), dp(30))
        )
        self.org_input.bind(text=self._on_org_change)
        row2.add_widget(self.org_input)

        row2.add_widget(Widget(size_hint_x=None, width=dp(10)))

        row2.add_widget(Label(text="Директор:", size_hint_x=None, width=dp(75),
                             color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(14)))
        
        self.dir_input = TextInput(
            text=self.app.data.get('director_name', DEFAULT_DIRECTOR),
            multiline=False, font_size=dp(14), font_name=FONT_NAME,
            foreground_color=(0.05, 0.05, 0.05, 1), background_color=(1, 1, 1, 1),
            padding=[dp(8), dp(8), dp(8), dp(8)],
            size_hint=(None, None), size=(dp(200), dp(30))
        )
        self.dir_input.bind(text=self._on_dir_change)
        row2.add_widget(self.dir_input)

        row2.add_widget(Widget())
        self.add_widget(row2)

        self.month_spinner.bind(text=lambda *a: self.update_preview())
        self.year_spinner.bind(text=lambda *a: self.update_preview())

        line = Widget(size_hint_y=None, height=dp(2))
        with line.canvas:
            Color(0.5, 0.5, 0.5, 1)
            line._rect = Rectangle(pos=line.pos, size=line.size)
        line.bind(pos=lambda i, v: setattr(i._rect, 'pos', v),
                  size=lambda i, v: setattr(i._rect, 'size', v))
        self.add_widget(line)

        scroll = ScrollView(scroll_type=['bars'], effect_cls=NoOverscrollEffect)
        self.preview = Label(text="", size_hint_y=None, halign='left',
                              valign='top', padding=(20, 20),
                              font_name=FONT_NAME, font_size=dp(13), color=config.TABLE_FG)
        self.preview.bind(width=lambda *a: setattr(
            self.preview, 'text_size', (self.preview.width - 40, None)))
        self.preview.bind(texture_size=self.preview.setter('size'))
        scroll.add_widget(self.preview)
        self.add_widget(scroll)

    def show_signers_popup(self, *args):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        add_title = Label(text="Добавить подписанта:", color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_y=None, height=dp(24), halign='left')
        add_title.bind(size=lambda i, v: setattr(i, 'text_size', v))
        content.add_widget(add_title)

        add_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=5)
        
        new_pos = TextInput(hint_text="Должность", multiline=False, font_size=dp(14), 
                            font_name=FONT_NAME, halign='left', padding=[dp(10), dp(12), dp(10), dp(12)])
        
        new_name = TextInput(hint_text="Фамилия И.О.", multiline=False, font_size=dp(14), 
                             font_name=FONT_NAME, halign='left', padding=[dp(10), dp(12), dp(10), dp(12)])
        
        pick_btn = Button(text="Выбрать...", size_hint_x=None, width=dp(110), 
                          background_color=(0.4, 0.5, 0.7, 1), color=(1, 1, 1, 1),
                          font_name=FONT_NAME, font_size=dp(14), bold=True)

        add_btn = Button(text="Добавить", size_hint_x=None, width=dp(100), background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1))
        
        add_row.add_widget(new_pos)
        add_row.add_widget(new_name)
        add_row.add_widget(pick_btn)
        add_row.add_widget(add_btn)
        content.add_widget(add_row)
        
        content.add_widget(Label(text="Список подписантов (галочка — выводить в Excel):", color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_y=None, height=dp(24), halign='left'))
        
        sv = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=5)
        grid.bind(minimum_height=grid.setter('height'))
        sv.add_widget(grid)
        content.add_widget(sv)
        
        close_btn = Button(text="Закрыть", size_hint_y=None, height=dp(40), color=(1,1,1,1), font_name=FONT_NAME)
        content.add_widget(close_btn)
        
        popup = Popup(title="Дополнительные подписанты", content=content, size_hint=(0.85, 0.65), title_color=LABEL_LIGHT, title_font=FONT_NAME)
        
        def save_signers(signers_list):
            set_local_signers(signers_list)
            self.update_preview()
            
        def rebuild_list():
            grid.clear_widgets()
            signers = get_local_signers()

            for i, s in enumerate(signers):
                row = BoxLayout(size_hint_y=None, height=dp(40), spacing=5)
                
                cb = CheckBox(active=s.get('active', True), size_hint_x=None, width=dp(40))
                def make_toggle(idx):
                    def toggle(inst, val):
                        signers[idx]['active'] = val
                        save_signers(signers)
                    return toggle
                cb.bind(active=make_toggle(i))
                row.add_widget(cb)
                
                pos_in = TextInput(text=s.get('position', ''), multiline=False, font_size=dp(14), 
                                   font_name=FONT_NAME, halign='left', padding=[dp(10), dp(12), dp(10), dp(12)])
                def make_pos_save(idx):
                    def save(inst, val):
                        signers[idx]['position'] = val
                        save_signers(signers)
                    return save
                pos_in.bind(text=make_pos_save(i))
                row.add_widget(pos_in)
                
                name_in = TextInput(text=s.get('name', ''), multiline=False, font_size=dp(14), 
                                    font_name=FONT_NAME, halign='left', padding=[dp(10), dp(12), dp(10), dp(12)])
                def make_name_save(idx):
                    def save(inst, val):
                        signers[idx]['name'] = val
                        save_signers(signers)
                    return save
                name_in.bind(text=make_name_save(i))
                row.add_widget(name_in)
                
                del_btn = Button(text="Удалить", size_hint_x=None, width=dp(100), background_color=(0.8, 0.2, 0.2, 1), color=(1, 1, 1, 1))
                def make_del(idx):
                    def delete(inst):
                        signers.pop(idx)
                        save_signers(signers)
                        rebuild_list()
                    return delete
                del_btn.bind(on_press=make_del(i))
                row.add_widget(del_btn)
                
                grid.add_widget(row)
                
        def do_add(*a):
            pos = new_pos.text.strip()
            nm = new_name.text.strip()
            if pos and nm:
                signers = get_local_signers()
                signers.append({'name': nm, 'position': pos, 'active': True})
                save_signers(signers)
                
                new_pos.text = ""
                new_name.text = ""
                rebuild_list()

        def open_signer_picker(*args):
            candidates = set()
            
            # Берем подписантов ТОЛЬКО из локального списка
            for s in get_local_signers():
                nm = s.get('name', '').strip()
                pos = s.get('position', '').strip()
                if pos and nm: candidates.add((pos, nm))

            sorted_cands = sorted(list(candidates), key=lambda x: (x[0].lower(), x[1].lower()))

            pick_content = BoxLayout(orientation='vertical', spacing=5, padding=5)
            
            search_input = TextInput(
                multiline=False, font_size=dp(14), font_name=FONT_NAME,
                foreground_color=(0.05, 0.05, 0.05, 1), background_color=(1, 1, 1, 1),
                padding=[dp(8), dp(8), dp(8), dp(8)], size_hint_y=None, height=dp(36),
                hint_text="Поиск по должности или ФИО..."
            )
            pick_content.add_widget(search_input)

            pick_header = BoxLayout(size_hint_y=None, height=dp(34), spacing=0)
            with pick_header.canvas.before:
                Color(0.30, 0.30, 0.35, 1) 
                _bg = Rectangle(pos=pick_header.pos, size=pick_header.size)
            pick_header.bind(pos=lambda i,v: setattr(_bg, 'pos', v), size=lambda i,v: setattr(_bg, 'size', v))

            h_pos = Label(text="Должность", bold=True, color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_x=0.6, 
                          halign='center', valign='middle')
            h_pos.bind(size=lambda i,v: setattr(i, 'text_size', (v[0], v[1])))
            add_bottom_border(h_pos, color=(0.4, 0.4, 0.4, 1))
            add_right_border(h_pos, color=(0.4, 0.4, 0.4, 1))
            pick_header.add_widget(h_pos)

            h_name = Label(text="Фамилия И.О.", bold=True, color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_x=0.4, 
                           halign='center', valign='middle')
            h_name.bind(size=lambda i,v: setattr(i, 'text_size', (v[0], v[1])))
            add_bottom_border(h_name, color=(0.4, 0.4, 0.4, 1))
            add_right_border(h_name, color=(0.4, 0.4, 0.4, 1))
            pick_header.add_widget(h_name)

            pick_content.add_widget(pick_header)

            pick_scroll = ScrollView(scroll_type=['bars'], effect_cls=NoOverscrollEffect)
            pick_grid = GridLayout(cols=1, size_hint_y=None, spacing=0)
            pick_grid.bind(minimum_height=pick_grid.setter('height'))
            pick_scroll.add_widget(pick_grid)
            pick_content.add_widget(pick_scroll)

            # Переименовали заголовок, так как база теперь локальная
            picker = Popup(title="Выбор подписанта из списка", content=pick_content, size_hint=(0.6, 0.6), 
                           title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)

            def rebuild_pick_list(query=''):
                pick_grid.clear_widgets()
                q = query.lower()
                found = False
                
                for pos, nm in sorted_cands:
                    if q in pos.lower() or q in nm.lower():
                        found = True
                        
                        row_btn = Button(
                            text='', size_hint_y=None, height=dp(40),
                            background_normal='', background_color=(0.15, 0.15, 0.18, 1),
                            padding=[0, 0, 0, 0]
                        )
                        add_bottom_border(row_btn, color=(0.4, 0.4, 0.4, 1))
                        add_left_border(row_btn, color=(0.4, 0.4, 0.4, 1))
                        add_right_border(row_btn, color=(0.4, 0.4, 0.4, 1))

                        row_layout = BoxLayout(orientation='horizontal', spacing=0)
                        row_btn.bind(pos=lambda inst, val, rl=row_layout: setattr(rl, 'pos', val),
                                     size=lambda inst, val, rl=row_layout: setattr(rl, 'size', val))

                        cell_pos = BoxLayout(size_hint_x=0.6, padding=(dp(10), 0, 0, 0))
                        lbl_pos = Label(text=pos, color=(1, 1, 1, 1), font_name=FONT_NAME, font_size=dp(14), halign='left', valign='middle')
                        lbl_pos.bind(size=lambda i,v: setattr(i, 'text_size', (v[0], v[1])))
                        cell_pos.add_widget(lbl_pos)
                        add_right_border(cell_pos, color=(0.4, 0.4, 0.4, 1))
                        row_layout.add_widget(cell_pos)

                        cell_name = BoxLayout(size_hint_x=0.4, padding=(dp(10), 0, 0, 0))
                        lbl_name = Label(text=nm, color=(1, 1, 1, 1), font_name=FONT_NAME, font_size=dp(14), halign='left', valign='middle')
                        lbl_name.bind(size=lambda i,v: setattr(i, 'text_size', (v[0], v[1])))
                        cell_name.add_widget(lbl_name)
                        row_layout.add_widget(cell_name)

                        row_btn.add_widget(row_layout)
                        
                        def make_select(p=pos, n=nm):
                            def _sel(*a):
                                new_pos.text = p
                                new_name.text = n
                                picker.dismiss()
                            return _sel

                        row_btn.bind(on_press=make_select())
                        pick_grid.add_widget(row_btn)

                if not found:
                    lbl = Label(text="Ничего не найдено", color=(0.6, 0.6, 0.6, 1), font_name=FONT_NAME, size_hint_y=None, height=dp(40))
                    pick_grid.add_widget(lbl)

            search_input.bind(text=lambda inst, val: rebuild_pick_list(val))
            rebuild_pick_list()

            pick_close = Button(text="Отмена", size_hint_y=None, height=dp(40), color=(1,1,1,1), font_name=FONT_NAME)
            pick_close.bind(on_press=picker.dismiss)
            pick_content.add_widget(pick_close)
            picker.open()

        pick_btn.bind(on_press=open_signer_picker)
        add_btn.bind(on_press=do_add)
        close_btn.bind(on_press=popup.dismiss)
        
        new_pos.bind(on_text_validate=do_add)
        new_name.bind(on_text_validate=do_add)
        
        popup.open()
        rebuild_list()

    def _get_signer(self, dept):
        signers = self.app.data.get('department_signer', {}) or {}
        entry = signers.get(dept)
        if entry and entry.get('name'):
            return (entry.get('position') or 'Энергетик', entry.get('name'))
        em = self.app.data.get('department_energetic', {}) or {}
        name = em.get(dept) or self.app.data.get('energetic_name', DEFAULT_ENERGETIC)
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
        day_types = [classify_day(y, m, d) for d in range(1, days_in_month + 1)]
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

        grand, days_in_month, work_days, norm_hours, pre_count, key = self._calc_grand()

        spis_count = sum(1 for emp in employees if emp.get('is_contract', True))
        total_days = sum(grand[k] for k in grand if k not in ('часы', 'сверхурочные', 'ночные', 'праздничные'))
        avg_count = total_days / days_in_month if days_in_month > 0 else 0

        if pre_count > 0:
            norm_line = (f"  Норма: {work_days} будних × 8 − {pre_count} предпраздн. = {fmt_hours(norm_hours)} ч")
        else:
            norm_line = (f"  Норма: {work_days} будних × 8 = {fmt_hours(norm_hours)} ч")

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
            f"  Роды (РО): {grand.get('отп_роды', 0)}    "
            f"Командировка: {grand.get('командировка', 0)}    "
            f"Мед.комиссия: {grand.get('мед_комиссия', 0)}    "
            f"Оплата по среднему: {grand.get('оплата_среднему', 0)}",
            f"  Ремонт: {grand.get('ремонт', 0)}    "
            f"Тех.обслуживание: {grand.get('тех_обслуживание', 0)}    "
            f"Кол.договор: {grand.get('кол_договор', 0)}    "
            f"Проч.неявки: {grand.get('проч_неявки', 0)}",
            f"  Всего часов: {fmt_hours(grand.get('часы', 0))}    "
            f"Сверхурочные: {fmt_hours(grand.get('сверхурочные', 0))}    "
            f"Ночные: {fmt_hours(grand.get('ночные', 0))}    "
            f"Праздничные: {fmt_hours(grand.get('праздничные', 0))}",
            f"  Подписи: {signer_pos} — {signer_name}    ",
        ]

        # Берем локальных подписантов
        add_signers = get_local_signers()
        for s in add_signers:
            if s.get('active', True):
                lines.append(f"            {s.get('position', '')} — {s.get('name', '')}")

        lines.append(f"  Директор — {director_name}")
        lines.extend([sep, "", "  По сотрудникам:"])

        name_w = 26
        day_types = [classify_day(y, m, d) for d in range(1, days_in_month + 1)]
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
            nm = (format_name(emp.get('name', '') or ''))[:name_w].ljust(name_w)
            lines.append(
                f"   {idx + 1:>2}. {nm} "
                f"явок {res['явки']:>2}  часов {fmt_hours(res['часы']):>7}  "
                f"сверхур {fmt_hours(res['сверхурочные']):>5}  "
                f"празд {fmt_hours(res['праздничные']):>5}  "
                f"В {res['вых']:>2}  О {res['отп']:>2}  РО {res['отп_роды']:>2}  "
                f"К {res['командировка']:>2}  Б {res['бол']:>2}"
            )

        lines += ["", sep, "  Нажмите «Сохранить в Excel», чтобы получить файл .xlsx"]
        self.preview.text = "\n".join(lines)

    def _show_openpyxl_error(self, err_msg):
        from kivy.uix.popup import Popup
        from kivy.uix.scrollview import ScrollView as _SV
        msg = ("Не удалось загрузить openpyxl в собранной программе.\n\n"
               "Техническая информация:\n" + err_msg)
        inner = BoxLayout(orientation='vertical', spacing=8, padding=8)
        sv = _SV()
        lbl = Label(text=msg, color=LABEL_LIGHT, halign='left', valign='top', font_name=FONT_NAME, font_size=dp(13))
        lbl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        lbl.bind(texture_size=lbl.setter('size'))
        sv.add_widget(lbl); inner.add_widget(sv)
        ok_btn = Button(text="OK", size_hint_y=None, height=dp(40), font_name=FONT_NAME, font_size=dp(16), bold=True, background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1))
        inner.add_widget(ok_btn)
        popup = Popup(title="Нужен openpyxl", content=inner, size_hint=(0.85, 0.55), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
        ok_btn.bind(on_press=popup.dismiss)
        popup.open()