# main.py
# -*- coding: utf-8 -*-
"""Точка входа приложения «Табель учёта рабочего времени»."""
import os
os.environ['KIVY_GL_BACKEND'] = 'angle_sdl2'
import sys
import ctypes

if sys.platform == 'win32':
    try:
        myappid = 'londimain.workschedule.tabel.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        print("Не удалось установить AppUserModelID:", e)

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    os.environ['KIVY_NO_CONSOLELOG'] = '1'

if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

if getattr(sys, 'frozen', False):
    _meipass = getattr(sys, '_MEIPASS', None)
    if _meipass and os.path.isdir(_meipass):
        while _meipass in sys.path:
            sys.path.remove(_meipass)
        sys.path.insert(0, _meipass)

import config
import platform

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout

from config import (DATA_FILE, decorate_title, apply_app_icon,
                    FONT_NAME, LABEL_LIGHT, APP_VERSION, 
                    DEFAULT_DIRECTOR, DEFAULT_ORG)
import data_utils
from data_utils import load_data, save_data

from tab_employees import EmployeesTab
from tab_timesheet import TimesheetTab
from tab_report import ReportTab
from tab_about import AboutTab
from ui_helpers import bind_enter_key

TOPBAR_H    = dp(52)
EXIT_BTN_W  = dp(120)
EXIT_BTN_H  = dp(40)
THEME_BTN_W = dp(100)


class TabelApp(App):
    title = "Табель учёта рабочего времени"
    _dir_save_ev = None
    _org_save_ev = None

    def on_start(self):
        try:
            Window.focus = True
            Window.raise_window()
        except Exception:
            pass

    def _on_director_change(self, inst, value):
        self.data['director_name'] = value
        if self._dir_save_ev:
            self._dir_save_ev.cancel()
        self._dir_save_ev = Clock.schedule_once(
            lambda *a: save_data(self.data), 0.5)
        try:
            self.rep_tab.update_preview()
        except Exception:
            pass

    def _on_org_change(self, inst, value):
        self.data['organization'] = value
        if self._org_save_ev:
            self._org_save_ev.cancel()
        self._org_save_ev = Clock.schedule_once(
            lambda *a: save_data(self.data), 0.5)
        try:
            self.rep_tab.update_preview()
        except Exception:
            pass

    def show_theme_dialog(self):
        from config import THEME_LABELS, CURRENT_THEME
        current = CURRENT_THEME

        content = BoxLayout(orientation='vertical', spacing=8, padding=10)
        theme_buttons = {}

        for key, label in THEME_LABELS.items():
            mark = '● ' if key == current else '   '
            btn = Button(
                text=mark + label,
                size_hint_y=None, height=dp(44),
                font_name=FONT_NAME, font_size=dp(15),
                bold=(key == current),
                color=(1, 1, 1, 1),
            )
            theme_buttons[key] = btn
            content.add_widget(btn)

        close_btn = Button(text="Отмена", size_hint_y=None, height=dp(40),
                           color=(1, 1, 1, 1), font_name=FONT_NAME,
                           font_size=dp(16), bold=True)
        content.add_widget(close_btn)

        popup = Popup(title="Тема оформления", content=content,
                      size_hint=(0.42, 0.55),
                      title_color=LABEL_LIGHT, title_font=FONT_NAME,
                      auto_dismiss=False)

        def make_sel(key):
            def _sel(*a):
                popup.dismiss()
                if key != current:
                    self._apply_theme_choice(key)
            return _sel

        for key, btn in theme_buttons.items():
            btn.bind(on_press=make_sel(key))
        close_btn.bind(on_press=popup.dismiss)
        popup.open()

    def _apply_theme_choice(self, theme_name):
        from config import THEME_LABELS
        try:
            data_utils.set_theme(theme_name)
        except Exception as e:
            print("Не удалось сохранить тему:", e)
            return

        label = THEME_LABELS.get(theme_name, theme_name)
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(
            text=(f"Тема «{label}» сохранена.\n\n"
                  "Чтобы она применилась, программу нужно\n"
                  "перезапустить. Перезапустить сейчас?"),
            color=LABEL_LIGHT, halign='center',
            font_name=FONT_NAME, font_size=dp(15),
            outline_color=(0, 0, 0, 1), outline_width=1))
        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=10)
        yes = Button(text="Перезапустить",
                     background_color=config.EXIT_BG,
                     color=(1, 1, 1, 1), font_name=FONT_NAME,
                     font_size=dp(15), bold=True)
        no = Button(text="Позже", color=(1, 1, 1, 1),
                    font_name=FONT_NAME, font_size=dp(15), bold=True)
        btns.add_widget(yes)
        btns.add_widget(no)
        content.add_widget(btns)

        popup = Popup(title="Перезапуск", content=content,
                      size_hint=(0.46, 0.36),
                      title_color=LABEL_LIGHT, title_font=FONT_NAME,
                      auto_dismiss=False)

        yes.bind(on_press=lambda *a: self._restart_app(popup))
        no.bind(on_press=popup.dismiss)
        bind_enter_key(popup, lambda: self._restart_app(popup))
        popup.open()

    def _restart_app(self, popup=None):
        if popup is not None:
            try:
                popup.dismiss()
            except Exception:
                pass
        try:
            self.ts_tab._save_for_key(self.ts_tab._get_key())
        except Exception:
            pass
        try:
            save_data(self.data)
        except Exception:
            pass

        try:
            import os
            import sys
            if getattr(sys, 'frozen', False):
                os.startfile(sys.executable)
            else:
                import subprocess
                subprocess.Popen([sys.executable] + sys.argv)
        except Exception as e:
            print("Ошибка перезапуска:", e)

        try:
            self.stop()
        except Exception:
            pass

    def build(self):
        base_title = "Табель учёта рабочего времени"
        self.title = decorate_title(f"{base_title} v{APP_VERSION}")
        
        try:
            Window.set_title(self.title)
            Window.clearcolor = config.WINDOW_BG
        except Exception:
            pass

        for delay in (0.3, 0.8, 1.5):
            Clock.schedule_once(
                lambda dt: apply_app_icon(self.title), delay)

        def _maximize_window_kivy(dt=0):
            try:
                Window.maximize()
            except Exception:
                pass

        def _maximize_window_win32(dt=0):
            if platform.system() != 'Windows':
                return
            try:
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = user32.FindWindowW(None, self.title)
                if hwnd:
                    SW_MAXIMIZE = 3
                    user32.ShowWindow(hwnd, SW_MAXIMIZE)
            except Exception:
                pass

        def _maximize_window(dt=0):
            _maximize_window_kivy(dt)
            _maximize_window_win32(dt)

        for t in (0, 0.15, 0.4, 1.0):
            Clock.schedule_once(_maximize_window, t)

        self.data = load_data()
        try:
            data_utils.set_last_mtime(os.path.getmtime(DATA_FILE))
        except Exception:
            data_utils.set_last_mtime(0.0)

        top_bar = BoxLayout(orientation='horizontal',
                            size_hint_y=None, height=TOPBAR_H,
                            spacing=6, padding=(10, 6, 10, 6))
        with top_bar.canvas.before:
            Color(*config.TOPBAR_BG)
            _bar_rect = Rectangle(pos=top_bar.pos, size=top_bar.size)
        top_bar.bind(pos=lambda i, v, r=_bar_rect: setattr(r, 'pos', v),
                     size=lambda i, v, r=_bar_rect: setattr(r, 'size', v))

        total_right_w = THEME_BTN_W + EXIT_BTN_W + dp(6)
        left_spacer = Widget(size_hint_x=None, width=total_right_w)
        top_bar.add_widget(left_spacer)

        title_lbl = Label(text=base_title,
                          halign='center', valign='middle',
                          font_name=FONT_NAME, font_size=dp(17), bold=True,
                          color=LABEL_LIGHT,
                          size_hint_x=1)
        title_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        top_bar.add_widget(title_lbl)

        right_box = BoxLayout(size_hint_x=None, width=total_right_w,
                              spacing=dp(6))
        
        theme_btn = Button(text="Тема",
                           size_hint_x=None, width=THEME_BTN_W,
                           font_name=FONT_NAME, font_size=dp(15), bold=True,
                           background_color=config.EXIT_BG,
                           background_normal='',
                           color=(1, 1, 1, 1))
        theme_btn.bind(on_press=lambda *a: self.show_theme_dialog())
        right_box.add_widget(theme_btn)

        exit_btn = Button(text="Выход",
                          size_hint_x=None, width=EXIT_BTN_W,
                          font_name=FONT_NAME, font_size=dp(16), bold=True,
                          background_color=config.EXIT_BG,
                          background_normal='',
                          color=(1, 1, 1, 1))
        exit_btn.bind(on_press=lambda *a: self.confirm_exit())
        right_box.add_widget(exit_btn)

        top_bar.add_widget(right_box)

        root_tabs = TabbedPanel(do_default_tab=False)
        root_tabs.tab_width = dp(230)

        emp_tab = TabbedPanelItem(text="Рабочий персонал", color=config.TABLE_FG)
        self.emp_tab = EmployeesTab(self)
        emp_tab.add_widget(self.emp_tab)
        root_tabs.add_widget(emp_tab)

        ts_tab = TabbedPanelItem(text="Табель", color=config.TABLE_FG)
        self.ts_tab = TimesheetTab(self)
        ts_tab.add_widget(self.ts_tab)
        root_tabs.add_widget(ts_tab)

        rep_tab = TabbedPanelItem(text="Отчёт и печать", color=config.TABLE_FG)
        self.rep_tab = ReportTab(self)
        rep_tab.add_widget(self.rep_tab)
        root_tabs.add_widget(rep_tab)

        about_tab = TabbedPanelItem(text="О программе", color=config.TABLE_FG)
        self.about_tab = AboutTab(self)
        about_tab.add_widget(self.about_tab)
        root_tabs.add_widget(about_tab)

        def on_tab_switch(instance, current_tab):
            if current_tab is None:
                return
            if current_tab.text == "Табель":
                self.ts_tab.load_timesheet()
            elif current_tab.text == "Рабочий персонал":
                self.emp_tab.refresh()
            elif current_tab.text == "Отчёт и печать":
                self.rep_tab.update_preview()
            elif current_tab.text == "О программе":
                pass

        root_tabs.bind(current_tab=on_tab_switch)
        Clock.schedule_once(lambda *a: root_tabs.switch_to(emp_tab), 0.2)
        Clock.schedule_interval(self._check_external_updates, 3.0)

        # ==========================================
        # СОЗДАЕМ ЕДИНЫЙ БЛОК ДЛЯ ДИРЕКТОРА И ОРГАНИЗАЦИИ
        # ==========================================
        fields_box = BoxLayout(orientation='vertical', spacing=4, 
                               size_hint=(None, None), 
                               width=dp(390), height=dp(70))

        # Ряд 1: Директор
        dir_row = BoxLayout(size_hint_y=None, height=dp(32), spacing=8)
        
        dir_lbl_holder = AnchorLayout(anchor_x='right', anchor_y='center',
                                       size_hint_x=None, width=dp(100))
        dir_lbl_holder.add_widget(Label(
            text="Директор:", color=LABEL_LIGHT,
            font_name=FONT_NAME, font_size=dp(14),
            size_hint=(None, None), size=(dp(100), dp(20)),
            halign='right', valign='middle',
            text_size=(dp(100), dp(20))))
        dir_row.add_widget(dir_lbl_holder)

        director_wrap = TextInput(
            text=self.data.get('director_name', DEFAULT_DIRECTOR),
            multiline=False,
            font_size=dp(14), font_name=FONT_NAME,
            foreground_color=(0.05, 0.05, 0.05, 1),
            background_color=(1, 1, 1, 1),
            cursor_color=(0.10, 0.30, 0.70, 1),
            cursor_width=dp(2),
            selection_color=(0.20, 0.45, 0.90, 0.40),
            padding=[dp(8), dp(7), dp(8), dp(7)],
            size_hint=(None, None),
            size=(dp(280), dp(30)),
        )
        director_wrap.bind(text=self._on_director_change)
        dir_row.add_widget(director_wrap)
        fields_box.add_widget(dir_row)

        # Ряд 2: Организация
        org_row = BoxLayout(size_hint_y=None, height=dp(32), spacing=8)
        
        org_lbl_holder = AnchorLayout(anchor_x='right', anchor_y='center',
                                       size_hint_x=None, width=dp(100))
        org_lbl_holder.add_widget(Label(
            text="Организация:", color=LABEL_LIGHT,
            font_name=FONT_NAME, font_size=dp(14),
            size_hint=(None, None), size=(dp(100), dp(20)),
            halign='right', valign='middle',
            text_size=(dp(100), dp(20))))
        org_row.add_widget(org_lbl_holder)

        org_wrap = TextInput(
            text=self.data.get('organization', DEFAULT_ORG),
            multiline=False,
            font_size=dp(14), font_name=FONT_NAME,
            foreground_color=(0.05, 0.05, 0.05, 1),
            background_color=(1, 1, 1, 1),
            cursor_color=(0.10, 0.30, 0.70, 1),
            cursor_width=dp(2),
            selection_color=(0.20, 0.45, 0.90, 0.40),
            padding=[dp(8), dp(7), dp(8), dp(7)],
            size_hint=(None, None),
            size=(dp(280), dp(30)),
        )
        org_wrap.bind(text=self._on_org_change)
        org_row.add_widget(org_wrap)
        fields_box.add_widget(org_row)

        self.director_wrap = director_wrap
        self.org_wrap = org_wrap

        tabs_wrapper = FloatLayout()
        tabs_wrapper.add_widget(root_tabs)
        tabs_wrapper.add_widget(fields_box)

        def _place_director(*_):
            # Привязываем блок полей к верхнему правому углу
            fields_box.right = tabs_wrapper.right - dp(10)
            fields_box.top = tabs_wrapper.top - dp(2)

        tabs_wrapper.bind(pos=_place_director, size=_place_director)
        Clock.schedule_once(_place_director, 0)
        Clock.schedule_once(_place_director, 0.2)
        Clock.schedule_once(_place_director, 0.6)

        def _update_director_visibility(*_):
            try:
                cur = root_tabs.current_tab
                show = cur is not None and cur.text == "Рабочий персонал"
            except Exception:
                show = False
            # Скрываем весь блок при переходе на другие вкладки
            fields_box.opacity = 1 if show else 0
            fields_box.disabled = not show

        root_tabs.bind(current_tab=_update_director_visibility)
        Clock.schedule_once(_update_director_visibility, 0.05)
        Clock.schedule_once(_update_director_visibility, 0.3)
        Clock.schedule_once(_update_director_visibility, 0.6)

        root = BoxLayout(orientation='vertical')
        root.add_widget(top_bar)
        root.add_widget(tabs_wrapper)
        return root

    def confirm_exit(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(
            text="Выйти из программы?\nВсе данные будут сохранены.",
            color=LABEL_LIGHT, halign='center',
            font_name=FONT_NAME, font_size=dp(15),
            outline_color=(0, 0, 0, 1), outline_width=1))
        btns = BoxLayout(size_hint_y=None, height=dp(40), spacing=10)
        yes = Button(text="Да, выйти",
                     background_color=config.EXIT_BG, color=(1, 1, 1, 1),
                     font_name=FONT_NAME, font_size=dp(16), bold=True)
        no = Button(text="Отмена", color=(1, 1, 1, 1),
                    font_name=FONT_NAME, font_size=dp(16), bold=True)
        btns.add_widget(yes)
        btns.add_widget(no)
        content.add_widget(btns)

        popup = Popup(title="Выход", content=content,
                      size_hint=(0.42, 0.32),
                      title_color=LABEL_LIGHT, title_font=FONT_NAME,
                      auto_dismiss=False)

        def do_exit(*a):
            import threading, time, os
            
            # Сохраняем данные и закрываем программу в отдельном потоке
            def _save_and_exit():
                try:
                    self.ts_tab._save_for_key(self.ts_tab._get_key())
                except Exception:
                    pass
                try:
                    save_data(self.data)
                except Exception:
                    pass
                # Даем файлу немного времени на запись и убиваем процесс
                time.sleep(0.2)
                os._exit(0)
                
            # Запускаем поток
            threading.Thread(target=_save_and_exit, daemon=True).start()
            
            # Сразу закрываем попап, чтобы пользователь видел, что программа отреагировала
            try:
                popup.dismiss()
            except Exception:
                pass

        yes.bind(on_press=do_exit)
        no.bind(on_press=popup.dismiss)
        bind_enter_key(popup, do_exit)
        popup.open()

    def _check_external_updates(self, dt):
        try:
            mt = os.path.getmtime(DATA_FILE)
        except Exception:
            return
        if mt <= data_utils.get_last_mtime() + 0.5:
            return
        data_utils.set_last_mtime(mt)
        new_data = load_data()
        self.data.clear()
        self.data.update(new_data)
        try:
            self.emp_tab.refresh()
        except Exception:
            pass

        try:
            editing = self.ts_tab.has_focused_cell()
        except Exception:
            editing = False
        if not editing:
            try:
                self.ts_tab.load_timesheet()
            except Exception:
                pass

        try:
            self.rep_tab.update_preview()
        except Exception:
            pass


if __name__ == '__main__':
    TabelApp().run()