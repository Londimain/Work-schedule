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

from config import (FONT_NAME, LABEL_LIGHT, DEFAULT_POSITIONS,
                    DEFAULT_DEPARTMENTS, DEFAULT_ORG,
                    DEPT_BAR_BG, DEPT_BAR_FG)
from data_utils import save_data
from ui_helpers import (add_bottom_border, add_top_border,
                        add_left_border, add_right_border, vsep)
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

        scroll = ScrollView(scroll_type=['bars'], effect_cls='ScrollEffect')
        self.list_layout = GridLayout(cols=1, size_hint_y=None,
                                       spacing=0, padding=5)
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
        with bar.canvas.before:
            Color = None  # placeholder, see below
        # на самом деле:
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

    def refresh(self):
        self.list_layout.clear_widgets()

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
        self.list_layout.add_widget(header)

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
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(
            text=f"Удалить сотрудника:\n«{emp.get('name', '')}»?",
            color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15),
            outline_color=(0, 0, 0, 1), outline_width=1,
            halign='center'))
        btns = BoxLayout(size_hint_y=None, height=dp(40), spacing=10)
        yes = Button(text="Да", background_color=(0.9, 0.35, 0.35, 1),
                     color=(1, 1, 1, 1), font_name=FONT_NAME,
                     font_size=dp(16), bold=True)
        no = Button(text="Нет", color=(1, 1, 1, 1),
                    font_name=FONT_NAME, font_size=dp(16), bold=True)
        btns.add_widget(yes)
        btns.add_widget(no)
        content.add_widget(btns)
        popup = Popup(title="Подтверждение", content=content,
                      size_hint=(0.5, 0.35), title_color=LABEL_LIGHT,
                      title_font=FONT_NAME)

        def do_del(*a):
            self.app.data['employees'].pop(idx)
            save_data(self.app.data)
            popup.dismiss()
            self.refresh()

        yes.bind(on_press=do_del)
        no.bind(on_press=popup.dismiss)
        popup.open()

    def show_edit_popup(self, idx):
        emp = (self.app.data['employees'][idx] if idx is not None
               else {'name': '', 'position': '', 'department': '',
                     'show_in_timesheet': True})
        positions = self.app.data.get('positions', []) or list(DEFAULT_POSITIONS)
        departments = self.app.data.get('departments', [])

        outer = BoxLayout(orientation='vertical', spacing=0,
                          padding=(10, 10, 10, 10))
        top_anchor = AnchorLayout(anchor_x='center', anchor_y='top')

        fields = BoxLayout(orientation='vertical', spacing=10,
                           size_hint=(1, None), height=dp(160))

        row_name = BoxLayout(size_hint_y=None, height=dp(44), spacing=5)
        row_name.add_widget(Label(text="Фамилия Имя Отчество",
                                   size_hint_x=0.4, color=LABEL_LIGHT,
                                   font_name=FONT_NAME, font_size=dp(15),
                                   outline_color=(0, 0, 0, 1),
                                   outline_width=1))
        name_w = CenteredField(text=emp.get('name', ''), font_size=dp(16),
                                pad_lr=dp(10), halign='left')
        name_w.size_hint_x = 0.6
        row_name.add_widget(name_w)
        fields.add_widget(row_name)

        row_dept = BoxLayout(size_hint_y=None, height=dp(44), spacing=5)
        row_dept.add_widget(Label(text="Отдел", size_hint_x=0.4,
                                   color=LABEL_LIGHT,
                                   font_name=FONT_NAME, font_size=dp(15),
                                   outline_color=(0, 0, 0, 1),
                                   outline_width=1))
        dept_w = CenteredSpinner(
            text=emp.get('department', '') or (departments[0] if departments else ''),
            values=departments, spinner_height=dp(32), font_size=dp(15))
        dept_w.size_hint_x = 0.6
        row_dept.add_widget(dept_w)
        fields.add_widget(row_dept)

        row_pos = BoxLayout(size_hint_y=None, height=dp(44), spacing=5)
        row_pos.add_widget(Label(text="Должность (профессия)",
                                  size_hint_x=0.4, color=LABEL_LIGHT,
                                  font_name=FONT_NAME, font_size=dp(15),
                                  outline_color=(0, 0, 0, 1),
                                  outline_width=1))
        pos_w = CenteredSpinner(
            text=emp.get('position', '') or (positions[0] if positions else ''),
            values=positions, spinner_height=dp(32), font_size=dp(15))
        pos_w.size_hint_x = 0.6
        row_pos.add_widget(pos_w)
        fields.add_widget(row_pos)

        top_anchor.add_widget(fields)
        outer.add_widget(top_anchor)

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
                      content=outer, size_hint=(0.6, 0.55),
                      title_color=LABEL_LIGHT, title_font=FONT_NAME)

        def on_save(*a):
            name = name_w.text.strip()
            if not name:
                return
            new_dept = dept_w.text.strip()
            show_in = emp.get('show_in_timesheet', True)
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

        list_scroll = ScrollView()
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
            flags[name] = not flags.get(name, True)
            save_data(self.app.data)
            rebuild_list()

        def delete_pos(ii):
            try:
                name = self.app.data['positions'][ii]
                self.app.data['positions'].pop(ii)
                self.app.data.get('night_flags', {}).pop(name, None)
                self.app.data.get('overtime_flags', {}).pop(name, None)
                self.app.data.get('holiday_flags', {}).pop(name, None)
                save_data(self.app.data)
                rebuild_list()
            except Exception:
                pass

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
                old_flag_h = flags_h.pop(old_name, True)
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

                holiday_on = bool(self.app.data['holiday_flags'].get(p, True))
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
            self.app.data.setdefault('holiday_flags', {}).setdefault(txt, True)
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
        if not self.app.data['departments']:
            self.app.data['departments'] = list(DEFAULT_DEPARTMENTS)

        content = BoxLayout(orientation='vertical', spacing=8, padding=10)
        add_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=5)
        new_dept_wrap = CenteredField(text='', font_size=dp(15),
                                       pad_lr=dp(10), halign='left')
        new_dept_wrap.size_hint_x = 0.7
        add_row.add_widget(new_dept_wrap)
        add_btn = Button(text="Добавить", size_hint_x=0.3,
                         background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1),
                         font_name=FONT_NAME, font_size=dp(16), bold=True)
        add_row.add_widget(add_btn)
        content.add_widget(add_row)

        list_scroll = ScrollView()
        list_grid = GridLayout(cols=1, size_hint_y=None, spacing=2)
        list_grid.bind(minimum_height=list_grid.setter('height'))

        def delete_dept(ii):
            try:
                name = self.app.data['departments'][ii]
                self.app.data['departments'].pop(ii)
                for emp in self.app.data['employees']:
                    if emp.get('department', '') == name:
                        emp['department'] = ''
                save_data(self.app.data)
                rebuild_list()
                self.refresh()
            except Exception:
                pass

        def edit_dept(ii):
            old_name = self.app.data['departments'][ii]
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
            p = Popup(title="Изменить отдел", content=c,
                      size_hint=(0.5, 0.35), title_color=LABEL_LIGHT,
                      title_font=FONT_NAME)

            def on_ok(*a):
                new_name = edit_wrap.text.strip()
                if not new_name or new_name == old_name:
                    p.dismiss()
                    return
                if new_name in self.app.data['departments']:
                    p.dismiss()
                    return
                self.app.data['departments'][ii] = new_name
                for emp in self.app.data['employees']:
                    if emp.get('department', '') == old_name:
                        emp['department'] = new_name
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
                row = BoxLayout(size_hint_y=None, height=dp(44), spacing=6)
                row.add_widget(Label(text=d, color=(1, 1, 1, 1),
                                      font_name=FONT_NAME,
                                      font_size=dp(16), bold=True,
                                      outline_color=(0, 0, 0, 1),
                                      outline_width=1,
                                      halign='left', valign='middle',
                                      text_size=(dp(300), dp(44))))
                edit_btn = Button(text="Изменить", size_hint_x=None, width=dp(130),
                                  font_name=FONT_NAME, font_size=dp(16), bold=True,
                                  background_color=(0.35, 0.55, 0.85, 1),
                                  color=(1, 1, 1, 1))
                edit_btn.bind(on_press=lambda *a, ii=i: edit_dept(ii))
                row.add_widget(edit_btn)
                del_btn = Button(text="Удалить", size_hint_x=None, width=dp(130),
                                 font_name=FONT_NAME, font_size=dp(16), bold=True,
                                 background_color=(0.9, 0.35, 0.35, 1),
                                 color=(1, 1, 1, 1))
                del_btn.bind(on_press=lambda *a, ii=i: delete_dept(ii))
                row.add_widget(del_btn)
                list_grid.add_widget(row)

        def add_dept(*a):
            txt = new_dept_wrap.text.strip()
            if not txt:
                return
            if txt in self.app.data['departments']:
                new_dept_wrap.text = ''
                return
            self.app.data['departments'].append(txt)
            save_data(self.app.data)
            new_dept_wrap.text = ''
            rebuild_list()

        add_btn.bind(on_press=add_dept)
        new_dept_wrap.input.bind(on_text_validate=add_dept)
        rebuild_list()
        list_scroll.add_widget(list_grid)
        content.add_widget(list_scroll)

        close_btn = Button(text="Закрыть", size_hint_y=None, height=dp(40),
                           color=(1, 1, 1, 1),
                           font_name=FONT_NAME, font_size=dp(16), bold=True)
        content.add_widget(close_btn)
        popup = Popup(title="Отделы", content=content,
                      size_hint=(0.55, 0.55), title_color=LABEL_LIGHT,
                      title_font=FONT_NAME)
        close_btn.bind(on_press=popup.dismiss)
        popup.open()