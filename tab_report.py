# tab_report.py
# -*- coding: utf-8 -*-
import config, webbrowser
import time
import sys
import traceback
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
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.button import Button as StdButton

from config import (FONT_NAME, LABEL_LIGHT, MONTHS, YEARS, SPINNER_BG, SPINNER_FG, 
                    RIGHT_COLUMNS, DEFAULT_ORG, DEFAULT_ENERGETIC, DEFAULT_DIRECTOR)

from data_storage import get_local_signers, set_local_signers
from data_utils import (classify_day, analyze_row, apply_overtime, fmt_hours, 
                        calc_norm_hours, set_local_show_legend, get_local_show_legend,
                        save_data)

from ui_helpers import (NoOverscrollEffect, add_top_border, add_bottom_border,
                        add_left_border, add_right_border, vsep, ask_password_and_run,
                        bind_enter_key)
from config import DELETE_PASSWORD
from ui_widgets import HoverButton as Button, LightSpinnerOption
from excel_export import export_full_excel, export_short_excel

# ==============================================================================
# БЛОК ДЛЯ ОТЛАДКИ (DEBUG)
# ==============================================================================
def dbg(msg):
    """Выводит сообщение с временной меткой"""
    print(f"[DEBUG {time.strftime('%H:%M:%S')}.{int(time.time()*1000)%1000:03d}] {msg}")

# Перехватчик необработанных исключений, чтобы программа не падала молча
def custom_excepthook(exc_type, exc_value, exc_traceback):
    print("\n!!! НЕОБРАБОТАННОЕ ИСКЛЮЧЕНИЕ !!!")
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
sys.excepthook = custom_excepthook
# ==============================================================================

class HoverClickableRow(ButtonBehavior, BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hovering = False
        with self.canvas.before:
            self._bg_color = Color(0.15, 0.15, 0.18, 1)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
            
        self.bind(pos=self._update_rect, size=self._update_rect, state=self._on_state)
        
        from kivy.core.window import Window
        Window.bind(mouse_pos=self._on_mouse_pos)
        self.bind(parent=self._on_parent)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            for child in self.walk():
                if isinstance(child, (Button, StdButton)) and child != self:
                    if child.collide_point(*touch.pos):
                        return super(ButtonBehavior, self).on_touch_down(touch)
        return super().on_touch_down(touch)

    def _on_parent(self, instance, parent):
        if parent is None:
            from kivy.core.window import Window
            try:
                Window.unbind(mouse_pos=self._on_mouse_pos)
            except Exception:
                pass

    def _update_rect(self, *a):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _is_covered(self):
        from kivy.core.window import Window
        from kivy.uix.popup import Popup
        from kivy.uix.dropdown import DropDown
        
        top_modal = None
        for child in Window.children:
            if isinstance(child, (Popup, DropDown)):
                top_modal = child
                break
                
        if top_modal is None:
            return False
            
        w = self
        depth = 0
        # ОГРАНИЧЕНИЕ ГЛУБИНЫ, ЧТОБЫ НЕ УЙТИ В БЕСКОНЕЧНЫЙ ЦИКЛ ПРИ УНИЧТОЖЕНИИ ВИДЖЕТА
        while w and depth < 50:
            if w == top_modal:
                return False
            w = w.parent
            depth += 1
            
        return True

    def _on_mouse_pos(self, window, pos):
        if not self.get_root_window() or self.disabled:
            return
            
        if self._is_covered():
            if self._hovering:
                self._hovering = False
                self._update_bg()
            return
            
        try:
            wx, wy = self.to_window(self.x, self.y)
            if wx <= pos[0] <= wx + self.width and wy <= pos[1] <= wy + self.height:
                if not self._hovering:
                    self._hovering = True
                    self._update_bg()
            else:
                if self._hovering:
                    self._hovering = False
                    self._update_bg()
        except Exception:
            pass

    def _on_state(self, inst, value):
        self._update_bg()

    def _update_bg(self):
        if self._hovering or self.state == 'down':
            self._bg_color.rgba = (0.30, 0.30, 0.35, 1) 
        else:
            self._bg_color.rgba = (0.15, 0.15, 0.18, 1)
# -------------------------------------------------------------------------

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
        self.active_signers_popup = None
        self.active_signers_rebuild = None
        self.active_picker_popup = None
        self.active_picker_rebuild = None

        with self.canvas.before:
            Color(*config.TABLE_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda i, v: setattr(self._bg, 'pos', v),
                  size=lambda i, v: setattr(self._bg, 'size', v))

        self._build()
        Clock.schedule_once(lambda *a: self.update_preview(), 0.3)
        
    def _migrate_signers_once(self):
        try:
            from data_storage import load_local, save_local
            import json as _json

            local = load_local()
            if local.get('signers_migrated'):
                return

            local_signers = local.get('additional_signers', [])

            if local_signers:
                try:
                    with open(config.DATA_FILE, 'r', encoding='utf-8') as f:
                        disk_data = _json.load(f)
                    if 'shared_signers' in disk_data:
                        self.app.data['shared_signers'] = disk_data['shared_signers']
                except Exception:
                    pass

                shared = self.app.data.setdefault('shared_signers', [])
                shared_keys = {(sh.get('name', '').strip(),
                                sh.get('position', '').strip()) for sh in shared}
                added = False
                for s in local_signers:
                    n = (s.get('name') or '').strip()
                    p = (s.get('position') or '').strip()
                    if n and p and (n, p) not in shared_keys:
                        shared.append({'name': n, 'position': p})
                        shared_keys.add((n, p))
                        added = True
                if added:
                    self.app.safe_save(self.app.data)

            local['signers_migrated'] = True
            save_local(local)
        except Exception as e:
            print("Ошибка миграции подписантов:", e)

    def _on_org_change(self, inst, value):
        self.app.data['organization'] = value
        if self._org_save_ev:
            self._org_save_ev.cancel()
        self._org_save_ev = Clock.schedule_once(lambda *a: self.app.safe_save(self.app.data), 0.5)
        Clock.schedule_once(lambda *a: self.update_preview(), 0.1)

    def _on_dir_change(self, inst, value):
        self.app.data['director_name'] = value
        if self._dir_save_ev:
            self._dir_save_ev.cancel()
        self._dir_save_ev = Clock.schedule_once(lambda *a: self.app.safe_save(self.app.data), 0.5)
        Clock.schedule_once(lambda *a: self.update_preview(), 0.1)

    def _build(self):
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

        signers_btn = Button(text="Доп. подписанты", size_hint_x=None, width=dp(180),
                             font_name=FONT_NAME, font_size=dp(14), bold=True,
                             background_color=(0.5, 0.4, 0.75, 1), color=(1, 1, 1, 1))
        signers_btn.bind(on_press=self.show_signers_popup)
        top.add_widget(signers_btn)

        top.add_widget(Widget(size_hint_x=None, width=dp(15)))

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

        admin_btn = Button(text="Выгрузить всё", size_hint_x=None, width=dp(150),
                           font_name=FONT_NAME, font_size=dp(15), bold=True,
                           background_color=(0.4, 0.5, 0.7, 1), color=(1, 1, 1, 1))
        
        admin_btn.bind(on_press=lambda *a: ask_password_and_run(
            DELETE_PASSWORD, 
            self.show_admin_export_dialog,
            title="Массовая выгрузка",
            btn_text="Выгрузить",
            password_prompt="Введите пароль для выгрузки ВСЕХ отделов:"
        ))
        top.add_widget(admin_btn)

        self.add_widget(top)

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
        dbg("show_signers_popup: Открытие окна подписантов")
        self._migrate_signers_once()

        content = BoxLayout(orientation='vertical', spacing=10, padding=10)

        add_title = Label(text="Добавить подписанта:", color=LABEL_LIGHT,
                          font_name=FONT_NAME, size_hint_y=None, height=dp(24),
                          halign='left')
        add_title.bind(size=lambda i, v: setattr(i, 'text_size', v))
        content.add_widget(add_title)

        add_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=5)

        new_pos = TextInput(hint_text="Должность", multiline=False,
                            font_size=dp(14), font_name=FONT_NAME, halign='left',
                            padding=[dp(10), dp(12), dp(10), dp(12)])
        new_name = TextInput(hint_text="Фамилия И.О.", multiline=False,
                             font_size=dp(14), font_name=FONT_NAME, halign='left',
                             padding=[dp(10), dp(12), dp(10), dp(12)])

        pick_btn = Button(text="Выбрать...", size_hint_x=None, width=dp(110),
                          background_color=(0.4, 0.5, 0.7, 1), color=(1, 1, 1, 1),
                          font_name=FONT_NAME, font_size=dp(14), bold=True)
        add_btn = Button(text="Добавить", size_hint_x=None, width=dp(100),
                         background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1))

        add_row.add_widget(new_pos)
        add_row.add_widget(new_name)
        add_row.add_widget(pick_btn)
        add_row.add_widget(add_btn)
        content.add_widget(add_row)

        table_header = BoxLayout(size_hint_y=None, height=dp(30), spacing=0)
        
        h_chk = BoxLayout(size_hint_x=None, width=dp(40))
        add_left_border(h_chk, color=(0.4, 0.4, 0.4, 1))
        add_right_border(h_chk, color=(0.4, 0.4, 0.4, 1))
        table_header.add_widget(h_chk)
        
        h_pos = BoxLayout(size_hint_x=1)
        add_right_border(h_pos, color=(0.4, 0.4, 0.4, 1))
        lbl_pos = Label(text="Должность", bold=True, color=LABEL_LIGHT, font_name=FONT_NAME)
        h_pos.add_widget(lbl_pos)
        table_header.add_widget(h_pos)
        
        h_name = BoxLayout(size_hint_x=1)
        add_right_border(h_name, color=(0.4, 0.4, 0.4, 1))
        lbl_name = Label(text="Фамилия И.О.", bold=True, color=LABEL_LIGHT, font_name=FONT_NAME)
        h_name.add_widget(lbl_name)
        table_header.add_widget(h_name)
        
        h_act = BoxLayout(size_hint_x=None, width=dp(200))
        add_right_border(h_act, color=(0.4, 0.4, 0.4, 1))
        lbl_act = Label(text="Действия", bold=True, color=LABEL_LIGHT, font_name=FONT_NAME)
        h_act.add_widget(lbl_act)
        table_header.add_widget(h_act)
        
        add_top_border(table_header, color=(0.4, 0.4, 0.4, 1))
        add_bottom_border(table_header, color=(0.4, 0.4, 0.4, 1))
        content.add_widget(table_header)

        sv = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=0)
        grid.bind(minimum_height=grid.setter('height'))
        sv.add_widget(grid)
        content.add_widget(sv)

        close_btn = Button(text="Закрыть", size_hint_y=None, height=dp(40),
                           color=(1, 1, 1, 1), font_name=FONT_NAME)
        content.add_widget(close_btn)

        popup = Popup(title="Дополнительные подписанты", content=content,
                      size_hint=(0.85, 0.75), title_color=LABEL_LIGHT,
                      title_font=FONT_NAME)

        def save_signers(signers_list):
            set_local_signers(signers_list)
            self.update_preview()

        def open_edit_local_dialog(idx, signers, rebuild_cb):
            if getattr(open_edit_local_dialog, 'active', False):
                return
            open_edit_local_dialog.active = True

            s = signers[idx]
            edit_content = BoxLayout(orientation='vertical', spacing=10, padding=(30, 20, 30, 20))

            edit_content.add_widget(Widget(size_hint_y=1))

            lbl_pos = Label(text="Должность:", color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_y=None, height=dp(20), halign='center', valign='middle')
            lbl_pos.bind(size=lambda i,v: setattr(i, 'text_size', v))
            pos_in = TextInput(text=s.get('position', ''), multiline=False, font_size=dp(14),
                               font_name=FONT_NAME, padding=[dp(10), dp(10), dp(10), dp(10)], size_hint_y=None, height=dp(38), halign='left')

            lbl_name = Label(text="Фамилия И.О.:", color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_y=None, height=dp(20), halign='center', valign='middle')
            lbl_name.bind(size=lambda i,v: setattr(i, 'text_size', v))
            name_in = TextInput(text=s.get('name', ''), multiline=False, font_size=dp(14),
                                font_name=FONT_NAME, padding=[dp(10), dp(10), dp(10), dp(10)], size_hint_y=None, height=dp(38), halign='left')

            edit_content.add_widget(lbl_pos)
            edit_content.add_widget(pos_in)
            edit_content.add_widget(lbl_name)
            edit_content.add_widget(name_in)
            
            edit_content.add_widget(Widget(size_hint_y=1))

            btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=10)
            save_b = Button(text="Сохранить", background_color=(0.3, 0.7, 0.3, 1), color=(1,1,1,1), font_name=FONT_NAME)
            cancel_b = Button(text="Отмена", color=(1,1,1,1), font_name=FONT_NAME)
            btns.add_widget(save_b)
            btns.add_widget(cancel_b)
            edit_content.add_widget(btns)

            p = Popup(title="Редактирование подписанта", content=edit_content, size_hint=(0.45, 0.45),
                      title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)

            def on_p_dismiss(*args):
                dbg("open_edit_local_dialog: окно закрыто (on_p_dismiss)")
                open_edit_local_dialog.active = False
            p.bind(on_dismiss=on_p_dismiss)

            saved = {'status': False}

            def do_save(*a):
                if saved['status']:
                    return
                saved['status'] = True
                dbg("do_save: нажата кнопка Сохранить")
                new_n = name_in.text.strip()
                new_p = pos_in.text.strip()
                old_n = s.get('name', '')
                old_p = s.get('position', '')
                
                if new_n and new_p:
                    dbg("do_save: данные валидны, закрываем окно...")
                    p.dismiss() 
                    
                    def _process_save(dt):
                        dbg("do_save._process_save: сохранение данных...")
                        signers[idx]['name'] = new_n
                        signers[idx]['position'] = new_p
                        set_local_signers(signers)
                        
                        shared = self.app.data.setdefault('shared_signers', [])
                        for sh in shared:
                            if sh.get('name') == old_n and sh.get('position') == old_p:
                                sh['name'] = new_n
                                sh['position'] = new_p
                                break
                        try:
                            self.app.safe_save(self.app.data)
                        except Exception as e:
                            print("Save error:", e)
                        
                        self.update_preview()
                        rebuild_cb()
                        dbg("do_save._process_save: сохранение завершено.")
                    
                    Clock.schedule_once(_process_save, 0) 
                else:
                    p.dismiss()

            save_b.bind(on_press=do_save)
            cancel_b.bind(on_press=p.dismiss)
            pos_in.bind(on_text_validate=do_save)
            name_in.bind(on_text_validate=do_save)
            
            dbg("open_edit_local_dialog: привязка bind_enter_key")
            bind_enter_key(p, do_save)
            
            dbg("open_edit_local_dialog: вызов p.open()")
            Clock.schedule_once(lambda dt: p.open(), 0.1)

        def rebuild_list(from_update=False):
            grid.clear_widgets()

            shared = self.app.data.get('shared_signers', [])
            shared_keys = {(sh.get('name', '').strip(), sh.get('position', '').strip()) for sh in shared}
            local_list = get_local_signers()
            
            cleaned = []
            seen = set()
            for s in local_list:
                n = (s.get('name') or '').strip()
                p = (s.get('position') or '').strip()
                key = (n, p)
                if key in shared_keys and key not in seen:
                    cleaned.append(s)
                    seen.add(key)
                    
            if len(cleaned) != len(local_list):
                set_local_signers(cleaned)
                if not from_update:
                    self.update_preview()

            signers = cleaned

            for i, s in enumerate(signers):
                orig_n = (s.get('name') or '').strip()
                orig_p = (s.get('position') or '').strip()

                row = BoxLayout(size_hint_y=None, height=dp(36), spacing=0)
                add_bottom_border(row, color=(0.4, 0.4, 0.4, 1))

                c_box = BoxLayout(size_hint_x=None, width=dp(40))
                add_left_border(c_box, color=(0.4, 0.4, 0.4, 1))
                add_right_border(c_box, color=(0.4, 0.4, 0.4, 1))
                cb = CheckBox(active=s.get('active', True))
                def make_toggle(idx):
                    def toggle(inst, val):
                        signers[idx]['active'] = val
                        save_signers(signers)
                    return toggle
                cb.bind(active=make_toggle(i))
                c_box.add_widget(cb)
                row.add_widget(c_box)

                p_box = BoxLayout(size_hint_x=1, padding=(dp(5), 0, 0, 0))
                add_right_border(p_box, color=(0.4, 0.4, 0.4, 1))
                lbl_pos = Label(text=orig_p, font_size=dp(14), font_name=FONT_NAME, halign='left', valign='middle', color=LABEL_LIGHT)
                lbl_pos.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0]-dp(5), val[1])))
                p_box.add_widget(lbl_pos)
                row.add_widget(p_box)

                n_box = BoxLayout(size_hint_x=1, padding=(dp(5), 0, 0, 0))
                add_right_border(n_box, color=(0.4, 0.4, 0.4, 1))
                lbl_name = Label(text=orig_n, font_size=dp(14), font_name=FONT_NAME, halign='left', valign='middle', color=LABEL_LIGHT)
                lbl_name.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0]-dp(5), val[1])))
                n_box.add_widget(lbl_name)
                row.add_widget(n_box)

                a_box = BoxLayout(size_hint_x=None, width=dp(200), spacing=dp(4), padding=(dp(4), dp(2)))
                add_right_border(a_box, color=(0.4, 0.4, 0.4, 1))
                
                edit_btn = Button(text="Изменить", background_color=(0.35, 0.55, 0.85, 1), color=(1, 1, 1, 1), font_name=FONT_NAME, font_size=dp(12))
                # ...
                del_btn = Button(text="Удалить", background_color=(0.8, 0.2, 0.2, 1), color=(1, 1, 1, 1), font_name=FONT_NAME, font_size=dp(12))
                def make_del(idx):
                    def delete(inst):
                        s_item = signers[idx]
                        s_n = (s_item.get('name') or '').strip()
                        s_p = (s_item.get('position') or '').strip()

                        def do_delete():
                            # Удаляем ТОЛЬКО из локального списка
                            signers.pop(idx)
                            set_local_signers(signers)
                            
                            def _process_delete(dt):
                                # Сохранение в базу (self.app.safe_save) больше не вызывается,
                                # так как общая база не меняется.
                                self.update_preview()
                                rebuild_list()
                            Clock.schedule_once(_process_delete, 0)

                        ask_password_and_run(
                            DELETE_PASSWORD, do_delete, 
                            description=f"Убрать подписанта «{s_p} — {s_n}»\nиз вашего списка?"
                        )
                    return delete
                del_btn.bind(on_press=make_del(i))
                a_box.add_widget(del_btn)
                
                row.add_widget(a_box)
                grid.add_widget(row)

        def do_add(*a):
            pos = new_pos.text.strip()
            nm = new_name.text.strip()
            if pos and nm:
                signers = get_local_signers()
                
                if any((s.get('name', '').strip() == nm and s.get('position', '').strip() == pos) for s in signers):
                    err_content = BoxLayout(orientation='vertical', spacing=10, padding=10)
                    err_content.add_widget(Label(
                        text=f"Подписант «{pos} — {nm}»\nуже добавлен в ваш список!",
                        color=LABEL_LIGHT, halign='center', valign='middle',
                        font_name=FONT_NAME, font_size=dp(14)
                    ))
                    ok_btn = StdButton(text="ОК", size_hint_y=None, height=dp(40), font_name=FONT_NAME, background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1))
                    err_content.add_widget(ok_btn)
                    err_popup = Popup(title="Дубликат", content=err_content, size_hint=(0.45, 0.3), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
                    ok_btn.bind(on_press=err_popup.dismiss)
                    bind_enter_key(err_popup, err_popup.dismiss)
                    err_popup.open()
                    return

                shared = self.app.data.setdefault('shared_signers', [])
                if not any((sh.get('name', '').strip() == nm and sh.get('position', '').strip() == pos) for sh in shared):
                    shared.append({'name': nm, 'position': pos})
                    
                    def _process_add(dt):
                        try:
                            self.app.safe_save(self.app.data)
                        except Exception as e:
                            print("Save error:", e)
                    Clock.schedule_once(_process_add, 0)

                signers.append({'name': nm, 'position': pos, 'active': True})
                save_signers(signers)

                new_pos.text = ""
                new_name.text = ""
                rebuild_list()

        def open_signer_picker(*args):
            dbg("open_signer_picker: Открытие окна выбора из базы")
            candidates = set()
            for s in self.app.data.get('shared_signers', []):
                nm = (s.get('name') or '').strip()
                pos = (s.get('position') or '').strip()
                if pos and nm: candidates.add((pos, nm))
            for s in get_local_signers():
                nm = (s.get('name') or '').strip()
                pos = (s.get('position') or '').strip()
                if pos and nm: candidates.add((pos, nm))

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

            h_pos = Label(text="Должность", bold=True, color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_x=0.5, halign='center', valign='middle')
            h_pos.bind(size=lambda i,v: setattr(i, 'text_size', (v[0], v[1])))
            add_bottom_border(h_pos, color=(0.4, 0.4, 0.4, 1)); add_right_border(h_pos, color=(0.4, 0.4, 0.4, 1))
            pick_header.add_widget(h_pos)

            h_name = Label(text="Фамилия И.О.", bold=True, color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_x=0.5, halign='center', valign='middle')
            h_name.bind(size=lambda i,v: setattr(i, 'text_size', (v[0], v[1])))
            add_bottom_border(h_name, color=(0.4, 0.4, 0.4, 1)); add_right_border(h_name, color=(0.4, 0.4, 0.4, 1))
            pick_header.add_widget(h_name)
            
            h_act = Label(text="Действия", bold=True, color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_x=None, width=dp(200), halign='center', valign='middle')
            h_act.bind(size=lambda i,v: setattr(i, 'text_size', (v[0], v[1])))
            add_bottom_border(h_act, color=(0.4, 0.4, 0.4, 1)); add_right_border(h_act, color=(0.4, 0.4, 0.4, 1))
            pick_header.add_widget(h_act)

            pick_content.add_widget(pick_header)

            pick_scroll = ScrollView(scroll_type=['bars'], effect_cls=NoOverscrollEffect)
            pick_grid = GridLayout(cols=1, size_hint_y=None, spacing=0)
            pick_grid.bind(minimum_height=pick_grid.setter('height'))
            pick_scroll.add_widget(pick_grid)
            pick_content.add_widget(pick_scroll)

            picker = Popup(title="Выбор подписанта из общей базы", content=pick_content, size_hint=(0.75, 0.7), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)

            editing = {'active': False}

            def edit_shared(p_pos, p_nm):
                if editing['active']:
                    return
                editing['active'] = True
                dbg(f"edit_shared: ВЫЗОВ ДЛЯ {p_pos} - {p_nm}")

                edit_content = BoxLayout(orientation='vertical', spacing=10, padding=(30, 20, 30, 20))
                edit_content.add_widget(Widget(size_hint_y=1))

                lbl_pos = Label(text="Должность:", color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_y=None, height=dp(20), halign='center', valign='middle')
                lbl_pos.bind(size=lambda i,v: setattr(i, 'text_size', v))
                pos_in = TextInput(text=p_pos, multiline=False, font_size=dp(14), font_name=FONT_NAME, padding=[dp(10), dp(10), dp(10), dp(10)], size_hint_y=None, height=dp(38), halign='left')
                
                lbl_name = Label(text="Фамилия И.О.:", color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_y=None, height=dp(20), halign='center', valign='middle')
                lbl_name.bind(size=lambda i,v: setattr(i, 'text_size', v))
                name_in = TextInput(text=p_nm, multiline=False, font_size=dp(14), font_name=FONT_NAME, padding=[dp(10), dp(10), dp(10), dp(10)], size_hint_y=None, height=dp(38), halign='left')

                edit_content.add_widget(lbl_pos)
                edit_content.add_widget(pos_in)
                edit_content.add_widget(lbl_name)
                edit_content.add_widget(name_in)
                edit_content.add_widget(Widget(size_hint_y=1))

                btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=10)
                save_b = Button(text="Сохранить", background_color=(0.3, 0.7, 0.3, 1), color=(1,1,1,1), font_name=FONT_NAME)
                cancel_b = Button(text="Отмена", color=(1,1,1,1), font_name=FONT_NAME)
                btns.add_widget(save_b); btns.add_widget(cancel_b)
                edit_content.add_widget(btns)

                ep = Popup(title="Редактирование в базе", content=edit_content, size_hint=(0.45, 0.45), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)

                def on_ep_dismiss(*args):
                    dbg("edit_shared: окно EP закрыто (on_ep_dismiss)")
                    editing['active'] = False
                    if not picker._window:
                        self.active_picker_popup = picker
                        self.active_picker_rebuild = rebuild_from_db
                        # Возвращаем picker с задержкой
                        Clock.schedule_once(lambda dt: picker.open(), 0.15)
                        
                ep.bind(on_dismiss=on_ep_dismiss)

                saved = {'status': False}

                def do_save(*a):
                    if saved['status']:
                        return
                    saved['status'] = True
                    dbg("edit_shared: нажата кнопка Сохранить (do_save)")
                    n_new = name_in.text.strip()
                    p_new = pos_in.text.strip()
                    if not n_new or not p_new: return
                    
                    dbg("edit_shared: вызываем ep.dismiss() перед сохранением")
                    ep.dismiss()

                    def _process_save(dt):
                        dbg("edit_shared._process_save: сохранение данных в базу...")
                        shared = self.app.data.get('shared_signers', [])
                        for sh in shared:
                            if (sh.get('name') or '').strip() == p_nm and (sh.get('position') or '').strip() == p_pos:
                                sh['name'] = n_new
                                sh['position'] = p_new
                        try:
                            self.app.safe_save(self.app.data)
                        except Exception as e:
                            print("Save error:", e)

                        local = get_local_signers()
                        changed = False
                        for s in local:
                            if (s.get('name') or '').strip() == p_nm and (s.get('position') or '').strip() == p_pos:
                                s['name'] = n_new
                                s['position'] = p_new
                                changed = True
                        if changed:
                            set_local_signers(local)

                        if (p_pos, p_nm) in candidates:
                            candidates.remove((p_pos, p_nm))
                        candidates.add((p_new, n_new))
                        
                        if changed:
                            self.update_preview()
                        rebuild_pick_list(search_input.text)
                        rebuild_list()
                        dbg("edit_shared._process_save: сохранение завершено.")
                    
                    Clock.schedule_once(_process_save, 0)

                save_b.bind(on_press=do_save)
                cancel_b.bind(on_press=ep.dismiss)
                pos_in.bind(on_text_validate=do_save)
                name_in.bind(on_text_validate=do_save)
                
                dbg("edit_shared: привязка bind_enter_key")
                bind_enter_key(ep, do_save)
                
                dbg("edit_shared: снимаем фокус с поиска и закрываем picker")
                try:
                    search_input.focus = False
                except Exception:
                    pass
                
                # === СТРОГО ПОСЛЕДОВАТЕЛЬНОЕ ОТКРЫТИЕ ===
                def launch_ep(*args):
                    picker.unbind(on_dismiss=launch_ep)
                    dbg("edit_shared: Picker полностью закрылся, открываем ep")
                    ep.open()

                picker.bind(on_dismiss=launch_ep)
                picker.dismiss()
                dbg("edit_shared: picker.dismiss() вызван, ожидаем завершения анимации")


            def delete_shared(p_pos, p_nm):
                def do_delete():
                    shared = self.app.data.get('shared_signers', [])
                    self.app.data['shared_signers'] = [s for s in shared if not ((s.get('name') or '').strip() == p_nm and (s.get('position') or '').strip() == p_pos)]
                    
                    local = get_local_signers()
                    local_clean = [s for s in local if not ((s.get('name') or '').strip() == p_nm and (s.get('position') or '').strip() == p_pos)]
                    set_local_signers(local_clean)
                    
                    if (p_pos, p_nm) in candidates:
                        candidates.remove((p_pos, p_nm))
                        
                    def _process_delete(dt):
                        try:
                            self.app.safe_save(self.app.data)
                        except Exception as e:
                            print("Save error:", e)
                            
                        self.update_preview()
                        rebuild_pick_list(search_input.text)
                        rebuild_list()
                        # После удаления возвращаем picker
                        self.active_picker_popup = picker
                        self.active_picker_rebuild = rebuild_from_db
                        Clock.schedule_once(lambda dt: picker.open(), 0.15)
                    Clock.schedule_once(_process_delete, 0)

                dbg(f"delete_shared: нажато удаление {p_pos} - {p_nm}, закрываем picker")
                try:
                    search_input.focus = False
                except Exception:
                    pass
                
                # === СТРОГО ПОСЛЕДОВАТЕЛЬНОЕ ОТКРЫТИЕ ПАРОЛЯ ===
                def launch_auth(*args):
                    picker.unbind(on_dismiss=launch_auth)
                    dbg("delete_shared: Picker полностью закрылся, открываем запрос пароля")
                    ask_password_and_run(
                        DELETE_PASSWORD, do_delete,
                        description=f"Удалить из базы «{p_pos} — {p_nm}»?\n(удалится у всех)"
                    )
                
                picker.bind(on_dismiss=launch_auth)
                picker.dismiss()
                dbg("delete_shared: picker.dismiss() вызван, ожидаем завершения анимации")

            def rebuild_pick_list(query=''):
                pick_grid.clear_widgets()
                q = query.lower()
                found = False
                
                for pos, nm in sorted(candidates, key=lambda x: (x[0].lower(), x[1].lower())):
                    if q in pos.lower() or q in nm.lower():
                        found = True
                        
                        row_layout = HoverClickableRow(spacing=0)
                        add_bottom_border(row_layout, color=(0.4, 0.4, 0.4, 1))
                        
                        def make_select(p=pos, n=nm):
                            def _sel(*a):
                                dbg(f"rebuild_pick_list._sel: выбран {p} - {n}")
                                new_pos.text = p
                                new_name.text = n
                                picker.dismiss()
                            return _sel

                        cell_pos = BoxLayout(size_hint_x=0.5, padding=(dp(10), 0, 0, 0))
                        lbl_pos = Label(text=pos, color=(1, 1, 1, 1), font_name=FONT_NAME, font_size=dp(14), halign='left', valign='middle')
                        lbl_pos.bind(size=lambda i,v: setattr(i, 'text_size', (v[0], v[1])))
                        cell_pos.add_widget(lbl_pos)
                        add_right_border(cell_pos, color=(0.4, 0.4, 0.4, 1))
                        row_layout.add_widget(cell_pos)
                        
                        cell_name = BoxLayout(size_hint_x=0.5, padding=(dp(10), 0, 0, 0))
                        lbl_name = Label(text=nm, color=(1, 1, 1, 1), font_name=FONT_NAME, font_size=dp(14), halign='left', valign='middle')
                        lbl_name.bind(size=lambda i,v: setattr(i, 'text_size', (v[0], v[1])))
                        cell_name.add_widget(lbl_name)
                        add_right_border(cell_name, color=(0.4, 0.4, 0.4, 1))
                        row_layout.add_widget(cell_name)
                        
                        row_layout.bind(on_press=make_select())

                        act_box = BoxLayout(size_hint_x=None, width=dp(200), spacing=dp(4), padding=(dp(4), dp(4)))
                        add_right_border(act_box, color=(0.4, 0.4, 0.4, 1))
                        
                        ed_btn = Button(text="Изменить", background_color=(0.35, 0.55, 0.85, 1), color=(1,1,1,1), font_name=FONT_NAME, font_size=dp(12))
                        ed_btn.bind(on_press=lambda *a, p=pos, n=nm: Clock.schedule_once(lambda dt: edit_shared(p, n), 0.1))
                        act_box.add_widget(ed_btn)

                        del_btn = Button(text="Удалить", background_color=(0.8, 0.2, 0.2, 1), color=(1,1,1,1), font_name=FONT_NAME, font_size=dp(12))
                        del_btn.bind(on_press=lambda *a, p=pos, n=nm: Clock.schedule_once(lambda dt: delete_shared(p, n), 0.1))
                        act_box.add_widget(del_btn)
                        
                        row_layout.add_widget(act_box)
                        pick_grid.add_widget(row_layout)

                if not found:
                    lbl = Label(text="Ничего не найдено", color=(0.6, 0.6, 0.6, 1), font_name=FONT_NAME, size_hint_y=None, height=dp(40))
                    pick_grid.add_widget(lbl)
                    
            def rebuild_from_db():
                nonlocal candidates
                candidates.clear()
                for s in self.app.data.get('shared_signers', []):
                    nm = (s.get('name') or '').strip()
                    pos = (s.get('position') or '').strip()
                    if pos and nm: candidates.add((pos, nm))
                for s in get_local_signers():
                    nm = (s.get('name') or '').strip()
                    pos = (s.get('position') or '').strip()
                    if pos and nm: candidates.add((pos, nm))
                rebuild_pick_list(search_input.text)

            self.active_picker_popup = picker
            self.active_picker_rebuild = rebuild_from_db
            
            def on_picker_dismiss(*args):
                dbg("open_signer_picker: окно Picker закрыто (on_picker_dismiss)")
                self.active_picker_popup = None
                self.active_picker_rebuild = None
                
            picker.bind(on_dismiss=on_picker_dismiss)

            search_input.bind(text=lambda inst, val: rebuild_pick_list(val))
            rebuild_pick_list()

            pick_close = Button(text="Отмена", size_hint_y=None, height=dp(40), color=(1,1,1,1), font_name=FONT_NAME)
            pick_close.bind(on_press=picker.dismiss)
            pick_content.add_widget(pick_close)
            
            dbg("open_signer_picker: вызов picker.open()")
            picker.open()
            
        pick_btn.bind(on_press=open_signer_picker)
        add_btn.bind(on_press=do_add)
        close_btn.bind(on_press=popup.dismiss)
        new_pos.bind(on_text_validate=do_add)
        new_name.bind(on_text_validate=do_add)

        self.active_signers_popup = popup
        self.active_signers_rebuild = rebuild_list
        
        def on_dismiss(*args):
            dbg("show_signers_popup: главное окно подписантов закрыто")
            self.active_signers_popup = None
            self.active_signers_rebuild = None
            self.update_preview()
            
        popup.bind(on_dismiss=on_dismiss)

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

    def update_open_popups(self):
        if getattr(self, 'active_signers_popup', None):
            if getattr(self, 'active_signers_rebuild', None):
                Clock.schedule_once(
                    lambda dt: self.active_signers_rebuild(from_update=True), 0)

        if getattr(self, 'active_picker_popup', None):
            if getattr(self, 'active_picker_rebuild', None):
                Clock.schedule_once(
                    lambda dt: self.active_picker_rebuild(), 0)
                
    def update_preview(self):
        local = get_local_signers()
        shared = self.app.data.get('shared_signers', [])
        shared_keys = {(s.get('name', '').strip(), s.get('position', '').strip()) for s in shared}
        
        cleaned = [s for s in local if ((s.get('name') or '').strip(), (s.get('position') or '').strip()) in shared_keys]
        if len(cleaned) != len(local):
            set_local_signers(cleaned)

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

    def show_admin_export_dialog(self, *args):
        content = BoxLayout(orientation='vertical', spacing=10, padding=15)
        content.add_widget(Widget(size_hint_y=1))

        content.add_widget(Label(
            text="Что именно нужно выгрузить?",
            color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(16), bold=True,
            size_hint_y=None, height=dp(30)))

        content.add_widget(Widget(size_hint_y=0.5))

        btns_choice = BoxLayout(orientation='vertical', spacing=10, size_hint_y=None, height=dp(98))
        
        btn_cur = Button(text=f"Только текущий месяц ({self.month_spinner.text} {self.year_spinner.text})",
                         background_color=(0.25, 0.55, 0.85, 1), color=(1,1,1,1), font_name=FONT_NAME)
        btn_all = Button(text="ВСЕ месяцы, где есть данные",
                         background_color=(0.4, 0.5, 0.7, 1), color=(1,1,1,1), font_name=FONT_NAME)

        btns_choice.add_widget(btn_cur)
        btns_choice.add_widget(btn_all)
        content.add_widget(btns_choice)

        content.add_widget(Widget(size_hint_y=1))

        btn_cancel = Button(text="Отмена", color=(1,1,1,1), font_name=FONT_NAME, size_hint_y=None, height=dp(44))
        content.add_widget(btn_cancel)

        popup_choice = Popup(title="Параметры выгрузки", content=content,
                             size_hint=(0.5, 0.5), title_color=LABEL_LIGHT,
                             title_font=FONT_NAME, auto_dismiss=False)

        def _proceed(export_all_months):
            popup_choice.dismiss()
            self._pick_folder_and_export(export_all_months)

        btn_cur.bind(on_press=lambda *a: _proceed(False))
        btn_all.bind(on_press=lambda *a: _proceed(True))
        btn_cancel.bind(on_press=popup_choice.dismiss)
        popup_choice.open()

    def _pick_folder_and_export(self, export_all_months):
        import os
        target_dir = ""
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            
            if os.path.exists(config.ICON_PATH):
                try:
                    root.iconbitmap(default=config.ICON_PATH)
                except Exception:
                    pass

            root.attributes('-topmost', True)
            target_dir = filedialog.askdirectory(title="Выберите папку для сохранения Excel-файлов")
            root.destroy()
        except Exception as e:
            print("Не удалось открыть системное окно выбора папки (tkinter):", e)
            return

        if not target_dir or not os.path.isdir(target_dir):
            return

        self._do_admin_export(target_dir, export_all_months)

    def _do_admin_export(self, target_dir, export_all_months):
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.metrics import dp
        from kivy.clock import Clock
        from excel_export import export_full_excel
        from ui_widgets import HoverButton
        
        prog_content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        prog_lbl = Label(text="Генерация файлов...\nПожалуйста, подождите.", 
                         color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(16),
                         halign='center', valign='middle')
        prog_content.add_widget(prog_lbl)
        
        prog_popup = Popup(title="Выгрузка", content=prog_content, size_hint=(0.4, 0.25),
                           title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
        prog_popup.open()
        
        def _do_work(dt):
            count = 0
            depts = self.app.data.get('departments', [])
            
            if export_all_months:
                keys = sorted(self.app.data.get('timesheets', {}).keys())
                for key in keys:
                    try:
                        y_str, m_str = key.split('-')
                        m_idx = int(m_str)
                        for d in depts:
                            export_full_excel(self, force_dept=d, save_dir=target_dir, force_year=y_str, force_month=m_idx)
                            count += 1
                    except Exception as e:
                        print(f"Ошибка при выгрузке {key}: {e}")
            else:
                y_str = self.year_spinner.text
                m_idx = MONTHS.index(self.month_spinner.text) + 1
                for d in depts:
                    try:
                        export_full_excel(self, force_dept=d, save_dir=target_dir, force_year=y_str, force_month=m_idx)
                        count += 1
                    except Exception as e:
                        print(f"Ошибка при выгрузке отдела {d}: {e}")
            
            prog_lbl.text = f"Готово! Выгружено отчетов: {count}"
            prog_popup.title = "Успешно"
            
            close_btn = HoverButton(text="ОК", size_hint_y=None, height=dp(44),
                                    background_color=(0.3, 0.7, 0.3, 1), color=(1,1,1,1),
                                    font_name=FONT_NAME, bold=True)
            close_btn.bind(on_press=prog_popup.dismiss)
            prog_content.add_widget(close_btn)
            
            prog_popup.size_hint = (0.4, 0.3)

        Clock.schedule_once(_do_work, 0.5)

    def _show_admin_export_kivy_dialog(self):
        from kivy.uix.filechooser import FileChooserListView
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        from config import FONT_NAME, LABEL_LIGHT
        from kivy.metrics import dp
        import os
        
        content = BoxLayout(orientation='vertical', spacing=10, padding=15)
        content.add_widget(Label(
            text="Выберите папку, куда сохранить Excel-файлы ВСЕХ отделов:",
            color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(16), bold=True,
            size_hint_y=None, height=dp(30)))
            
        filechooser = FileChooserListView(path=os.path.expanduser('~'), dirselect=True)
        content.add_widget(filechooser)
        
        btns = BoxLayout(size_hint_y=None, height=dp(48), spacing=10)
        ok_btn = Button(text="Выгрузить все", background_color=(0.3, 0.7, 0.3, 1), color=(1,1,1,1), font_name=FONT_NAME, font_size=dp(15), bold=True)
        cancel_btn = Button(text="Отмена", color=(1,1,1,1), font_name=FONT_NAME, font_size=dp(15), bold=True)
        btns.add_widget(ok_btn)
        btns.add_widget(cancel_btn)
        content.add_widget(btns)
        
        popup = Popup(title="Выбор папки", content=content, size_hint=(0.9, 0.9),
                      title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
        
        def do_export(*a):
            target_dir = filechooser.path
            if not target_dir or not os.path.isdir(target_dir):
                return
            popup.dismiss()
            self._do_admin_export(target_dir, False)
            
        ok_btn.bind(on_press=do_export)
        cancel_btn.bind(on_press=popup.dismiss)
        popup.open()
        
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
        bind_enter_key(popup, popup.dismiss)
        popup.open()