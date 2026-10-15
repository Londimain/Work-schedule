# tab_employees.py
# -*- coding: utf-8 -*-
"""Вкладка «Рабочий персонал»."""
import config  # noqa: F401 — настройка Kivy первой

from datetime import datetime

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from kivy.uix.textinput import TextInput

from config import (FONT_NAME, LABEL_LIGHT, DEFAULT_POSITIONS,
                    DEFAULT_DEPARTMENTS, DEFAULT_ORG,
                    DEPT_BAR_BG, DEPT_BAR_FG,
                    DEFAULT_ENERGETIC, DELETE_PASSWORD)
from data_utils import save_data
from ui_helpers import (add_bottom_border, add_top_border,
                        add_left_border, add_right_border, vsep,
                        NoOverscrollEffect, ask_password_and_run)
from ui_widgets import CenteredField, CenteredSpinner


class EmployeesTab(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        self._org_save_ev = None
        self._build()

    def _build(self):
        top = BoxLayout(size_hint_y=None, height=dp(42), spacing=5,
                        padding=(5, 2, 5, 2))
        add_btn = Button(text="+ Добавить сотрудника",
                         size_hint_x=None, width=dp(200),
                         font_name=FONT_NAME,
                         background_color=(0.3, 0.7, 0.3, 1),
                         color=(1, 1, 1, 1))
        add_btn.bind(on_press=lambda *a: self.add_employee())
        top.add_widget(add_btn)

        pos_btn = Button(text="+ Должность", size_hint_x=None, width=dp(140),
                         font_name=FONT_NAME,
                         background_color=(0.35, 0.55, 0.85, 1),
                         color=(1, 1, 1, 1))
        pos_btn.bind(on_press=lambda *a: self.show_positions_popup())
        top.add_widget(pos_btn)

        dept_btn = Button(text="+ Отдел", size_hint_x=None, width=dp(130),
                          font_name=FONT_NAME,
                          background_color=(0.55, 0.40, 0.75, 1),
                          color=(1, 1, 1, 1))
        dept_btn.bind(on_press=lambda *a: self.show_departments_popup())
        top.add_widget(dept_btn)

        top.add_widget(Widget())

        top.add_widget(Label(text="Организация:", size_hint_x=None,
                             width=dp(110), color=LABEL_LIGHT,
                             font_name=FONT_NAME))
        org_wrap = CenteredField(
            text=self.app.data.get('organization', DEFAULT_ORG),
            font_size=dp(14), pad_lr=dp(10), halign='left',
        )
        org_wrap.size_hint = (None, None)
        org_wrap.size = (dp(320), dp(38))
        org_wrap.input.bind(text=self._on_org_change)
        top.add_widget(org_wrap)
        self.org_wrap = org_wrap

        self.add_widget(top)

        # ---- Фиксированная шапка таблицы (НЕ прокручивается) ----
        self.header_holder = GridLayout(cols=1, size_hint_y=None,
                                         height=dp(37),
                                         padding=(5, 0, 5, 0))
        self.add_widget(self.header_holder)
        self._build_header()

        # ---- Прокручиваемое тело таблицы ----
        scroll = ScrollView(scroll_type=['bars'],
                            effect_cls=NoOverscrollEffect)
        self.list_layout = GridLayout(cols=1, size_hint_y=None,
                                       spacing=0, padding=(5, 0, 5, 5))
        self.list_layout.bind(minimum_height=self.list_layout.setter('height'))
        scroll.add_widget(self.list_layout)
        self.add_widget(scroll)
        self.refresh()

    def _on_org_change(self, inst, value):
        self.app.data['organization'] = value
        if self._org_save_ev:
            self._org_save_ev.cancel()
        self._org_save_ev = Clock.schedule_once(
            lambda *a: save_data(self.app.data), 0.5)

    def _active_dept(self):
        for emp in self.app.data['employees']:
            if emp.get('show_in_timesheet', True):
                return emp.get('department', '')
        return ''

    def _show_dept_conflict(self, other_dept):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(
            text=(f"Табель уже ведётся по отделу «{other_dept}».\n\n"
                  f"Сначала снимите галочки\nу всех сотрудников "
                  f"этого отдела, затем отмечайте другой."),
            color=LABEL_LIGHT, halign='center',
            font_name=FONT_NAME, font_size=dp(15),
            outline_color=(0, 0, 0, 1), outline_width=1))
        btn = Button(text="OK", size_hint_y=None, height=dp(40),
                     font_name=FONT_NAME, font_size=dp(16),
                     background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1))
        content.add_widget(btn)
        popup = Popup(title="Только один отдел", content=content,
                      size_hint=(0.55, 0.4), title_color=LABEL_LIGHT,
                      title_font=FONT_NAME)
        btn.bind(on_press=popup.dismiss)
        popup.open()

    def _toggle_in_timesheet(self, idx, value):
        try:
            if value:
                emp = self.app.data['employees'][idx]
                my_dept = emp.get('department', '')
                active = self._active_dept()
                if active and active != my_dept:
                    self._show_dept_conflict(active)
                    self.refresh()
                    return
            self.app.data['employees'][idx]['show_in_timesheet'] = bool(value)
            save_data(self.app.data)
            self.refresh()
        except Exception:
            pass

    def _add_employee_row(self, idx, emp):
        show_in = emp.get('show_in_timesheet', True)
        row = BoxLayout(size_hint_y=None, height=dp(42), spacing=0)
        row.add_widget(Label(text=str(idx + 1), size_hint_x=0.4,
                             font_name=FONT_NAME, font_size=dp(15),
                             color=LABEL_LIGHT))
        row.add_widget(vsep(color=LABEL_LIGHT))
        row.add_widget(Label(text=emp.get('name', ''), size_hint_x=3.0,
                             font_name=FONT_NAME, font_size=dp(15),
                             color=LABEL_LIGHT))
        row.add_widget(vsep(color=LABEL_LIGHT))
        row.add_widget(Label(text=emp.get('position', ''), size_hint_x=2.3,
                             font_name=FONT_NAME, font_size=dp(15),
                             color=LABEL_LIGHT))
        row.add_widget(vsep(color=LABEL_LIGHT))

        chk_box = AnchorLayout(anchor_x='center', anchor_y='center',
                                size_hint_x=0.7)
        cb = CheckBox(active=show_in,
                      size_hint=(None, None),
                      size=(dp(30), dp(30)),
                      color=((0.30, 0.90, 0.40, 1) if show_in
                             else (0.85, 0.85, 0.85, 1)))
        cb.bind(active=lambda inst, val, i=idx:
                self._toggle_in_timesheet(i, val))
        chk_box.add_widget(cb)
        row.add_widget(chk_box)
        row.add_widget(vsep(color=LABEL_LIGHT))

        btns = BoxLayout(size_hint_x=1.6, spacing=2)
        edit_btn = Button(text="Изменить", color=(1, 1, 1, 1),
                          font_name=FONT_NAME, font_size=dp(15), bold=True)
        edit_btn.bind(on_press=lambda *a, i=idx: self.edit_employee(i))
        del_btn = Button(text="Удалить",
                         background_color=(0.9, 0.35, 0.35, 1),
                         color=(1, 1, 1, 1),
                         font_name=FONT_NAME, font_size=dp(15), bold=True)
        del_btn.bind(on_press=lambda *a, i=idx: self.delete_employee(i))
        btns.add_widget(edit_btn)
        btns.add_widget(del_btn)
        row.add_widget(btns)

        add_bottom_border(row)
        self.list_layout.add_widget(row)

    def _add_dept_bar(self, name, bg=DEPT_BAR_BG):
        bar = BoxLayout(size_hint_y=None, height=dp(30),
                        padding=(0, 0, 0, 0))
        from kivy.graphics import Color as _Color, Rectangle as _Rect
        with bar.canvas.before:
            _Color(*bg)
            rect = _Rect(pos=bar.pos, size=bar.size)
        bar.bind(pos=lambda i, v, r=rect: setattr(r, 'pos', v),
                 size=lambda i, v, r=rect: setattr(r, 'size', v))
        lbl = Label(text=name, color=DEPT_BAR_FG,
                    font_name=FONT_NAME, font_size=dp(15),
                    halign='center', valign='middle')
        lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        bar.add_widget(lbl)
        self.list_layout.add_widget(bar)
        
    def _build_header(self):
        """Строка-шапка таблицы — не прокручивается."""
        self.header_holder.clear_widgets()
        header = BoxLayout(size_hint_y=None, height=dp(35), spacing=0)
        header.add_widget(Label(text="№", bold=True, size_hint_x=0.4,
                                 font_name=FONT_NAME, font_size=dp(15),
                                 color=LABEL_LIGHT))
        header.add_widget(vsep(color=LABEL_LIGHT))
        header.add_widget(Label(text="Фамилия Имя Отчество", bold=True,
                                 size_hint_x=3.0, font_name=FONT_NAME,
                                 font_size=dp(15), color=LABEL_LIGHT))
        header.add_widget(vsep(color=LABEL_LIGHT))
        header.add_widget(Label(text="Должность", bold=True,
                                 size_hint_x=2.3, font_name=FONT_NAME,
                                 font_size=dp(15), color=LABEL_LIGHT))
        header.add_widget(vsep(color=LABEL_LIGHT))
        header.add_widget(Label(text="В таблицу", bold=True,
                                 size_hint_x=0.7, font_name=FONT_NAME,
                                 font_size=dp(15), color=LABEL_LIGHT))
        header.add_widget(vsep(color=LABEL_LIGHT))
        header.add_widget(Label(text="Действия", bold=True,
                                 size_hint_x=1.6, font_name=FONT_NAME,
                                 font_size=dp(15), color=LABEL_LIGHT))

        add_top_border(header, color=LABEL_LIGHT, thickness=2)
        add_bottom_border(header, color=LABEL_LIGHT, thickness=2)
        add_left_border(header, color=LABEL_LIGHT, thickness=2)
        add_right_border(header, color=LABEL_LIGHT, thickness=2)
        self.header_holder.add_widget(header)

    def refresh(self):
        self.list_layout.clear_widgets()

        departments = self.app.data.get('departments', [])
        employees = self.app.data['employees']
        used = set()
        for dept in departments:
            idxs = [i for i, e in enumerate(employees)
                    if e.get('department', '') == dept]
            if not idxs:
                continue
            self._add_dept_bar(dept)
            for i in idxs:
                self._add_employee_row(i, employees[i])
                used.add(i)
        others = [i for i in range(len(employees)) if i not in used]
        if others:
            if departments:
                self._add_dept_bar("Без отдела", bg=(0.30, 0.30, 0.34, 1))
            for i in others:
                self._add_employee_row(i, employees[i])

    def add_employee(self):
        self.show_edit_popup(None)

    def edit_employee(self, idx):
        self.show_edit_popup(idx)

    def delete_employee(self, idx):
        emp = self.app.data['employees'][idx]

        def _do():
            self.app.data['employees'].pop(idx)
            save_data(self.app.data)
            self.refresh()

        ask_password_and_run(
            DELETE_PASSWORD, _do,
            description=f"Удалить сотрудника:\n«{emp.get('name', '')}»?")

    def show_edit_popup(self, idx):
        emp = (self.app.data['employees'][idx] if idx is not None
               else {'name': '', 'position': '', 'department': '',
                     'show_in_timesheet': False})
        positions = self.app.data.get('positions', []) or list(DEFAULT_POSITIONS)
        departments = self.app.data.get('departments', [])

        outer = BoxLayout(orientation='vertical', spacing=10,
                          padding=(20, 15, 20, 15))

        fields = BoxLayout(orientation='vertical', spacing=10,
                           size_hint=(1, None), height=dp(140))

        LBL_W = dp(180)

        # --- ФИО ---
        row_name = BoxLayout(size_hint_y=None, height=dp(38), spacing=8)
        row_name.add_widget(Label(
            text="Фамилия Имя Отчество", size_hint=(None, 1), width=LBL_W,
            color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15),
            halign='right', valign='middle',
            text_size=(LBL_W, dp(38))))
        name_w = CenteredField(text=emp.get('name', ''), font_size=dp(15),
                               pad_lr=dp(10), halign='left')
        name_w.size_hint = (1, None)
        name_w.height = dp(32)
        row_name.add_widget(name_w)
        fields.add_widget(row_name)

        # --- Отдел ---
        row_dept = BoxLayout(size_hint_y=None, height=dp(38), spacing=8)
        row_dept.add_widget(Label(
            text="Отдел", size_hint=(None, 1), width=LBL_W,
            color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15),
            halign='right', valign='middle',
            text_size=(LBL_W, dp(38))))
        dept_w = CenteredSpinner(
            text=emp.get('department', '') or (departments[0] if departments else ''),
            values=departments, spinner_height=dp(30), font_size=dp(14))
        dept_w.size_hint = (1, None)
        dept_w.height = dp(32)
        row_dept.add_widget(dept_w)
        fields.add_widget(row_dept)

        # --- Должность ---
        row_pos = BoxLayout(size_hint_y=None, height=dp(38), spacing=8)
        row_pos.add_widget(Label(
            text="Должность (профессия)",
            size_hint=(None, 1), width=LBL_W,
            color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15),
            halign='right', valign='middle',
            text_size=(LBL_W, dp(38))))
        pos_w = CenteredSpinner(
            text=emp.get('position', '') or (positions[0] if positions else ''),
            values=positions, spinner_height=dp(30), font_size=dp(14))
        pos_w.size_hint = (1, None)
        pos_w.height = dp(32)
        row_pos.add_widget(pos_w)
        fields.add_widget(row_pos)

        outer.add_widget(fields)
        outer.add_widget(Widget())     # распорка

        btns = BoxLayout(size_hint_y=None, height=dp(50), spacing=10)
        save_btn = Button(text="Сохранить",
                          background_color=(0.3, 0.7, 0.3, 1),
                          color=(1, 1, 1, 1), font_name=FONT_NAME,
                          font_size=dp(16), bold=True)
        cancel_btn = Button(text="Отмена", color=(1, 1, 1, 1),
                            font_name=FONT_NAME, font_size=dp(16), bold=True)
        btns.add_widget(save_btn)
        btns.add_widget(cancel_btn)
        outer.add_widget(btns)

        popup = Popup(title="Сотрудник" if idx is not None else "Новый сотрудник",
                      content=outer, size_hint=(0.6, 0.42),
                      title_color=LABEL_LIGHT, title_font=FONT_NAME)

        def on_save(*a):
            name = name_w.text.strip()
            if not name:
                return
            new_dept = dept_w.text.strip()
            show_in = emp.get('show_in_timesheet', False)
            new_emp = {
                'id': emp.get('id') or f"emp_{int(datetime.now().timestamp() * 1000)}",
                'name': name,
                'position': pos_w.text.strip(),
                'department': new_dept,
                'show_in_timesheet': show_in,
                'category': emp.get('category', ''),
            }
            if idx is not None:
                self.app.data['employees'][idx] = new_emp
            else:
                self.app.data['employees'].append(new_emp)
            save_data(self.app.data)
            popup.dismiss()
            self.refresh()

        save_btn.bind(on_press=on_save)
        cancel_btn.bind(on_press=popup.dismiss)
        popup.open()

    def show_positions_popup(self):
        self.app.data.setdefault('positions', list(DEFAULT_POSITIONS))
        self.app.data.setdefault('night_flags', {})
        self.app.data.setdefault('overtime_flags', {})
        self.app.data.setdefault('holiday_flags', {})
        positions = self.app.data['positions']
        if not positions:
            self.app.data['positions'] = list(DEFAULT_POSITIONS)
            positions = self.app.data['positions']

        content = BoxLayout(orientation='vertical', spacing=8, padding=10)
        add_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=5)
        new_pos_wrap = CenteredField(text='', font_size=dp(15),
                                      pad_lr=dp(10), halign='left')
        new_pos_wrap.size_hint_x = 0.7
        add_row.add_widget(new_pos_wrap)
        add_btn = Button(text="Добавить", size_hint_x=0.3,
                         background_color=(0.3, 0.7, 0.3, 1),
                         color=(1, 1, 1, 1),
                         font_name=FONT_NAME, font_size=dp(16), bold=True)
        add_row.add_widget(add_btn)
        content.add_widget(add_row)

        list_scroll = ScrollView(scroll_type=['bars'], bar_width=dp(8),
                                  effect_cls=NoOverscrollEffect)
        list_grid = GridLayout(cols=1, size_hint_y=None, spacing=2)
        list_grid.bind(minimum_height=list_grid.setter('height'))

        def toggle_night(name):
            flags = self.app.data.setdefault('night_flags', {})
            flags[name] = not flags.get(name, False)
            save_data(self.app.data)
            rebuild_list()

        def toggle_overtime(name):
            flags = self.app.data.setdefault('overtime_flags', {})
            flags[name] = not flags.get(name, False)
            save_data(self.app.data)
            rebuild_list()

        def toggle_holiday(name):
            flags = self.app.data.setdefault('holiday_flags', {})
            flags[name] = not flags.get(name, False)
            save_data(self.app.data)
            rebuild_list()

        def delete_pos(ii):
            name = self.app.data['positions'][ii]

            def _do():
                try:
                    self.app.data['positions'].pop(ii)
                    self.app.data.get('night_flags', {}).pop(name, None)
                    self.app.data.get('overtime_flags', {}).pop(name, None)
                    self.app.data.get('holiday_flags', {}).pop(name, None)
                    save_data(self.app.data)
                    rebuild_list()
                except Exception:
                    pass

            ask_password_and_run(
                DELETE_PASSWORD, _do,
                description=f"Удалить должность:\n«{name}»?")

        def edit_pos(ii):
            old_name = self.app.data['positions'][ii]
            c = BoxLayout(orientation='vertical', spacing=10, padding=10)
            c.add_widget(Label(text=f"Новое название для «{old_name}»:",
                                color=LABEL_LIGHT, halign='center',
                                font_name=FONT_NAME, font_size=dp(15),
                                outline_color=(0, 0, 0, 1), outline_width=1))
            edit_wrap = CenteredField(text=old_name, font_size=dp(15),
                                       pad_lr=dp(10), halign='left')
            edit_wrap.size_hint_y = None
            edit_wrap.height = dp(40)
            c.add_widget(edit_wrap)
            btns = BoxLayout(size_hint_y=None, height=dp(40), spacing=10)
            ok = Button(text="Сохранить",
                        background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1),
                        font_name=FONT_NAME, font_size=dp(16), bold=True)
            cancel = Button(text="Отмена", color=(1, 1, 1, 1),
                            font_name=FONT_NAME, font_size=dp(16), bold=True)
            btns.add_widget(ok)
            btns.add_widget(cancel)
            c.add_widget(btns)
            p = Popup(title="Изменить должность", content=c,
                      size_hint=(0.5, 0.35), title_color=LABEL_LIGHT,
                      title_font=FONT_NAME)

            def on_ok(*a):
                new_name = edit_wrap.text.strip()
                if not new_name or new_name == old_name:
                    p.dismiss()
                    return
                if new_name in self.app.data['positions']:
                    p.dismiss()
                    return
                self.app.data['positions'][ii] = new_name

                flags_n = self.app.data.setdefault('night_flags', {})
                old_flag_n = flags_n.pop(old_name, False)
                flags_n[new_name] = old_flag_n

                flags_o = self.app.data.setdefault('overtime_flags', {})
                old_flag_o = flags_o.pop(old_name, False)
                flags_o[new_name] = old_flag_o

                flags_h = self.app.data.setdefault('holiday_flags', {})
                old_flag_h = flags_h.pop(old_name, False)
                flags_h[new_name] = old_flag_h

                for emp in self.app.data['employees']:
                    if emp.get('position', '') == old_name:
                        emp['position'] = new_name
                save_data(self.app.data)
                p.dismiss()
                rebuild_list()
                self.refresh()

            ok.bind(on_press=on_ok)
            cancel.bind(on_press=p.dismiss)
            p.open()

        def rebuild_list():
            list_grid.clear_widgets()
            for i, p in enumerate(self.app.data['positions']):
                row = BoxLayout(size_hint_y=None, height=dp(44), spacing=6)

                night_on = bool(self.app.data['night_flags'].get(p, False))
                night_box = BoxLayout(size_hint_x=None, width=dp(120),
                                       spacing=4)
                cb = CheckBox(active=night_on, size_hint_x=None, width=dp(30),
                              color=((0.30, 0.90, 0.40, 1) if night_on
                                     else (0.85, 0.85, 0.85, 1)))
                cb.bind(active=lambda inst, val, nm=p: toggle_night(nm))
                night_box.add_widget(cb)
                night_box.add_widget(Label(text="Ночные", color=(1, 1, 1, 1),
                                            font_name=FONT_NAME,
                                            font_size=dp(15), bold=True,
                                            outline_color=(0, 0, 0, 1),
                                            outline_width=1,
                                            valign='middle'))
                row.add_widget(night_box)

                overtime_on = bool(self.app.data['overtime_flags'].get(p, False))
                overtime_box = BoxLayout(size_hint_x=None, width=dp(170),
                                          spacing=4)
                cb2 = CheckBox(active=overtime_on, size_hint_x=None, width=dp(30),
                               color=((0.30, 0.90, 0.40, 1) if overtime_on
                                      else (0.85, 0.85, 0.85, 1)))
                cb2.bind(active=lambda inst, val, nm=p: toggle_overtime(nm))
                overtime_box.add_widget(cb2)
                overtime_box.add_widget(Label(text="Сверхурочные", color=(1, 1, 1, 1),
                                               font_name=FONT_NAME,
                                               font_size=dp(15), bold=True,
                                               outline_color=(0, 0, 0, 1),
                                               outline_width=1,
                                               valign='middle'))
                row.add_widget(overtime_box)

                holiday_on = bool(self.app.data['holiday_flags'].get(p, False))
                holiday_box = BoxLayout(size_hint_x=None, width=dp(170),
                                        spacing=4)
                cb3 = CheckBox(active=holiday_on, size_hint_x=None, width=dp(30),
                               color=((0.30, 0.90, 0.40, 1) if holiday_on
                                      else (0.85, 0.85, 0.85, 1)))
                cb3.bind(active=lambda inst, val, nm=p: toggle_holiday(nm))
                holiday_box.add_widget(cb3)
                holiday_box.add_widget(Label(text="Праздничные", color=(1, 1, 1, 1),
                                              font_name=FONT_NAME,
                                              font_size=dp(15), bold=True,
                                              outline_color=(0, 0, 0, 1),
                                              outline_width=1,
                                              valign='middle'))
                row.add_widget(holiday_box)

                row.add_widget(Label(text=p, color=(1, 1, 1, 1),
                                      font_name=FONT_NAME,
                                      font_size=dp(15), bold=True,
                                      outline_color=(0, 0, 0, 1),
                                      outline_width=1,
                                      halign='left', valign='middle',
                                      text_size=(dp(200), dp(44))))
                edit_btn = Button(text="Изменить", size_hint_x=None, width=dp(110),
                                  font_name=FONT_NAME, font_size=dp(15), bold=True,
                                  background_color=(0.35, 0.55, 0.85, 1),
                                  color=(1, 1, 1, 1))
                edit_btn.bind(on_press=lambda *a, ii=i: edit_pos(ii))
                row.add_widget(edit_btn)
                del_btn = Button(text="Удалить", size_hint_x=None, width=dp(110),
                                 font_name=FONT_NAME, font_size=dp(15), bold=True,
                                 background_color=(0.9, 0.35, 0.35, 1),
                                 color=(1, 1, 1, 1))
                del_btn.bind(on_press=lambda *a, ii=i: delete_pos(ii))
                row.add_widget(del_btn)
                list_grid.add_widget(row)

        def add_position(*a):
            txt = new_pos_wrap.text.strip()
            if not txt:
                return
            if txt in self.app.data['positions']:
                new_pos_wrap.text = ''
                return
            self.app.data['positions'].append(txt)
            self.app.data.setdefault('night_flags', {}).setdefault(txt, False)
            self.app.data.setdefault('overtime_flags', {}).setdefault(txt, False)
            self.app.data.setdefault('holiday_flags', {}).setdefault(txt, False)
            save_data(self.app.data)
            new_pos_wrap.text = ''
            rebuild_list()

        add_btn.bind(on_press=add_position)
        new_pos_wrap.input.bind(on_text_validate=add_position)
        rebuild_list()
        list_scroll.add_widget(list_grid)
        content.add_widget(list_scroll)

        close_btn = Button(text="Закрыть", size_hint_y=None, height=dp(40),
                           font_name=FONT_NAME, font_size=dp(16), bold=True,
                           color=(1, 1, 1, 1))
        content.add_widget(close_btn)
        popup = Popup(title="Должности", content=content,
                      size_hint=(0.9, 0.65), title_color=LABEL_LIGHT,
                      title_font=FONT_NAME)
        close_btn.bind(on_press=popup.dismiss)
        popup.open()

    def show_departments_popup(self):
        self.app.data.setdefault('departments', list(DEFAULT_DEPARTMENTS))
        self.app.data.setdefault('department_signer', {})
        self.app.data.setdefault('department_energetic', {})   # legacy
        if not self.app.data['departments']:
            self.app.data['departments'] = list(DEFAULT_DEPARTMENTS)

        # Должности подписантов отдела — отдельный список,
        # НЕ связан с должностями сотрудников (positions).
        signer_positions = self.app.data.setdefault('signer_positions',
                                                     ['Энергетик'])
        if not signer_positions:
            signer_positions.append('Энергетик')
            self.app.data['signer_positions'] = signer_positions

        content = BoxLayout(orientation='vertical', spacing=8, padding=10)

        add_btn = Button(text="+ Добавить отдел",
                         size_hint_y=None, height=dp(40),
                         background_color=(0.3, 0.7, 0.3, 1),
                         color=(1, 1, 1, 1),
                         font_name=FONT_NAME, font_size=dp(16), bold=True)
        content.add_widget(add_btn)

        # --- строка заголовка ---
        header = BoxLayout(size_hint_y=None, height=dp(34), spacing=6)
        header.add_widget(vsep(color=LABEL_LIGHT))          # левый край
        header.add_widget(Label(text="№", bold=True, size_hint_x=None,
                                 width=dp(40), color=LABEL_LIGHT,
                                 font_name=FONT_NAME, font_size=dp(14)))
        header.add_widget(vsep(color=LABEL_LIGHT))
        header.add_widget(Label(text="Название отдела", bold=True,
                                 size_hint_x=2.2, color=LABEL_LIGHT,
                                 font_name=FONT_NAME, font_size=dp(14),
                                 halign='left', valign='middle',
                                 text_size=(dp(220), dp(34))))
        header.add_widget(vsep(color=LABEL_LIGHT))
        header.add_widget(Label(text="Должность", bold=True,
                                 size_hint_x=1.8, color=LABEL_LIGHT,
                                 font_name=FONT_NAME, font_size=dp(14),
                                 halign='left', valign='middle',
                                 text_size=(dp(180), dp(34))))
        header.add_widget(vsep(color=LABEL_LIGHT))
        header.add_widget(Label(text="Фамилия Имя Отчество", bold=True,
                                 size_hint_x=2.5, color=LABEL_LIGHT,
                                 font_name=FONT_NAME, font_size=dp(14),
                                 halign='left', valign='middle',
                                 text_size=(dp(260), dp(34))))
        header.add_widget(vsep(color=LABEL_LIGHT))
        header.add_widget(Label(text="Действия", bold=True,
                                 size_hint_x=None,
                                 width=dp(230), color=LABEL_LIGHT,
                                 font_name=FONT_NAME, font_size=dp(14),
                                 halign='center', valign='middle',
                                 text_size=(dp(230), dp(34))))
        header.add_widget(vsep(color=LABEL_LIGHT))          # правый край
        add_top_border(header, color=LABEL_LIGHT, thickness=1)
        add_bottom_border(header, color=LABEL_LIGHT, thickness=1)
        content.add_widget(header)

        list_scroll = ScrollView(scroll_type=['bars'], bar_width=dp(8),
                                  effect_cls=NoOverscrollEffect)
        list_grid = GridLayout(cols=1, size_hint_y=None, spacing=2)
        list_grid.bind(minimum_height=list_grid.setter('height'))

        def get_signer(dept):
            signers = self.app.data.get('department_signer', {})
            entry = signers.get(dept)
            if entry and entry.get('name'):
                return (entry.get('position') or 'Энергетик',
                        entry.get('name'))
            em = self.app.data.get('department_energetic', {})
            return ('Энергетик', em.get(dept) or DEFAULT_ENERGETIC)

        def delete_dept(ii):
            name = self.app.data['departments'][ii]

            def _do():
                try:
                    self.app.data['departments'].pop(ii)
                    self.app.data.get('department_signer', {}).pop(name, None)
                    self.app.data.get('department_energetic', {}).pop(name, None)
                    for emp in self.app.data['employees']:
                        if emp.get('department', '') == name:
                            emp['department'] = ''
                    save_data(self.app.data)
                    rebuild_list()
                    self.refresh()
                except Exception:
                    pass

            ask_password_and_run(
                DELETE_PASSWORD, _do,
                description=f"Удалить отдел:\n«{name}»?")

        def open_dept_editor(idx):
            """idx=None — создание, иначе — редактирование."""
            is_new = (idx is None)
            old_name = '' if is_new else self.app.data['departments'][idx]
            signers = self.app.data.setdefault('department_signer', {})
            entry = signers.get(old_name, {})
            # Для нового отдела — поля пустые, для существующего —
            # подставляем сохранённые значения.
            old_pos = '' if is_new else entry.get('position', 'Энергетик')
            old_fio = '' if is_new else entry.get('name', DEFAULT_ENERGETIC)

            positions_now = list(self.app.data.get('signer_positions',
                                                    ['Энергетик']))
            if old_pos and old_pos not in positions_now:
                positions_now.append(old_pos)

            outer = BoxLayout(orientation='vertical', spacing=10,
                              padding=(20, 15, 20, 15))

            fields = BoxLayout(orientation='vertical', spacing=10,
                               size_hint=(1, None), height=dp(140))

            LBL_W = dp(150)
            BTN_W = dp(130)

            def _make_input(text_value):
                return TextInput(
                    text=text_value, multiline=False,
                    font_size=dp(14), font_name=FONT_NAME,
                    foreground_color=(0.05, 0.05, 0.05, 1),
                    background_color=(1, 1, 1, 1),
                    cursor_color=(0.10, 0.30, 0.70, 1),
                    cursor_width=dp(2),
                    selection_color=(0.20, 0.45, 0.90, 0.40),
                    padding=[dp(8), dp(6), dp(8), dp(6)],
                    size_hint=(1, None), height=dp(32),
                )

            # --- Название отдела ---
            row_name = BoxLayout(size_hint_y=None, height=dp(38), spacing=8)
            row_name.add_widget(Label(
                text="Название:", size_hint=(None, 1), width=LBL_W,
                color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15),
                halign='right', valign='middle',
                text_size=(LBL_W, dp(38))))
            edit_wrap = _make_input(old_name)
            row_name.add_widget(edit_wrap)
            fields.add_widget(row_name)

            # --- Должность (поле + кнопка «Выбрать») ---
            row_pos = BoxLayout(size_hint_y=None, height=dp(38), spacing=8)
            row_pos.add_widget(Label(
                text="Должность:", size_hint=(None, 1), width=LBL_W,
                color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15),
                halign='right', valign='middle',
                text_size=(LBL_W, dp(38))))

            pos_row = BoxLayout(orientation='horizontal', spacing=6,
                                 size_hint=(1, None), height=dp(32))
            pos_w = _make_input(old_pos)
            pos_row.add_widget(pos_w)

            pos_btn = Button(
                text="Выбрать",
                size_hint=(None, 1), width=BTN_W,
                font_name=FONT_NAME, font_size=dp(14), bold=True,
                background_normal='', background_down='',
                background_color=(0.25, 0.55, 0.85, 1),
                color=(1, 1, 1, 1),
            )
            pos_row.add_widget(pos_btn)

            row_pos.add_widget(pos_row)
            fields.add_widget(row_pos)

            # --- ФИО руководителя ---
            row_fio = BoxLayout(size_hint_y=None, height=dp(38), spacing=8)
            row_fio.add_widget(Label(
                text="ФИО руководителя:", size_hint=(None, 1), width=LBL_W,
                color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15),
                halign='right', valign='middle',
                text_size=(LBL_W, dp(38))))
            fio_w = _make_input(old_fio)
            row_fio.add_widget(fio_w)
            fields.add_widget(row_fio)

            outer.add_widget(fields)
            outer.add_widget(Widget())     # распорка — «съедает» лишнюю высоту

            # --- попап со списком существующих должностей подписантов ---
            def _open_positions_picker(*a):
                picker = Popup(title="Существующие должности",
                               size_hint=(0.65, 0.65),
                               title_color=LABEL_LIGHT,
                               title_font=FONT_NAME)

                inner = BoxLayout(orientation='vertical', spacing=6,
                                  padding=8)
                sv = ScrollView(scroll_type=['bars'], bar_width=dp(8),
                                effect_cls=NoOverscrollEffect)
                grid = GridLayout(cols=1, size_hint_y=None, spacing=4)
                grid.bind(minimum_height=grid.setter('height'))

                def _pick(name):
                    pos_w.text = name
                    picker.dismiss()

                def _rename(rename_old):
                    c = BoxLayout(orientation='vertical',
                                  spacing=10, padding=10)
                    c.add_widget(Label(
                        text=f"Новое название для «{rename_old}»:",
                        color=LABEL_LIGHT, halign='center',
                        font_name=FONT_NAME, font_size=dp(15),
                        outline_color=(0, 0, 0, 1), outline_width=1))
                    new_wrap = _make_input(rename_old)
                    c.add_widget(new_wrap)
                    btns2 = BoxLayout(size_hint_y=None,
                                      height=dp(40), spacing=10)
                    ok = Button(text="Сохранить",
                                background_color=(0.3, 0.7, 0.3, 1),
                                color=(1, 1, 1, 1),
                                font_name=FONT_NAME, font_size=dp(15),
                                bold=True)
                    cancel = Button(text="Отмена", color=(1, 1, 1, 1),
                                    font_name=FONT_NAME, font_size=dp(15),
                                    bold=True)
                    btns2.add_widget(ok)
                    btns2.add_widget(cancel)
                    c.add_widget(btns2)
                    rp = Popup(title="Переименовать должность",
                               content=c, size_hint=(0.5, 0.35),
                               title_color=LABEL_LIGHT,
                               title_font=FONT_NAME)

                    def do_rename(*a):
                        new_name = new_wrap.text.strip()
                        if not new_name or new_name == rename_old:
                            rp.dismiss()
                            return
                        sp_list = self.app.data.setdefault(
                            'signer_positions', ['Энергетик'])
                        if new_name in sp_list:
                            rp.dismiss()
                            return
                        sp_list[sp_list.index(rename_old)] = new_name

                        # Обновляем ссылки в department_signer
                        signers_map = self.app.data.get(
                            'department_signer', {})
                        for _d, ent in signers_map.items():
                            if ent.get('position') == rename_old:
                                ent['position'] = new_name

                        if pos_w.text.strip() == rename_old:
                            pos_w.text = new_name

                        save_data(self.app.data)
                        rp.dismiss()
                        rebuild_rows()
                        rebuild_list()

                    ok.bind(on_press=do_rename)
                    cancel.bind(on_press=rp.dismiss)
                    rp.open()

                def _delete(name):
                    signers_map = self.app.data.get('department_signer', {})
                    used_by = [d for d, ent in signers_map.items()
                               if ent.get('position') == name]
                    if used_by:
                        c = BoxLayout(orientation='vertical',
                                      spacing=10, padding=10)
                        c.add_widget(Label(
                            text=(f"Должность «{name}» используется "
                                  f"отделами:\n" + ", ".join(used_by) +
                                  "\n\nСначала измените её у этих отделов."),
                            color=LABEL_LIGHT, halign='center',
                            valign='middle',
                            font_name=FONT_NAME, font_size=dp(15),
                            outline_color=(0, 0, 0, 1), outline_width=1))
                        ok = Button(text="OK", size_hint_y=None,
                                    height=dp(40),
                                    font_name=FONT_NAME, font_size=dp(15),
                                    bold=True,
                                    background_color=(0.3, 0.7, 0.3, 1),
                                    color=(1, 1, 1, 1))
                        c.add_widget(ok)
                        p2 = Popup(title="Нельзя удалить", content=c,
                                   size_hint=(0.55, 0.4),
                                   title_color=LABEL_LIGHT,
                                   title_font=FONT_NAME)
                        ok.bind(on_press=p2.dismiss)
                        p2.open()
                        return

                    def _do():
                        sp_list = self.app.data.get('signer_positions', [])
                        if name in sp_list:
                            sp_list.remove(name)
                            save_data(self.app.data)
                            rebuild_rows()
                            rebuild_list()

                    ask_password_and_run(
                        DELETE_PASSWORD, _do,
                        description=(f"Удалить должность подписанта:\n"
                                     f"«{name}»?"))

                def rebuild_rows():
                    grid.clear_widgets()
                    sp_list = list(self.app.data.get(
                        'signer_positions', ['Энергетик']))
                    if not sp_list:
                        grid.add_widget(Label(
                            text="(список пуст)", color=LABEL_LIGHT,
                            font_name=FONT_NAME, font_size=dp(14),
                            size_hint_y=None, height=dp(40)))
                        return
                    for nm in sp_list:
                        row = BoxLayout(size_hint_y=None,
                                        height=dp(40), spacing=4)
                        b = Button(text=nm, size_hint_x=1,
                                   font_name=FONT_NAME, font_size=dp(14),
                                   color=(1, 1, 1, 1))
                        b.bind(on_press=lambda *a, x=nm: _pick(x))
                        row.add_widget(b)

                        ren_btn = Button(
                            text="Изменить",
                            size_hint_x=None, width=dp(130),
                            font_name=FONT_NAME, font_size=dp(15),
                            bold=True,
                            background_color=(0.35, 0.55, 0.85, 1),
                            color=(1, 1, 1, 1))
                        ren_btn.bind(on_press=lambda *a, x=nm: _rename(x))
                        row.add_widget(ren_btn)

                        del_btn = Button(
                            text="Удалить",
                            size_hint_x=None, width=dp(130),
                            font_name=FONT_NAME, font_size=dp(15),
                            bold=True,
                            background_color=(0.9, 0.35, 0.35, 1),
                            color=(1, 1, 1, 1))
                        del_btn.bind(on_press=lambda *a, x=nm: _delete(x))
                        row.add_widget(del_btn)

                        grid.add_widget(row)

                rebuild_rows()
                sv.add_widget(grid)
                inner.add_widget(sv)

                close_b = Button(text="Закрыть", size_hint_y=None,
                                 height=dp(40), color=(1, 1, 1, 1),
                                 font_name=FONT_NAME, font_size=dp(15),
                                 bold=True)
                close_b.bind(on_press=picker.dismiss)
                inner.add_widget(close_b)
                picker.content = inner
                picker.open()

            pos_btn.bind(on_press=_open_positions_picker)

            # --- кнопки Сохранить / Отмена ---
            btns = BoxLayout(size_hint_y=None, height=dp(50), spacing=10)
            ok = Button(text="Сохранить",
                        background_color=(0.3, 0.7, 0.3, 1),
                        color=(1, 1, 1, 1),
                        font_name=FONT_NAME, font_size=dp(16), bold=True)
            cancel = Button(text="Отмена", color=(1, 1, 1, 1),
                            font_name=FONT_NAME, font_size=dp(16), bold=True)
            btns.add_widget(ok)
            btns.add_widget(cancel)
            outer.add_widget(btns)

            p = Popup(title=("Новый отдел" if is_new
                             else "Изменить отдел"),
                      content=outer, size_hint=(0.6, 0.42),
                      title_color=LABEL_LIGHT, title_font=FONT_NAME)

            def on_ok(*a):
                new_name = edit_wrap.text.strip()
                new_pos = pos_w.text.strip()
                new_fio = fio_w.text.strip()

                missing = []
                if not new_name:
                    missing.append("Название отдела")
                if not new_pos:
                    missing.append("Должность")
                if not new_fio:
                    missing.append("ФИО руководителя")
                if missing:
                    err = BoxLayout(orientation='vertical',
                                    spacing=10, padding=10)
                    err.add_widget(Label(
                        text=("Заполните обязательные поля:\n• "
                              + "\n• ".join(missing)),
                        color=LABEL_LIGHT, halign='center', valign='middle',
                        font_name=FONT_NAME, font_size=dp(15),
                        outline_color=(0, 0, 0, 1), outline_width=1))
                    err_btn = Button(
                        text="OK", size_hint_y=None, height=dp(40),
                        font_name=FONT_NAME, font_size=dp(16), bold=True,
                        background_color=(0.3, 0.7, 0.3, 1),
                        color=(1, 1, 1, 1))
                    err.add_widget(err_btn)
                    err_popup = Popup(title="Не все поля заполнены",
                                      content=err, size_hint=(0.45, 0.35),
                                      title_color=LABEL_LIGHT,
                                      title_font=FONT_NAME)
                    err_btn.bind(on_press=err_popup.dismiss)
                    err_popup.open()
                    return

                if (new_name != old_name
                        and new_name in self.app.data['departments']):
                    return

                sp = self.app.data.setdefault('signer_positions',
                                              ['Энергетик'])
                if new_pos not in sp:
                    sp.append(new_pos)

                if is_new:
                    self.app.data['departments'].append(new_name)
                else:
                    if new_name != old_name:
                        self.app.data['departments'][idx] = new_name
                        for emp in self.app.data['employees']:
                            if emp.get('department', '') == old_name:
                                emp['department'] = new_name
                        signers.pop(old_name, None)
                        self.app.data.get('department_energetic', {}).pop(
                            old_name, None)
                signers[new_name] = {'position': new_pos, 'name': new_fio}
                save_data(self.app.data)
                p.dismiss()
                rebuild_list()
                self.refresh()

            ok.bind(on_press=on_ok)
            cancel.bind(on_press=p.dismiss)
            p.open()

        def rebuild_list():
            list_grid.clear_widgets()
            for i, d in enumerate(self.app.data['departments']):
                row = BoxLayout(size_hint_y=None, height=dp(42), spacing=6)

                row.add_widget(vsep(color=LABEL_LIGHT))     # левый край

                # №
                row.add_widget(Label(text=str(i + 1),
                                      size_hint_x=None, width=dp(40),
                                      color=LABEL_LIGHT,
                                      font_name=FONT_NAME, font_size=dp(14),
                                      halign='center', valign='middle',
                                      text_size=(dp(40), dp(42))))
                row.add_widget(vsep(color=LABEL_LIGHT))

                # Название отдела
                row.add_widget(Label(text=d, color=(1, 1, 1, 1),
                                      size_hint_x=2.2,
                                      font_name=FONT_NAME,
                                      font_size=dp(15), bold=True,
                                      halign='left', valign='middle',
                                      text_size=(dp(220), dp(42))))
                row.add_widget(vsep(color=LABEL_LIGHT))

                # Должность / ФИО
                sign_pos, sign_fio = get_signer(d)
                row.add_widget(Label(text=sign_pos,
                                      size_hint_x=1.8,
                                      color=(0.85, 0.90, 1.0, 1),
                                      font_name=FONT_NAME,
                                      font_size=dp(13),
                                      halign='left', valign='middle',
                                      text_size=(dp(180), dp(42))))
                row.add_widget(vsep(color=LABEL_LIGHT))

                row.add_widget(Label(text=sign_fio,
                                      size_hint_x=2.5,
                                      color=(0.85, 0.90, 1.0, 1),
                                      font_name=FONT_NAME,
                                      font_size=dp(13),
                                      halign='left', valign='middle',
                                      text_size=(dp(260), dp(42))))
                row.add_widget(vsep(color=LABEL_LIGHT))

                # Кнопки
                btns_box = BoxLayout(size_hint_x=None, width=dp(230),
                                     spacing=4)
                edit_btn = Button(text="Изменить",
                                  font_name=FONT_NAME, font_size=dp(15),
                                  bold=True,
                                  background_color=(0.35, 0.55, 0.85, 1),
                                  color=(1, 1, 1, 1))
                edit_btn.bind(on_press=lambda *a, ii=i:
                              open_dept_editor(ii))
                btns_box.add_widget(edit_btn)

                del_btn = Button(text="Удалить",
                                 font_name=FONT_NAME, font_size=dp(15),
                                 bold=True,
                                 background_color=(0.9, 0.35, 0.35, 1),
                                 color=(1, 1, 1, 1))
                del_btn.bind(on_press=lambda *a, ii=i: delete_dept(ii))
                btns_box.add_widget(del_btn)

                row.add_widget(btns_box)

                row.add_widget(vsep(color=LABEL_LIGHT))     # правый край

                add_bottom_border(row)
                list_grid.add_widget(row)

        add_btn.bind(on_press=lambda *a: open_dept_editor(None))
        rebuild_list()
        list_scroll.add_widget(list_grid)
        content.add_widget(list_scroll)

        close_btn = Button(text="Закрыть", size_hint_y=None, height=dp(40),
                           color=(1, 1, 1, 1),
                           font_name=FONT_NAME, font_size=dp(16), bold=True)
        content.add_widget(close_btn)
        popup = Popup(title="Отделы", content=content,
                      size_hint=(0.80, 0.65), title_color=LABEL_LIGHT,
                      title_font=FONT_NAME)
        close_btn.bind(on_press=popup.dismiss)
        popup.open()