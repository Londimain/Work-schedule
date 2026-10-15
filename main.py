# main.py
# -*- coding: utf-8 -*-
"""Точка входа приложения «Табель учёта рабочего времени».

Запуск:
    python main.py

Структура проекта:
    config.py         — настройка Kivy, шрифт, константы, иконка
    data_utils.py     — загрузка/сохранение данных, пересчёт итогов
    ui_helpers.py     — границы, измерения, синхронный скролл
    ui_widgets.py     — кастомные виджеты
    tab_employees.py  — вкладка «Рабочий персонал»
    tab_timesheet.py  — вкладка «Табель»
    tab_report.py     — вкладка «Отчёт и печать» (в т.ч. Excel)
    tab_about.py      — вкладка «О программе»
    ico/tabel.ico     — иконка (необязательно)
"""
import config  # noqa: F401 — ВАЖНО: настройка Kivy + шрифт
# main.py
# -*- coding: utf-8 -*-
"""Точка входа приложения «Табель учёта рабочего времени»."""
import sys
import os

# --- ВАЖНО для .exe в режиме --windowed:
# PyInstaller подменяет sys.stdout/sys.stderr на None, и Kivy может
# молча терять специальные клавиши (Tab, стрелки). Подменяем на devnull.
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

# --- ВАЖНО для собранного .exe: вернуть _MEIPASS в начало sys.path ---
if getattr(sys, 'frozen', False):
    _meipass = getattr(sys, '_MEIPASS', None)
    if _meipass and os.path.isdir(_meipass):
        while _meipass in sys.path:
            sys.path.remove(_meipass)
        sys.path.insert(0, _meipass)

import config  # noqa: F401 — настройка Kivy + шрифт
import platform

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.widget import Widget

from config import (DATA_FILE, decorate_title, apply_app_icon,
                    FONT_NAME, LABEL_LIGHT)
import data_utils
from data_utils import load_data, save_data

from tab_employees import EmployeesTab
from tab_timesheet import TimesheetTab
from tab_report import ReportTab
from tab_about import AboutTab
from kivy.uix.floatlayout import FloatLayout

from config import (DATA_FILE, decorate_title, apply_app_icon,
                    FONT_NAME, LABEL_LIGHT, DEFAULT_DIRECTOR)
from ui_widgets import CenteredField

# Цвета верхней панели
TOPBAR_BG = (0.11, 0.12, 0.15, 1)
EXIT_BG = (0.20, 0.30, 0.55, 1)

# Размеры шапки
TOPBAR_H    = dp(52)     # общая высота шапки
EXIT_BTN_W  = dp(150)    # ширина кнопки «Выход»
EXIT_BTN_H  = dp(40)     # высота кнопки «Выход»

class TabelApp(App):
    title = "Табель учёта рабочего времени"
    _dir_save_ev = None      # <— таймер автосохранения ФИО директора

    def on_start(self):
        """Форсируем фокус окна — иначе в .exe клавиатура
        может не дойти до TextInput до первого клика."""
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
        
    def build(self):
        # ---- Заголовок: если иконки нет — добавим эмодзи ----
        self.title = decorate_title(self.title)
        try:
            Window.set_title(self.title)
        except Exception:
            pass

        # ---- Иконка окна и панели задач ----
        # Вызываем несколько раз с задержкой: Kivy создаёт окно
        # асинхронно, к моменту build() его HWND может ещё не
        # существовать, а WinAPI не найдёт окно по заголовку.
        for delay in (0.3, 0.8, 1.5):
            Clock.schedule_once(
                lambda dt: apply_app_icon(self.title), delay)

        # ---------------- Разворот окна на весь экран ----------------
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

        # ---------------- Данные ----------------
        self.data = load_data()
        try:
            data_utils.set_last_mtime(os.path.getmtime(DATA_FILE))
        except Exception:
            data_utils.set_last_mtime(0.0)

        # ---------------- Верхняя панель (шапка) ----------------
        top_bar = BoxLayout(orientation='horizontal',
                            size_hint_y=None, height=TOPBAR_H,
                            spacing=6, padding=(10, 6, 10, 6))
        with top_bar.canvas.before:
            Color(*TOPBAR_BG)
            _bar_rect = Rectangle(pos=top_bar.pos, size=top_bar.size)
        top_bar.bind(pos=lambda i, v, r=_bar_rect: setattr(r, 'pos', v),
                     size=lambda i, v, r=_bar_rect: setattr(r, 'size', v))

        # Левая «распорка» — компенсирует ширину кнопки «Выход» справа,
        # чтобы заголовок оказался строго по центру окна.
        left_spacer = Widget(size_hint_x=None, width=EXIT_BTN_W)
        top_bar.add_widget(left_spacer)

        # Заголовок по центру
        title_lbl = Label(text=self.title,
                          halign='center', valign='middle',
                          font_name=FONT_NAME, font_size=dp(17), bold=True,
                          color=LABEL_LIGHT,
                          size_hint_x=1)
        title_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        top_bar.add_widget(title_lbl)

        # Кнопка «Выход» — теперь на всю высоту шапки
        exit_btn = Button(text="Выход",
                          size_hint=(None, 1),
                          width=EXIT_BTN_W,
                          font_name=FONT_NAME, font_size=dp(16), bold=True,
                          background_color=EXIT_BG,
                          background_normal='',
                          color=(1, 1, 1, 1))
        exit_btn.bind(on_press=lambda *a: self.confirm_exit())
        top_bar.add_widget(exit_btn)

        # ---------------- Вкладки ----------------
        root_tabs = TabbedPanel(do_default_tab=False)
        root_tabs.tab_width = dp(230)

        emp_tab = TabbedPanelItem(text="Рабочий персонал")
        self.emp_tab = EmployeesTab(self)
        emp_tab.add_widget(self.emp_tab)
        root_tabs.add_widget(emp_tab)

        ts_tab = TabbedPanelItem(text="Табель")
        self.ts_tab = TimesheetTab(self)
        ts_tab.add_widget(self.ts_tab)
        root_tabs.add_widget(ts_tab)

        rep_tab = TabbedPanelItem(text="Отчёт и печать")
        self.rep_tab = ReportTab(self)
        rep_tab.add_widget(self.rep_tab)
        root_tabs.add_widget(rep_tab)

        about_tab = TabbedPanelItem(text="О программе")
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

        # -------- Поле «Директор» — поверх строки вкладок справа --------
        director_box = BoxLayout(orientation='horizontal',
                                  size_hint=(None, None),
                                  size=(dp(360), dp(38)),
                                  spacing=8)

        # Метку «Директор:» оборачиваем в AnchorLayout —
        # тогда её текст всегда стоит ровно по центру высоты бокса,
        # независимо от размера поля справа.
        dir_lbl_holder = AnchorLayout(anchor_x='right', anchor_y='center',
                                       size_hint_x=None, width=dp(80))
        dir_lbl_holder.add_widget(Label(
            text="Директор:", color=LABEL_LIGHT,
            font_name=FONT_NAME, font_size=dp(14),
            size_hint=(None, None), size=(dp(80), dp(20)),
            halign='right', valign='middle',
            text_size=(dp(80), dp(20))))
        director_box.add_widget(dir_lbl_holder)

        # Поле тоже оборачиваем в AnchorLayout(center) —
        # чтобы его 30-пиксельная высота вставала по центру строки 38 px.
        dir_field_holder = AnchorLayout(anchor_x='left', anchor_y='center',
                                         size_hint=(None, 1),
                                         width=dp(270))
        director_wrap = CenteredField(
            text=self.data.get('director_name', DEFAULT_DIRECTOR),
            font_size=dp(14), pad_lr=dp(8), halign='left',
        )
        director_wrap.size_hint = (None, None)
        director_wrap.size = (dp(270), dp(30))
        director_wrap.input.bind(text=self._on_director_change)
        dir_field_holder.add_widget(director_wrap)
        director_box.add_widget(dir_field_holder)

        self.director_wrap = director_wrap

        tabs_wrapper = FloatLayout()
        tabs_wrapper.add_widget(root_tabs)
        tabs_wrapper.add_widget(director_box)

        def _place_director(*_):
            try:
                strip_h = root_tabs._tab_strip.height
            except Exception:
                strip_h = dp(40)
            director_box.right = tabs_wrapper.right - dp(8)
            director_box.center_y = tabs_wrapper.top - strip_h / 2.0

        tabs_wrapper.bind(pos=_place_director, size=_place_director)
        Clock.schedule_once(_place_director, 0)
        Clock.schedule_once(_place_director, 0.2)
        Clock.schedule_once(_place_director, 0.6)
    
        # -------- Показываем поле «Директор» только на вкладке
        #          «Рабочий персонал», на остальных — прячем --------
        def _update_director_visibility(*_):
            try:
                cur = root_tabs.current_tab
                show = cur is not None and cur.text == "Рабочий персонал"
            except Exception:
                show = False
            director_box.opacity = 1 if show else 0
            director_box.disabled = not show

        root_tabs.bind(current_tab=_update_director_visibility)
        Clock.schedule_once(_update_director_visibility, 0.05)
        Clock.schedule_once(_update_director_visibility, 0.3)
        Clock.schedule_once(_update_director_visibility, 0.6)

        # ---------------- Итоговая сборка ----------------
        root = BoxLayout(orientation='vertical')
        root.add_widget(top_bar)
        root.add_widget(tabs_wrapper)
        return root

    # ------------------------------------------------------------------
    def confirm_exit(self):
        """Диалог подтверждения выхода с автосохранением."""
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(
            text="Выйти из программы?\nВсе данные будут сохранены.",
            color=LABEL_LIGHT, halign='center',
            font_name=FONT_NAME, font_size=dp(15),
            outline_color=(0, 0, 0, 1), outline_width=1))
        btns = BoxLayout(size_hint_y=None, height=dp(40), spacing=10)
        yes = Button(text="Да, выйти",
                     background_color=EXIT_BG, color=(1, 1, 1, 1),
                     font_name=FONT_NAME, font_size=dp(16), bold=True)
        no = Button(text="Отмена", color=(1, 1, 1, 1),
                    font_name=FONT_NAME, font_size=dp(16), bold=True)
        btns.add_widget(yes)
        btns.add_widget(no)
        content.add_widget(btns)
        popup = Popup(title="Выход", content=content,
                      size_hint=(0.42, 0.32),
                      title_color=LABEL_LIGHT, title_font=FONT_NAME)

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

    # ------------------------------------------------------------------
    def _check_external_updates(self, dt):
        try:
            mt = os.path.getmtime(DATA_FILE)
        except Exception:
            return
        if mt <= data_utils.get_last_mtime() + 0.001:
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
            self.ts_tab.load_timesheet()
        except Exception:
            pass
        try:
            self.rep_tab.update_preview()
        except Exception:
            pass


if __name__ == '__main__':
    TabelApp().run()