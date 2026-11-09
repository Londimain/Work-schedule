# tab_timesheet.py
# -*- coding: utf-8 -*-
"""Вкладка «Табель»."""
import config  # noqa: F401

from calendar import monthrange
from datetime import datetime, date

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from ui_widgets import HoverButton as Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, Rectangle
from kivy.uix.stencilview import StencilView
from kivy.uix.anchorlayout import AnchorLayout

from config import (FONT_NAME, LABEL_LIGHT, MONTHS, YEARS,
                    SPINNER_BG, SPINNER_FG, RIGHT_COLUMNS,
                    RIGHT_COLUMN_GROUPS,
                    HEADER_BG, HEADER_FG)
from data_utils import (save_data, classify_day, analyze_row,
                        apply_overtime, fmt_hours, calc_norm_hours,
                        set_local_results_hidden, get_local_results_hidden)
from data_storage import (get_visible_right_columns,
                          get_local_visible_columns,
                          set_local_visible_columns,
                          save_cells)
from ui_helpers import (add_bottom_border, add_top_border,
                        add_left_border, add_right_border,
                        vsep, sync_vertical, measure_text_width,
                        measure_text_height, HorizontalScrollView, SmartScrollView,
                        NoOverscrollEffect, bind_enter_key)
from ui_widgets import (VerticalLabel, DayCell, ResultCell, DayHeader,
                        NavTextInput, CenteredSpinner, LightSpinnerOption)

def _stretch_grid(grid, sv):
    """Grid должен быть не меньше ScrollView по высоте,
    иначе Kivy прижимает содержимое к низу окна просмотра."""
    def _sync(*_):
        try:
            h = max(grid.minimum_height, sv.height)
            if abs(grid.height - h) > 0.5:
                grid.height = h
        except Exception:
            pass
    sv.bind(height=_sync)
    Clock.schedule_once(_sync, 0)
    Clock.schedule_once(_sync, 0.1)

class TimesheetTab(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        
        with self.canvas.before:
            Color(*config.TABLE_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda i, v: setattr(self._bg, 'pos', v),
                  size=lambda i, v: setattr(self._bg, 'size', v))

        self.day_inputs = {}
        self.total_labels = {}
        self._last_key = None
        self._loading = False
        self._save_event = None
        self._auto_fit_ev = None
        self._auto_fit_right_ev = None
        self._day_types = []
        self._emp_night = {}
        self._emp_overtime = {}
        self._emp_no_weekends = {} 
        self._emp_holiday = {}
        self._suppress_result_cb = False
        self._employees_order = []
        self._days_sv = None
        self._right_sv = None
        self._days_in_month = 0
        self._sel_anchor = None
        self._sel_current = None
        self._dirty_cells = set()
        self._is_syncing = False
        
        # --- ДЛЯ АВТООБНОВЛЕНИЯ ОКНА ВРЕМЕННЫХ СОТРУДНИКОВ ---
        self.active_extra_popup = None
        self.active_extra_rebuild = None

        # --- ПЕРЕМЕННЫЕ ДЛЯ УПРАВЛЕНИЯ ВИДИМОСТЬЮ ИТОГОВ ---
        self._results_hidden = get_local_results_hidden()
        self.right_sv = None
        self.right_top = None
        self.right_header = None
        self.RIGHT_W = 0
        self._right_cols = list(RIGHT_COLUMNS)
        self.LEFT_W = 0
        self._all_day_headers = []
        self._all_day_rows = []
        self._days_grid = None
        self._dh = None
        self._update_days_header_func = None
        
        # --- ПЕРЕМЕННЫЕ ДЛЯ ДИНАМИЧЕСКОЙ ВЫСОТЫ ТАБЛИЦЫ ---
        self._current_body = None
        self._current_header_top = None
        self._current_header_bottom = None
        self._current_content_h = 0
        # ---------------------------------------------------

        self._shift_held = False
        self._min_right_widths = []       # <--- ДОБАВИТЬ
        self._built_names = {}            # <--- ДОБАВИТЬ
        self._built_positions = {}        # <--- ДОБАВИТЬ
        
        from kivy.core.window import Window
        Window.bind(on_keyboard=self._on_window_keyboard,
                    on_key_down=self._on_win_key_down,
                    on_key_up=self._on_win_key_up)

        self.bind(height=self._on_window_resize)
        self._build()

    def _on_window_resize(self, *args):
        Clock.schedule_once(self._resize_body, 0)

    def _resize_body(self, *args):
        if self._current_body is None or self._current_header_top is None or self._current_header_bottom is None:
            return
        try:
            avail_h = self.height - self.top_bar.height - self.hint_wrap.height - dp(10)
            avail_h -= self._current_header_top.height + self._current_header_bottom.height
            
            target_h = min(avail_h, self._current_content_h)
            if target_h < dp(50):
                target_h = dp(50)
                
            if abs(self._current_body.height - target_h) > 0.5:
                self._current_body.height = target_h
                
            main_h = self._current_header_top.height + self._current_header_bottom.height + target_h
            if abs(self.main_container.height - main_h) > 0.5:
                self.main_container.height = main_h
            
            # Пересчитываем ширину колонок при изменении размера окна
            if getattr(self, '_auto_fit_ev', None):
                self._auto_fit_ev.cancel()
            self._auto_fit_ev = Clock.schedule_once(lambda dt: self._auto_fit_day_columns(), 0.1)
            
            if getattr(self, '_auto_fit_right_ev', None):
                self._auto_fit_right_ev.cancel()
            self._auto_fit_right_ev = Clock.schedule_once(lambda dt: self._auto_fit_right_columns(), 0.1)
            
        except Exception:
            pass

    def _build(self):
        self.top_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), spacing=5, padding=(5, 2, 5, 2))
        
        # --- Левая часть: Период (35% ширины) ---
        left_box = BoxLayout(size_hint_x=0.35, spacing=5)
        left_box.add_widget(Label(text="Месяц:", size_hint_x=None, width=dp(60), color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(14)))
        
        self.month_spinner = Spinner(text=MONTHS[datetime.now().month - 1], values=MONTHS, 
                                     size_hint_x=1, font_name=FONT_NAME, 
                                     background_color=SPINNER_BG, color=SPINNER_FG, 
                                     option_cls=LightSpinnerOption)
        left_box.add_widget(self.month_spinner)
        
        left_box.add_widget(Label(text="Год:", size_hint_x=None, width=dp(40), color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(14)))
        
        self.year_spinner = Spinner(text=str(datetime.now().year), values=YEARS, 
                                    size_hint_x=1, font_name=FONT_NAME, 
                                    background_color=SPINNER_BG, color=SPINNER_FG, 
                                    option_cls=LightSpinnerOption)
        left_box.add_widget(self.year_spinner)
        
        self.top_bar.add_widget(left_box)

        # --- Правая часть: Кнопки (65% ширины) ---
        right_box = BoxLayout(size_hint_x=0.65, spacing=4)
        
        # Вспомогательная функция для создания адаптивных кнопок
        # Вспомогательная функция для создания адаптивных кнопок
        def make_btn(text, hint_x, bg):
            b = Button(
                text=text, 
                size_hint_x=hint_x, 
                font_name=FONT_NAME, 
                font_size=dp(13), 
                bold=True, 
                background_color=bg, 
                color=(1, 1, 1, 1),
                shorten=True, 
                shorten_from='right',
                halign='center',  # <--- Центрируем по горизонтали
                valign='middle'   # <--- Центрируем по вертикали
            )
            # Передаем (ширину с отступом, высоту), чтобы Kivy знал рамки для центрирования
            b.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0] - dp(8), val[1])))
            return b

        apply_btn = make_btn("Применить правки", 1.8, (0.25, 0.55, 0.85, 1))
        apply_btn.bind(on_press=lambda *a: self.apply_overrides())
        right_box.add_widget(apply_btn)

        reset_btn = make_btn("Сбросить правки", 1.8, (0.5, 0.4, 0.75, 1))
        reset_btn.bind(on_press=lambda *a: self.reset_overrides())
        right_box.add_widget(reset_btn)

        self.toggle_btn = make_btn("Показать итоги" if self._results_hidden else "Скрыть итоги", 1.4, 
                                   (0.3, 0.7, 0.3, 1) if self._results_hidden else (0.4, 0.6, 0.8, 1))
        self.toggle_btn.bind(on_press=self.toggle_results)
        right_box.add_widget(self.toggle_btn)

        cols_btn = make_btn("Настроить итоги", 1.8, (0.55, 0.40, 0.75, 1))
        cols_btn.bind(on_press=self.show_columns_popup)
        right_box.add_widget(cols_btn)

        temp_btn = make_btn("Временные сотрудники", 2.2, (0.3, 0.6, 0.4, 1))
        temp_btn.bind(on_press=self.show_manage_extra_popup)
        right_box.add_widget(temp_btn)

        clear_btn = make_btn("Очистить", 1.2, (0.9, 0.55, 0.2, 1))
        clear_btn.bind(on_press=lambda *a: self.confirm_clear())
        right_box.add_widget(clear_btn)

        self.top_bar.add_widget(right_box)
        self.add_widget(self.top_bar)

        # Контейнер для таблицы (не растягиваем на весь экран)
        self.main_container = BoxLayout(orientation='vertical', spacing=0, size_hint_y=None, 
                                        padding=(dp(10), 0, dp(10), 0)) 
        self.add_widget(self.main_container)

        # Распорка, чтобы сдвинуть блоки вниз
        self.add_widget(Widget(size_hint_y=1))

        # --- УСЛОВНЫЕ ОБОЗНАЧЕНИЯ (прижаты к низу) ---
        HINT_BG   = config.TOPBAR_BG
        HINT_FG   = (0.88, 0.90, 0.94, 1)
        HINT_CODE = (1.00, 0.85, 0.35, 1)
        HINT_DASH = (0.40, 0.42, 0.48, 1)

        hint_items = [
            ('В',    '  выходной'),
            ('О',    '  труд. отпуск'),
            ('Б',    '  больничный'),
            ('А',    '  за свой счёт'),
            ('РО',   '  отпуск по родам'),
            ('К',    '  командировка'),
            ('МК',   '  мед. комиссия'),
            ('СР',   '  оплата по среднему'),
            ('Р',    '  ремонт'),
            ('ТО',   '  тех. обслуживание'),
            ('КД',   '  кол. договор'),
            ('Н',    '  прочие неявки'),
            ('ДМ',   '  день матери'),
            ('П',    '  прогул'),
            ('Т',    '  текущий простой'),
            ('Ц',    '  целосменный простой'),
            ('У',    '  опоздание'),
            ('8д',   '  часы без ночных (8 тоже)'),
            ('8//N', '  часы // смена (и /)'),
            ('Tab',  '  стрелки — по ячейкам'),
        ]

        self.hint_wrap = BoxLayout(orientation='vertical',
                              size_hint_y=None,
                              height=dp(96), # Высота для 3-х строк
                              padding=(dp(6), dp(4), dp(6), dp(4)))
        with self.hint_wrap.canvas.before:
            Color(*HINT_BG)
            _hw = Rectangle(pos=self.hint_wrap.pos, size=self.hint_wrap.size)
        self.hint_wrap.bind(pos=lambda i, v, r=_hw: setattr(r, 'pos', v),
                       size=lambda i, v, r=_hw: setattr(r, 'size', v))

        hint_grid = GridLayout(cols=7, size_hint_y=None, height=dp(88),
                               spacing=dp(2))
        for code, desc in hint_items:
            cell = BoxLayout(orientation='horizontal', spacing=dp(4),
                             padding=(dp(6), 0, dp(4), 0))

            code_lbl = Label(
                text=code, bold=True, color=HINT_CODE,
                font_name=FONT_NAME, font_size=dp(13),
                size_hint_x=None, width=dp(42),
                halign='center', valign='middle',
            )
            code_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
            cell.add_widget(code_lbl)

            dash_lbl = Label(
                text='—', color=HINT_DASH,
                font_name=FONT_NAME, font_size=dp(12),
                size_hint_x=None, width=dp(10),
                halign='center', valign='middle',
            )
            cell.add_widget(dash_lbl)

            desc_lbl = Label(
                text=desc, color=HINT_FG,
                font_name=FONT_NAME, font_size=dp(12),
                halign='left', valign='middle',
                shorten=True, shorten_from='right',
            )
            desc_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
            cell.add_widget(desc_lbl)

            hint_grid.add_widget(cell)

        self.hint_wrap.add_widget(hint_grid)
        add_top_border(self.hint_wrap, color=(0, 0, 0, 1), thickness=1)
        self.add_widget(self.hint_wrap)

        self.month_spinner.bind(text=self._on_period_change)
        self.year_spinner.bind(text=self._on_period_change)

        self.bind(width=lambda *a: Clock.schedule_once(
            lambda dt: self._apply_results_visibility(), 0))

        # Откладываем загрузку таблицы, чтобы окно появилось мгновенно
        Clock.schedule_once(lambda dt: self.load_timesheet(), 0.1)

    # =======================================================================
    # МЕТОДЫ ДЛЯ УПРАВЛЕНИЯ ВИДИМОСТЬЮ ИТОГОВ
    # =======================================================================
    def toggle_results(self, *args):
        self._results_hidden = not self._results_hidden
        if self._results_hidden:
            self.toggle_btn.text = "Показать итоги"
            self.toggle_btn.background_color = (0.3, 0.7, 0.3, 1)
        else:
            self.toggle_btn.text = "Скрыть итоги"
            self.toggle_btn.background_color = (0.4, 0.6, 0.8, 1)
            
        set_local_results_hidden(self._results_hidden)
        self._apply_results_visibility()

    def _apply_results_visibility(self):
        hidden = getattr(self, '_results_hidden', False)
        if getattr(self, 'right_sv', None) is None:
            return
            
        w = 0 if hidden else self.RIGHT_W
        
        self.right_sv.width = w
        self.right_sv.opacity = 0 if hidden else 1
        self.right_sv.disabled = hidden
        
        if getattr(self, 'right_top', None) is not None:
            self.right_top.width = w
            self.right_top.opacity = 0 if hidden else 1
            
        if getattr(self, 'right_header', None) is not None:
            self.right_header.width = w
            self.right_header.opacity = 0 if hidden else 1
        
        Clock.schedule_once(lambda dt: self._auto_fit_day_columns(), 0.05)
        Clock.schedule_once(lambda dt: self._auto_fit_right_columns(), 0.05)

    # =======================================================================
    # АВТО-ПОДГОНКА ШИРИНЫ СТОЛБЦОВ
    # =======================================================================
    def _auto_fit_day_columns(self):
        if not getattr(self, 'day_inputs', None) or not getattr(self, '_days_in_month', 0):
            return

        days_in_month = self._days_in_month
        
        avail_w = self._days_sv.width if getattr(self, '_days_sv', None) else 0
        if avail_w <= 0:
            return
            
        base_w = max(dp(36), avail_w / days_in_month)
        new_widths = [base_w] * days_in_month

        for emp_id, cells in self.day_inputs.items():
            for d_idx, cell in enumerate(cells):
                if d_idx >= days_in_month:
                    continue
                txt = cell.input.text.strip()
                if txt:
                    req_w = measure_text_width(txt, font_size=14) + dp(6)
                    if req_w > new_widths[d_idx]:
                        new_widths[d_idx] = req_w

        changed = False
        for i in range(days_in_month):
            if i < len(self._all_day_headers):
                if abs(self._all_day_headers[i].width - new_widths[i]) > 1:
                    changed = True
                    break
        if not changed:
            return

        total_w = 0
        for i in range(days_in_month):
            w = new_widths[i]
            total_w += w
            if i < len(self._all_day_headers):
                self._all_day_headers[i].width = w
            for row in self._all_day_rows:
                if i < len(row.children):
                    child = row.children[-(i + 1)]
                    child.width = w

        self._days_grid.width = total_w
        if self._dh is not None:
            self._dh.width = total_w

        for row in self._all_day_rows:
            row.width = total_w

        if self._update_days_header_func:
            self._update_days_header_func()

        if self._days_grid.width <= self._days_sv.width + 1:
            self._days_sv.scroll_x = 0

    def _auto_fit_right_columns(self):
        if not getattr(self, 'total_labels', None) or not self.total_labels:
            return

        num_cols = len(self._right_cols)
        
        # 1. Начальная минимальная ширина колонки
        new_widths = [max(dp(36), col[2]) for col in self._right_cols]

        # 2. Учитываем вертикальные заголовки
        for i, (label, key_, w) in enumerate(self._right_cols):
            vert_h = measure_text_height(label, 1000, font_size=9)
            req_w = vert_h + dp(16)
            if req_w > new_widths[i]:
                new_widths[i] = req_w

        # 3. Учитываем содержимое ячеек
        for i in range(num_cols):
            cells = (getattr(self, '_right_col_cells', [[]])[i]
                     if hasattr(self, '_right_col_cells') else [])
            for cell in cells:
                txt = cell.input.text.strip()
                if txt:
                    req_w = measure_text_width(txt, font_size=14) + dp(8)
                    if req_w > new_widths[i]:
                        new_widths[i] = req_w

        # 4. ЗАЩИТА ОТ СУЖЕНИЯ (уберет мерцание)
        if not hasattr(self, '_min_right_widths') or len(self._min_right_widths) != num_cols:
            self._min_right_widths = [0] * num_cols

        for i in range(num_cols):
            if new_widths[i] > self._min_right_widths[i]:
                self._min_right_widths[i] = new_widths[i]
            new_widths[i] = self._min_right_widths[i]

        # 5. Учитываем заголовки групп
        col_index = {col[1]: i for i, col in enumerate(self._right_cols)}
        group_widths = []
        
        for gname, gkeys in RIGHT_COLUMN_GROUPS:
            gvis = [k for k in gkeys if k in col_index]
            if not gvis:
                continue
            
            gw = sum(new_widths[col_index[k]] for k in gvis)
            min_gw = measure_text_width(gname, font_size=11) + dp(24)
            
            if gw < min_gw:
                diff = min_gw - gw
                per_col = diff / len(gvis)
                for k in gvis:
                    new_widths[col_index[k]] += per_col
                gw = min_gw
                
            group_widths.append(gw)

        total_w = sum(new_widths)
        if abs(self.RIGHT_W - total_w) < 1:
            return

        self.RIGHT_W = total_w
        
        # 6. Применяем новые размеры к заголовкам колонок
        if hasattr(self, '_right_headers'):
            for i, hdr in enumerate(self._right_headers):
                last = (i == num_cols - 1)
                hdr.width = new_widths[i] if last else new_widths[i] - 1

        # 7. Применяем новые размеры к самим ячейкам
        if hasattr(self, '_right_col_cells'):
            for i in range(num_cols):
                for cell in self._right_col_cells[i]:
                    cell.width = new_widths[i]

        # 8. Обновляем ширину строк и сетки
        if hasattr(self, '_right_rows'):
            for r in self._right_rows:
                r.width = self.RIGHT_W

        if getattr(self, '_right_grid', None):
            self._right_grid.width = self.RIGHT_W

        if not getattr(self, '_results_hidden', False):
            if getattr(self, 'right_sv', None):
                self.right_sv.width = self.RIGHT_W
            if getattr(self, 'right_header', None):
                self.right_header.width = self.RIGHT_W
            if getattr(self, 'right_top', None):
                self.right_top.width = self.RIGHT_W
                
        # 9. Применяем новые размеры к верхним группам
        if hasattr(self, '_right_top_groups') and self._right_top_groups:
            for i, gw in enumerate(group_widths):
                is_last = (i == len(group_widths) - 1)
                self._right_top_groups[i].width = gw if is_last else gw - 1
                
        Clock.schedule_once(lambda dt: self._apply_results_visibility(), 0)

    # =======================================================================

    def _get_active_dept(self):
        for emp in self.app.data.get('employees', []):
            if emp.get('show_in_timesheet', False):
                return emp.get('department', '')
        return ''

    def _get_month_dict(self, key):
        extra_all = self.app.data.setdefault('extra_employees', {})
        if not isinstance(extra_all, dict):
            extra_all = {}
            self.app.data['extra_employees'] = extra_all
            
        month_dict = extra_all.get(key)
        if not isinstance(month_dict, dict):
            if isinstance(month_dict, list):
                month_dict = {'': month_dict}
            else:
                month_dict = {}
            extra_all[key] = month_dict
        return month_dict

    def _show_selection_popup(self, title, items, callback):
        """items может быть списком ИЛИ функцией-геттером, возвращающей список.
        Если функция — вызывается при каждой перестройке списка,
        так что список всегда актуален (подхватывает внешние изменения)."""
        def _get_items():
            try:
                if callable(items):
                    return list(items() or [])
                return list(items or [])
            except Exception:
                return []

        content = BoxLayout(orientation='vertical', spacing=5, padding=5)

        search_input = TextInput(
            multiline=False, font_size=dp(14), font_name=FONT_NAME,
            foreground_color=(0.05, 0.05, 0.05, 1),
            background_color=(1, 1, 1, 1),
            cursor_color=(0.10, 0.30, 0.70, 1),
            padding=[dp(8), dp(8), dp(8), dp(8)],
            size_hint_y=None, height=dp(36),
            hint_text="Введите для поиска..."
        )
        content.add_widget(search_input)

        scroll = ScrollView(scroll_type=['bars'], effect_cls=NoOverscrollEffect)
        grid = GridLayout(cols=1, size_hint_y=None, spacing=2)
        grid.bind(minimum_height=grid.setter('height'))

        popup = Popup(title=title, content=content, size_hint=(0.6, 0.5),
                      title_color=LABEL_LIGHT, title_font=FONT_NAME,
                      auto_dismiss=False)

        def do_select(val):
            callback(val)
            popup.dismiss()

        def rebuild_list(query=''):
            grid.clear_widgets()
            q = query.lower()
            current_items = _get_items()  # <-- актуальный список на каждый вызов
            for it in current_items:
                if q in it.lower():
                    btn = Button(
                        text=it, size_hint_y=None, height=dp(36),
                        font_name=FONT_NAME, font_size=dp(14),
                        background_normal='',
                        background_color=(0.2, 0.2, 0.25, 1),
                        color=(1, 1, 1, 1),
                        halign='center', valign='middle',
                        shorten=True, shorten_from='right'
                    )
                    btn.bind(size=lambda instance, value: setattr(
                        instance, 'text_size', (value[0] - 20, None)))
                    btn.bind(on_press=lambda *a, x=it: do_select(x))
                    grid.add_widget(btn)

            if not grid.children:
                grid.add_widget(Label(
                    text="Нет элементов",
                    color=(0.6, 0.6, 0.6, 1),
                    font_name=FONT_NAME, font_size=dp(14),
                    size_hint_y=None, height=dp(36)
                ))

        search_input.bind(text=lambda inst, val: rebuild_list(val))
        rebuild_list()

        scroll.add_widget(grid)
        content.add_widget(scroll)

        close_btn = Button(text="Отмена", size_hint_y=None, height=dp(40),
                           font_name=FONT_NAME, color=(1, 1, 1, 1))
        close_btn.bind(on_press=popup.dismiss)
        content.add_widget(close_btn)

        popup.open()

    def show_manage_extra_popup(self, *args):
        dept = self._get_active_dept()
        if not dept:
            err_content = BoxLayout(orientation='vertical', spacing=10, padding=10)
            err_content.add_widget(Label(
                text="Сначала выберите отдел\nна вкладке «Рабочий персонал»",
                color=LABEL_LIGHT, halign='center', valign='middle',
                font_name=FONT_NAME, font_size=dp(15)
            ))
            ok = Button(text="ОК", size_hint_y=None, height=dp(40), font_name=FONT_NAME)
            err_content.add_widget(ok)
            p = Popup(title="Внимание", content=err_content, size_hint=(0.45, 0.3), title_color=LABEL_LIGHT, title_font=FONT_NAME)
            ok.bind(on_press=p.dismiss)
            p.open()
            return

        content = BoxLayout(orientation='vertical', spacing=10, padding=15)

        add_title = Label(text="Добавить нового сотрудника:", color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_y=None, height=dp(24), halign='left')
        add_title.bind(size=lambda i, v: setattr(i, 'text_size', v))
        content.add_widget(add_title)

        all_names = sorted(list(set(e['name'] for e in self.app.data.get('employees', []))))
        positions = self.app.data.get('positions', [])

        name_input = TextInput(
            multiline=False, font_size=dp(15), font_name=FONT_NAME,
            foreground_color=(0.05, 0.05, 0.05, 1), background_color=(1, 1, 1, 1),
            cursor_color=(0.10, 0.30, 0.70, 1), cursor_width=dp(2),
            padding=[dp(8), dp(10), dp(8), dp(10)], size_hint_y=None, height=dp(40),
            hint_text="Введите любую фамилию", halign='left'
        )
        name_btn = Button(text="Выбрать...", size_hint=(None, None), size=(dp(100), dp(40)), font_name=FONT_NAME)
        name_btn.bind(on_press=lambda *a: self._show_selection_popup(
            "Выбор сотрудника",
            lambda: sorted(list(set(
                e['name'] for e in self.app.data.get('employees', [])
            ))),
            lambda val: setattr(name_input, 'text', val)))
        
        name_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=5)
        name_row.add_widget(name_input)
        name_row.add_widget(name_btn)

        pos_holder = BoxLayout(size_hint_y=None, height=dp(40), padding=(dp(8), 0, 0, 0))
        with pos_holder.canvas.before:
            Color(1, 1, 1, 1)
            _pos_rect = Rectangle(pos=pos_holder.pos, size=pos_holder.size)
        pos_holder.bind(pos=lambda i, v: setattr(_pos_rect, 'pos', v),
                        size=lambda i, v: setattr(_pos_rect, 'size', v))
        
        pos_input = Label(text="", font_size=dp(15), font_name=FONT_NAME, color=(0.05, 0.05, 0.05, 1), halign='left', valign='middle')
        pos_input.bind(size=lambda i, v: setattr(i, 'text_size', (v[0]-dp(8), v[1])))
        pos_holder.add_widget(pos_input)
        
        pos_btn = Button(text="Выбрать...", size_hint=(None, None), size=(dp(100), dp(40)), font_name=FONT_NAME)
        pos_btn.bind(on_press=lambda *a: self._show_selection_popup(
            "Выбор должности",
            lambda: list(self.app.data.get('positions', [])),
            lambda val: setattr(pos_input, 'text', val)))
        
        pos_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=5)
        pos_row.add_widget(pos_holder)
        pos_row.add_widget(pos_btn)

        add_btn = Button(text="Добавить в табель", size_hint_y=None, height=dp(44), 
                         font_name=FONT_NAME, background_color=(0.3, 0.7, 0.3, 1), color=(1,1,1,1))

        content.add_widget(name_row)
        content.add_widget(pos_row)
        content.add_widget(add_btn)

        content.add_widget(Widget(size_hint_y=None, height=dp(10)))

        list_title = Label(text="Добавленные сотрудники:", color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_y=None, height=dp(24), halign='left')
        list_title.bind(size=lambda i, v: setattr(i, 'text_size', v))
        content.add_widget(list_title)

        # --- Создание заголовка таблицы ---
        hdr_row = BoxLayout(size_hint_y=None, height=dp(30), spacing=0)
        
        h_box = BoxLayout(size_hint_x=None, width=dp(40))
        add_left_border(h_box, color=(0.4, 0.4, 0.4, 1))
        add_right_border(h_box, color=(0.4, 0.4, 0.4, 1))
        h_box.add_widget(Label(text="№", bold=True, color=LABEL_LIGHT, font_name=FONT_NAME))
        hdr_row.add_widget(h_box)

        h_box = BoxLayout(size_hint_x=1)
        add_right_border(h_box, color=(0.4, 0.4, 0.4, 1))
        lbl = Label(text="Фамилия И.О.", bold=True, color=LABEL_LIGHT, font_name=FONT_NAME, halign='center', valign='middle')
        lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        h_box.add_widget(lbl)
        hdr_row.add_widget(h_box)

        h_box = BoxLayout(size_hint_x=1.5)
        add_right_border(h_box, color=(0.4, 0.4, 0.4, 1))
        lbl = Label(text="Должность", bold=True, color=LABEL_LIGHT, font_name=FONT_NAME, halign='center', valign='middle')
        lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        h_box.add_widget(lbl)
        hdr_row.add_widget(h_box)

        h_box = BoxLayout(size_hint_x=None, width=dp(200))
        add_right_border(h_box, color=(0.4, 0.4, 0.4, 1))
        h_box.add_widget(Label(text="Действия", bold=True, color=LABEL_LIGHT, font_name=FONT_NAME))
        hdr_row.add_widget(h_box)

        add_top_border(hdr_row, color=(0.4, 0.4, 0.4, 1))
        add_bottom_border(hdr_row, color=(0.4, 0.4, 0.4, 1))
        content.add_widget(hdr_row)

        list_scroll = ScrollView(size_hint_y=1, scroll_type=['bars'], effect_cls=NoOverscrollEffect)
        list_grid = GridLayout(cols=1, size_hint_y=None, spacing=0)
        list_grid.bind(minimum_height=list_grid.setter('height'))
        list_scroll.add_widget(list_grid)
        content.add_widget(list_scroll)

        close_btn = Button(text="Закрыть", size_hint_y=None, height=dp(44), font_name=FONT_NAME, color=(1,1,1,1))
        content.add_widget(close_btn)

        popup = Popup(title=f"Временные сотрудники (Отдел: {dept})", content=content, 
                      size_hint=(0.7, 0.8), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)

        # --- ФУНКЦИЯ РЕДАКТИРОВАНИЯ ---
        def open_edit_dialog(emp_data):
            edit_content = BoxLayout(orientation='vertical', spacing=10, padding=15)

            name_in = TextInput(
                text=emp_data['name'], multiline=False, font_size=dp(15), font_name=FONT_NAME,
                foreground_color=(0.05, 0.05, 0.05, 1), background_color=(1, 1, 1, 1),
                padding=[dp(8), dp(10), dp(8), dp(10)], size_hint_y=None, height=dp(40), halign='left'
            )
            name_btn = Button(text="Выбрать...", size_hint=(None, None), size=(dp(100), dp(40)), font_name=FONT_NAME)
            name_btn.bind(on_press=lambda *a: self._show_selection_popup(
                "Выбор сотрудника",
                lambda: sorted(list(set(
                    e['name'] for e in self.app.data.get('employees', [])
                ))),
                lambda val: setattr(name_in, 'text', val)))
            name_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=5)
            name_row.add_widget(name_in)
            name_row.add_widget(name_btn)

            # --- ЗАМЕНА TextInput НА Label ---
            pos_holder_edit = BoxLayout(size_hint_y=None, height=dp(40), padding=(dp(8), 0, 0, 0))
            with pos_holder_edit.canvas.before:
                Color(1, 1, 1, 1)
                _pos_rect_edit = Rectangle(pos=pos_holder_edit.pos, size=pos_holder_edit.size)
            pos_holder_edit.bind(pos=lambda i, v: setattr(_pos_rect_edit, 'pos', v),
                                 size=lambda i, v: setattr(_pos_rect_edit, 'size', v))

            pos_in = Label(
                text=emp_data['position'], font_size=dp(15), font_name=FONT_NAME,
                color=(0.05, 0.05, 0.05, 1), halign='left', valign='middle'
            )
            pos_in.bind(size=lambda i, v: setattr(i, 'text_size', (v[0]-dp(8), v[1])))
            pos_holder_edit.add_widget(pos_in)

            pos_btn = Button(text="Выбрать...", size_hint=(None, None), size=(dp(100), dp(40)), font_name=FONT_NAME)
            pos_btn.bind(on_press=lambda *a: self._show_selection_popup(
                "Выбор должности",
                lambda: list(self.app.data.get('positions', [])),
                lambda val: setattr(pos_in, 'text', val)))
            pos_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=5)
            pos_row.add_widget(pos_holder_edit)
            pos_row.add_widget(pos_btn)
            # ----------------------------------

            btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=10)
            save_btn = Button(text="Сохранить", background_color=(0.3, 0.7, 0.3, 1), color=(1,1,1,1), font_name=FONT_NAME)
            cancel_btn = Button(text="Отмена", color=(1,1,1,1), font_name=FONT_NAME)
            btns.add_widget(save_btn)
            btns.add_widget(cancel_btn)

            edit_content.add_widget(Widget(size_hint_y=1))

            lbl = Label(text="Редактирование сотрудника:", color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_y=None, height=dp(24), halign='center')
            lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
            edit_content.add_widget(lbl)
            
            edit_content.add_widget(name_row)
            edit_content.add_widget(pos_row)
            
            edit_content.add_widget(Widget(size_hint_y=1))
            
            edit_content.add_widget(btns)

            popup_edit = Popup(
                title="Изменить", content=edit_content, 
                size_hint=(None, None), size=(dp(550), dp(320)), 
                title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False
            )

            def do_save_edit(*args):
                new_name = name_in.text.strip()
                new_pos = pos_in.text.strip()
                if new_name and new_pos:
                    emp_data['name'] = new_name
                    emp_data['position'] = new_pos
                    self.app.safe_save(self.app.data)
                    self.load_timesheet()
                    rebuild_list()
                    popup_edit.dismiss()

            save_btn.bind(on_press=do_save_edit)
            cancel_btn.bind(on_press=popup_edit.dismiss)
            
            name_in.bind(on_text_validate=do_save_edit)
            bind_enter_key(popup_edit, do_save_edit)
            
            popup_edit.open()

        # --- ОБНОВЛЕННЫЙ СПИСОК ---
        def rebuild_list():
            list_grid.clear_widgets()
            key = self._get_key()
            month_dict = self._get_month_dict(key)
            extra = month_dict.get(dept, [])

            if not extra:
                empty_lbl = Label(text="Нет добавленных сотрудников", color=(0.6, 0.6, 0.6, 1), 
                                  font_name=FONT_NAME, size_hint_y=None, height=dp(36))
                list_grid.add_widget(empty_lbl)
                return
                
            for i, emp in enumerate(extra, start=1):
                row = BoxLayout(size_hint_y=None, height=dp(36), spacing=0)
                
                c_box = BoxLayout(size_hint_x=None, width=dp(40))
                add_left_border(c_box, color=(0.4, 0.4, 0.4, 1))
                add_right_border(c_box, color=(0.4, 0.4, 0.4, 1))
                c_box.add_widget(Label(text=str(i), color=LABEL_LIGHT, font_name=FONT_NAME))
                row.add_widget(c_box)

                c_box = BoxLayout(size_hint_x=1, padding=(dp(5), 0, 0, 0))
                add_right_border(c_box, color=(0.4, 0.4, 0.4, 1))
                lbl = Label(text=emp['name'], color=LABEL_LIGHT, font_name=FONT_NAME, halign='left', valign='middle', shorten=True, shorten_from='right')
                lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0]-dp(5), val[1])))
                c_box.add_widget(lbl)
                row.add_widget(c_box)

                c_box = BoxLayout(size_hint_x=1.5, padding=(dp(5), 0, 0, 0))
                add_right_border(c_box, color=(0.4, 0.4, 0.4, 1))
                lbl = Label(text=emp['position'], color=LABEL_LIGHT, font_name=FONT_NAME, halign='left', valign='middle', shorten=True, shorten_from='right')
                lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0]-dp(5), val[1])))
                c_box.add_widget(lbl)
                row.add_widget(c_box)

                c_box = BoxLayout(size_hint_x=None, width=dp(200), spacing=dp(4), padding=(dp(4), dp(4)))
                add_right_border(c_box, color=(0.4, 0.4, 0.4, 1))
                
                edit_btn = Button(text="Изменить", size_hint=(1, 1), 
                                 background_color=(0.35, 0.55, 0.85, 1), color=(1,1,1,1), font_name=FONT_NAME, font_size=dp(14))
                edit_btn.bind(on_press=lambda *a, e=emp: open_edit_dialog(e))
                c_box.add_widget(edit_btn)

                del_btn = Button(text="Удалить", size_hint=(1, 1), 
                                 background_color=(0.8, 0.3, 0.3, 1), color=(1,1,1,1), font_name=FONT_NAME, font_size=dp(14))
                
                def do_del(*a, eid=emp['id']):
                    month_dict[dept] = [e for e in extra if e['id'] != eid]
                    self.app.safe_save(self.app.data)
                    self.load_timesheet()
                    rebuild_list()
                    
                del_btn.bind(on_press=do_del)
                c_box.add_widget(del_btn)
                row.add_widget(c_box)
                
                add_bottom_border(row, color=(0.4, 0.4, 0.4, 1))
                list_grid.add_widget(row)

        def do_add(*args):
            name = name_input.text.strip()
            pos = pos_input.text.strip()
            
            if not name or not pos:
                missing = []
                if not name: missing.append("ФИО")
                if not pos: missing.append("Должность")
                
                err_content = BoxLayout(orientation='vertical', spacing=10, padding=10)
                err_content.add_widget(Label(text="Не выбрано:\n• " + "\n• ".join(missing), color=LABEL_LIGHT, halign='center', valign='middle', font_name=FONT_NAME, font_size=dp(15)))
                err_btn = Button(text="ОК", size_hint_y=None, height=dp(40), font_name=FONT_NAME, background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1))
                err_content.add_widget(err_btn)
                err_popup = Popup(title="Внимание", content=err_content, size_hint=(0.45, 0.3), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
                err_btn.bind(on_press=err_popup.dismiss)
                err_popup.open()
                return
            
            key = self._get_key()
            month_dict = self._get_month_dict(key)
            extra = month_dict.setdefault(dept, [])
            
            for e in extra:
                if e['name'].strip().lower() == name.lower():
                    err_content = BoxLayout(orientation='vertical', spacing=10, padding=10)
                    err_content.add_widget(Label(text=f"Сотрудник «{name}»\nуже добавлен в этот список!", color=LABEL_LIGHT, halign='center', valign='middle', font_name=FONT_NAME, font_size=dp(15)))
                    err_btn = Button(text="ОК", size_hint_y=None, height=dp(40), font_name=FONT_NAME, background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1))
                    err_content.add_widget(err_btn)
                    err_popup = Popup(title="Дубликат", content=err_content, size_hint=(0.45, 0.3), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
                    err_btn.bind(on_press=err_popup.dismiss)
                    err_popup.open()
                    return

            new_id = f"extra_{key}_{int(datetime.now().timestamp() * 1000)}"
            extra.append({'id': new_id, 'name': name, 'position': pos, 'is_contract': False})
            self.app.safe_save(self.app.data)
            self.load_timesheet()
            rebuild_list()
            
            name_input.text = ""
            pos_input.text = ""

        add_btn.bind(on_press=do_add)
        close_btn.bind(on_press=popup.dismiss)
        
        name_input.bind(on_text_validate=do_add)
        bind_enter_key(popup, do_add)

        # --- ПРИВЯЗКА ДЛЯ АВТООБНОВЛЕНИЯ ---
        self.active_extra_popup = popup
        self.active_extra_rebuild = rebuild_list

        def on_extra_dismiss(*args):
            self.active_extra_popup = None
            self.active_extra_rebuild = None

        popup.bind(on_dismiss=on_extra_dismiss)
        # -----------------------------------

        popup.open()
        rebuild_list()

    def _get_key(self):
        m = MONTHS.index(self.month_spinner.text) + 1
        y = int(self.year_spinner.text)
        return f"{y}-{m:02d}"

    def _get_norm_hours(self):
        y = int(self.year_spinner.text)
        m = MONTHS.index(self.month_spinner.text) + 1
        norm, _, _ = calc_norm_hours(y, m)
        return norm

    def _on_period_change(self, *args):
        if self._loading:
            return
        if self._last_key:
            self._save_for_key(self._last_key)
        
        # Дебаунс: даем спиннеру закрыться и интерфейсу успокоиться
        if getattr(self, '_period_change_ev', None):
            self._period_change_ev.cancel()
        self._period_change_ev = Clock.schedule_once(lambda dt: self.load_timesheet(), 0.2)

    def _on_win_key_down(self, window, key, scancode, codepoint, modifiers):
        if 'shift' in (modifiers or []):
            self._shift_held = True
            NavTextInput.shift_state['held'] = True

    def _on_win_key_up(self, window, key, scancode):
        if key in (303, 304):
            self._shift_held = False
            NavTextInput.shift_state['held'] = False

    def _flush_pending_save(self):
        """Записать только грязные ячейки в файл под локом с merge."""
        if not self._dirty_cells:
            return
        key = self._last_key
        if not key:
            self._dirty_cells.clear()
            return

        cells_values = {}
        for emp_id, day_str in self._dirty_cells:
            try:
                day_int = int(day_str)
            except ValueError:
                continue
            cells = self.day_inputs.get(emp_id, [])
            if 1 <= day_int <= len(cells):
                cells_values[(emp_id, day_str)] = cells[day_int - 1].input.text.strip()

        if cells_values:
            try:
                from data_storage import save_cells
                save_cells(self.app.data, key, cells_values)
                self._dirty_cells.clear() # Очищаем только при успехе
            except ConnectionError:
                # Показываем окно через главное приложение
                self.app._show_save_error("Отсутствует связь с сетевой базой данных. Изменения не сохранены!")
                # НЕ очищаем _dirty_cells, чтобы при появлении сети они сохранились
            except Exception as e:
                print("Ошибка сохранения ячеек:", e)

    def _apply_external_data(self, new_data):
        """Обновляет только значения ячеек, не пересоздавая таблицу."""
        self._is_syncing = True
        try:
            key = self._get_key()
            ts = new_data.get('timesheets', {}).get(key, {})

            for emp_id, cells in self.day_inputs.items():
                day_values = ts.get(emp_id, {})
                for d_idx, cell in enumerate(cells, start=1):
                    # Если пользователь прямо сейчас печатает в этой ячейке — не трогаем
                    if cell.input.focused and (emp_id, str(d_idx)) in self._dirty_cells:
                        continue

                    new_val = str(day_values.get(str(d_idx), ''))
                    if cell.input.text != new_val:
                        cell.input.text = new_val

            # Пересчёт итогов внутри _is_syncing — чтобы не дёргать авто-подгонку на каждый сотрудник
            for emp_id in list(self.day_inputs.keys()):
                self._recalc_totals(emp_id)
        finally:
            self._is_syncing = False

        cells_values = {}
        for emp_id, day_str in self._dirty_cells:
            try:
                day_int = int(day_str)
            except ValueError:
                continue
            cells = self.day_inputs.get(emp_id, [])
            if 1 <= day_int <= len(cells):
                cells_values[(emp_id, day_str)] = cells[day_int - 1].input.text.strip()

        if cells_values:
            save_cells(self.app.data, key, cells_values)

        self._dirty_cells.clear()

        # Одна авто-подгонка после синхронизации (а не на каждый пересчёт)
        if getattr(self, '_auto_fit_right_ev', None):
            self._auto_fit_right_ev.cancel()
        self._auto_fit_right_ev = Clock.schedule_once(
            lambda dt: self._auto_fit_right_columns(), 0.3)

    def _save_for_key(self, key=None):
        """Совместимость: старый API, используется в паре мест."""
        self._flush_pending_save()

    def _save_all(self, dt=0):
        self._flush_pending_save()

    def _schedule_save(self, *a):
        if self._save_event:
            self._save_event.cancel()
        self._save_event = Clock.schedule_once(self._save_all, 0.6)

    def _on_day_change(self, emp_id, day=None):
        if getattr(self, '_is_syncing', False):
            return
        if day is not None:
            self._dirty_cells.add((emp_id, str(day)))
        self._recalc_totals(emp_id)
        self._schedule_save()

        if getattr(self, '_auto_fit_ev', None):
            self._auto_fit_ev.cancel()
        self._auto_fit_ev = Clock.schedule_once(lambda dt: self._auto_fit_day_columns(), 0.5)

    def update_open_popups(self):
        """Обновляет открытое окно временных сотрудников, если оно есть."""
        if getattr(self, 'active_extra_popup', None) and getattr(self, 'active_extra_rebuild', None):
            Clock.schedule_once(lambda dt: self.active_extra_rebuild(), 0)
            
    def _employees_for_ts(self):
        key = self._get_key()
        dept = self._get_active_dept()
        
        emps = [emp for emp in self.app.data['employees'] if emp.get('show_in_timesheet', False)]
        
        month_dict = self._get_month_dict(key)
        extra = month_dict.get(dept, [])
        for e in extra:
            e['is_extra'] = True
        return emps + extra

    def _make_day_nav_callback(self, emp_id, day_idx):
        def cb(key, modifiers):
            return self._handle_day_nav(emp_id, day_idx, key, modifiers)
        return cb

    def _make_result_nav_callback(self, emp_id, col_idx):
        def cb(key, modifiers):
            return self._handle_result_nav(emp_id, col_idx, key, modifiers)
        return cb

    def _on_extra_key(self, key, modifiers):
        mods = modifiers or []
        ctrl = 'ctrl' in mods

        if key == 127:
            cell = self._get_focused_cell()
            if cell is not None:
                try:
                    if cell.input.selection_text:
                        return False
                except Exception:
                    pass
            if (self._sel_anchor and self._sel_current
                    and self._sel_anchor != self._sel_current):
                if self._clear_selection_cells():
                    return True
                return False
            if cell is not None:
                cell.input.text = ''
                return True
            return False

        if not ctrl:
            return False

        if key == 99:
            if (self._sel_anchor and self._sel_current
                    and self._sel_anchor != self._sel_current):
                return self._save_selection_to_clipboard()
            cell = self._get_focused_cell()
            if cell is not None:
                value = cell.input.text
                try:
                    from kivy.core.clipboard import Clipboard
                    Clipboard.copy(value)
                    return True
                except Exception:
                    return False
            return False

        if key == 118:
            try:
                from kivy.core.clipboard import Clipboard
                txt = Clipboard.paste() or ''
            except Exception:
                txt = ''

            if not txt:
                return False

            lines = txt.replace('\r\n', '\n').split('\n')
            while len(lines) > 1 and lines[-1] == '':
                lines.pop()

            if len(lines) == 1 and '\t' not in lines[0]:
                cell = self._get_focused_cell()
                if cell is None:
                    return False
                value = lines[0]
                cell.input.text = value
                try:
                    cell.input.cursor = (len(value), 0)
                except Exception:
                    pass
                return True

            if self._paste_tsv_from_text(lines):
                return True
            return False

        return False

    def _on_window_keyboard(self, window, key, scancode, codepoint, modifiers):
        mods = modifiers or []
        ctrl = 'ctrl' in mods

        if ctrl and key == 99:
            if self._sel_anchor and self._sel_current:
                if self._save_selection_to_clipboard():
                    return True
            return False

        if ctrl and key == 118:
            if self._sel_anchor and self._sel_current:
                try:
                    from kivy.core.clipboard import Clipboard
                    txt = Clipboard.paste() or ''
                except Exception:
                    txt = ''
                if not txt:
                    return False
                lines = txt.replace('\r\n', '\n').split('\n')
                while len(lines) > 1 and lines[-1] == '':
                    lines.pop()
                if self._paste_tsv_from_text(lines):
                    return True
            return False

        if key != 127:
            return False

        cell = self._get_focused_cell()

        if cell is not None:
            try:
                if cell.input.selection_text:
                    return False
            except Exception:
                pass

        if (self._sel_anchor and self._sel_current
                and self._sel_anchor != self._sel_current):
            if self._clear_selection_cells():
                return True
            return False

        if cell is not None:
            cell.input.text = ''
            return True
        return False

    def _save_selection_to_clipboard(self):
        bounds = self._selection_bounds()
        if bounds is None:
            return False
        kind, ia, ib, ca, cb = bounds
        emps = self._employees_order
        rows = []
        if kind == 'd':
            for i in range(ia, ib + 1):
                emp = emps[i]
                cells = self.day_inputs.get(emp, [])
                row = []
                for c in range(ca, cb + 1):
                    if 1 <= c <= len(cells):
                        row.append(cells[c - 1].input.text)
                    else:
                        row.append('')
                rows.append('\t'.join(row))
        else:
            for i in range(ia, ib + 1):
                emp = emps[i]
                labels = self.total_labels.get(emp, {})
                row = []
                for c in range(ca, cb + 1):
                    if 0 <= c < len(self._right_cols):
                        key_ = self._right_cols[c][1]
                        cell = labels.get(key_)
                        row.append(cell.input.text if cell else '')
                    else:
                        row.append('')
                rows.append('\t'.join(row))
        text = '\n'.join(rows)
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(text)
            return True
        except Exception:
            return False

    def _paste_tsv_from_text(self, lines):
        kind = None
        emp_id_start = None
        idx_start = None

        if self._sel_anchor:
            kind = self._sel_anchor[0]
            emp_id_start = self._sel_anchor[1]
            idx_start = self._sel_anchor[2]
        else:
            cell = self._get_focused_cell()
            info = self._cell_info(cell) if cell else None
            if info is not None:
                emp_id_start, idx_start, kind = info

        if emp_id_start is None or kind is None:
            return False

        emps = self._employees_order
        try:
            i0 = emps.index(emp_id_start)
        except ValueError:
            return False

        if kind == 'd':
            for r, line in enumerate(lines):
                ei = i0 + r
                if ei >= len(emps):
                    break
                emp = emps[ei]
                cells = self.day_inputs.get(emp, [])
                parts = line.split('\t')
                for c, val in enumerate(parts):
                    d = idx_start + c
                    if 1 <= d <= len(cells):
                        cells[d - 1].input.text = val
            self._schedule_save()
        else:
            overrides = self._get_overrides()
            affected = []
            for r, line in enumerate(lines):
                ei = i0 + r
                if ei >= len(emps):
                    break
                emp = emps[ei]
                labels = self.total_labels.get(emp, {})
                emp_over = overrides.setdefault(emp, {})
                parts = line.split('\t')
                for c, val in enumerate(parts):
                    cc = idx_start + c
                    if 0 <= cc < len(self._right_cols):
                        key_ = self._right_cols[cc][1]
                        cell = labels.get(key_)
                        v = val.strip()
                        if v == '':
                            emp_over.pop(key_, None)
                        else:
                            emp_over[key_] = v
                        if cell is not None and cell.input.focused:
                            cell.input.text = v
                affected.append(emp)
            for emp_id in affected:
                try:
                    self._recalc_totals(emp_id)
                except Exception:
                    pass
            self._schedule_save()
        return True

    def _clear_selection_cells(self):
        bounds = self._selection_bounds()
        if bounds is None:
            return False
        kind, ia, ib, ca, cb = bounds
        emps = self._employees_order

        if kind == 'd':
            for i in range(ia, ib + 1):
                emp = emps[i]
                cells = self.day_inputs.get(emp, [])
                for d in range(ca, cb + 1):
                    if 1 <= d <= len(cells):
                        cells[d - 1].input.text = ''
            for i in range(ia, ib + 1):
                try:
                    self._recalc_totals(emps[i])
                except Exception:
                    pass
        else:
            overrides = self._get_overrides()
            for i in range(ia, ib + 1):
                emp_id = emps[i]
                labels = self.total_labels.get(emp_id, {})
                emp_over = overrides.setdefault(emp_id, {})
                for c in range(ca, cb + 1):
                    if 0 <= c < len(self._right_cols):
                        key_ = self._right_cols[c][1]
                        emp_over.pop(key_, None)
                        cell = labels.get(key_)
                        if cell is not None and cell.input.focused:
                            cell.input.text = ''
            for i in range(ia, ib + 1):
                try:
                    self._recalc_totals(emps[i])
                except Exception:
                    pass
        self._schedule_save()
        return True

    def _get_focused_cell(self):
        for cells in self.day_inputs.values():
            for c in cells:
                try:
                    if c.input.focused:
                        return c
                except Exception:
                    pass
        for labels in self.total_labels.values():
            for c in labels.values():
                try:
                    if c.input.focused:
                        return c
                except Exception:
                    pass
        return None

    def has_focused_cell(self):
        return self._get_focused_cell() is not None

    def _blur_all_cells(self):
        for cells in self.day_inputs.values():
            for c in cells:
                try:
                    if c.input.focused:
                        c.input.focus = False
                except Exception:
                    pass
        for labels in self.total_labels.values():
            for c in labels.values():
                try:
                    if c.input.focused:
                        c.input.focus = False
                except Exception:
                    pass

    def _on_cell_touch_down(self, cell, touch):
        info = self._cell_info(cell)
        if info is None:
            return
        emp_id, idx, kind = info
        if self._shift_held:
            self._blur_all_cells()

            if self._sel_anchor is None or self._sel_anchor[0] != kind:
                self._sel_anchor = (kind, emp_id, idx)
            self._sel_current = (kind, emp_id, idx)
            self._refresh_highlights()
        else:
            if self._sel_anchor or self._sel_current:
                self._clear_selection()

    def _cell_info(self, cell):
        for emp_id, cells in self.day_inputs.items():
            for idx, c in enumerate(cells, start=1):
                if c is cell:
                    return (emp_id, idx, 'd')
        for emp_id, labels in self.total_labels.items():
            for col_idx, (_, key_, _) in enumerate(self._right_cols):
                c = labels.get(key_)
                if c is cell:
                    return (emp_id, col_idx, 'r')
        return None

    def _clear_selection(self):
        self._sel_anchor = None
        self._sel_current = None
        self._refresh_highlights()

    def _refresh_highlights(self):
        for emp_cells in self.day_inputs.values():
            for c in emp_cells:
                try:
                    c.set_highlight(False)
                except Exception:
                    pass
        for labels in self.total_labels.values():
            for c in labels.values():
                try:
                    c.set_highlight(False)
                except Exception:
                    pass

        if not self._sel_anchor or not self._sel_current:
            return
        a = self._sel_anchor
        b = self._sel_current
        if a[0] != b[0]:
            return
        kind = a[0]
        idx_a, idx_b = a[2], b[2]

        emps = self._employees_order
        try:
            ia = emps.index(a[1])
            ib = emps.index(b[1])
        except ValueError:
            return
        if ia > ib:
            ia, ib = ib, ia
        if idx_a > idx_b:
            idx_a, idx_b = idx_b, idx_a

        if kind == 'd':
            for i in range(ia, ib + 1):
                emp = emps[i]
                cells = self.day_inputs.get(emp, [])
                for d in range(idx_a, idx_b + 1):
                    if 1 <= d <= len(cells):
                        try:
                            cells[d - 1].set_highlight(True)
                        except Exception:
                            pass
        else:
            for i in range(ia, ib + 1):
                emp = emps[i]
                labels = self.total_labels.get(emp, {})
                for cc in range(idx_a, idx_b + 1):
                    if 0 <= cc < len(self._right_cols):
                        key_ = self._right_cols[cc][1]
                        cell = labels.get(key_)
                        if cell is not None:
                            try:
                                cell.set_highlight(True)
                            except Exception:
                                pass

    def _selection_bounds(self):
        if not self._sel_anchor or not self._sel_current:
            return None
        a = self._sel_anchor
        b = self._sel_current
        if a[0] != b[0]:
            return None
        kind = a[0]
        emps = self._employees_order
        try:
            ia = emps.index(a[1])
            ib = emps.index(b[1])
        except ValueError:
            return None
        if ia > ib:
            ia, ib = ib, ia
        ca, cb = a[2], b[2]
        if ca > cb:
            ca, cb = cb, ca
        return (kind, ia, ib, ca, cb)

    def _handle_day_nav(self, emp_id, day_idx, key, modifiers):
        mods = modifiers or []
        if 'ctrl' in mods:
            return False

        shift = 'shift' in mods

        if key == 9:
            if shift:
                self._focus_prev_day(emp_id, day_idx)
            else:
                self._focus_next_day(emp_id, day_idx)
            return True

        if key == 275:
            cell = self._get_day_cell(emp_id, day_idx)
            if cell is not None:
                try:
                    if cell.input.cursor_index() >= len(cell.input.text):
                        return self._focus_next_day(emp_id, day_idx)
                except Exception:
                    pass
            return False

        if key == 276:
            cell = self._get_day_cell(emp_id, day_idx)
            if cell is not None:
                try:
                    if cell.input.cursor_index() <= 0:
                        return self._focus_prev_day(emp_id, day_idx)
                except Exception:
                    pass
            return False

        if key == 274:
            return self._focus_row_down_day(emp_id, day_idx)
        if key == 273:
            return self._focus_row_up_day(emp_id, day_idx)
        return False

    def _handle_result_nav(self, emp_id, col_idx, key, modifiers):
        mods = modifiers or []
        if 'ctrl' in mods:
            return False

        shift = 'shift' in mods

        if key == 9:
            if shift:
                self._focus_result_prev(emp_id, col_idx)
            else:
                self._focus_result_next(emp_id, col_idx)
            return True

        if key == 275:
            cell = self._get_result_cell(emp_id, col_idx)
            if cell is not None:
                try:
                    if cell.input.cursor_index() >= len(cell.input.text):
                        self._focus_result_next(emp_id, col_idx)
                        return True
                except Exception:
                    pass
            return False

        if key == 276:
            cell = self._get_result_cell(emp_id, col_idx)
            if cell is not None:
                try:
                    if cell.input.cursor_index() <= 0:
                        self._focus_result_prev(emp_id, col_idx)
                        return True
                except Exception:
                    pass
            return False

        if key == 274:
            return self._focus_result_row_down(emp_id, col_idx)
        if key == 273:
            return self._focus_result_row_up(emp_id, col_idx)
        return False

    def _get_day_cell(self, emp_id, day_idx):
        cells = self.day_inputs.get(emp_id, [])
        if 1 <= day_idx <= len(cells):
            return cells[day_idx - 1]
        return None

    def _focus_next_day(self, emp_id, day_idx):
        cells = self.day_inputs.get(emp_id, [])
        if day_idx < len(cells):
            self._focus_cell(cells[day_idx])
            return True
        return self._focus_result_first(emp_id)

    def _focus_prev_day(self, emp_id, day_idx):
        if day_idx > 1:
            cells = self.day_inputs.get(emp_id, [])
            if day_idx - 2 < len(cells):
                self._focus_cell(cells[day_idx - 2])
                return True
        emps = self._employees_order
        try:
            ei = emps.index(emp_id)
        except ValueError:
            return False
        if ei > 0:
            return self._focus_result_last(emps[ei - 1])
        return False

    def _focus_row_down_day(self, emp_id, day_idx):
        emps = self._employees_order
        try:
            ei = emps.index(emp_id)
        except ValueError:
            return False
        if ei + 1 < len(emps):
            next_cells = self.day_inputs.get(emps[ei + 1], [])
            if day_idx <= len(next_cells):
                self._focus_cell(next_cells[day_idx - 1])
                return True
        return False

    def _focus_row_up_day(self, emp_id, day_idx):
        emps = self._employees_order
        try:
            ei = emps.index(emp_id)
        except ValueError:
            return False
        if ei > 0:
            prev_cells = self.day_inputs.get(emps[ei - 1], [])
            if day_idx <= len(prev_cells):
                self._focus_cell(prev_cells[day_idx - 1])
                return True
        return False

    def _get_result_cell(self, emp_id, col_idx):
        if col_idx < 0 or col_idx >= len(self._right_cols):
            return None
        key_ = self._right_cols[col_idx][1]
        return self.total_labels.get(emp_id, {}).get(key_)

    def _focus_result_first(self, emp_id):
        return self._focus_result_by_index(emp_id, 0)

    def _focus_result_last(self, emp_id):
        return self._focus_result_by_index(emp_id, len(self._right_cols) - 1)

    def _focus_result_by_index(self, emp_id, col_idx):
        cell = self._get_result_cell(emp_id, col_idx)
        if cell is None:
            return False
        self._focus_result_cell(cell)
        return True

    def _focus_result_next(self, emp_id, col_idx):
        if col_idx + 1 < len(self._right_cols):
            return self._focus_result_by_index(emp_id, col_idx + 1)
        emps = self._employees_order
        try:
            ei = emps.index(emp_id)
        except ValueError:
            return False
        if ei + 1 < len(emps):
            next_cells = self.day_inputs.get(emps[ei + 1], [])
            if next_cells:
                self._focus_cell(next_cells[0])
                return True
        return False

    def _focus_result_prev(self, emp_id, col_idx):
        if col_idx > 0:
            return self._focus_result_by_index(emp_id, col_idx - 1)
        cells = self.day_inputs.get(emp_id, [])
        if cells:
            self._focus_cell(cells[-1])
            return True
        return False

    def _focus_result_row_down(self, emp_id, col_idx):
        emps = self._employees_order
        try:
            ei = emps.index(emp_id)
        except ValueError:
            return False
        if ei + 1 < len(emps):
            return self._focus_result_by_index(emps[ei + 1], col_idx)
        return False

    def _focus_result_row_up(self, emp_id, col_idx):
        emps = self._employees_order
        try:
            ei = emps.index(emp_id)
        except ValueError:
            return False
        if ei > 0:
            return self._focus_result_by_index(emps[ei - 1], col_idx)
        return False

    def _focus_cell(self, cell):
        try:
            cell.input.focus = True
            sv = self._days_sv
            if sv is not None:
                Clock.schedule_once(lambda dt: self._scroll_to_safe(sv, cell), 0)
        except Exception:
            pass

    def _focus_result_cell(self, cell):
        try:
            cell.input.focus = True
        except Exception:
            pass

    @staticmethod
    def _select_all_safe(cell):
        try:
            cell.input.select_all()
        except Exception:
            pass

    @staticmethod
    def _scroll_to_safe(sv, cell):
        try:
            if not sv.children:
                return
            grid = sv.children[0]
            content_w = grid.width
            view_w = sv.width
            if content_w <= view_w or view_w <= 0:
                return
            cell_left = cell.x
            cell_right = cell.x + cell.width
            cur_x = sv.scroll_x * (content_w - view_w)
            if cur_x <= cell_left and cell_right <= cur_x + view_w:
                return
            target_x = cell_left + cell.width / 2.0 - view_w / 2.0
            max_x = content_w - view_w
            if target_x < 0:
                target_x = 0
            if target_x > max_x:
                target_x = max_x
            sv.scroll_x = target_x / max_x
        except Exception:
            pass

    def refresh_if_needed(self):
        """Вызывается при переключении на вкладку. Перестраивает только при изменениях."""
        if getattr(self, '_last_key', None) is None:
            self.load_timesheet()
            return

        # Проверяем, совпадает ли месяц/год
        if self._last_key != self._get_key():
            self.load_timesheet()
            return

        employees = self._employees_for_ts()
        current_ids = [emp['id'] for emp in employees]
        
        # Если изменился состав или порядок сотрудников -> нужна полная перестройка
        if current_ids != self._employees_order:
            self.load_timesheet()
            return
            
        # Если изменились только имена или должности -> обновляем текст БЕЗ перестройки!
        changed = False
        for emp in employees:
            if self._built_names.get(emp['id']) != emp.get('name', ''):
                changed = True
                break
            if self._built_positions.get(emp['id']) != emp.get('position', ''):
                changed = True
                break
                
        if changed:
            self._update_texts_only(employees)
        else:
            # Если структура та же, просто обновляем значения ячеек (без мерцания)
            self._apply_external_data(self.app.data)

    def _update_texts_only(self, employees):
        """Обновляет только ФИО и Должность, не перестраивая таблицу (убирает мерцание)."""
        try:
            left_sv = None
            # Ищем левый ScrollView (он имеет ширину LEFT_W)
            if getattr(self, '_current_body', None):
                for child in self._current_body.children:
                    if isinstance(child, SmartScrollView) and child.width == self.LEFT_W:
                        left_sv = child
                        break
            
            if left_sv and left_sv.children:
                left_grid = left_sv.children[0]
                for i, emp in enumerate(employees):
                    if i < len(left_grid.children):
                        r = left_grid.children[-(i+1)]
                        # r.children = [pos_lbl, name_lbl, num_lbl] в обратном порядке
                        pos_lbl = r.children[0]
                        name_lbl = r.children[1]
                        
                        name_lbl.text = emp.get('name', '')
                        pos_lbl.text = emp.get('position', '')
                        
                        self._built_names[emp['id']] = emp.get('name', '')
                        self._built_positions[emp['id']] = emp.get('position', '')
            
            self._apply_external_data(self.app.data)
        except Exception as e:
            print("Ошибка при обновлении текста:", e)
            self.load_timesheet()
            
    def confirm_clear(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(
            text=f"Очистить все данные за\n{self.month_spinner.text} "
                 f"{self.year_spinner.text}?",
            color=LABEL_LIGHT, halign='center',
            font_name=FONT_NAME, font_size=dp(15),
            outline_color=(0, 0, 0, 1), outline_width=1))
        btns = BoxLayout(size_hint_y=None, height=dp(40), spacing=10)
        yes = Button(text="Да, очистить", background_color=(0.9, 0.35, 0.35, 1),
                     color=(1, 1, 1, 1),
                     font_name=FONT_NAME, font_size=dp(16), bold=True)
        no = Button(text="Отмена", color=(1, 1, 1, 1),
                    font_name=FONT_NAME, font_size=dp(16), bold=True)
        btns.add_widget(yes)
        btns.add_widget(no)
        content.add_widget(btns)
        popup = Popup(title="Подтверждение", content=content,
                      size_hint=(0.5, 0.35), title_color=LABEL_LIGHT,
                      title_font=FONT_NAME, auto_dismiss=False)

        def do_clear(*a):
            key = self._get_key()
            self.app.data['timesheets'][key] = {}
            self.app.safe_save(self.app.data)
            popup.dismiss()
            self.load_timesheet()

        yes.bind(on_press=do_clear)
        no.bind(on_press=popup.dismiss)
        bind_enter_key(popup, do_clear)
        popup.open()

    def _get_overrides(self):
        key = self._get_key()
        return (self.app.data.setdefault('result_overrides', {})
                .setdefault(key, {}))

    def _on_result_change(self, emp_id, col_key, value):
        if self._suppress_result_cb:
            return
        cell = self.total_labels.get(emp_id, {}).get(col_key)
        if cell is None or not cell.input.focused:
            return
        emp_over = self._get_overrides().setdefault(emp_id, {})
        v = value.strip()
        if v == '':
            emp_over.pop(col_key, None)
            self._recalc_totals(emp_id)
        else:
            if len(v) > 1 and v[0] == '0' and v[1].isdigit():
                v_norm = v.lstrip('0') or '0'
                if v_norm != v:
                    self._suppress_result_cb = True
                    try:
                        cell.input.text = v_norm
                        try:
                            cell.input.cursor = (len(v_norm), 0)
                        except Exception:
                            pass
                    finally:
                        self._suppress_result_cb = False
                    v = v_norm
            emp_over[col_key] = v
        self._schedule_save()
        
        if getattr(self, '_auto_fit_right_ev', None):
            self._auto_fit_right_ev.cancel()
        self._auto_fit_right_ev = Clock.schedule_once(lambda dt: self._auto_fit_right_columns(), 0.5)

    def _on_result_focus(self, emp_id, col_key, focused):
        cell = self.total_labels.get(emp_id, {}).get(col_key)
        if cell is None:
            return
        if focused:
            pass
        else:
            if cell.input.text.strip() == '':
                self._recalc_totals(emp_id)

    def apply_overrides(self):
        key = self._get_key()
        overrides = self.app.data.setdefault('result_overrides', {}).setdefault(key, {})
        for emp_id, labels in self.total_labels.items():
            emp_over = overrides.setdefault(emp_id, {})
            for col_key, cell in labels.items():
                if not cell.input.focused:
                    continue
                txt = cell.input.text.strip()
                if txt == '':
                    emp_over.pop(col_key, None)
                else:
                    emp_over[col_key] = txt
        self.app.safe_save(self.app.data)
        for emp_id in list(self.total_labels.keys()):
            self._recalc_totals(emp_id)

    def reset_overrides(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(
            text=(f"Сбросить все ручные правки итогов за\n"
                  f"{self.month_spinner.text} {self.year_spinner.text}?"),
            color=LABEL_LIGHT, halign='center',
            font_name=FONT_NAME, font_size=dp(15),
            outline_color=(0, 0, 0, 1), outline_width=1))
        btns = BoxLayout(size_hint_y=None, height=dp(40), spacing=10)
        yes = Button(text="Да, сбросить",
                     background_color=(0.6, 0.4, 0.8, 1), color=(1, 1, 1, 1),
                     font_name=FONT_NAME, font_size=dp(16), bold=True)
        no = Button(text="Отмена", color=(1, 1, 1, 1),
                    font_name=FONT_NAME, font_size=dp(16), bold=True)
        btns.add_widget(yes)
        btns.add_widget(no)
        content.add_widget(btns)
        popup = Popup(title="Сброс правок", content=content,
                      size_hint=(0.5, 0.35), title_color=LABEL_LIGHT,
                      title_font=FONT_NAME, auto_dismiss=False)

        def do_reset(*a):
            key = self._get_key()
            self.app.data.setdefault('result_overrides', {})[key] = {}
            self.app.safe_save(self.app.data)
            popup.dismiss()
            self.load_timesheet()

        yes.bind(on_press=do_reset)
        no.bind(on_press=popup.dismiss)
        bind_enter_key(popup, do_reset)
        popup.open()

    def load_timesheet(self):
        if getattr(self, '_loading', False):
            return
        self._loading = True
        try:
            # --- ПЕРЕСЧЁТ ВИДИМЫХ КОЛОНОК ---
            self._right_cols = get_visible_right_columns()
            if not self._right_cols:
                self._right_cols = list(RIGHT_COLUMNS)
                
            # Сбрасываем ширины, чтобы они пересчитались под новый месяц
            self._min_right_widths = [0] * len(self._right_cols)

            # Список для новых виджетов (строим в памяти)
            new_widgets = []

            self.day_inputs.clear()
            self.total_labels.clear()
            self._all_day_headers = []
            self._all_day_rows = []

            key = self._get_key()
            y = int(self.year_spinner.text)
            m = MONTHS.index(self.month_spinner.text) + 1
            days_in_month = monthrange(y, m)[1]
            self._days_in_month = days_in_month
            ts = self.app.data['timesheets'].setdefault(key, {})

            day_types = [classify_day(y, m, d) for d in range(1, days_in_month + 1)]
            self._day_types = day_types

            night_flags = self.app.data.get('night_flags', {})
            overtime_flags = self.app.data.get('overtime_flags', {})
            no_weekends_flags = self.app.data.get('no_weekends_flags', {})
            self._emp_night = {}
            self._emp_overtime = {}
            employees = self._employees_for_ts()
            self._employees_order = [emp['id'] for emp in employees]
            for emp in employees:
                pos_name = emp.get('position', '')
                self._emp_night[emp['id']] = bool(night_flags.get(pos_name, False))
                self._emp_overtime[emp['id']] = bool(overtime_flags.get(pos_name, False))
                self._emp_no_weekends[emp['id']] = bool(no_weekends_flags.get(pos_name, False))

            W_NUM = dp(40)
            W_DAY = dp(36)
            ROW_H = dp(28)
            HEAD_TOP_H = dp(24)
            HEAD_BOT_H = dp(120)

            max_name_w = dp(100)
            max_pos_w  = dp(90)
            for emp in employees:
                nm_w = measure_text_width(emp.get('name', ''), font_size=14)
                ps_w = measure_text_width(emp.get('position', ''), font_size=14)
                if nm_w + dp(6) > max_name_w: 
                    max_name_w = nm_w + dp(6)
                if ps_w + dp(6) > max_pos_w:
                    max_pos_w = ps_w + dp(6)
            max_name_w = min(max_name_w, dp(500))
            max_pos_w  = min(max_pos_w,  dp(140)) 

            W_NAME = max_name_w
            W_POS  = max_pos_w

            row_heights = []
            for emp in employees:
                h_name = measure_text_height(emp.get('name', ''), W_NAME - dp(6))
                h_pos = measure_text_height(emp.get('position', ''), W_POS - dp(6))
                rh = max(ROW_H, h_name + dp(4), h_pos + dp(4)) 
                row_heights.append(rh)

            LEFT_W  = W_NUM + W_NAME + W_POS

            # ============ ПРАВЫЕ КОЛОНКИ ============
            right_widths = [max(dp(36), col[2]) for col in self._right_cols]

            for i, (label, key_, w) in enumerate(self._right_cols):
                vert_h = measure_text_height(label, 1000, font_size=9)
                req_w = vert_h + dp(16)
                if req_w > right_widths[i]:
                    right_widths[i] = req_w

            norm_hours_val = self._get_norm_hours()
            overrides_all = self.app.data.get('result_overrides', {}).get(key, {})

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
                    apply_overtime(res, norm_hours_val)
                else:
                    res['сверхурочные'] = 0.0

                emp_over = overrides_all.get(emp_id, {})
                for i, (_, key_, _) in enumerate(self._right_cols):
                    val = emp_over.get(key_, res.get(key_, 0))
                    if key_ in ('часы', 'сверхурочные', 'ночные', 'праздничные', 'выходные_часы'):
                        val_str = fmt_hours(val)
                    else:
                        val_str = str(val)
                    if val_str and val_str != '0':
                        req_w = measure_text_width(val_str, font_size=14) + dp(8)
                        if req_w > right_widths[i]:
                            right_widths[i] = req_w

            col_index_map = {col[1]: i for i, col in enumerate(self._right_cols)}
            for gname, gkeys in RIGHT_COLUMN_GROUPS:
                gvis = [k for k in gkeys if k in col_index_map]
                if not gvis:
                    continue
                gw = sum(right_widths[col_index_map[k]] for k in gvis)
                min_gw = measure_text_width(gname, font_size=11) + dp(24)
                if gw < min_gw:
                    diff = min_gw - gw
                    per_col = diff / len(gvis)
                    for k in gvis:
                        right_widths[col_index_map[k]] += per_col

            RIGHT_W = sum(right_widths)
            # ============ КОНЕЦ ПРАВЫХ КОЛОНОК ============

            # ============ ДНИ МЕСЯЦА ============
            results_hidden = getattr(self, '_results_hidden', False)
            right_w_for_days = 0 if results_hidden else RIGHT_W

            if self.width > 0:
                avail_w_est = max(0, self.width - dp(20) - LEFT_W - right_w_for_days)
                base_w = max(dp(36), avail_w_est / days_in_month) if avail_w_est > 0 else dp(36)
            else:
                base_w = dp(36)

            day_widths = [base_w] * days_in_month
            for emp in employees:
                emp_id = emp['id']
                day_data = ts.get(emp_id, {})
                for d in range(1, days_in_month + 1):
                    val = str(day_data.get(str(d), '')).strip()
                    if val:
                        req_w = measure_text_width(val, font_size=14) + dp(6)
                        if req_w > day_widths[d - 1]:
                            day_widths[d - 1] = req_w

            DAYS_W = sum(day_widths)
            # ============ КОНЕЦ ДНЕЙ ============

            self.LEFT_W = LEFT_W
            self.RIGHT_W = RIGHT_W

            BORDER_BLACK = (0, 0, 0, 1)
            LINE_T = 1

            # ============================================================
            # ВЕРХНЯЯ ЧАСТЬ ШАПКИ
            # ============================================================
            header_strip = BoxLayout(orientation='horizontal',
                                     size_hint_y=None, height=HEAD_TOP_H,
                                     spacing=0)

            def _spacer_bg(w):
                b = BoxLayout(size_hint=(None, 1), width=w, spacing=0)
                with b.canvas.before:
                    Color(*HEADER_BG)
                    _r = Rectangle(pos=b.pos, size=b.size)
                b.bind(pos=lambda i, v, r=_r: setattr(r, 'pos', v),
                       size=lambda i, v, r=_r: setattr(r, 'size', v))
                return b

            s_num = _spacer_bg(W_NUM)
            add_left_border(s_num, color=BORDER_BLACK, thickness=LINE_T)
            add_right_border(s_num, color=BORDER_BLACK, thickness=LINE_T)
            header_strip.add_widget(s_num)

            s_name = _spacer_bg(W_NAME)
            add_right_border(s_name, color=BORDER_BLACK, thickness=LINE_T)
            header_strip.add_widget(s_name)

            s_pos = _spacer_bg(W_POS)
            add_right_border(s_pos, color=BORDER_BLACK, thickness=LINE_T)
            header_strip.add_widget(s_pos)

            c_holder = BoxLayout(size_hint=(1, 1))
            with c_holder.canvas.before:
                Color(*HEADER_BG)
                _ch = Rectangle(pos=c_holder.pos, size=c_holder.size)
            c_holder.bind(pos=lambda i, v, r=_ch: setattr(r, 'pos', v),
                          size=lambda i, v, r=_ch: setattr(r, 'size', v))
            c_lbl = Label(text="Числа месяца", bold=True, color=HEADER_FG,
                          font_size=dp(11), halign='center', valign='middle',
                          font_name=FONT_NAME)
            c_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
            c_holder.add_widget(c_lbl)
            header_strip.add_widget(c_holder)

            visible_keys = set(c[1] for c in self._right_cols)
            right_top = BoxLayout(size_hint=(None, 1), width=RIGHT_W, spacing=0)
            self.right_top = right_top
            add_left_border(right_top, color=BORDER_BLACK, thickness=LINE_T)

            group_widgets = []
            group_list = []
            for gname, gkeys in RIGHT_COLUMN_GROUPS:
                gvis = [k for k in gkeys if k in visible_keys]
                if not gvis:
                    continue
                gw = sum(right_widths[col_index_map[k]] for k in gvis)
                group_list.append((gname, gw))

            for i, (gname, gw) in enumerate(group_list):
                is_last = (i == len(group_list) - 1)
                width = gw if is_last else gw - 1
                g = self._lbl_bg(gname, width, HEAD_TOP_H)
                group_widgets.append(g)
                right_top.add_widget(g)
                if not is_last:
                    right_top.add_widget(vsep(color=BORDER_BLACK, thickness=LINE_T))

            self._right_top_groups = group_widgets
            header_strip.add_widget(right_top)

            add_bottom_border(c_holder, color=BORDER_BLACK, thickness=LINE_T)
            add_bottom_border(right_top, color=BORDER_BLACK, thickness=LINE_T)

            new_widgets.append(header_strip)

            # ============================================================
            # НИЖНЯЯ ЧАСТЬ ШАПКИ (фиксированная)
            # ============================================================
            header_bottom = BoxLayout(orientation='horizontal', size_hint_y=None,
                                      height=HEAD_BOT_H, spacing=0)

            lh = BoxLayout(size_hint=(None, 1), width=LEFT_W, spacing=0)
            c = self._lbl_bg("№", W_NUM, HEAD_BOT_H)
            add_left_border(c, color=BORDER_BLACK, thickness=LINE_T)
            add_right_border(c, color=BORDER_BLACK, thickness=LINE_T)
            lh.add_widget(c)
            c = self._lbl_bg("Фамилия И.О.", W_NAME, HEAD_BOT_H)
            add_right_border(c, color=BORDER_BLACK, thickness=LINE_T)
            lh.add_widget(c)
            c = self._lbl_bg("Должность", W_POS, HEAD_BOT_H)
            add_right_border(c, color=BORDER_BLACK, thickness=LINE_T)
            lh.add_widget(c)
            add_bottom_border(lh, color=BORDER_BLACK, thickness=LINE_T)

            days_head_container = StencilView(size_hint=(1, 1))
            dh = BoxLayout(size_hint=(None, None), size=(DAYS_W, HEAD_BOT_H),
                           spacing=0)
            self._dh = dh
            for i, dt in enumerate(day_types):
                wd_idx = date(y, m, i + 1).weekday()
                day_hdr = DayHeader(i + 1, day_type=dt,
                                         weekday_idx=wd_idx,
                                         show_right=True,
                                         size_hint=(None, None),
                                         size=(day_widths[i], HEAD_BOT_H))
                self._all_day_headers.append(day_hdr)
                dh.add_widget(day_hdr)
            add_bottom_border(dh, color=BORDER_BLACK, thickness=LINE_T)
            days_head_container.add_widget(dh)

            def _on_header_touch(inst, touch):
                if touch.is_mouse_scrolling:
                    step = 0.15
                    if touch.button in ('scrollup', 'scrollleft'):
                        days_sv.scroll_x = max(0.0, days_sv.scroll_x - step)
                    else:
                        days_sv.scroll_x = min(1.0, days_sv.scroll_x + step)
                    return True
                return False
            
            dh.bind(on_touch_down=_on_header_touch)
            
            rh_box = BoxLayout(size_hint=(None, 1), width=RIGHT_W, spacing=0)
            self.right_header = rh_box
            self._right_headers = []
            n = len(self._right_cols)
            for i, (label, key_, w) in enumerate(self._right_cols):
                last = (i == n - 1)
                vl = VerticalLabel(text=label, font_size=9, pad_top=6,
                                    size_hint=(None, None),
                                    size=(right_widths[i] if last else right_widths[i] - LINE_T, HEAD_BOT_H))
                if i == 0:
                    add_left_border(vl, color=BORDER_BLACK, thickness=LINE_T)
                rh_box.add_widget(vl)
                self._right_headers.append(vl)
                if not last:
                    rh_box.add_widget(vsep(color=BORDER_BLACK, thickness=LINE_T))
            add_bottom_border(rh_box, color=BORDER_BLACK, thickness=LINE_T)

            header_bottom.add_widget(lh)
            header_bottom.add_widget(days_head_container)
            header_bottom.add_widget(rh_box)
            new_widgets.append(header_bottom)

            # ============================================================
            # СОДЕРЖИМОЕ (прокручиваемая часть)
            # ============================================================
            body = BoxLayout(orientation='horizontal', spacing=0, size_hint=(1, None))

            left_sv = SmartScrollView(do_scroll_x=False, do_scroll_y=True,
                                 size_hint=(None, 1), width=LEFT_W,
                                 bar_width=0, scroll_type=['content'],
                                 effect_cls=NoOverscrollEffect)
            left_grid = GridLayout(cols=1, size_hint=(None, None), spacing=0)
            left_grid.width = LEFT_W
            _stretch_grid(left_grid, left_sv)

            for idx, emp in enumerate(employees):
                rh = row_heights[idx]
                is_extra = emp.get('is_extra', False)
                
                r = BoxLayout(size_hint=(None, None),
                              size=(LEFT_W, rh), spacing=0)
                
                if is_extra:
                    with r.canvas.before:
                        Color(0.20, 0.25, 0.35, 1) 
                        _rect = Rectangle(pos=r.pos, size=r.size)
                    r.bind(pos=lambda i, v, rect=_rect: setattr(rect, 'pos', v),
                           size=lambda i, v, rect=_rect: setattr(rect, 'size', v))

                num_lbl = self._lbl(str(idx + 1), W_NUM, rh)
                add_left_border(num_lbl, color=BORDER_BLACK, thickness=LINE_T)
                add_right_border(num_lbl, color=BORDER_BLACK, thickness=LINE_T)
                r.add_widget(num_lbl)

                name_color = (1.0, 0.75, 0.3, 1) if is_extra else config.TABLE_FG
                pos_color = (0.8, 0.8, 0.85, 1) if is_extra else config.TABLE_FG

                name_lbl = self._lbl(emp.get('name', ''),
                                      W_NAME, rh, align_left=True, shorten=False, color=name_color)
                add_right_border(name_lbl, color=BORDER_BLACK, thickness=LINE_T)
                r.add_widget(name_lbl)

                pos_lbl = self._lbl(emp.get('position', ''), W_POS, rh,
                                     align_left=True, shorten=False, color=pos_color)
                add_right_border(pos_lbl, color=BORDER_BLACK, thickness=LINE_T)
                r.add_widget(pos_lbl)

                add_bottom_border(r)
                left_grid.add_widget(r)
            left_sv.add_widget(left_grid)
            body.add_widget(left_sv)

            # ДНИ МЕСЯЦА (do_scroll_y=True)
            days_sv = HorizontalScrollView(do_scroll_x=True, do_scroll_y=True,
                                            bar_width=0,
                                            scroll_type=['content'],
                                            effect_cls=NoOverscrollEffect)
            self._days_sv = days_sv
            
            days_grid = GridLayout(cols=1, size_hint=(None, None), spacing=0)
            days_grid.width = DAYS_W 
            _stretch_grid(days_grid, days_sv)
            self._days_grid = days_grid

            for idx, emp in enumerate(employees):
                rh = row_heights[idx]
                emp_id = emp['id']
                r = BoxLayout(size_hint=(None, None),
                              size=(DAYS_W, rh), spacing=0)
                self._all_day_rows.append(r)
                day_values = ts.get(emp_id, {})
                cells = []
                for d in range(1, days_in_month + 1):
                    cb = self._make_day_nav_callback(emp_id, d)
                    cell = DayCell(text=str(day_values.get(str(d), '')),
                                    day_type=day_types[d - 1],
                                    show_right=True,
                                    on_key_callback=cb,
                                    on_cell_touch_down=self._on_cell_touch_down,
                                    extra_key_callback=self._on_extra_key,
                                    size_hint=(None, None),
                                    size=(day_widths[d - 1], rh))
                    cell.input.bind(text=lambda inst, val, eid=emp_id, d=d:
                                    self._on_day_change(eid, d))
                    r.add_widget(cell)
                    cells.append(cell)
                add_bottom_border(r)
                self.day_inputs[emp_id] = cells
                days_grid.add_widget(r)
            days_sv.add_widget(days_grid)
            body.add_widget(days_sv)

            def _update_days_header(*args):
                try:
                    dh.y = days_head_container.y
                    sx = max(0.0, min(1.0, days_sv.scroll_x))
                    max_scroll = max(0, dh.width - days_sv.width)
                    if max_scroll > 0:
                        dh.x = days_head_container.x - (sx * max_scroll)
                    else:
                        dh.x = days_head_container.x
                except Exception:
                    pass
            
            def _delayed_update_days_header(*args):
                Clock.schedule_once(_update_days_header, 0)

            self._update_days_header_func = _update_days_header
            days_sv.bind(scroll_x=_update_days_header)
            days_sv.bind(size=_delayed_update_days_header)
            days_head_container.bind(pos=_delayed_update_days_header, size=_delayed_update_days_header)
            
            Clock.schedule_once(_update_days_header, 0)

            right_sv = SmartScrollView(do_scroll_x=False, do_scroll_y=True,
                                  size_hint=(None, 1), width=RIGHT_W,
                                  bar_width=0, scroll_type=['content'],
                                  effect_cls=NoOverscrollEffect)
            self._right_sv = right_sv
            self.right_sv = right_sv
            right_grid = GridLayout(cols=1, size_hint=(None, None), spacing=0)
            right_grid.width = RIGHT_W
            _stretch_grid(right_grid, right_sv)
            
            self._right_grid = right_grid
            self._right_rows = []
            self._right_col_cells = [[] for _ in range(len(self._right_cols))]
            for idx, emp in enumerate(employees):
                rh = row_heights[idx]
                emp_id = emp['id']
                r = BoxLayout(size_hint=(None, None),
                              size=(RIGHT_W, rh), spacing=0)
                self._right_rows.append(r)
                labels = {}
                last_i = len(self._right_cols) - 1
                for i, (_, key_, w) in enumerate(self._right_cols):
                    cb = self._make_result_nav_callback(emp_id, i)
                    cell = ResultCell(
                        text='0', fg_color=config.TABLE_FG,
                        show_left=(i == 0),
                        show_right=(i < last_i),
                        border_color=BORDER_BLACK, border_th=LINE_T,
                        size_hint=(None, None), size=(right_widths[i], rh),
                        on_key_callback=cb,
                        on_cell_touch_down=self._on_cell_touch_down,
                        extra_key_callback=self._on_extra_key,
                    )
                    cell.input.bind(
                        text=lambda inst, val, eid=emp_id, k=key_:
                            self._on_result_change(eid, k, val),
                        focus=lambda inst, val, eid=emp_id, k=key_:
                            self._on_result_focus(eid, k, val),
                    )
                    cell.input.bind(
                        on_text_validate=lambda inst, eid=emp_id, k=key_:
                            self._commit_one(eid, k)
                    )
                    r.add_widget(cell)
                    labels[key_] = cell
                    self._right_col_cells[i].append(cell)
                self.total_labels[emp_id] = labels
                add_bottom_border(r)
                right_grid.add_widget(r)
            right_sv.add_widget(right_grid)
            body.add_widget(right_sv)

            new_widgets.append(body)
            sync_vertical([left_sv, days_sv, right_sv])

            for emp_id in list(self.day_inputs.keys()):
                self._recalc_totals(emp_id)

            self._last_key = key
            
            # --- ДИНАМИЧЕСКАЯ ВЫСОТА ТАБЛИЦЫ ---
            self._current_body = body
            self._current_header_top = header_strip
            self._current_header_bottom = header_bottom
            self._current_content_h = sum(row_heights)
            
            self._built_names = {emp['id']: emp.get('name', '') for emp in employees}
            self._built_positions = {emp['id']: emp.get('position', '') for emp in employees}

            # Обновляем высоту контейнера ДО очистки, чтобы избежать скачка интерфейса
            main_h = 0
            try:
                avail_h = self.height - self.top_bar.height - self.hint_wrap.height - dp(10)
                avail_h -= header_strip.height + header_bottom.height
                target_h = min(avail_h, self._current_content_h)
                if target_h < dp(50):
                    target_h = dp(50)
                
                body.height = target_h
                main_h = header_strip.height + header_bottom.height + target_h
            except Exception:
                pass

            # === СКРЫТАЯ ЗАМЕНА (Убирает мерцание и скачки) ===
            self.main_container.opacity = 0
            
            if main_h > 0:
                self.main_container.height = main_h
                
            self.main_container.clear_widgets()
            for w in new_widgets:
                self.main_container.add_widget(w)
                
            if getattr(self, '_finalize_ev', None):
                self._finalize_ev.cancel()

            def _finalize(dt):
                try:
                    self._resize_body()
                    self._apply_results_visibility()
                except Exception:
                    pass
                finally:
                    self.main_container.opacity = 1

            self._finalize_ev = Clock.schedule_once(_finalize, 0.02)

        finally:
            self._loading = False

    @staticmethod
    def _lbl(text, w, h, bold=False, align_left=False, shorten=False, color=None):
        if color is None:
            color = config.TABLE_FG
            
        lbl = Label(text=text, bold=bold,
                    size_hint=(None, None), size=(w, h),
                    color=color,
                    font_name=FONT_NAME, font_size=dp(14),
                    halign='left' if align_left else 'center',
                    valign='middle',
                    shorten=shorten,
                    shorten_from='right',
                    text_size=(w - 6, h))
        return lbl

    @staticmethod
    def _lbl_bg(text, w, h):
        holder = BoxLayout(size_hint=(None, None), size=(w, h))
        with holder.canvas.before:
            Color(*HEADER_BG)
            rect = Rectangle(pos=holder.pos, size=holder.size)
        holder.bind(pos=lambda inst, val: setattr(rect, 'pos', val),
                    size=lambda inst, val: setattr(rect, 'size', val))
        
        lbl = Label(text=text, bold=True, color=HEADER_FG,
                    font_name=FONT_NAME,
                    font_size=dp(11),
                    halign='center', valign='middle')
        
        # ГЛАВНОЕ ИСПРАВЛЕНИЕ: привязываем text_size к размерам контейнера.
        # Теперь при расширении группы текст не будет обрезаться.
        lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0] - dp(8), val[1])))
        
        holder.add_widget(lbl)
        return holder

    def _commit_one(self, emp_id, col_key):
        cell = self.total_labels.get(emp_id, {}).get(col_key)
        if cell is None:
            return
        txt = cell.input.text.strip()
        emp_over = self._get_overrides().setdefault(emp_id, {})
        if txt == '':
            emp_over.pop(col_key, None)
        else:
            emp_over[col_key] = txt
        cell.input.focus = False
        self._schedule_save()
        self._recalc_totals(emp_id)

    def _recalc_totals(self, emp_id):
        cells = self.day_inputs.get(emp_id, [])
        values = [c.input.text for c in cells]
        night_on = self._emp_night.get(emp_id, False)
        overtime_on = self._emp_overtime.get(emp_id, False)
        no_weekends_on = self._emp_no_weekends.get(emp_id, False)
        
        res = analyze_row(values, self._day_types, night_on, no_weekends_on)

        if overtime_on:
            apply_overtime(res, self._get_norm_hours())
        else:
            res['сверхурочные'] = 0.0

        overrides = (self.app.data.get('result_overrides', {})
                     .get(self._get_key(), {})
                     .get(emp_id, {}))

        labels = self.total_labels.get(emp_id, {})
        self._suppress_result_cb = True
        try:
            for k, cell in labels.items():
                if cell.input.focused:
                    continue
                if k in overrides:
                    new_text = str(overrides[k])
                else:
                    val = res.get(k, 0)
                    if k in ('часы', 'сверхурочные', 'ночные', 'праздничные', 'выходные_часы'):
                        new_text = fmt_hours(val)
                    else:
                        new_text = str(val)
                if cell.input.text != new_text:
                    cell.text = new_text
        finally:
            self._suppress_result_cb = False
            
        # Авто-подгонка правой колонки при перерасчете
        if getattr(self, '_is_syncing', False):
            return
        if getattr(self, '_auto_fit_right_ev', None):
            self._auto_fit_right_ev.cancel()
        self._auto_fit_right_ev = Clock.schedule_once(lambda dt: self._auto_fit_right_columns(), 0.5)
        
    def show_columns_popup(self, *args):
        from kivy.uix.checkbox import CheckBox

        content = BoxLayout(orientation='vertical', spacing=10, padding=15)

        title_lbl = Label(
            text=("Выберите итоги, которые будут отображаться\n"
                  "в таблице и в Excel-отчёте (настройка — для вас):"),
            color=LABEL_LIGHT, halign='center', valign='middle',
            font_name=FONT_NAME, font_size=dp(14),
            size_hint_y=None, height=dp(40),
            outline_color=(0, 0, 0, 1), outline_width=1)
        content.add_widget(title_lbl)

        scroll = ScrollView(scroll_type=['bars'],
                            effect_cls=NoOverscrollEffect)
        
        main_grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(12))
        main_grid.bind(minimum_height=main_grid.setter('height'))

        current = get_local_visible_columns()
        cur_set = (set(c[1] for c in RIGHT_COLUMNS)
                   if current is None else set(current))

        checkboxes = {}
        col_by_key = {c[1]: c for c in RIGHT_COLUMNS}

        for group_name, group_keys in RIGHT_COLUMN_GROUPS:
            # Заголовок группы
            hdr = Label(text=group_name, bold=True,
                        color=(1, 0.7, 0.3, 1), font_name=FONT_NAME,
                        font_size=dp(14), size_hint_y=None, height=dp(24),
                        halign='left', valign='middle')
            hdr.bind(size=lambda i, v: setattr(i, 'text_size', (v[0]-10, v[1])))
            main_grid.add_widget(hdr)

            # Сетка для чекбоксов (2 колонки)
            items_grid = GridLayout(cols=2, size_hint_y=None, spacing=[dp(20), dp(4)])
            items_grid.bind(minimum_height=items_grid.setter('height'))

            for key in group_keys:
                col = col_by_key.get(key)
                if col is None:
                    continue
                label = col[0]
                is_on = key in cur_set

                # Каждая пара (чекбокс + текст) в своём BoxLayout
                row = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(6))
                
                cb = CheckBox(active=is_on, size_hint=(None, None), size=(dp(28), dp(28)),
                              color=((0.30, 0.90, 0.40, 1) if is_on else (0.85, 0.85, 0.85, 1)))
                cb.bind(active=lambda inst, val: setattr(inst, 'color', (0.30, 0.90, 0.40, 1) if val else (0.85, 0.85, 0.85, 1)))
                checkboxes[key] = cb
                row.add_widget(cb)

                lbl = Label(text=label, color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(13),
                            halign='left', valign='middle', size_hint_x=1, shorten=True, shorten_from='right')
                lbl.bind(size=lambda i, v: setattr(i, 'text_size', (v[0], v[1])))
                row.add_widget(lbl)

                items_grid.add_widget(row)

            # Если элементов в группе нечётное количество, добавляем пустышку для выравнивания
            if len(group_keys) % 2 != 0:
                items_grid.add_widget(Widget(size_hint_y=None, height=dp(30)))

            main_grid.add_widget(items_grid)

        scroll.add_widget(main_grid)
        content.add_widget(scroll)

        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=8)
        save_btn = Button(text="Сохранить",
                          background_color=(0.3, 0.7, 0.3, 1),
                          color=(1, 1, 1, 1), font_name=FONT_NAME, bold=True)
        all_btn = Button(text="Показать все",
                         background_color=(0.35, 0.55, 0.85, 1),
                         color=(1, 1, 1, 1), font_name=FONT_NAME, bold=True)
        cancel_btn = Button(text="Отмена", color=(1, 1, 1, 1),
                            font_name=FONT_NAME, bold=True)
        btns.add_widget(save_btn)
        btns.add_widget(all_btn)
        btns.add_widget(cancel_btn)
        content.add_widget(btns)

        # Сделал окно чуть уже, но выше, так как оно теперь аккуратное
        popup = Popup(title="Отображаемые итоги", content=content,
                      size_hint=(None, 0.75), width=dp(720), title_color=LABEL_LIGHT,
                      title_font=FONT_NAME, auto_dismiss=False)

        def do_save(*a):
            keys = [k for k, cb in checkboxes.items() if cb.active]
            if not keys:
                err_c = BoxLayout(orientation='vertical', spacing=10, padding=10)
                err_c.add_widget(Label(
                    text="Нельзя скрыть все итоги.\nВыберите хотя бы один.",
                    color=LABEL_LIGHT, halign='center', valign='middle',
                    font_name=FONT_NAME, font_size=dp(14)))
                ok = Button(text="ОК", size_hint_y=None, height=dp(40),
                            background_color=(0.3, 0.7, 0.3, 1),
                            color=(1, 1, 1, 1), font_name=FONT_NAME, bold=True)
                err_c.add_widget(ok)
                ep = Popup(title="Внимание", content=err_c,
                           size_hint=(0.45, 0.32), title_color=LABEL_LIGHT,
                           title_font=FONT_NAME, auto_dismiss=False)
                ok.bind(on_press=ep.dismiss)
                ep.open()
                return
            set_local_visible_columns(keys)
            popup.dismiss()
            self.load_timesheet()

        def do_all(*a):
            for cb in checkboxes.values():
                cb.active = True

        save_btn.bind(on_press=do_save)
        all_btn.bind(on_press=do_all)
        cancel_btn.bind(on_press=popup.dismiss)
        
        bind_enter_key(popup, do_save)
        
        popup.open()