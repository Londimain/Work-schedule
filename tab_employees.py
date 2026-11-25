# tab_employees.py
# -*- coding: utf-8 -*-
"""Вкладка «Рабочий персонал»."""
import config  # noqa: F401 — настройка Kivy первой

from datetime import datetime

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.textinput import TextInput

# --- ЗАМЕНА СТАНДАРТНОЙ КНОПКИ НА КНОПКУ С ЭФФЕКТОМ НАВЕДЕНИЯ ---
from ui_widgets import CenteredSpinner, HoverButton, _is_widget_covered
from ui_widgets import HoverButton as Button 

from config import (FONT_NAME, LABEL_LIGHT, DEFAULT_POSITIONS,
                    DEFAULT_DEPARTMENTS, DEFAULT_ORG,
                    DEPT_BAR_BG, DEPT_BAR_FG,
                    DEFAULT_ENERGETIC, DELETE_PASSWORD)
from data_utils import (save_data, set_show_in_timesheet,
                        save_local_order, get_local_collapsed_depts, 
                        save_local_collapsed_depts) 
from ui_helpers import (add_bottom_border, add_top_border,
                        add_left_border, add_right_border, vsep,
                        NoOverscrollEffect, ask_password_and_run,
                        bind_enter_key)

# ---------------------------------------------------------------------------
class HoverRow(BoxLayout):
    """Строка таблицы с эффектом легкого осветления при наведении мыши."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hovering = False
        with self.canvas.before:
            self._bg_color = Color(0, 0, 0, 0) # Прозрачный по умолчанию
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)
        
        Window.bind(mouse_pos=self._on_mouse_pos)
        self.bind(parent=self._on_parent)

    def _on_parent(self, instance, parent):
        if parent is None:
            try:
                Window.unbind(mouse_pos=self._on_mouse_pos)
            except Exception:
                pass

    def _update_rect(self, *a):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _on_mouse_pos(self, window, pos):
        if not self.get_root_window() or self.disabled:
            return
        
        try:
            wx, wy = self.to_window(self.x, self.y)
            inside = wx <= pos[0] <= wx + self.width and wy <= pos[1] <= wy + self.height
            
            # Вызываем тяжелую проверку попапа ТОЛЬКО когда мышь заходит на виджет
            if inside and not self._hovering:
                if _is_widget_covered(self):
                    return
                self._hovering = True
                self._bg_color.rgba = (1, 1, 1, 0.1)
            elif not inside and self._hovering:
                self._hovering = False
                self._bg_color.rgba = (0, 0, 0, 0)
        except Exception:
            pass


class RightClickBox(BoxLayout):
    SELECT_COLOR = (1.00, 0.72, 0.10, 1)
    SELECT_TH = 3
    HOVER_BG = (1, 1, 1, 0.1) # Эффект при наведении

    def __init__(self, on_right_click=None, on_left_click=None, **kwargs):
        super().__init__(**kwargs)
        self._on_right_click = on_right_click
        self._on_left_click = on_left_click  
        self._selected = False
        self._sel_top = None
        self._sel_bottom = None
        self._sel_left = None
        self._sel_right = None
        self._hovering = False

        with self.canvas.before:
            self._bg_color = Color(0, 0, 0, 0)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        self.bind(pos=self._update_sel, size=self._update_sel)
        Clock.schedule_once(self._init_sel_canvas, 0)

        Window.bind(mouse_pos=self._on_mouse_pos)
        self.bind(parent=self._on_parent)

    def _on_parent(self, instance, parent):
        if parent is None:
            try:
                Window.unbind(mouse_pos=self._on_mouse_pos)
            except Exception:
                pass

    def _update_bg(self, *a):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _on_mouse_pos(self, window, pos):
        if not self.get_root_window() or self.disabled:
            return
        
        try:
            wx, wy = self.to_window(self.x, self.y)
            inside = wx <= pos[0] <= wx + self.width and wy <= pos[1] <= wy + self.height
            
            if inside and not self._hovering:
                if _is_widget_covered(self):
                    return
                self._hovering = True
                self._bg_color.rgba = self.HOVER_BG
            elif not inside and self._hovering:
                self._hovering = False
                self._bg_color.rgba = (0, 0, 0, 0)
        except Exception:
            pass

    def _init_sel_canvas(self, dt=0):
        if self._sel_top is not None:
            return
        with self.canvas.after:
            Color(*self.SELECT_COLOR)
            self._sel_top = Rectangle(pos=self.pos, size=(0, 0))
            self._sel_bottom = Rectangle(pos=self.pos, size=(0, 0))
            self._sel_left = Rectangle(pos=self.pos, size=(0, 0))
            self._sel_right = Rectangle(pos=self.pos, size=(0, 0))
        self._update_sel()

    def set_selected(self, on):
        self._selected = bool(on)
        if self._sel_top is None:
            self._init_sel_canvas()
        self._update_sel()

    def _update_sel(self, *a):
        if self._sel_top is None:
            return
        if not self._selected:
            for r in (self._sel_top, self._sel_bottom,
                      self._sel_left, self._sel_right):
                r.size = (0, 0)
            return
        t = dp(self.SELECT_TH)
        x, y = self.x, self.y
        w, h = self.width, self.height
        self._sel_top.pos = (x, y + h - t)
        self._sel_top.size = (w, t)
        self._sel_bottom.pos = (x, y)
        self._sel_bottom.size = (w, t)
        self._sel_left.pos = (x, y)
        self._sel_left.size = (t, h)
        self._sel_right.pos = (x + w - t, y)
        self._sel_right.size = (t, h)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if getattr(touch, 'button', None) == 'right':
                if self._on_right_click is not None:
                    try:
                        self._on_right_click(touch)
                    except Exception as e:
                        print("Right-click handler error:", e)
                return True
            elif getattr(touch, 'button', None) == 'left':
                if self._on_left_click is not None:
                    try:
                        self._on_left_click(touch)
                        return True  
                    except Exception as e:
                        print("Left-click handler error:", e)
        return super().on_touch_down(touch)


class EmployeesTab(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        self._collapsed_depts = get_local_collapsed_depts() 
        
        # --- ПЕРЕМЕННЫЕ ДЛЯ АВТООБНОВЛЕНИЯ ОКОН ---
        self.active_positions_popup = None
        self.active_positions_rebuild = None
        self.active_depts_popup = None
        self.active_depts_rebuild = None
        self.active_edit_popup = None
        self.active_edit_rebuild = None
        self.active_dept_editor_popup = None      
        self.active_dept_editor_rebuild = None    
        self.active_dept_picker_popup = None
        self.active_dept_picker_rebuild = None
        # -------------------------------------------

        # Сессия авторизации по отделам (кто уже ввел пароль в этой сессии работы).
        # Сбрасывается при снятии всех галочек «В таблицу» и при перезапуске.
        self._authorized_depts = set()
        
        with self.canvas.before:
            Color(*config.TABLE_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda i, v: setattr(self._bg, 'pos', v),
                  size=lambda i, v: setattr(self._bg, 'size', v))
        
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
        self.add_widget(top)

        self.header_holder = GridLayout(cols=1, size_hint_y=None,
                                         height=dp(37),
                                         padding=(5, 0, 5, 0))
        self.add_widget(self.header_holder)
        self._build_header()

        self.scroll_view = ScrollView(scroll_type=['bars'],
                            effect_cls=NoOverscrollEffect)
        self.list_layout = GridLayout(cols=1, size_hint_y=None,
                                       spacing=0, padding=(5, 0, 5, 5))
        self.list_layout.bind(minimum_height=self.list_layout.setter('height'))
        self.scroll_view.add_widget(self.list_layout)
        self.add_widget(self.scroll_view)
        self.refresh()

    def _active_dept(self):
        for emp in self.app.data['employees']:
            if emp.get('show_in_timesheet', False):
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
        
        btn = HoverButton(text="OK", size_hint_y=None, height=dp(40),
                     font_name=FONT_NAME, font_size=dp(16),
                     background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1))
        content.add_widget(btn)
        popup = Popup(title="Только один отдел", content=content,
                      size_hint=(0.55, 0.4), title_color=LABEL_LIGHT,
                      title_font=FONT_NAME, auto_dismiss=False)
        btn.bind(on_press=popup.dismiss)
        bind_enter_key(popup, popup.dismiss)
        popup.open()

    def _dept_has_password(self, dept):
        """True, если у отдела задан пароль."""
        if not dept:
            return False
        pw = self.app.data.get('department_passwords', {}).get(dept, '')
        return bool(pw)

    def _check_dept_access(self, dept, on_success):
        """Проверяет, есть ли пароль у отдела. Если есть и он не разблокирован,
        запрашивает его. В случае успеха вызывает on_success()."""
        if not dept:
            on_success()
            return
        if not self._dept_has_password(dept) or dept in self._authorized_depts:
            on_success()
            return
        self._ask_dept_password(dept, on_success)

    def _toggle_in_timesheet(self, idx, value):
        try:
            emp = self.app.data['employees'][idx]
            my_dept = emp.get('department', '')

            if value:
                active = self._active_dept()
                # Ограничение: табель ведется только по одному отделу.
                # Если активный уже есть и он не наш — блокируем (старое поведение).
                if active and active != my_dept:
                    self._show_dept_conflict(active)
                    self.refresh()
                    return

                # Отдел защищен паролем, мы в нем еще не авторизованы,
                # и это не уже активный отдел (в активном мы «внутри»).
                if (self._dept_has_password(my_dept)
                        and my_dept not in self._authorized_depts
                        and my_dept != active):
                    # Откатываем визуальную галочку и спрашиваем пароль.
                    self.refresh()
                    self._ask_dept_password(
                        my_dept,
                        on_success=lambda: self._toggle_in_timesheet_do(idx, True))
                    return

            self._toggle_in_timesheet_do(idx, value)
        except Exception as e:
            print("toggle error:", e)

    def _toggle_in_timesheet_do(self, idx, value):
        """Непосредственно меняет флаг и сохраняет его."""
        try:
            emp = self.app.data['employees'][idx]
            emp_id = emp.get('id')
            emp['show_in_timesheet'] = bool(value)
            if emp_id:
                set_show_in_timesheet(emp_id, bool(value))

            # Если после снятия не осталось ни одной галочки вообще —
            # сбрасываем сессию: в следующий раз при постановке спросим пароль снова.
            if not value and not self._active_dept():
                self._authorized_depts.clear()

            self.refresh()
        except Exception as e:
            print("toggle_do error:", e)

    def _ask_dept_password(self, dept, on_success):
        """Запрашивает пароль отдела. При успехе добавляет отдел в сессию
        и вызывает on_success(). Пароль admins подходит для любого отдела."""
        from config import DELETE_PASSWORD

        stored = self.app.data.get('department_passwords', {}).get(dept, '')

        content = BoxLayout(orientation='vertical', spacing=8, padding=12,
                            size_hint=(1, None), height=dp(230))
        
        lbl = Label(
            text=f"Отдел «{dept}» защищён паролем.\n"
                 f"Введите пароль для доступа:",
            color=LABEL_LIGHT, halign='center', valign='middle',
            font_name=FONT_NAME, font_size=dp(14),
            outline_color=(0, 0, 0, 1), outline_width=1,
            size_hint_y=None)
        lbl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1] + dp(10)))
        content.add_widget(lbl)

        pw = TextInput(
            multiline=False, password=True,
            font_size=dp(15), font_name=FONT_NAME,
            foreground_color=(0.05, 0.05, 0.05, 1),
            background_color=(1, 1, 1, 1),
            cursor_color=(0.10, 0.30, 0.70, 1),
            padding=[dp(8), dp(6), dp(8), dp(6)],
            size_hint_y=None, height=dp(34))
        content.add_widget(pw)

        err = Label(text="", color=(1, 0.4, 0.4, 1),
                    font_name=FONT_NAME, font_size=dp(13),
                    size_hint_y=None, height=dp(20))
        content.add_widget(err)

        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=10)
        ok = Button(text="Войти",
                    background_color=(0.25, 0.55, 0.85, 1),
                    color=(1, 1, 1, 1), font_name=FONT_NAME,
                    font_size=dp(15), bold=True)
        cancel = Button(text="Отмена", color=(1, 1, 1, 1),
                        font_name=FONT_NAME, font_size=dp(15), bold=True)
        btns.add_widget(ok)
        btns.add_widget(cancel)
        content.add_widget(btns)

        popup = Popup(title="Доступ к отделу", content=content,
                      size_hint=(0.45, None), height=dp(240),
                      title_color=LABEL_LIGHT, title_font=FONT_NAME,
                      auto_dismiss=False)

        def do_ok(*a):
            val = pw.text
            if val == stored or val == DELETE_PASSWORD:
                self._authorized_depts.add(dept)
                popup.dismiss()
                Clock.schedule_once(lambda dt: on_success(), 0.1)
            else:
                err.text = "Неверный пароль"
                pw.text = ""

        ok.bind(on_press=do_ok)
        cancel.bind(on_press=popup.dismiss)
        pw.bind(on_text_validate=do_ok)
        bind_enter_key(popup, do_ok)
        popup.open()

    def _update_dept_bar_color(self, dept):
        for child in self.list_layout.children:
            if getattr(child, 'raw_name', None) == dept or (dept == '' and getattr(child, 'raw_name', None) == 'Без отдела'):
                idxs = [i for i, e in enumerate(self.app.data['employees']) if e.get('department', '') == dept]
                if dept == '':
                     idxs = [i for i, e in enumerate(self.app.data['employees']) if e.get('department', '') not in self.app.data.get('departments', [])]
                
                has_checked = any(self.app.data['employees'][i].get('show_in_timesheet', False) for i in idxs)
                
                if has_checked:
                    bg = config.ACTIVE_DEPT_BAR_BG
                    fg = config.ACTIVE_DEPT_BAR_FG
                else:
                    bg = config.DEPT_BAR_BG if dept != '' else (0.30, 0.30, 0.34, 1)
                    fg = config.DEPT_BAR_FG
                    
                child.canvas.before.clear()
                with child.canvas.before:
                    Color(*bg)
                    rect = Rectangle(pos=child.pos, size=child.size)
                child.bind(pos=lambda i, v, r=rect: setattr(r, 'pos', v),
                           size=lambda i, v, r=rect: setattr(r, 'size', v))
                
                if hasattr(child, 'lbl'):
                    child.lbl.color = fg
                break

    # ---------------- перестановка ---------------------------------------
    def _employee_neighbor(self, idx, direction):
        employees = self.app.data['employees']
        if idx < 0 or idx >= len(employees):
            return None
        dept = employees[idx].get('department', '')
        same_dept = [i for i, e in enumerate(employees)
                     if e.get('department', '') == dept]
        try:
            pos = same_dept.index(idx)
        except ValueError:
            return None
        new_pos = pos + direction
        if new_pos < 0 or new_pos >= len(same_dept):
            return None
        return same_dept[new_pos]

    def _move_employee(self, idx, direction):
        other = self._employee_neighbor(idx, direction)
        if other is None:
            return
        employees = self.app.data['employees']
        employees[idx], employees[other] = employees[other], employees[idx]
        self._save_local_order()
        self.refresh()

    def _move_employee_to(self, idx, where):
        employees = self.app.data['employees']
        if idx < 0 or idx >= len(employees):
            return
        emp = employees.pop(idx)
        dept = emp.get('department', '')
        same_dept = [i for i, e in enumerate(employees)
                     if e.get('department', '') == dept]
        if not same_dept:
            employees.insert(idx, emp)
            return
        if where == 'top':
            insert_at = same_dept[0]
        else:
            insert_at = same_dept[-1] + 1
        employees.insert(insert_at, emp)
        self._save_local_order()
        self.refresh()

    def _move_department(self, name, direction):
        depts = self.app.data.get('departments', [])
        try:
            idx = depts.index(name)
        except ValueError:
            return
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(depts):
            return
        depts[idx], depts[new_idx] = depts[new_idx], depts[idx]
        self._save_local_order()
        self.refresh()

    def _move_department_to(self, name, where):
        depts = self.app.data.get('departments', [])
        if name not in depts:
            return
        depts.remove(name)
        if where == 'top':
            depts.insert(0, name)
        else:
            depts.append(name)
        self._save_local_order()
        self.refresh()
        
    def _save_local_order(self):
        try:
            save_local_order(self.app.data.get('departments', []),
                             self.app.data.get('employees', []))
        except Exception as e:
            print("Не удалось сохранить локальный порядок:", e)

    # ---------------- контекстное меню -----------------------------------
    def _open_menu(self, items, touch, highlight_widget=None):
        items = [(t, cb) for t, cb in items if t is not None or cb is not None]
        cleaned = []
        for t, cb in items:
            if t is None:
                if not cleaned or cleaned[-1][0] is None:
                    continue
                cleaned.append((None, None))
            else:
                cleaned.append((t, cb))
        while cleaned and cleaned[-1][0] is None:
            cleaned.pop()
        if not cleaned:
            return

        cleaned.append((None, None))
        cleaned.append(("Отмена", lambda: None))

        content = BoxLayout(orientation='vertical', spacing=2, padding=4)
        popup = Popup(
            title='',
            content=content,
            size_hint=(None, None),
            separator_height=0,
            background_color=(0.13, 0.13, 0.16, 1),
            title_color=LABEL_LIGHT,
            title_font=FONT_NAME,
            auto_dismiss=False
        )

        item_h = dp(44)
        sep_h = dp(8)
        popup_w = dp(300)
        total_h = dp(8)
        for t, _cb in cleaned:
            total_h += (sep_h if t is None else item_h)
        popup.size = (popup_w, total_h)

        def _wrap(cb):
            def _go(*a):
                popup.dismiss()
                Clock.schedule_once(lambda dt: cb(), 0)
            return _go

        for t, cb in cleaned:
            if t is None:
                sep = Widget(size_hint_y=None, height=sep_h)
                with sep.canvas.before:
                    Color(0.35, 0.35, 0.40, 1)
                    _r = Rectangle(pos=sep.pos, size=sep.size)
                sep.bind(pos=lambda i, v, r=_r: setattr(r, 'pos', v),
                         size=lambda i, v, r=_r: setattr(r, 'size', v))
                content.add_widget(sep)
                continue
            b = Button(
                text=t,
                size_hint_y=None, height=item_h,
                font_name=FONT_NAME, font_size=dp(15),
                background_normal='', background_down='',
                background_color=(0.20, 0.20, 0.24, 1),
                color=(1, 1, 1, 1),
                halign='center',
                valign='middle',
            )
            b.bind(size=lambda i, v: setattr(i, 'text_size', v))
            b.bind(on_press=_wrap(cb))
            content.add_widget(b)

        if highlight_widget is not None:
            try:
                highlight_widget.set_selected(True)
            except Exception:
                pass

            def _unselect(*a):
                try:
                    highlight_widget.set_selected(False)
                except Exception:
                    pass
            popup.bind(on_dismiss=_unselect)

        popup.open()

        def _place(dt):
            try:
                wx, wy = Window.mouse_pos
                popup.x = wx
                if wy - popup.height < 0:
                    popup.y = 0
                else:
                    popup.y = wy - popup.height
            except Exception:
                pass

        Clock.schedule_once(_place, 0)

    def _employee_position(self, idx):
        employees = self.app.data['employees']
        if idx < 0 or idx >= len(employees):
            return None
        dept = employees[idx].get('department', '')
        same_dept = [i for i, e in enumerate(employees)
                     if e.get('department', '') == dept]
        if not same_dept:
            return None
        pos = same_dept.index(idx)
        if len(same_dept) == 1:
            return 'only'
        if pos == 0:
            return 'top'
        if pos == len(same_dept) - 1:
            return 'bottom'
        return 'mid'

    def _show_employee_menu(self, idx, touch, widget=None):
        where = self._employee_position(idx)
        if where in (None, 'only'):
            return

        items = []
        if where in ('mid', 'bottom'):
            items.append(("Переставить вверх",
                          lambda: self._move_employee(idx, -1)))
            items.append(("В начало отдела",
                          lambda: self._move_employee_to(idx, 'top')))
        if where in ('mid', 'top'):
            if items:
                items.append((None, None))
            items.append(("Переставить вниз",
                          lambda: self._move_employee(idx, +1)))
            items.append(("В конец отдела",
                          lambda: self._move_employee_to(idx, 'bottom')))

        self._open_menu(items, touch, highlight_widget=widget)
        
    def _department_position(self, name):
        depts = self.app.data.get('departments', [])
        if name not in depts:
            return None
        if len(depts) == 1:
            return 'only'
        pos = depts.index(name)
        if pos == 0:
            return 'top'
        if pos == len(depts) - 1:
            return 'bottom'
        return 'mid'

    def _show_department_menu(self, name, touch, widget=None):
        where = self._department_position(name)
        if where in (None, 'only'):
            return

        items = []
        if where in ('mid', 'bottom'):
            items.append(("Отдел вверх",
                          lambda: self._move_department(name, -1)))
            items.append(("В начало списка",
                          lambda: self._move_department_to(name, 'top')))
        if where in ('mid', 'top'):
            if items:
                items.append((None, None))
            items.append(("Отдел вниз",
                          lambda: self._move_department(name, +1)))
            items.append(("В конец списка",
                          lambda: self._move_department_to(name, 'bottom')))

        self._open_menu(items, touch, highlight_widget=widget)

    # ---------------- строки ---------------------------------------------
    def _add_employee_row(self, idx, emp, display_num=None):
        show_in = emp.get('show_in_timesheet', False)
        if display_num is None:
            display_num = idx + 1

        row = RightClickBox(size_hint_y=None, height=dp(40), spacing=0)
        row._on_right_click = (
            lambda t, i=idx, w=row: self._show_employee_menu(i, t, w)
        )

        row.add_widget(Label(text=str(display_num), size_hint_x=0.4,
                             font_name=FONT_NAME, font_size=dp(15),
                             color=config.TABLE_FG))
        row.add_widget(vsep(color=config.TABLE_FG))
        row.add_widget(Label(text=emp.get('name', ''), size_hint_x=3.0,
                             font_name=FONT_NAME, font_size=dp(15),
                             color=config.TABLE_FG))
        row.add_widget(vsep(color=config.TABLE_FG))
        
        pos_lbl = Label(text=emp.get('position', ''), size_hint_x=2.3,
                        font_name=FONT_NAME, font_size=dp(15),
                        color=config.TABLE_FG, halign='left', valign='middle',
                        text_size=(100, None))
        pos_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0] - 10, None)))
        
        row.add_widget(pos_lbl)
        row.add_widget(vsep(color=config.TABLE_FG))

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

    def _build_header(self):
        self.header_holder.clear_widgets()
        header = BoxLayout(size_hint_y=None, height=dp(35), spacing=0)
        header.add_widget(Label(text="№", bold=True, size_hint_x=0.4,
                                 font_name=FONT_NAME, font_size=dp(15),
                                 color=config.TABLE_FG))
        header.add_widget(vsep(color=config.TABLE_FG))
        header.add_widget(Label(text="Фамилия Имя Отчество", bold=True,
                                 size_hint_x=3.0, font_name=FONT_NAME,
                                 font_size=dp(15), color=config.TABLE_FG))
        header.add_widget(vsep(color=config.TABLE_FG))
        header.add_widget(Label(text="Должность", bold=True,
                                 size_hint_x=2.3, font_name=FONT_NAME,
                                 font_size=dp(15), color=config.TABLE_FG))
        header.add_widget(vsep(color=config.TABLE_FG))
        header.add_widget(Label(text="В таблицу", bold=True,
                                 size_hint_x=0.7, font_name=FONT_NAME,
                                 font_size=dp(15), color=config.TABLE_FG))
        header.add_widget(vsep(color=config.TABLE_FG))
        header.add_widget(Label(text="Действия", bold=True,
                                 size_hint_x=1.6, font_name=FONT_NAME,
                                 font_size=dp(15), color=config.TABLE_FG))

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
        
        first_dept = True
        for dept in departments:
            idxs = [i for i, e in enumerate(employees)
                    if e.get('department', '') == dept]
            if not idxs:
                continue
                
            if not first_dept:
                self.list_layout.add_widget(Widget(size_hint_y=None, height=dp(8)))
            first_dept = False
            
            has_checked = any(employees[i].get('show_in_timesheet', False) for i in idxs)
            
            if has_checked:
                bg = config.ACTIVE_DEPT_BAR_BG
                fg = config.ACTIVE_DEPT_BAR_FG
                name = dept
            else:
                bg = config.DEPT_BAR_BG
                fg = config.DEPT_BAR_FG
                name = dept
                
            self._add_dept_bar(name, bg=bg, fg=fg, movable=True, raw_name=dept)
            
            if dept in self._collapsed_depts:
                continue 
                
            for num, i in enumerate(idxs, start=1):
                self._add_employee_row(i, employees[i], num)
                used.add(i)
        
        others = [i for i in range(len(employees)) if i not in used and employees[i].get('department', '') not in departments]
        if others:
            if departments:
                self.list_layout.add_widget(Widget(size_hint_y=None, height=dp(8)))
                
                has_checked_others = any(employees[i].get('show_in_timesheet', False) for i in others)
                if has_checked_others:
                    bg_others = config.ACTIVE_DEPT_BAR_BG
                    fg_others = config.ACTIVE_DEPT_BAR_FG
                    name_others = "Без отдела"
                else:
                    bg_others = (0.30, 0.30, 0.34, 1)
                    fg_others = config.DEPT_BAR_FG
                    name_others = "Без отдела"
                    
                self._add_dept_bar(name_others, bg=bg_others, fg=fg_others, movable=False, raw_name="Без отдела")
                
            for num, i in enumerate(others, start=1):
                self._add_employee_row(i, employees[i], num)
                
        # ДОБАВЛЕНО: Фиксим пустоту после любого обновления списка
        Clock.schedule_once(self._fix_layout_gap, 0.01)

    def update_open_popups(self):
        """Вызывается из main.py для обновления открытых окон..."""
        if getattr(self, 'active_positions_popup', None) and getattr(self, 'active_positions_rebuild', None):
            Clock.schedule_once(lambda dt: self.active_positions_rebuild(), 0)
        if getattr(self, 'active_depts_popup', None) and getattr(self, 'active_depts_rebuild', None):
            Clock.schedule_once(lambda dt: self.active_depts_rebuild(), 0)
        if getattr(self, 'active_edit_popup', None) and getattr(self, 'active_edit_rebuild', None):
            Clock.schedule_once(lambda dt: self.active_edit_rebuild(), 0)
        if getattr(self, 'active_dept_editor_popup', None) and getattr(self, 'active_dept_editor_rebuild', None):
            Clock.schedule_once(lambda dt: self.active_dept_editor_rebuild(), 0)
            
        if getattr(self, 'active_dept_picker_popup', None) and getattr(self, 'active_dept_picker_rebuild', None):
            Clock.schedule_once(lambda dt: self.active_dept_picker_rebuild(), 0)

    def add_employee(self):
        self.show_edit_popup(None)

    def edit_employee(self, idx):
        emp = self.app.data['employees'][idx]
        dept = emp.get('department', '')
        self._check_dept_access(dept, lambda: self.show_edit_popup(idx))

    def delete_employee(self, idx):
        emp = self.app.data['employees'][idx]
        dept = emp.get('department', '')

        def _do_delete():
            def _do():
                self.app.data['employees'].pop(idx)
                self.app.safe_save(self.app.data)
                self.refresh()

            ask_password_and_run(
                DELETE_PASSWORD, _do,
                description=f"Удалить сотрудника:\n«{emp.get('name', '')}»?")

        # Убран _check_dept_access — теперь запрашивается только пароль администратора
        _do_delete()

    def show_edit_popup(self, idx):
        emp = (self.app.data['employees'][idx] if idx is not None
               else {'name': '', 'position': '', 'department': '',
                     'show_in_timesheet': False})
        positions = self.app.data.get('positions', []) or list(DEFAULT_POSITIONS)
        departments = self.app.data.get('departments', [])
        sorted_positions = sorted(positions, key=lambda s: s.lower())
        sorted_departments = sorted(departments, key=lambda s: s.lower())

        outer = BoxLayout(orientation='vertical', spacing=10,
                          padding=(20, 15, 20, 15))

        fields = BoxLayout(orientation='vertical', spacing=10,
                           size_hint=(1, None), height=dp(190))

        LBL_W = dp(180)

        row_name = BoxLayout(size_hint_y=None, height=dp(38), spacing=8)
        row_name.add_widget(Label(
            text="Фамилия Имя Отчество", size_hint=(None, 1), width=LBL_W,
            color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15),
            halign='right', valign='middle',
            text_size=(LBL_W, dp(38))))
        name_w = TextInput(
            text=emp.get('name', ''), multiline=False,
            font_size=dp(14), font_name=FONT_NAME,
            foreground_color=(0.05, 0.05, 0.05, 1),
            background_color=(1, 1, 1, 1),
            cursor_color=(0.10, 0.30, 0.70, 1),
            cursor_width=dp(2),
            selection_color=(0.20, 0.45, 0.90, 0.40),
            padding=[dp(8), dp(10), dp(8), dp(10)],
            size_hint=(1, 1),
        )
        row_name.add_widget(name_w)
        fields.add_widget(row_name)

        row_dept = BoxLayout(size_hint_y=None, height=dp(38), spacing=8)
        row_dept.add_widget(Label(
            text="Отдел", size_hint=(None, 1), width=LBL_W,
            color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15),
            halign='right', valign='middle',
            text_size=(LBL_W, dp(38))))
        if idx is None:
            dept_text = '= Выбрать отдел ='
        else:
            dept_text = (emp.get('department', '')
                         or (sorted_departments[0] if sorted_departments else ''))
        dept_w = CenteredSpinner(
            text=dept_text,
            values=sorted_departments,
            spinner_height=dp(30), font_size=dp(14))
        dept_w.size_hint = (1, None)
        dept_w.height = dp(32)
        row_dept.add_widget(dept_w)
        fields.add_widget(row_dept)

        row_pos = BoxLayout(size_hint_y=None, height=dp(38), spacing=8)
        row_pos.add_widget(Label(
            text="Должность (профессия)",
            size_hint=(None, 1), width=LBL_W,
            color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15),
            halign='right', valign='middle',
            text_size=(LBL_W, dp(38))))
        if idx is None:
            pos_text = '= Выбрать должность ='
        else:
            pos_text = (emp.get('position', '')
                        or (sorted_positions[0] if sorted_positions else ''))
        pos_w = CenteredSpinner(
            text=pos_text,
            values=sorted_positions,
            spinner_height=dp(30), font_size=dp(14))
        pos_w.size_hint = (1, None)
        pos_w.height = dp(32)
        row_pos.add_widget(pos_w)
        fields.add_widget(row_pos)

        # --- Логика автообновления списков Отделов и Должностей ---
        prev_depts_set = set(sorted_departments)
        prev_pos_set = set(sorted_positions)

        def rebuild_choices():
            """Обновляет .values спиннеров, не трогая то, что пользователь уже ввел."""
            try:
                cur_depts = sorted(self.app.data.get('departments', []),
                                   key=lambda s: s.lower())
                cur_pos = self.app.data.get('positions', []) or list(DEFAULT_POSITIONS)
                cur_pos = sorted(cur_pos, key=lambda s: s.lower())

                new_depts_set = set(cur_depts)
                new_pos_set = set(cur_pos)

                # Автопереименование: если выбранное значение исчезло,
                # а в списке появилось ровно одно новое — считаем это переименованием.
                cur_dept_text = dept_w.text.strip()
                if cur_dept_text in prev_depts_set and cur_dept_text not in new_depts_set:
                    rem = prev_depts_set - new_depts_set
                    add = new_depts_set - prev_depts_set
                    if len(rem) == 1 and len(add) == 1:
                        dept_w.text = next(iter(add))

                cur_pos_text = pos_w.text.strip()
                if cur_pos_text in prev_pos_set and cur_pos_text not in new_pos_set:
                    rem = prev_pos_set - new_pos_set
                    add = new_pos_set - prev_pos_set
                    if len(rem) == 1 and len(add) == 1:
                        pos_w.text = next(iter(add))

                dept_w.spinner.values = cur_depts
                pos_w.spinner.values = cur_pos

                prev_depts_set.clear()
                prev_depts_set.update(new_depts_set)
                prev_pos_set.clear()
                prev_pos_set.update(new_pos_set)
            except Exception:
                pass
        # ----------------------------------------------------------

        row_contract = BoxLayout(size_hint_y=None, height=dp(38), spacing=8)
        row_contract.add_widget(Label(
            text="На контракте",
            size_hint=(None, 1), width=LBL_W,
            color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15),
            halign='right', valign='middle',
            text_size=(LBL_W, dp(38))))
        
        cb_holder = AnchorLayout(anchor_x='left', anchor_y='center',
                                 size_hint=(1, 1))
        cb_contract = CheckBox(active=emp.get('is_contract', True),
                               size_hint=(None, None), size=(dp(30), dp(30)))
        cb_holder.add_widget(cb_contract)
        row_contract.add_widget(cb_holder)
        fields.add_widget(row_contract)

        outer.add_widget(fields)
        outer.add_widget(Widget())

        btns = BoxLayout(size_hint_y=None, height=dp(50), spacing=10)
        save_btn = HoverButton(text="Сохранить",
                          background_color=(0.3, 0.7, 0.3, 1),
                          color=(1, 1, 1, 1), font_name=FONT_NAME,
                          font_size=dp(16), bold=True)
        cancel_btn = HoverButton(text="Отмена", color=(1, 1, 1, 1),
                            font_name=FONT_NAME, font_size=dp(16), bold=True)
        btns.add_widget(save_btn)
        btns.add_widget(cancel_btn)
        outer.add_widget(btns)

        popup = Popup(title="Сотрудник" if idx is not None else "Новый сотрудник",
                      content=outer, size_hint=(0.6, 0.52),
                      title_color=LABEL_LIGHT, title_font=FONT_NAME,
                      auto_dismiss=False)

        def on_save(*a):
            name = name_w.text.strip()
            if not name:
                return
                
            is_duplicate = False
            for i, e in enumerate(self.app.data['employees']):
                if i != idx and e.get('name', '').strip().lower() == name.lower():
                    is_duplicate = True
                    break
            
            if is_duplicate:
                err_content = BoxLayout(orientation='vertical', spacing=10, padding=10)
                err_content.add_widget(Label(text=f"Сотрудник «{name}»\nуже существует!", color=LABEL_LIGHT, halign='center', valign='middle', font_name=FONT_NAME, font_size=dp(15)))
                ok_btn = Button(text="ОК", size_hint_y=None, height=dp(40), font_name=FONT_NAME, background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1))
                err_content.add_widget(ok_btn)
                err = Popup(title="Ошибка", content=err_content, size_hint=(0.45, 0.3), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
                ok_btn.bind(on_press=err.dismiss)
                err.open()
                return

            new_dept = dept_w.text.strip()
            if new_dept == '(Выбрать отдел)':
                new_dept = ''
            new_pos = pos_w.text.strip()
            if new_pos == '(Выбрать должность)':
                new_pos = ''
                
            def _do_save():
                show_in = emp.get('show_in_timesheet', False)
                new_emp = {
                    'id': emp.get('id') or f"emp_{int(datetime.now().timestamp() * 1000)}",
                    'name': name,
                    'position': new_pos,
                    'department': new_dept,
                    'show_in_timesheet': show_in,
                    'is_contract': cb_contract.active,
                    'category': emp.get('category', ''),
                }
                if idx is not None:
                    self.app.data['employees'][idx] = new_emp
                else:
                    self.app.data['employees'].append(new_emp)
                self.app.safe_save(self.app.data)
                popup.dismiss()
                self.refresh()

            self._check_dept_access(new_dept, _do_save)

        save_btn.bind(on_press=on_save)
        cancel_btn.bind(on_press=popup.dismiss)
        name_w.bind(on_text_validate=lambda *a: on_save())
        bind_enter_key(popup, on_save)

        # --- РЕГИСТРАЦИЯ ДЛЯ АВТООБНОВЛЕНИЯ ---
        self.active_edit_popup = popup
        self.active_edit_rebuild = rebuild_choices

        def on_edit_dismiss(*args):
            self.active_edit_popup = None
            self.active_edit_rebuild = None

        popup.bind(on_dismiss=on_edit_dismiss)
        # --------------------------------------

        popup.open()

    def show_positions_popup(self):
        self.app.data.setdefault('positions', list(DEFAULT_POSITIONS))
        self.app.data.setdefault('night_flags', {})
        self.app.data.setdefault('overtime_flags', {})
        self.app.data.setdefault('holiday_flags', {})
        self.app.data.setdefault('no_weekends_flags', {})
        positions = self.app.data['positions']
        if not positions:
            self.app.data['positions'] = list(DEFAULT_POSITIONS)
            positions = self.app.data['positions']

        content = BoxLayout(orientation='vertical', spacing=8, padding=10)
        add_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=5)
        new_pos_wrap = TextInput(
            text='', multiline=False,
            font_size=dp(14), font_name=FONT_NAME,
            foreground_color=(0.05, 0.05, 0.05, 1),
            background_color=(1, 1, 1, 1),
            cursor_color=(0.10, 0.30, 0.70, 1),
            cursor_width=dp(2),
            selection_color=(0.20, 0.45, 0.90, 0.40),
            padding=[dp(8), dp(13), dp(8), dp(13)],
            size_hint=(0.7, 1),
        )
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
            rebuild_list()
            def _do():
                flags = self.app.data.setdefault('night_flags', {})
                flags[name] = not flags.get(name, False)
                self.app.safe_save(self.app.data)
                rebuild_list()
            ask_password_and_run(
                DELETE_PASSWORD, _do, 
                title="Изменение настройки", 
                description=f"Изменить настройку «Ночные» для\n«{name}»?",
                btn_text="Изменить",
                password_prompt="Введите пароль администратора:")

        def toggle_overtime(name):
            rebuild_list()
            def _do():
                flags = self.app.data.setdefault('overtime_flags', {})
                flags[name] = not flags.get(name, False)
                self.app.safe_save(self.app.data)
                rebuild_list()
            ask_password_and_run(
                DELETE_PASSWORD, _do, 
                title="Изменение настройки", 
                description=f"Изменить настройку «Сверхурочные» для\n«{name}»?",
                btn_text="Изменить",
                password_prompt="Введите пароль администратора:")

        def toggle_no_weekends(name):
            rebuild_list()
            def _do():
                flags = self.app.data.setdefault('no_weekends_flags', {})
                flags[name] = not flags.get(name, False)
                self.app.safe_save(self.app.data)
                rebuild_list()
            ask_password_and_run(
                DELETE_PASSWORD, _do, 
                title="Изменение настройки", 
                description=f"Изменить настройку «Без вых.» для\n«{name}»?",
                btn_text="Изменить",
                password_prompt="Введите пароль администратора:")

        def delete_pos(ii):
            name = self.app.data['positions'][ii]

            def _do():
                try:
                    self.app.data['positions'].pop(ii)
                    self.app.data.get('night_flags', {}).pop(name, None)
                    self.app.data.get('overtime_flags', {}).pop(name, None)
                    self.app.data.get('no_weekends_flags', {}).pop(name, None)
                    self.app.data.get('holidays_only_flags', {}).pop(name, None)
                    self.app.safe_save(self.app.data)
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
            edit_wrap = TextInput(
                text=old_name, multiline=False,
                font_size=dp(14), font_name=FONT_NAME,
                foreground_color=(0.05, 0.05, 0.05, 1),
                background_color=(1, 1, 1, 1),
                cursor_color=(0.10, 0.30, 0.70, 1),
                cursor_width=dp(2),
                selection_color=(0.20, 0.45, 0.90, 0.40),
                padding=[dp(8), dp(10), dp(8), dp(10)],
                size_hint=(1, None), height=dp(38),
            )
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
                      title_font=FONT_NAME, auto_dismiss=False)

            def on_ok(*a):
                new_name = edit_wrap.text.strip()
                if not new_name or new_name == old_name:
                    p.dismiss()
                    return

                if new_name in self.app.data['positions']:
                    p.dismiss()
                    err_content = BoxLayout(orientation='vertical', spacing=10, padding=10)
                    err_content.add_widget(Label(text=f"Должность «{new_name}»\nуже существует!", color=LABEL_LIGHT, halign='center', valign='middle', font_name=FONT_NAME, font_size=dp(15)))
                    ok_btn = Button(text="ОК", size_hint_y=None, height=dp(40), font_name=FONT_NAME, background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1))
                    err_content.add_widget(ok_btn)
                    err = Popup(title="Ошибка", content=err_content, size_hint=(0.45, 0.3), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
                    ok_btn.bind(on_press=err.dismiss)
                    err.open()
                    return
                    
                self.app.data['positions'][ii] = new_name

                flags_n = self.app.data.setdefault('night_flags', {})
                old_flag_n = flags_n.pop(old_name, False)
                flags_n[new_name] = old_flag_n

                flags_o = self.app.data.setdefault('overtime_flags', {})
                old_flag_o = flags_o.pop(old_name, False)
                flags_o[new_name] = old_flag_o

                flags_nw = self.app.data.setdefault('no_weekends_flags', {})
                old_flag_nw = flags_nw.pop(old_name, False)
                flags_nw[new_name] = old_flag_nw

                for emp in self.app.data['employees']:
                    if emp.get('position', '') == old_name:
                        emp['position'] = new_name
                self.app.safe_save(self.app.data)
                p.dismiss()
                rebuild_list()
                self.refresh()

            ok.bind(on_press=on_ok)
            cancel.bind(on_press=p.dismiss)
            edit_wrap.bind(on_text_validate=lambda *a: on_ok())
            bind_enter_key(p, on_ok)
            
            # ЗАДЕРЖКА ДЛЯ ОТКРЫТИЯ ОКНА
            Clock.schedule_once(lambda dt: p.open(), 0.1)

        def rebuild_list():
            list_grid.clear_widgets()
            items = [(i, p) for i, p in enumerate(self.app.data['positions'])]
            items.sort(key=lambda x: x[1].lower())
            for i, p in items:
                # Используем HoverRow вместо обычного BoxLayout
                row = HoverRow(size_hint_y=None, height=dp(48), spacing=0)
                
                add_top_border(row, color=LABEL_LIGHT, thickness=1)
                add_bottom_border(row, color=LABEL_LIGHT, thickness=1)
                add_left_border(row, color=LABEL_LIGHT, thickness=1)
                add_right_border(row, color=LABEL_LIGHT, thickness=1)

                night_on = bool(self.app.data['night_flags'].get(p, False))
                night_box = BoxLayout(size_hint_x=None, width=dp(110), spacing=4)
                cb = CheckBox(active=night_on, size_hint_x=None, width=dp(30),
                              color=((0.30, 0.90, 0.40, 1) if night_on
                                     else (0.85, 0.85, 0.85, 1)))
                cb.bind(active=lambda inst, val, nm=p: toggle_night(nm))
                night_box.add_widget(cb)
                night_box.add_widget(Label(text="Ночные", color=(1, 1, 1, 1),
                                            font_name=FONT_NAME,
                                            font_size=dp(14), bold=True,
                                            outline_color=(0, 0, 0, 1),
                                            outline_width=1, valign='middle'))
                row.add_widget(night_box)
                row.add_widget(vsep(color=LABEL_LIGHT))

                overtime_on = bool(self.app.data['overtime_flags'].get(p, False))
                overtime_box = BoxLayout(size_hint_x=None, width=dp(150), spacing=4)
                cb2 = CheckBox(active=overtime_on, size_hint_x=None, width=dp(30),
                               color=((0.30, 0.90, 0.40, 1) if overtime_on
                                      else (0.85, 0.85, 0.85, 1)))
                cb2.bind(active=lambda inst, val, nm=p: toggle_overtime(nm))
                overtime_box.add_widget(cb2)
                overtime_box.add_widget(Label(text="Сверхурочные", color=(1, 1, 1, 1),
                                               font_name=FONT_NAME,
                                               font_size=dp(14), bold=True,
                                               outline_color=(0, 0, 0, 1),
                                               outline_width=1, valign='middle'))
                row.add_widget(overtime_box)
                row.add_widget(vsep(color=LABEL_LIGHT))

                no_weekends_on = bool(self.app.data.get('no_weekends_flags', {}).get(p, False))
                no_weekends_box = BoxLayout(size_hint_x=None, width=dp(150), spacing=4)
                cb3 = CheckBox(active=no_weekends_on, size_hint_x=None, width=dp(30),
                               color=((0.30, 0.90, 0.40, 1) if no_weekends_on
                                      else (0.85, 0.85, 0.85, 1)))
                cb3.bind(active=lambda inst, val, nm=p: toggle_no_weekends(nm))
                no_weekends_box.add_widget(cb3)
                no_weekends_box.add_widget(Label(text="Без вых.", color=(1, 1, 1, 1),
                                               font_name=FONT_NAME,
                                               font_size=dp(14), bold=True,
                                               outline_color=(0, 0, 0, 1),
                                               outline_width=1, valign='middle'))
                row.add_widget(no_weekends_box)
                row.add_widget(vsep(color=LABEL_LIGHT))

                pos_lbl = Label(text=p, color=(1, 1, 1, 1),
                                font_name=FONT_NAME,
                                font_size=dp(15), bold=True,
                                outline_color=(0, 0, 0, 1),
                                outline_width=1,
                                halign='center', valign='middle',
                                shorten=True, shorten_from='right',
                                size_hint_x=1)
                pos_lbl.bind(size=lambda i, v: setattr(i, 'text_size', (v[0]-10, v[1])))
                row.add_widget(pos_lbl)
                row.add_widget(vsep(color=LABEL_LIGHT))

                edit_btn = Button(text="Изменить", size_hint_x=None, width=dp(100),
                                  font_name=FONT_NAME, font_size=dp(15), bold=True,
                                  background_normal='', background_down='',
                                  background_color=(0.35, 0.55, 0.85, 1),
                                  color=(1, 1, 1, 1))
                edit_btn.bind(on_press=lambda *a, ii=i: edit_pos(ii))
                row.add_widget(edit_btn)
                row.add_widget(vsep(color=LABEL_LIGHT))

                del_btn = Button(text="Удалить", size_hint_x=None, width=dp(100),
                                 font_name=FONT_NAME, font_size=dp(15), bold=True,
                                 background_normal='', background_down='',
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
                err_content = BoxLayout(orientation='vertical', spacing=10, padding=10)
                err_content.add_widget(Label(text=f"Должность «{txt}»\nуже существует!", color=LABEL_LIGHT, halign='center', valign='middle', font_name=FONT_NAME, font_size=dp(15)))
                ok_btn = Button(text="ОК", size_hint_y=None, height=dp(40), font_name=FONT_NAME, background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1))
                err_content.add_widget(ok_btn)
                err = Popup(title="Ошибка", content=err_content, size_hint=(0.45, 0.3), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
                ok_btn.bind(on_press=err.dismiss)
                err.open()
                new_pos_wrap.text = ''
                return
                
            self.app.data['positions'].append(txt)
            self.app.data.setdefault('night_flags', {}).setdefault(txt, False)
            self.app.data.setdefault('overtime_flags', {}).setdefault(txt, False)
            self.app.data.setdefault('no_weekends_flags', {}).setdefault(txt, False)
            self.app.safe_save(self.app.data)
            new_pos_wrap.text = ''
            rebuild_list()

        add_btn.bind(on_press=add_position)
        new_pos_wrap.bind(on_text_validate=add_position)
        rebuild_list()
        list_scroll.add_widget(list_grid)
        content.add_widget(list_scroll)

        close_btn = Button(text="Закрыть", size_hint_y=None, height=dp(40),
                           font_name=FONT_NAME, font_size=dp(16), bold=True,
                           color=(1, 1, 1, 1))
        content.add_widget(close_btn)
        popup = Popup(title="Должности", content=content,
                      size_hint=(0.9, 0.65), title_color=LABEL_LIGHT,
                      title_font=FONT_NAME, auto_dismiss=False)
        close_btn.bind(on_press=popup.dismiss)
        
        # --- ПРИВЯЗКА ДЛЯ АВТООБНОВЛЕНИЯ ---
        self.active_positions_popup = popup
        self.active_positions_rebuild = rebuild_list
        def on_pos_dismiss(*args):
            self.active_positions_popup = None
            self.active_positions_rebuild = None
        popup.bind(on_dismiss=on_pos_dismiss)
        # -----------------------------------

        popup.open()
        rebuild_list()

    def show_departments_popup(self):
        self.app.data.setdefault('departments', list(DEFAULT_DEPARTMENTS))
        self.app.data.setdefault('department_signer', {})
        self.app.data.setdefault('department_energetic', {})
        if not self.app.data['departments']:
            self.app.data['departments'] = list(DEFAULT_DEPARTMENTS)

        signer_positions = self.app.data.setdefault('signer_positions',
                                                     ['Энергетик'])
        if not signer_positions:
            signer_positions.append('Энергетик')
            self.app.data['signer_positions'] = signer_positions

        def open_show_passwords(*args):
            all_depts = self.app.data.get('departments', [])
            pw_map = self.app.data.get('department_passwords', {})

            def _show_list():
                # --- КАСТОМНЫЙ ВИДЖЕТ СТРОКИ ---
                class PasswordRow(BoxLayout):
                    def __init__(self, dept, pw, dept_passwords_map, app, rebuild_cb, **kwargs):
                        super().__init__(**kwargs)
                        self.dept = dept
                        self.orig_pw = pw
                        self.dept_passwords_map = dept_passwords_map
                        self.app = app
                        self.rebuild_cb = rebuild_cb
                        self._hovering = False
                        
                        # Фон для эффекта наведения
                        with self.canvas.before:
                            self.bg_color = Color(0, 0, 0, 0)
                            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
                        self.bind(pos=self._update_rect, size=self._update_rect)
                        
                        # Колонка 1: Отдел (50%)
                        box1 = BoxLayout(size_hint_x=0.5)
                        add_left_border(box1, color=(0.4, 0.4, 0.4, 1))
                        add_right_border(box1, color=(0.4, 0.4, 0.4, 1))
                        self.l1 = Label(text=dept, color=LABEL_LIGHT, font_name=FONT_NAME, halign='left', valign='middle', shorten=True, shorten_from='right')
                        self.l1.bind(size=lambda i,v: setattr(i, 'text_size', (v[0]-dp(10), v[1])))
                        box1.add_widget(self.l1)
                        self.add_widget(box1)
                        
                        # Колонка 2: Пароль (30%)
                        self.box2 = BoxLayout(size_hint_x=0.3)
                        add_right_border(self.box2, color=(0.4, 0.4, 0.4, 1))
                        self.orig_color = (1, 0.85, 0.35, 1) if pw else (0.6, 0.6, 0.6, 1)
                        self.l2 = Label(text=pw if pw else "(не задан)", color=self.orig_color, font_name=FONT_NAME, halign='left', valign='middle')
                        self.l2.bind(size=lambda i,v: setattr(i, 'text_size', (v[0]-dp(10), v[1])))
                        self.box2.add_widget(self.l2)
                        self.add_widget(self.box2)

                        # Колонка 3: Действия (20%)
                        self.act_box = BoxLayout(size_hint_x=0.2, spacing=dp(4), padding=(dp(4), dp(4)))
                        add_right_border(self.act_box, color=(0.4, 0.4, 0.4, 1))
                        
                        # Контейнер для двух кнопок (Изменить / Удалить)
                        self.btns_cont = BoxLayout(spacing=dp(4))
                        self.btn_edit = Button(text="Изменить", background_color=(0.35, 0.55, 0.85, 1), color=(1,1,1,1), font_name=FONT_NAME, font_size=dp(12))
                        self.btn_del = Button(text="Удалить", background_color=(0.9, 0.35, 0.35, 1), color=(1,1,1,1), font_name=FONT_NAME, font_size=dp(12))
                        self.btns_cont.add_widget(self.btn_edit)
                        self.btns_cont.add_widget(self.btn_del)
                        
                        # Кнопка подтверждения (изначально скрыта, появляется одна на всю ширину)
                        self.btn_save = Button(text="Подтвердить", background_color=(0.3, 0.7, 0.3, 1), color=(1,1,1,1), font_name=FONT_NAME, font_size=dp(12))

                        self.act_box.add_widget(self.btns_cont)
                        self.add_widget(self.act_box)

                        self.btn_edit.bind(on_press=self.start_edit)
                        self.btn_del.bind(on_press=self.delete_password)
                        self.btn_save.bind(on_press=self.save_password)
                        
                        add_bottom_border(self, color=(0.4, 0.4, 0.4, 1))
                        
                        from kivy.core.window import Window
                        Window.bind(mouse_pos=self._on_mouse_pos)
                        self.bind(parent=self._on_parent)
                        self._last_click = 0

                    def start_edit(self, *args):
                        # Меняем Label на TextInput
                        self.box2.clear_widgets()
                        self.pw_input = TextInput(
                            text=self.orig_pw, password=True, multiline=False,
                            font_size=dp(14), font_name=FONT_NAME,
                            foreground_color=(0.05, 0.05, 0.05, 1),
                            background_color=(1, 1, 1, 1),
                            cursor_color=(0.10, 0.30, 0.70, 1),
                            padding=[dp(10), dp(8), dp(10), dp(8)], # Отступы для центрирования текста по вертикали
                            halign='left'                           # Текст и курсор прижаты влево
                        )
                        self.pw_input.bind(on_text_validate=self.save_password)
                        self.box2.add_widget(self.pw_input)
                        self.pw_input.focus = True

                        # Заменяем две кнопки на одну широкую по центру
                        self.act_box.clear_widgets()
                        self.act_box.add_widget(self.btn_save)

                    def save_password(self, *args):
                        new_pw = self.pw_input.text.strip()
                        if new_pw:
                            self.dept_passwords_map[self.dept] = new_pw
                        else:
                            self.dept_passwords_map.pop(self.dept, None)
                        self.app.safe_save(self.app.data)
                        self.rebuild_cb()

                    def delete_password(self, *args):
                        # Полный сброс пароля
                        self.dept_passwords_map.pop(self.dept, None)
                        self.app.safe_save(self.app.data)
                        self.rebuild_cb()

                    def _update_rect(self, *a):
                        self.bg_rect.pos = self.pos
                        self.bg_rect.size = self.size

                    def _on_parent(self, instance, parent):
                        if parent is None:
                            try: Window.unbind(mouse_pos=self._on_mouse_pos)
                            except Exception: pass

                    def _on_mouse_pos(self, window, pos):
                        if not self.get_root_window() or self.disabled: return
                        try:
                            wx, wy = self.to_window(self.x, self.y)
                            inside = wx <= pos[0] <= wx + self.width and wy <= pos[1] <= wy + self.height
                            if inside and not self._hovering:
                                self._hovering = True
                                self.bg_color.rgba = (1, 1, 1, 0.1)
                            elif not inside and self._hovering:
                                self._hovering = False
                                self.bg_color.rgba = (0, 0, 0, 0)
                        except Exception: pass

                    def on_touch_down(self, touch):
                        # Двойной клик для копирования (только если не в режиме редактирования)
                        if self.collide_point(*touch.pos) and self.orig_pw and getattr(touch, 'button', 'left') == 'left':
                            if hasattr(self, 'l2') and self.l2.parent == self.box2:
                                lx, ly = self.to_local(*touch.pos)
                                if self.box2.collide_point(lx, ly):
                                    import time
                                    now = time.time()
                                    if now - self._last_click < 0.5:
                                        self._copy_password()
                                        self._last_click = 0
                                        return True
                                    else:
                                        self._last_click = now
                        return super().on_touch_down(touch)

                    def _copy_password(self):
                        if hasattr(self, 'l2'):
                            self.l2.color = (0.3, 0.9, 0.3, 1)
                            def reset_color(dt): 
                                if hasattr(self, 'l2'): self.l2.color = self.orig_color
                            Clock.schedule_once(reset_color, 0.3)
                        try:
                            from kivy.core.clipboard import Clipboard
                            Clipboard.copy(self.orig_pw)
                        except Exception as e:
                            print("Не удалось скопировать в буфер обмена:", e)
                # ---------------------------------

                c = BoxLayout(orientation='vertical', spacing=8, padding=10)
                
                # Шапка таблицы
                hdr = BoxLayout(size_hint_y=None, height=dp(32), spacing=0)
                add_top_border(hdr, color=(0.4, 0.4, 0.4, 1))
                add_bottom_border(hdr, color=(0.4, 0.4, 0.4, 1))
                
                h1_box = BoxLayout(size_hint_x=0.5)
                add_left_border(h1_box, color=(0.4, 0.4, 0.4, 1))
                add_right_border(h1_box, color=(0.4, 0.4, 0.4, 1))
                h1 = Label(text="Отдел", bold=True, color=LABEL_LIGHT, font_name=FONT_NAME, halign='center', valign='middle')
                h1.bind(size=lambda i,v: setattr(i, 'text_size', v))
                h1_box.add_widget(h1)
                hdr.add_widget(h1_box)

                h2_box = BoxLayout(size_hint_x=0.3)
                add_right_border(h2_box, color=(0.4, 0.4, 0.4, 1))
                h2 = Label(text="Пароль", bold=True, color=LABEL_LIGHT, font_name=FONT_NAME, halign='center', valign='middle')
                h2.bind(size=lambda i,v: setattr(i, 'text_size', v))
                h2_box.add_widget(h2)
                hdr.add_widget(h2_box)

                h3_box = BoxLayout(size_hint_x=0.2)
                add_right_border(h3_box, color=(0.4, 0.4, 0.4, 1))
                h3 = Label(text="Действия", bold=True, color=LABEL_LIGHT, font_name=FONT_NAME, halign='center', valign='middle')
                h3.bind(size=lambda i,v: setattr(i, 'text_size', v))
                h3_box.add_widget(h3)
                hdr.add_widget(h3_box)
                
                c.add_widget(hdr)

                # Прокручиваемый список
                sv = ScrollView(scroll_type=['bars'], effect_cls=NoOverscrollEffect)
                grid = GridLayout(cols=1, size_hint_y=None, spacing=0)
                grid.bind(minimum_height=grid.setter('height'))

                def rebuild_grid():
                    grid.clear_widgets()
                    for dept in sorted(all_depts, key=lambda s: s.lower()):
                        pw = pw_map.get(dept, '')
                        row = PasswordRow(dept=dept, pw=pw, dept_passwords_map=pw_map, app=self.app, rebuild_cb=rebuild_grid, size_hint_y=None, height=dp(36))
                        grid.add_widget(row)

                rebuild_grid()
                sv.add_widget(grid)
                c.add_widget(sv)

                close_btn = Button(text="Закрыть", size_hint_y=None, height=dp(40), font_name=FONT_NAME, color=(1,1,1,1))
                close_btn.bind(on_press=lambda *a: p.dismiss())
                c.add_widget(close_btn)

                p = Popup(title="Пароли отделов", content=c, size_hint=(0.6, 0.7), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
                p.open()

            # Запрашиваем мастер-пароль перед показом
            ask_password_and_run(
                DELETE_PASSWORD, _show_list,
                title="Просмотр паролей",
                description=None,
                btn_text="Показать",
                btn_bg=(0.3, 0.7, 0.3, 1),
                password_prompt="Введите пароль администратора:"
            )

        content = BoxLayout(orientation='vertical', spacing=8, padding=10)

        # Блок с кнопками в верхней части окна
        top_btns = BoxLayout(size_hint_y=None, height=dp(40), spacing=10)
        
        add_btn = Button(text="+ Добавить отдел",
                         background_color=(0.3, 0.7, 0.3, 1),
                         color=(1, 1, 1, 1),
                         font_name=FONT_NAME, font_size=dp(16), bold=True)
        add_btn.bind(on_press=lambda *a: open_dept_editor(None))
        top_btns.add_widget(add_btn)

        show_pw_btn = Button(text="Показать пароли",
                             background_color=(0.4, 0.5, 0.7, 1),
                             color=(1, 1, 1, 1),
                             font_name=FONT_NAME, font_size=dp(16), bold=True)
        show_pw_btn.bind(on_press=open_show_passwords)
        top_btns.add_widget(show_pw_btn)
        
        content.add_widget(top_btns)

        header = BoxLayout(size_hint_y=None, height=dp(34), spacing=0)
        header.add_widget(vsep(color=LABEL_LIGHT))
        
        h_num = Label(text="№", bold=True, size_hint_x=None, width=dp(40), color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(14), halign='center', valign='middle')
        header.add_widget(h_num)
        header.add_widget(vsep(color=LABEL_LIGHT))
        
        h_dept = Label(text="Название отдела", bold=True, size_hint_x=2.2, color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(14), halign='center', valign='middle')
        h_dept.bind(size=lambda i, v: setattr(i, 'text_size', (v[0], v[1])))
        header.add_widget(h_dept)
        header.add_widget(vsep(color=LABEL_LIGHT))
        
        h_pos = Label(text="Должность", bold=True, size_hint_x=1.8, color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(14), halign='center', valign='middle')
        h_pos.bind(size=lambda i, v: setattr(i, 'text_size', (v[0], v[1])))
        header.add_widget(h_pos)
        header.add_widget(vsep(color=LABEL_LIGHT))
        
        h_fio = Label(text="Фамилия Имя Отчество", bold=True, size_hint_x=2.5, color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(14), halign='center', valign='middle')
        h_fio.bind(size=lambda i, v: setattr(i, 'text_size', (v[0], v[1])))
        header.add_widget(h_fio)
        header.add_widget(vsep(color=LABEL_LIGHT))
        
        h_act = Label(text="Действия", bold=True, size_hint_x=None, width=dp(230), color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(14), halign='center', valign='middle')
        header.add_widget(h_act)
        header.add_widget(vsep(color=LABEL_LIGHT))
        
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

            def _do_delete():
                def _do():
                    try:
                        self.app.data['departments'].pop(ii)
                        self.app.data.get('department_signer', {}).pop(name, None)
                        self.app.data.get('department_energetic', {}).pop(name, None)
                        self.app.data.get('department_passwords', {}).pop(name, None)
                        for emp in self.app.data['employees']:
                            if emp.get('department', '') == name:
                                emp['department'] = ''
                        self.app.safe_save(self.app.data)
                        rebuild_list()
                        self.refresh()
                    except Exception:
                        pass

                ask_password_and_run(
                    DELETE_PASSWORD, _do,
                    description=f"Удалить отдел:\n«{name}»?")

            # Убран _check_dept_access — теперь запрашивается только пароль администратора
            _do_delete()

        def open_dept_editor(idx):
            is_new = (idx is None)
            old_name = '' if is_new else self.app.data['departments'][idx]

            def _build_and_open():
                signers = self.app.data.setdefault('department_signer', {})
                entry = signers.get(old_name, {})
                old_pos = '' if is_new else entry.get('position', 'Энергетик')
                old_fio = '' if is_new else entry.get('name', DEFAULT_ENERGETIC)

                positions_now = list(self.app.data.get('signer_positions',
                                                        ['Энергетик']))
                if old_pos and old_pos not in positions_now:
                    positions_now.append(old_pos)

                outer = BoxLayout(orientation='vertical', spacing=10,
                                  padding=(20, 15, 20, 15))

                fields = BoxLayout(orientation='vertical', spacing=10,
                                   size_hint=(1, None))

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
                        padding=[dp(8), dp(11), dp(8), dp(6)],
                        size_hint=(1, 1),
                    )

                # === НАЗВАНИЕ (только для нового отдела) ===
                if is_new:
                    fields.height = dp(202)
                    row_name = BoxLayout(size_hint_y=None, height=dp(38), spacing=8)
                    row_name.add_widget(Label(
                        text="Название:", size_hint=(None, 1), width=LBL_W,
                        color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15),
                        halign='right', valign='middle',
                        text_size=(LBL_W, dp(38))))
                    edit_wrap = _make_input('')
                    row_name.add_widget(edit_wrap)
                    fields.add_widget(row_name)
                else:
                    # Высота для 2 полей: Должность и ФИО
                    fields.height = dp(86)
                    edit_wrap = None

                # === ДОЛЖНОСТЬ ===
                row_pos = BoxLayout(size_hint_y=None, height=dp(38), spacing=8)
                row_pos.add_widget(Label(
                    text="Должность:", size_hint=(None, 1), width=LBL_W,
                    color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15),
                    halign='right', valign='middle',
                    text_size=(LBL_W, dp(38))))

                pos_row = BoxLayout(orientation='horizontal', spacing=6,
                                     size_hint=(1, None), height=dp(38))
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

                # === ФИО ===
                row_fio = BoxLayout(size_hint_y=None, height=dp(38), spacing=8)
                row_fio.add_widget(Label(
                    text="ФИО руководителя:", size_hint=(None, 1), width=LBL_W,
                    color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15),
                    halign='right', valign='middle',
                    text_size=(LBL_W, dp(38))))
                fio_w = _make_input(old_fio)
                row_fio.add_widget(fio_w)
                fields.add_widget(row_fio)

                # === ПАРОЛЬ ОТДЕЛА (только для нового отдела) ===
                dept_passwords_map = self.app.data.setdefault('department_passwords', {})
                new_pw_input = None

                if is_new:
                    row_pw = BoxLayout(size_hint_y=None, height=dp(38), spacing=8)
                    row_pw.add_widget(Label(
                        text="Пароль отдела:", size_hint=(None, 1), width=LBL_W,
                        color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15),
                        halign='right', valign='middle',
                        text_size=(LBL_W, dp(38))))

                    new_pw_input = _make_input('')
                    new_pw_input.password = True
                    row_pw.add_widget(new_pw_input)
                    
                    fields.add_widget(row_pw)

                # --- ИСПРАВЛЕНИЕ: Добавляем распорку сверху, чтобы отцентрировать поля ---
                outer.add_widget(Widget())
                outer.add_widget(fields)
                outer.add_widget(Widget())
                # ----------------------------------------------------------------------

                def _open_positions_picker(*a):
                    picker = Popup(title="Существующие должности",
                                   size_hint=(0.65, 0.65),
                                   title_color=LABEL_LIGHT,
                                   title_font=FONT_NAME, auto_dismiss=False)

                    inner = BoxLayout(orientation='vertical', spacing=6,
                                      padding=8)
                    
                    search_input = TextInput(
                        multiline=False, font_size=dp(14), font_name=FONT_NAME,
                        foreground_color=(0.05, 0.05, 0.05, 1),
                        background_color=(1, 1, 1, 1),
                        cursor_color=(0.10, 0.30, 0.70, 1),
                        padding=[dp(8), dp(8), dp(8), dp(8)],
                        size_hint_y=None, height=dp(36),
                        hint_text="Поиск по должностям..."
                    )
                    inner.add_widget(search_input)

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
                        new_wrap.size_hint = (1, None)
                        new_wrap.height = dp(38)
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
                                   title_font=FONT_NAME, auto_dismiss=False)

                        def do_rename(*a):
                            new_name = new_wrap.text.strip()
                            if not new_name or new_name == rename_old:
                                rp.dismiss()
                                return
                                
                            sp_list = self.app.data.setdefault(
                                'signer_positions', ['Энергетик'])
                                
                            if not isinstance(sp_list, list):
                                sp_list = list(sp_list)
                                self.app.data['signer_positions'] = sp_list

                            sp_list[:] = [x for x in sp_list if str(x).lower() != rename_old.lower()]
                            
                            if new_name not in sp_list:
                                sp_list.append(new_name)
                            
                            seen = set()
                            unique_sp = []
                            for x in sp_list:
                                x_lower = str(x).lower()
                                if x_lower not in seen:
                                    unique_sp.append(x)
                                    seen.add(x_lower)
                            sp_list[:] = unique_sp

                            signers_map = self.app.data.get('department_signer', {})
                            for _d, ent in signers_map.items():
                                if ent.get('position', '').lower() == rename_old.lower():
                                    ent['position'] = new_name

                            if pos_w.text.strip().lower() == rename_old.lower():
                                pos_w.text = new_name

                            self.app.safe_save(self.app.data)
                            rp.dismiss()
                            
                            Clock.schedule_once(lambda dt: rebuild_rows(search_input.text), 0)
                            Clock.schedule_once(lambda dt: rebuild_list(), 0)

                        ok.bind(on_press=do_rename)
                        cancel.bind(on_press=rp.dismiss)
                        new_wrap.bind(on_text_validate=lambda *a: do_rename())
                        bind_enter_key(rp, do_rename)
                        
                        Clock.schedule_once(lambda dt: rp.open(), 0.1)

                    def _delete(name):
                        signers_map = self.app.data.get('department_signer', {})
                        current_depts = self.app.data.get('departments', [])
                        
                        used_by = [d for d, ent in signers_map.items()
                                   if ent.get('position', '').lower() == name.lower() and d in current_depts]
                        
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
                                       title_font=FONT_NAME, auto_dismiss=False)
                            ok.bind(on_press=p2.dismiss)
                            bind_enter_key(p2, p2.dismiss)
                            
                            Clock.schedule_once(lambda dt: p2.open(), 0.1)
                            return

                        def _do():
                            sp_list = self.app.data.get('signer_positions', [])
                            if name in sp_list:
                                sp_list.remove(name)
                            
                            for d in list(signers_map.keys()):
                                if signers_map[d].get('position', '').lower() == name.lower():
                                    signers_map.pop(d, None)
                                    
                            self.app.safe_save(self.app.data)
                            rebuild_rows(search_input.text)
                            rebuild_list()

                        ask_password_and_run(
                            DELETE_PASSWORD, _do,
                            description=(f"Удалить должность подписанта:\n"
                                         f"«{name}»?"))

                    def rebuild_rows(query=''):
                        grid.clear_widgets()
                        sp_list = list(self.app.data.get(
                            'signer_positions', ['Энергетик']))
                        
                        sp_list.sort(key=lambda x: x.lower())
                        
                        q = query.strip().lower()
                        if q:
                            sp_list = [nm for nm in sp_list if q in nm.lower()]

                        if not sp_list:
                            msg = "(ничего не найдено)" if q else "(список пуст)"
                            grid.add_widget(Label(
                                text=msg, color=LABEL_LIGHT,
                                font_name=FONT_NAME, font_size=dp(14),
                                size_hint_y=None, height=dp(40)))
                            return
                            
                        for nm in sp_list:
                            row = HoverRow(size_hint_y=None,
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
                            ren_btn.bind(on_press=lambda *a, x=nm: Clock.schedule_once(lambda dt: _rename(x), 0.1))
                            row.add_widget(ren_btn)

                            del_btn = Button(
                                text="Удалить",
                                size_hint_x=None, width=dp(130),
                                font_name=FONT_NAME, font_size=dp(15),
                                bold=True,
                                background_color=(0.9, 0.35, 0.35, 1),
                                color=(1, 1, 1, 1))
                            del_btn.bind(on_press=lambda *a, x=nm: Clock.schedule_once(lambda dt: _delete(x), 0.1))
                            row.add_widget(del_btn)

                            grid.add_widget(row)

                    search_input.bind(text=lambda inst, val: rebuild_rows(val))

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

                    self.active_dept_picker_popup = picker
                    self.active_dept_picker_rebuild = lambda: rebuild_rows(search_input.text)

                    def on_picker_dismiss(*args):
                        self.active_dept_picker_popup = None
                        self.active_dept_picker_rebuild = None

                    picker.bind(on_dismiss=on_picker_dismiss)

                    Clock.schedule_once(lambda dt: picker.open(), 0.1)

                pos_btn.bind(on_press=_open_positions_picker)

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
                          content=outer, size_hint=(0.6, 0.52 if is_new else 0.36),
                          title_color=LABEL_LIGHT, title_font=FONT_NAME,
                          auto_dismiss=False)

                def on_ok(*a):
                    if is_new:
                        new_name = edit_wrap.text.strip()
                    else:
                        new_name = old_name
                        
                    new_pos = pos_w.text.strip()
                    new_fio = fio_w.text.strip()

                    missing = []
                    if is_new and not new_name:
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
                                          title_font=FONT_NAME, auto_dismiss=False)
                        err_btn.bind(on_press=err_popup.dismiss)
                        bind_enter_key(err_popup, err_popup.dismiss)
                        err_popup.open()
                        return

                    if is_new and new_name in self.app.data['departments']:
                        p.dismiss()
                        err_content = BoxLayout(orientation='vertical', spacing=10, padding=10)
                        err_content.add_widget(Label(text=f"Отдел «{new_name}»\nуже существует!", color=LABEL_LIGHT, halign='center', valign='middle', font_name=FONT_NAME, font_size=dp(15)))
                        ok_btn = Button(text="ОК", size_hint_y=None, height=dp(40), font_name=FONT_NAME, background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1))
                        err_content.add_widget(ok_btn)
                        err = Popup(title="Ошибка", content=err_content, size_hint=(0.45, 0.3), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
                        ok_btn.bind(on_press=err.dismiss)
                        err.open()
                        return

                    sp = self.app.data.setdefault('signer_positions',
                                                  ['Энергетик'])
                    if new_pos.lower() not in [x.lower() for x in sp]:
                        sp.append(new_pos)

                    if is_new:
                        self.app.data['departments'].append(new_name)
                        if new_pw_input is not None:
                            npw = new_pw_input.text.strip()
                            if npw:
                                dept_passwords_map[new_name] = npw
                                
                    signers[new_name] = {'position': new_pos, 'name': new_fio}
                    self.app.safe_save(self.app.data)
                    p.dismiss()
                    rebuild_list()
                    self.refresh()

                prev_pos_set = set(self.app.data.get('signer_positions', ['Энергетик']))

                def rebuild_dept_editor():
                    try:
                        new_pos_set = set(self.app.data.get('signer_positions', ['Энергетик']))
                        cur_val = pos_w.text.strip()
                        if cur_val in prev_pos_set and cur_val not in new_pos_set:
                            rem = prev_pos_set - new_pos_set
                            add = new_pos_set - prev_pos_set
                            if len(rem) == 1 and len(add) == 1:
                                pos_w.text = next(iter(add))
                        prev_pos_set.clear()
                        prev_pos_set.update(new_pos_set)
                    except Exception:
                        pass

                self.active_dept_editor_popup = p
                self.active_dept_editor_rebuild = rebuild_dept_editor

                def on_dept_editor_dismiss(*args):
                    self.active_dept_editor_popup = None
                    self.active_dept_editor_rebuild = None

                p.bind(on_dismiss=on_dept_editor_dismiss)

                ok.bind(on_press=on_ok)
                cancel.bind(on_press=p.dismiss)
                
                if is_new and edit_wrap is not None:
                    edit_wrap.bind(on_text_validate=lambda *a: on_ok())
                fio_w.bind(on_text_validate=lambda *a: on_ok())
                bind_enter_key(p, on_ok)
                
                Clock.schedule_once(lambda dt: p.open(), 0.1)

            if not is_new:
                self._check_dept_access(old_name, _build_and_open)
            else:
                _build_and_open()

        def rebuild_list():
            list_grid.clear_widgets()
            items = [(i, d) for i, d in enumerate(self.app.data['departments'])]
            items.sort(key=lambda x: x[1].lower())
            
            for display_num, (i, d) in enumerate(items, start=1):
                row = HoverRow(size_hint_y=None, height=dp(42), spacing=0)
                row.add_widget(vsep(color=LABEL_LIGHT))

                r_num = Label(text=str(display_num), size_hint_x=None, width=dp(40), color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(14), halign='center', valign='middle')
                row.add_widget(r_num)
                row.add_widget(vsep(color=LABEL_LIGHT))

                r_dept = Label(text=d, color=(1, 1, 1, 1), size_hint_x=2.2, font_name=FONT_NAME, font_size=dp(15), bold=True, halign='left', valign='middle')
                r_dept.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0] - dp(10), val[1])))
                row.add_widget(r_dept)
                row.add_widget(vsep(color=LABEL_LIGHT))

                sign_pos, sign_fio = get_signer(d)
                
                r_pos = Label(text=sign_pos, size_hint_x=1.8, color=(0.85, 0.90, 1.0, 1), font_name=FONT_NAME, font_size=dp(13), halign='left', valign='middle')
                r_pos.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0] - dp(10), val[1])))
                row.add_widget(r_pos)
                row.add_widget(vsep(color=LABEL_LIGHT))

                r_fio = Label(text=sign_fio, size_hint_x=2.5, color=(0.85, 0.90, 1.0, 1), font_name=FONT_NAME, font_size=dp(13), halign='left', valign='middle')
                r_fio.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0] - dp(10), val[1])))
                row.add_widget(r_fio)
                row.add_widget(vsep(color=LABEL_LIGHT))

                btns_box = BoxLayout(size_hint_x=None, width=dp(230), spacing=4, padding=(dp(4), dp(4)))
                edit_btn = Button(text="Изменить", font_name=FONT_NAME, font_size=dp(15), bold=True, background_color=(0.35, 0.55, 0.85, 1), color=(1, 1, 1, 1))
                edit_btn.bind(on_press=lambda *a, ii=i: open_dept_editor(ii))
                btns_box.add_widget(edit_btn)

                del_btn = Button(text="Удалить", font_name=FONT_NAME, font_size=dp(15), bold=True, background_color=(0.9, 0.35, 0.35, 1), color=(1, 1, 1, 1))
                del_btn.bind(on_press=lambda *a, ii=i: delete_dept(ii))
                btns_box.add_widget(del_btn)

                row.add_widget(btns_box)
                row.add_widget(vsep(color=LABEL_LIGHT))

                add_bottom_border(row)
                list_grid.add_widget(row)

        rebuild_list()
        list_scroll.add_widget(list_grid)
        content.add_widget(list_scroll)

        close_btn = Button(text="Закрыть", size_hint_y=None, height=dp(40),
                           color=(1, 1, 1, 1),
                           font_name=FONT_NAME, font_size=dp(16), bold=True)
        content.add_widget(close_btn)
        popup = Popup(title="Отделы", content=content,
                      size_hint=(0.80, 0.65), title_color=LABEL_LIGHT,
                      title_font=FONT_NAME, auto_dismiss=False)
        close_btn.bind(on_press=popup.dismiss)
        
        self.active_depts_popup = popup
        self.active_depts_rebuild = rebuild_list
        def on_depts_dismiss(*args):
            self.active_depts_popup = None
            self.active_depts_rebuild = None
        popup.bind(on_dismiss=on_depts_dismiss)

        popup.open()
        rebuild_list()

    def _fix_layout_gap(self, dt=0):
        """Принудительно пересчитывает высоту списка и убирает пустоту"""
        if hasattr(self, 'list_layout') and hasattr(self, 'scroll_view'):
            self.list_layout.height = self.list_layout.minimum_height
            self.list_layout.do_layout()
            # Если контента стало меньше, чем высота окна — прилипаем к верху
            if self.list_layout.height <= self.scroll_view.height:
                self.scroll_view.scroll_y = 1.0
                
    def _toggle_dept_collapse(self, name):
        if name in self._collapsed_depts:
            self._collapsed_depts.remove(name)
        else:
            self._collapsed_depts.append(name)
        save_local_collapsed_depts(self._collapsed_depts)
        self.refresh()
        
        # ДОБАВЛЕНО: откладываем пересчет на следующий кадр
        Clock.schedule_once(self._fix_layout_gap, 0.01)

    def _add_dept_bar(self, name, bg=DEPT_BAR_BG, fg=DEPT_BAR_FG, movable=True, raw_name=None):
        if raw_name is None:
            raw_name = name

        if movable:
            bar = RightClickBox(size_hint_y=None, height=dp(30),
                                padding=(0, 0, 0, 0))
            bar._on_right_click = (
                lambda t, n=raw_name, w=bar: self._show_department_menu(n, t, w)
            )
            bar._on_left_click = ( 
                lambda t, n=raw_name: self._toggle_dept_collapse(n)
            )
        else:
            bar = BoxLayout(size_hint_y=None, height=dp(30),
                            padding=(0, 0, 0, 0))

        bar.raw_name = raw_name  # <--- ДОБАВЛЕНО: сохраняем имя отдела
        
        with bar.canvas.before:
            Color(*bg)
            rect = Rectangle(pos=bar.pos, size=bar.size)
        bar.bind(pos=lambda i, v, r=rect: setattr(r, 'pos', v),
                 size=lambda i, v, r=rect: setattr(r, 'size', v))

        lbl = Label(text=name, color=fg,
                    font_name=FONT_NAME, font_size=dp(15),
                    bold=True,
                    halign='center', valign='middle')
        lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        bar.lbl = lbl  # <--- ДОБАВЛЕНО: сохраняем ссылку на текст
        
        bar.add_widget(lbl)
        self.list_layout.add_widget(bar)