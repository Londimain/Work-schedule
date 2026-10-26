# main.py
# -*- coding: utf-8 -*-
"""Точка входа приложения «Табель учёта рабочего времени»."""
import os
# Указываем Kivy использовать ANGLE
os.environ['KIVY_GL_BACKEND'] = 'angle_sdl2'
# Указываем ANGLE использовать DirectX 9 (спасает на Windows 7 / VirtualBox)
os.environ['ANGLE_DEFAULT_PLATFORM'] = 'd3d9' 

import sys
# ... (остальной код без изменений) ...

# Принудительно указываем Kivy, где искать ресурсы при сборке в один файл
if getattr(sys, 'frozen', False):
    os.environ['KIVY_DATA_DIR'] = os.path.join(sys._MEIPASS, 'kivy', 'data')
    
    from kivy.resources import resource_add_path
    resource_add_path(sys._MEIPASS)
    resource_add_path(os.path.join(sys._MEIPASS, 'kivy'))
    resource_add_path(os.path.join(sys._MEIPASS, 'kivy', 'data'))
        
# --- Защита логов для .exe в режиме --windowed ---
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

# --- Пути PyInstaller (если используется) ---
if getattr(sys, 'frozen', False):
    _meipass = getattr(sys, '_MEIPASS', None)
    if _meipass and os.path.isdir(_meipass):
        while _meipass in sys.path:
            sys.path.remove(_meipass)
        sys.path.insert(0, _meipass)

import config  # Настройка Kivy и шрифтов
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
                    FONT_NAME, LABEL_LIGHT, APP_VERSION, DEFAULT_DIRECTOR)
import data_utils
from data_utils import load_data, save_data

from tab_employees import EmployeesTab
from tab_timesheet import TimesheetTab
from tab_report import ReportTab
from tab_about import AboutTab

# Размеры шапки
TOPBAR_H    = dp(52)     # общая высота шапки
EXIT_BTN_W  = dp(120)    # ширина кнопки «Выход»
EXIT_BTN_H  = dp(40)     # высота кнопки «Выход»
THEME_BTN_W = dp(100)    # ширина кнопки «Тема»


class TabelApp(App):
    title = "Табель учёта рабочего времени"
    _dir_save_ev = None

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

    def show_theme_dialog(self):
        from config import THEME_LABELS, CURRENT_THEME
        current = CURRENT_THEME

        # Создаем контейнер для кнопок. 
        # size_hint_y=None и привязка minimum_height заставят контейнер 
        # сжаться до высоты самих кнопок.
        content = BoxLayout(
            orientation='vertical', 
            spacing=dp(10), 
            padding=dp(15), 
            size_hint=(1, None) 
        )
        content.bind(minimum_height=content.setter('height'))
        
        theme_buttons = {}

        for key, label in THEME_LABELS.items():
            mark = '● ' if key == current else '   '
            
            # Подсвечиваем текущую тему зеленым, остальные - синим
            btn_bg = (0.2, 0.6, 0.3, 1) if key == current else (0.25, 0.35, 0.55, 1)
            
            btn = Button(
                text=mark + label,
                size_hint_y=None, height=dp(44),
                font_name=FONT_NAME, font_size=dp(15),
                bold=(key == current),
                color=(1, 1, 1, 1),
                background_normal='', 
                background_down='',
                background_color=btn_bg,
            )
            theme_buttons[key] = btn
            content.add_widget(btn)

        # Кнопка "Отмена" (красная)
        close_btn = Button(
            text="Отмена", 
            size_hint_y=None, height=dp(44),
            color=(1, 1, 1, 1), 
            font_name=FONT_NAME, font_size=dp(16), bold=True,
            background_normal='', 
            background_down='',
            background_color=(0.75, 0.25, 0.25, 1) 
        )
        content.add_widget(close_btn)

        # Создаем Popup без автоматического растягивания
        popup = Popup(
            title="Тема оформления", 
            content=content,
            size_hint=(None, None), # Отключаем проценты
            width=dp(340),          # Фиксированная ширина
            title_color=LABEL_LIGHT, 
            title_font=FONT_NAME,
            auto_dismiss=False, 
            separator_height=0
        )

        # Динамически высчитываем высоту окна: высота кнопок + высота заголовка
        def update_popup_height(*args):
            # dp(80) — это примерная высота заголовка окна + отступы
            popup.height = content.height + dp(80)
            
        content.bind(minimum_height=update_popup_height)
        Clock.schedule_once(update_popup_height, 0)

        # Обработчики нажатий
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
        # 1. Сохраняем тему в локальный файл
        try:
            data_utils.set_theme(theme_name)
        except Exception as e:
            print("Не удалось сохранить тему:", e)
            return

        # 2. Применяем тему (меняем переменные цветов в config)
        config.apply_theme(theme_name)

        # 3. Сохраняем данные перед пересозданием интерфейса
        try:
            self.ts_tab._save_for_key(self.ts_tab._get_key())
            save_data(self.data)
        except Exception:
            pass

        # 4. Создаем окно загрузки с идеальным центрированием
        loading_layout = AnchorLayout(anchor_x='center', anchor_y='center')
        loading_label = Label(
            text="Применение темы...", 
            color=LABEL_LIGHT, 
            halign='center', 
            valign='middle',
            font_name=FONT_NAME,
            font_size=dp(15)
        )
        # Привязываем размер текста к размеру лейбла для центрирования
        loading_label.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        loading_layout.add_widget(loading_label)

        loading_popup = Popup(
            title="",
            content=loading_layout,
            size_hint=(0.3, 0.15),
            title_color=LABEL_LIGHT,
            title_font=FONT_NAME,
            auto_dismiss=False,
            separator_height=0
        )
        loading_popup.open()

        # 5. Пересоздаем интерфейс с задержкой
        def _do_rebuild(dt):
            self._rebuild_ui()
            loading_popup.dismiss()
            
            # Окно успеха тоже центрируем через AnchorLayout
            success_layout = AnchorLayout(anchor_x='center', anchor_y='center')
            label_text = THEME_LABELS.get(theme_name, theme_name)
            success_label = Label(
                text=f"Тема «{label_text}» применена!", 
                color=LABEL_LIGHT,
                halign='center',
                valign='middle',
                font_name=FONT_NAME,
                font_size=dp(15)
            )
            success_label.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
            success_layout.add_widget(success_label)

            success_popup = Popup(
                title="Тема", 
                content=success_layout,
                size_hint=(0.4, 0.2), 
                title_color=LABEL_LIGHT, 
                title_font=FONT_NAME,
                auto_dismiss=False
            )
            Clock.schedule_once(lambda dt: success_popup.dismiss(), 1.5)
            success_popup.open()

        # Задержка 0.1 секунды дает Kivy время отрисовать окно "Применение темы..."
        Clock.schedule_once(_do_rebuild, 0.1)

    def _rebuild_ui(self):
        """Пересоздает весь интерфейс без перезапуска программы."""
        # Запоминаем текущее состояние (вкладку, месяц, год)
        current_idx = 0
        if hasattr(self, 'root_tabs') and self.root_tabs and self.root_tabs.current_tab:
            try:
                current_idx = self.root_tabs.tab_list.index(self.root_tabs.current_tab)
            except ValueError:
                pass
                
        m_text = "Октябрь"
        y_text = "2026"
        if hasattr(self, 'ts_tab'):
            m_text = self.ts_tab.month_spinner.text
            y_text = self.ts_tab.year_spinner.text
            self.ts_tab.cleanup() # Отвязываем горячие клавиши

        if getattr(self, '_update_event', None):
            self._update_event.cancel()

        # Очищаем корневой виджет и обновляем фон окна
        self.root.clear_widgets()
        Window.clearcolor = config.WINDOW_BG

        # --- СОЗДАНИЕ ИНТЕРФЕЙСА ---
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

        base_title = "Табель учёта рабочего времени"
        title_lbl = Label(text=base_title,
                          halign='center', valign='middle',
                          font_name=FONT_NAME, font_size=dp(17), bold=True,
                          color=LABEL_LIGHT,
                          size_hint_x=1)
        title_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        top_bar.add_widget(title_lbl)

        right_box = BoxLayout(size_hint_x=None, width=total_right_w, spacing=dp(6))
        
        theme_btn = Button(text="Тема", size_hint_x=None, width=THEME_BTN_W,
                           font_name=FONT_NAME, font_size=dp(15), bold=True,
                           background_color=config.EXIT_BG, background_normal='',
                           color=(1, 1, 1, 1))
        theme_btn.bind(on_press=lambda *a: self.show_theme_dialog())
        right_box.add_widget(theme_btn)

        exit_btn = Button(text="Выход", size_hint_x=None, width=EXIT_BTN_W,
                          font_name=FONT_NAME, font_size=dp(16), bold=True,
                          background_color=config.EXIT_BG, background_normal='',
                          color=(1, 1, 1, 1))
        exit_btn.bind(on_press=lambda *a: self.confirm_exit())
        right_box.add_widget(exit_btn)

        top_bar.add_widget(right_box)

        self.root_tabs = TabbedPanel(do_default_tab=False)
        self.root_tabs.tab_width = dp(230)

        emp_tab = TabbedPanelItem(text="Рабочий персонал", color=config.TABLE_FG)
        self.emp_tab = EmployeesTab(self)
        emp_tab.add_widget(self.emp_tab)
        self.root_tabs.add_widget(emp_tab)

        ts_tab = TabbedPanelItem(text="Табель", color=config.TABLE_FG)
        self.ts_tab = TimesheetTab(self)
        ts_tab.add_widget(self.ts_tab)
        self.root_tabs.add_widget(ts_tab)

        rep_tab = TabbedPanelItem(text="Отчёт и печать", color=config.TABLE_FG)
        self.rep_tab = ReportTab(self)
        rep_tab.add_widget(self.rep_tab)
        self.root_tabs.add_widget(rep_tab)

        about_tab = TabbedPanelItem(text="О программе", color=config.TABLE_FG)
        self.about_tab = AboutTab(self)
        about_tab.add_widget(self.about_tab)
        self.root_tabs.add_widget(about_tab)

        def on_tab_switch(instance, current_tab):
            if current_tab is None:
                return
            if current_tab.text == "Табель":
                # Загружаем таблицу ТОЛЬКО когда пользователь зашел на вкладку
                if not self.ts_tab.day_inputs:
                    self.ts_tab.load_timesheet()
            elif current_tab.text == "Рабочий персонал":
                self.emp_tab.refresh()
            elif current_tab.text == "Отчёт и печать":
                self.rep_tab.update_preview()

        self.root_tabs.bind(current_tab=on_tab_switch)

        director_box = BoxLayout(orientation='horizontal',
                                  size_hint=(None, None),
                                  size=(dp(360), dp(38)),
                                  spacing=8, padding=(10, 0, 10, 0))
        with director_box.canvas.before:
            self._db_color = Color(*config.TOPBAR_BG)
            self._db_rect = Rectangle(pos=director_box.pos, size=director_box.size)
        director_box.bind(pos=lambda i, v: setattr(self._db_rect, 'pos', v),
                          size=lambda i, v: setattr(self._db_rect, 'size', v))

        dir_lbl_holder = AnchorLayout(anchor_x='right', anchor_y='center', size_hint_x=None, width=dp(80))
        dir_lbl_holder.add_widget(Label(text="Директор:", color=LABEL_LIGHT,
                                         font_name=FONT_NAME, font_size=dp(14),
                                         size_hint=(None, None), size=(dp(80), dp(20)),
                                         halign='right', valign='middle', text_size=(dp(80), dp(20))))
        director_box.add_widget(dir_lbl_holder)

        dir_field_holder = AnchorLayout(anchor_x='left', anchor_y='center', size_hint=(None, 1), width=dp(270))
        director_wrap = TextInput(
            text=self.data.get('director_name', DEFAULT_DIRECTOR),
            multiline=False, font_size=dp(14), font_name=FONT_NAME,
            foreground_color=(0.05, 0.05, 0.05, 1), background_color=(1, 1, 1, 1),
            cursor_color=(0.10, 0.30, 0.70, 1), cursor_width=dp(2),
            selection_color=(0.20, 0.45, 0.90, 0.40), padding=[dp(8), dp(6), dp(8), dp(6)],
            size_hint=(None, None), size=(dp(270), dp(30)),
        )
        director_wrap.bind(text=self._on_director_change)
        dir_field_holder.add_widget(director_wrap)
        director_box.add_widget(dir_field_holder)

        self.director_wrap = director_wrap

        tabs_wrapper = FloatLayout()
        tabs_wrapper.add_widget(self.root_tabs)
        tabs_wrapper.add_widget(director_box)

        def _place_director(*_):
            try:
                strip_h = self.root_tabs._tab_strip.height
            except Exception:
                strip_h = dp(40)
            director_box.right = tabs_wrapper.right - dp(8)
            director_box.center_y = tabs_wrapper.top - strip_h / 2.0

        tabs_wrapper.bind(pos=_place_director, size=_place_director)
        Clock.schedule_once(_place_director, 0)
        Clock.schedule_once(_place_director, 0.2)

        def _update_director_visibility(*_):
            try:
                cur = self.root_tabs.current_tab
                show = cur is not None and cur.text == "Рабочий персонал"
            except Exception:
                show = False
            director_box.opacity = 1 if show else 0
            director_box.disabled = not show

        self.root_tabs.bind(current_tab=_update_director_visibility)
        Clock.schedule_once(_update_director_visibility, 0.05)

        self.root.add_widget(top_bar)
        self.root.add_widget(tabs_wrapper)

        # Восстанавливаем сохраненное состояние
        self.ts_tab.month_spinner.text = m_text
        self.ts_tab.year_spinner.text = y_text
        # self.ts_tab.load_timesheet()
        
        if current_idx < len(self.root_tabs.tab_list):
            self.root_tabs.switch_to(self.root_tabs.tab_list[current_idx])
            
        self._update_event = Clock.schedule_interval(self._check_external_updates, 3.0)

    def build(self):
        base_title = "Табель учёта рабочего времени"
        self.title = decorate_title(f"{base_title} v{APP_VERSION}")
        
        try:
            Window.set_title(self.title)
            Window.clearcolor = config.WINDOW_BG
        except Exception:
            pass

        for delay in (0.3, 0.8, 1.5):
            Clock.schedule_once(lambda dt: apply_app_icon(self.title), delay)

        def _maximize_window(dt=0):
            try:
                Window.maximize()
            except Exception:
                pass
            if platform.system() == 'Windows':
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    hwnd = user32.FindWindowW(None, self.title)
                    if hwnd:
                        user32.ShowWindow(hwnd, 3) # 3 = SW_MAXIMIZE
                except Exception:
                    pass

        for t in (0, 0.15, 0.4, 1.0):
            Clock.schedule_once(_maximize_window, t)

        self.data = load_data()
        try:
            data_utils.set_last_mtime(os.path.getmtime(DATA_FILE))
        except Exception:
            data_utils.set_last_mtime(0.0)

        self.root = BoxLayout(orientation='vertical')
        self._rebuild_ui()
        
        return self.root

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
            try:
                self.ts_tab._save_for_key(self.ts_tab._get_key())
            except Exception:
                pass
            try:
                save_data(self.data)
            except Exception:
                pass
            popup.dismiss()
            Clock.schedule_once(lambda *_: App.get_running_app().stop(), 0.1)

        yes.bind(on_press=do_exit)
        no.bind(on_press=popup.dismiss)
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