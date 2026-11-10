# main.py
# -*- coding: utf-8 -*-
"""Точка входа приложения «Табель учёта рабочего времени»."""
import os
os.environ['KIVY_GL_BACKEND'] = 'angle_sdl2'
import sys
import ctypes
import json

# --- ЗАЩИТА ОТ ПОВТОРНОГО ЗАПУСКА EXE ---
if getattr(sys, 'frozen', False) and sys.platform == 'win32':
    try:
        mutex_name = "TabelAppMutex_1_1_7"
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        if ctypes.windll.kernel32.GetLastError() == 183: 
            ctypes.windll.user32.MessageBoxW(0, "Программа уже запущена.\nПереключитесь на открытое окно.", "Внимание", 0x40)
            sys.exit(0)
    except Exception: pass

if sys.platform == 'win32':
    try:
        myappid = 'londimain.workschedule.tabel.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception: pass

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    os.environ['KIVY_NO_CONSOLELOG'] = '1'

if sys.stdout is None: sys.stdout = open(os.devnull, 'w')
if sys.stderr is None: sys.stderr = open(os.devnull, 'w')

if getattr(sys, 'frozen', False):
    _meipass = getattr(sys, '_MEIPASS', None)
    if _meipass and os.path.isdir(_meipass):
        while _meipass in sys.path: sys.path.remove(_meipass)
        sys.path.insert(0, _meipass)

import config
import platform
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from ui_widgets import HoverButton as Button

from config import (DATA_FILE, decorate_title, apply_app_icon, FONT_NAME, LABEL_LIGHT, APP_VERSION, LOCAL_FILE)
import data_utils
from data_utils import load_data, save_data

from tab_employees import EmployeesTab
from tab_timesheet import TimesheetTab
from tab_report import ReportTab
from tab_about import AboutTab
from ui_helpers import bind_enter_key
from ui_widgets import HoverButton
from updater import check_for_updates

TOPBAR_H    = dp(52)
EXIT_BTN_W  = dp(100)
THEME_BTN_W = dp(100)
SETTINGS_BTN_W = dp(120)

class TabelApp(App):
    title = "Табель учёта рабочего времени"

    def on_start(self):
        try:
            Window.focus = True
            Window.raise_window()
        except Exception: pass
        check_for_updates(self)
        self.update_connection_status()

    def update_connection_status(self):
        """Проверяет связь и обновляет индикатор."""
        is_connected = data_utils.test_db_connection()
        is_network = bool(config.NETWORK_DATA_FILE)
        mode_str = "сетевая" if is_network else "локальная"
        
        if is_connected:
            self.db_status_lbl.text = f"[color=00ff00]●[/color] База доступна ({mode_str})"
        else:
            self.db_status_lbl.text = f"[color=ff0000]●[/color] Нет связи ({mode_str})"
        Clock.schedule_once(lambda dt: self.update_connection_status(), 5.0)

    def _show_save_error(self, error_msg):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(
            text=f"ОШИБКА СОХРАНЕНИЯ!\n\n{error_msg}\n\nДанные не сохранены на диск.",
            color=(1, 0.4, 0.4, 1), halign='center', valign='middle',
            font_name=FONT_NAME, font_size=dp(15)))
        btn = Button(text="OK", size_hint_y=None, height=dp(40),
                     background_color=(0.8, 0.2, 0.2, 1), color=(1, 1, 1, 1),
                     font_name=FONT_NAME, bold=True)
        content.add_widget(btn)
        p = Popup(title="Ошибка БД", content=content, size_hint=(0.5, 0.4),
                  title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
        btn.bind(on_press=p.dismiss)
        p.open()

    def show_settings_dialog(self):
        """Диалог настройки сетевого пути"""
        try:
            with open(LOCAL_FILE, 'r', encoding='utf-8') as f:
                local_data = json.load(f)
        except Exception:
            local_data = {}
        current_path = local_data.get('network_data_path', '')

        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        content.add_widget(Widget(size_hint_y=1)) 
        
        content.add_widget(Label(
            text="Путь к общей базе данных (сетевой диск):\n"
                 "Оставьте пустым, чтобы использовать локальную базу.",
            color=LABEL_LIGHT, halign='center', valign='middle',
            font_name=FONT_NAME, font_size=dp(15), size_hint_y=None, height=dp(60)
        ))
        
        # --- БЛОК ВЫБОРА ПУТИ С КНОПКОЙ "ОБЗОР" ---
        path_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=10)
        
        path_input = TextInput(
            text=current_path, multiline=False, 
            font_size=dp(15), font_name=FONT_NAME,
            foreground_color=(0.05, 0.05, 0.05, 1),
            background_color=(1, 1, 1, 1),
            padding=[dp(8), dp(12), dp(8), dp(12)],
            hint_text=r"\\Desktop-0sja6qs\soft\Tabel\tabel_data.json"
        )
        path_row.add_widget(path_input)
        
        browse_btn = HoverButton(
            text="Обзор...", 
            size_hint=(None, 1), width=dp(100),
            background_color=(0.4, 0.5, 0.7, 1), color=(1,1,1,1),
            font_name=FONT_NAME
        )
        path_row.add_widget(browse_btn)
        content.add_widget(path_row)
        
        def open_browse(*args):
            try:
                import tkinter as tk
                from tkinter import filedialog
                
                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                
                file_path = filedialog.askopenfilename(
                    title="Выберите файл базы данных",
                    filetypes=[("Файлы базы данных", "*.json"), ("Все файлы", "*.*")]
                )
                root.destroy()
                
                if file_path:
                    # Приводим путь к виду Windows (заменяем слеши)
                    file_path = os.path.normpath(file_path)
                    path_input.text = file_path
            except Exception as e:
                print("Ошибка открытия окна выбора файла:", e)

        browse_btn.bind(on_press=open_browse)
        # ---------------------------------------------
        
        content.add_widget(Widget(size_hint_y=1))

        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=10)
        save_btn = HoverButton(text="Сохранить", background_color=(0.3, 0.7, 0.3, 1), color=(1,1,1,1), font_name=FONT_NAME)
        cancel_btn = HoverButton(text="Отмена", color=(1,1,1,1), font_name=FONT_NAME)
        btns.add_widget(save_btn); btns.add_widget(cancel_btn)
        content.add_widget(btns)

        popup = Popup(title="Настройки базы данных", content=content,
                      size_hint=(0.6, 0.5), title_color=LABEL_LIGHT,
                      title_font=FONT_NAME, auto_dismiss=False)

        def on_save(*a):
            new_path = path_input.text.strip()
            local_data['network_data_path'] = new_path
            try:
                with open(LOCAL_FILE, 'w', encoding='utf-8') as f:
                    json.dump(local_data, f, ensure_ascii=False, indent=2)
                popup.dismiss()
                self._show_restart_info()
            except Exception as e:
                print("Ошибка сохранения настроек:", e)

        save_btn.bind(on_press=on_save)
        cancel_btn.bind(on_press=popup.dismiss)
        bind_enter_key(popup, on_save)
        popup.open()

    def _show_restart_info(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(
            text="Настройки сохранены.\n\n"
                 "Чтобы применить новый путь к базе,\n"
                 "нужно перезапустить программу.",
            color=LABEL_LIGHT, halign='center',
            font_name=FONT_NAME, font_size=dp(15)))
        btn = HoverButton(text="OK", size_hint_y=None, height=dp(40),
                     background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1),
                     font_name=FONT_NAME, bold=True)
        content.add_widget(btn)
        p = Popup(title="Перезапуск", content=content, size_hint=(0.4, 0.3),
                  title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
        
        btn.bind(on_press=p.dismiss)
        # --- ДОБАВЛЕНО: Работает Enter ---
        bind_enter_key(p, p.dismiss) 
        
        p.open()

    def show_theme_dialog(self):
        from config import THEME_LABELS, CURRENT_THEME
        current = CURRENT_THEME

        content = BoxLayout(orientation='vertical', spacing=8, padding=(20, 15, 20, 15))
        content.add_widget(Widget(size_hint_y=1))
        theme_buttons = {}
        for key, label in THEME_LABELS.items():
            is_current = (key == current)
            bg_color = config.ACTIVE_DEPT_BAR_BG if is_current else (0.20, 0.20, 0.24, 1)
            fg_color = config.ACTIVE_DEPT_BAR_FG if is_current else (1, 1, 1, 1)
            btn = HoverButton(text=label, size_hint_y=None, height=dp(44),
                font_name=FONT_NAME, font_size=dp(15), bold=is_current,
                color=fg_color, background_normal='', background_color=bg_color)
            theme_buttons[key] = btn
            content.add_widget(btn)

        content.add_widget(Widget(size_hint_y=None, height=dp(10)))
        close_btn = HoverButton(text="Отмена", size_hint_y=None, height=dp(44),
            color=(1, 1, 1, 1), font_name=FONT_NAME, font_size=dp(16), bold=True,
            background_normal='', background_color=(0.75, 0.25, 0.25, 1))
        content.add_widget(close_btn)
        content.add_widget(Widget(size_hint_y=1))

        popup = Popup(title="Тема оформления", content=content,
                      size_hint=(None, None), size=(dp(350), dp(420)),
                      title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)

        def make_sel(key):
            def _sel(*a):
                popup.dismiss()
                if key != current: self._apply_theme_choice(key)
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
        yes = Button(text="Перезапустить", background_color=config.EXIT_BG,
                     color=(1, 1, 1, 1), font_name=FONT_NAME, font_size=dp(15), bold=True)
        no = Button(text="Позже", color=(1, 1, 1, 1),
                    font_name=FONT_NAME, font_size=dp(15), bold=True)
        btns.add_widget(yes); btns.add_widget(no)
        content.add_widget(btns)

        popup = Popup(title="Перезапуск", content=content,
                      size_hint=(0.46, 0.36), title_color=LABEL_LIGHT,
                      title_font=FONT_NAME, auto_dismiss=False)

        yes.bind(on_press=lambda *a: self._restart_app(popup))
        no.bind(on_press=popup.dismiss)
        bind_enter_key(popup, lambda: self._restart_app(popup))
        popup.open()

    def _restart_app(self, popup=None):
        if popup is not None:
            try: popup.dismiss()
            except Exception: pass
        try:
            self.ts_tab._save_for_key(self.ts_tab._get_key())
        except ConnectionError:
            pass # Игнорируем при перезапуске, если не удалось
        except Exception: pass
        
        try: self.safe_save()
        except Exception: pass

        try:
            import os, sys
            if getattr(sys, 'frozen', False):
                os.startfile(sys.executable)
            else:
                import subprocess
                subprocess.Popen([sys.executable] + sys.argv)
        except Exception as e: print("Ошибка перезапуска:", e)
        try: self.stop()
        except Exception: pass

    def build(self):
        base_title = "Табель учёта рабочего времени"
        self.title = decorate_title(f"{base_title} v{APP_VERSION}")
        
        try:
            Window.set_title(self.title)
            Window.clearcolor = config.WINDOW_BG
            Window.minimum_width = dp(1024)
            Window.minimum_height = dp(700)
        except Exception: pass

        for delay in (0.3, 0.8, 1.5):
            Clock.schedule_once(lambda dt: apply_app_icon(self.title), delay)

        def _maximize_window_kivy(dt=0):
            try: Window.maximize()
            except Exception: pass

        def _maximize_window_win32(dt=0):
            if platform.system() != 'Windows': return
            try:
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = user32.FindWindowW(None, self.title)
                if hwnd:
                    user32.ShowWindow(hwnd, 3) # SW_MAXIMIZE
            except Exception: pass

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

        top_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=TOPBAR_H, spacing=6, padding=(10, 6, 10, 6))
        with top_bar.canvas.before:
            Color(*config.TOPBAR_BG)
            _bar_rect = Rectangle(pos=top_bar.pos, size=top_bar.size)
        top_bar.bind(pos=lambda i, v, r=_bar_rect: setattr(r, 'pos', v),
                     size=lambda i, v, r=_bar_rect: setattr(r, 'size', v))

        # ИНДИКАТОР СВЯЗИ
        self.db_status_lbl = Label(
            text="[color=ffff00]●[/color] Проверка...", markup=True,
            size_hint_x=None, width=dp(200),
            color=(1, 1, 1, 1), font_name=FONT_NAME, font_size=dp(14),
            halign='left', valign='middle')
        self.db_status_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        top_bar.add_widget(self.db_status_lbl)

        top_bar.add_widget(Widget()) # Распорка

        right_box = BoxLayout(size_hint_x=None, width=SETTINGS_BTN_W + THEME_BTN_W + EXIT_BTN_W + dp(12), spacing=dp(6))
                                    
        settings_btn = Button(text="База Данных", size_hint_x=None, width=SETTINGS_BTN_W,
            font_name=FONT_NAME, font_size=dp(15), bold=True, background_color=(0.4, 0.4, 0.4, 1),
            background_normal='', color=(1, 1, 1, 1))
        settings_btn.bind(on_press=lambda *a: self.show_settings_dialog())
        right_box.add_widget(settings_btn)

        theme_btn = Button(text="Тема", size_hint_x=None, width=THEME_BTN_W,
            font_name=FONT_NAME, font_size=dp(15), bold=True, background_color=config.EXIT_BG,
            background_normal='', color=(1, 1, 1, 1))
        theme_btn.bind(on_press=lambda *a: self.show_theme_dialog())
        right_box.add_widget(theme_btn)

        exit_btn = Button(text="Выход", size_hint_x=None, width=EXIT_BTN_W,
            font_name=FONT_NAME, font_size=dp(16), bold=True, background_color=config.EXIT_BG,
            background_normal='', color=(1, 1, 1, 1))
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
            if current_tab is None: return
            if current_tab.text == "Табель": 
                if hasattr(self, 'ts_tab') and self.ts_tab:
                    self.ts_tab.refresh_if_needed()  # <--- ИЗМЕНЕНО: не перестраиваем, если данные те же
            elif current_tab.text == "Рабочий персонал": 
                self.emp_tab.refresh()
            elif current_tab.text == "Отчёт и печать": 
                self.rep_tab.update_preview()

        root_tabs.bind(current_tab=on_tab_switch)
        Clock.schedule_once(lambda *a: root_tabs.switch_to(emp_tab), 0.2)
        Clock.schedule_interval(self._check_external_updates, 3.0)

        root = BoxLayout(orientation='vertical')
        root.add_widget(top_bar)
        root.add_widget(root_tabs)
        return root

    def confirm_exit(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(
            text="Выйти из программы?\nВсе данные будут сохранены.",
            color=LABEL_LIGHT, halign='center',
            font_name=FONT_NAME, font_size=dp(15),
            outline_color=(0, 0, 0, 1), outline_width=1))
        btns = BoxLayout(size_hint_y=None, height=dp(40), spacing=10)
        yes = Button(text="Да, выйти", background_color=config.EXIT_BG, color=(1, 1, 1, 1),
                     font_name=FONT_NAME, font_size=dp(16), bold=True)
        no = Button(text="Отмена", color=(1, 1, 1, 1),
                    font_name=FONT_NAME, font_size=dp(16), bold=True)
        btns.add_widget(yes); btns.add_widget(no)
        content.add_widget(btns)

        popup = Popup(title="Выход", content=content,
                      size_hint=(0.42, 0.32),
                      title_color=LABEL_LIGHT, title_font=FONT_NAME,
                      auto_dismiss=False)

        def do_exit(*a):
            try: popup.dismiss()
            except Exception: pass
            try:
                self.ts_tab._save_for_key(self.ts_tab._get_key())
            except Exception: pass
            try: self.safe_save()
            except Exception: pass
            self.stop()

        yes.bind(on_press=do_exit)
        no.bind(on_press=popup.dismiss)
        bind_enter_key(popup, do_exit)
        popup.open()
        
    def _check_external_updates(self, dt):
        if not data_utils.test_db_connection():
            return # Не проверяем обновления, если нет связи

        from kivy.core.window import Window
        from kivy.uix.popup import Popup
        
        for child in Window.children:
            if isinstance(child, Popup) and getattr(child, 'opacity', 1) > 0:
                return

        try: mt = os.path.getmtime(DATA_FILE)
        except Exception: return
        if mt <= data_utils.get_last_mtime() + 0.5: return

        try: self.ts_tab._flush_pending_save()
        except Exception: pass

        try:
            new_data = load_data()
            need_full_reload = True
            key = self.ts_tab._get_key()
            dept = self.ts_tab._get_active_dept()

            def _collect_ts_info(data_dict):
                info = []
                for emp in data_dict.get('employees', []):
                    if emp.get('show_in_timesheet', False):
                        info.append((emp['id'], emp.get('name', ''), emp.get('position', '')))
                month_dict = data_dict.get('extra_employees', {}).get(key, {})
                if isinstance(month_dict, dict):
                    for e in month_dict.get(dept, []):
                        info.append((e['id'], e.get('name', ''), e.get('position', '')))
                return info

            old_info = _collect_ts_info(self.data)
            new_info = _collect_ts_info(new_data)
            need_full_reload = (old_info != new_info)

            self.data.clear()
            self.data.update(new_data)

            if need_full_reload:
                if not self.ts_tab.has_focused_cell() and not self.ts_tab._dirty_cells:
                    self.ts_tab.load_timesheet()
            else:
                self.ts_tab._apply_external_data(new_data)
                
            data_utils.set_last_mtime(os.path.getmtime(DATA_FILE))
        except Exception:
            pass

        try:
            self.emp_tab.refresh()
            self.emp_tab.update_open_popups()
        except Exception: pass
        try:
            self.ts_tab.update_open_popups()
        except Exception: pass
        try:
            self.rep_tab.update_open_popups()
            self.rep_tab.update_preview()
        except Exception: pass
        
    def safe_save(self, data=None):
        try:
            if data is None:
                data = self.data
            save_data(data)
            return True
        except ConnectionError:
            self._show_save_error("Отсутствует связь с сетевой базой данных. Изменения не сохранены!")
            return False

if __name__ == '__main__':
    TabelApp().run()