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
                    HEADER_BG, HEADER_FG)
from data_utils import (save_data, classify_day, analyze_row,
                        apply_overtime, fmt_hours, calc_norm_hours,
                        set_local_results_hidden, get_local_results_hidden)
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
        self._sync_body_height = None

        # --- ПЕРЕМЕННЫЕ ДЛЯ УПРАВЛЕНИЯ ВИДИМОСТЬЮ ИТОГОВ ---
        self._results_hidden = get_local_results_hidden()  # <--- Читаем настройку
        self.right_sv = None
        self.right_top = None
        self.right_header = None
        self.RIGHT_W = 0
        self.LEFT_W = 0
        self._all_day_headers = []
        self._all_day_rows = []
        self._days_grid = None
        self._dh = None
        self._update_days_header_func = None
        # ---------------------------------------------------

        self._shift_held = False
        from kivy.core.window import Window
        Window.bind(on_keyboard=self._on_window_keyboard,
                    on_key_down=self._on_win_key_down,
                    on_key_up=self._on_win_key_up)

        self._build()

    def _build(self):
        self.top_bar = BoxLayout(size_hint_y=None, height=dp(46), spacing=5,
                        padding=(5, 2, 5, 2))
        self.top_bar.add_widget(Label(text="Месяц:", size_hint_x=None, width=dp(70),
                             color=LABEL_LIGHT, font_name=FONT_NAME,
                             font_size=dp(15)))
        self.month_spinner = Spinner(text=MONTHS[datetime.now().month - 1],
                                     values=MONTHS, size_hint_x=None, width=dp(150),
                                     font_name=FONT_NAME,
                                     background_color=SPINNER_BG, color=SPINNER_FG,
                                     option_cls=LightSpinnerOption) # <--- ДОБАВИТЬ ЭТО
        self.top_bar.add_widget(self.month_spinner)

        self.top_bar.add_widget(Label(text="Год:", size_hint_x=None, width=dp(50),
                             color=LABEL_LIGHT, font_name=FONT_NAME,
                             font_size=dp(15)))
        self.year_spinner = Spinner(text=str(datetime.now().year),
                                    values=YEARS, size_hint_x=None, width=dp(100),
                                    font_name=FONT_NAME,
                                    background_color=SPINNER_BG, color=SPINNER_FG,
                                    option_cls=LightSpinnerOption) # <--- ДОБАВИТЬ ЭТО
        self.top_bar.add_widget(self.year_spinner)

        self.top_bar.add_widget(Widget())

        apply_btn = Button(text="Применить правки", size_hint_x=None, width=dp(170),
                           font_name=FONT_NAME, font_size=dp(15), bold=True,
                           background_color=(0.25, 0.55, 0.85, 1),
                           color=(1, 1, 1, 1))
        apply_btn.bind(on_press=lambda *a: self.apply_overrides())
        self.top_bar.add_widget(apply_btn)

        reset_btn = Button(text="Сбросить правки",
                           size_hint_x=None, width=dp(170),
                           font_name=FONT_NAME, font_size=dp(15), bold=True,
                           background_color=(0.5, 0.4, 0.75, 1),
                           color=(1, 1, 1, 1))
        reset_btn.bind(on_press=lambda *a: self.reset_overrides())
        self.top_bar.add_widget(reset_btn)

        # --- КНОПКА СКРЫТИЯ/ОТОБРАЖЕНИЯ ИТОГОВ ---
        self.toggle_btn = Button(
            text="Показать итоги" if self._results_hidden else "Скрыть итоги",
            size_hint_x=None, width=dp(150),
            font_name=FONT_NAME, font_size=dp(15), bold=True,
            background_color=(0.3, 0.7, 0.3, 1) if self._results_hidden else (0.4, 0.6, 0.8, 1), 
            color=(1, 1, 1, 1)
        )
        self.toggle_btn.bind(on_press=self.toggle_results)
        self.top_bar.add_widget(self.toggle_btn)
        # ------------------------------------------------

        clear_btn = Button(text="Очистить", size_hint_x=None, width=dp(140),
                           font_name=FONT_NAME, font_size=dp(15), bold=True,
                           background_color=(0.9, 0.55, 0.2, 1), color=(1, 1, 1, 1))
        clear_btn.bind(on_press=lambda *a: self.confirm_clear())
        self.top_bar.add_widget(clear_btn)
        self.add_widget(self.top_bar)

        self.main_container = BoxLayout(orientation='vertical', spacing=0, size_hint_y=None, 
                                        padding=(dp(10), 0, dp(10), 0)) # <--- ДОБАВЛЕНЫ ОТСТУПЫ
        self.add_widget(self.main_container)

        # Распорка, чтобы сдвинуть блоки вниз
        self.add_widget(Widget(size_hint_y=1))

        # --- Отступ между таблицей и блоком временных сотрудников (70dp) ---
        self.spacer_gap = Widget(size_hint_y=None, height=dp(70))
        self.add_widget(self.spacer_gap)

        # --- БЛОК ДОПОЛНИТЕЛЬНЫХ СОТРУДНИКОВ ---
        self.extra_wrapper = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), padding=(dp(20), 0, dp(20), 0))
        
        # Растягиваем контейнер на всю ширину
        self.extra_container = BoxLayout(orientation='vertical', size_hint=(1, 1), spacing=dp(5))
        
        top_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=10)
        lbl = Label(text="Временные сотрудники (на этот месяц):", color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_x=None, width=dp(320), halign='left', valign='middle')
        lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        top_row.add_widget(lbl)
        
        add_btn = Button(text="+ Добавить", size_hint_x=None, width=dp(120), font_name=FONT_NAME, background_color=config.EXIT_BG, color=(1,1,1,1))
        add_btn.bind(on_press=self.show_add_extra_popup)
        top_row.add_widget(add_btn)
        top_row.add_widget(Widget()) # Отодвигает кнопку влево
        self.extra_container.add_widget(top_row)

        # Шапка таблицы (фиксированная, вне скролла)
        self.extra_header = BoxLayout(size_hint_y=None, height=dp(30), spacing=0)
        with self.extra_header.canvas.before:
            Color(*HEADER_BG)
            self._eh_rect = Rectangle(pos=self.extra_header.pos, size=self.extra_header.size)
        self.extra_header.bind(pos=lambda i,v: setattr(self._eh_rect, 'pos', v), size=lambda i,v: setattr(self._eh_rect, 'size', v))
        
        # Ширина колонок: ФИО (350), Должность (растягивается), Действие (100)
        self.extra_header.add_widget(Label(text="ФИО", color=HEADER_FG, font_name=FONT_NAME, size_hint_x=None, width=dp(350), bold=True))
        self.extra_header.add_widget(vsep(color=(0.5, 0.5, 0.5, 1)))
        self.extra_header.add_widget(Label(text="Должность", color=HEADER_FG, font_name=FONT_NAME, size_hint_x=1, bold=True))
        self.extra_header.add_widget(vsep(color=(0.5, 0.5, 0.5, 1)))
        self.extra_header.add_widget(Label(text="Действие", color=HEADER_FG, font_name=FONT_NAME, size_hint_x=None, width=dp(100), bold=True))
        
        add_top_border(self.extra_header, color=(0.5, 0.5, 0.5, 1))
        add_bottom_border(self.extra_header, color=(0.5, 0.5, 0.5, 1))
        self.extra_container.add_widget(self.extra_header)

        # Скролл со списком (убираем scrollbar)
        self.extra_scroll = ScrollView(size_hint_y=None, height=0, do_scroll_x=False, scroll_type=['content'])
        self.extra_emp_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=0)
        self.extra_emp_box.bind(minimum_height=self.extra_emp_box.setter('height'))
        self.extra_scroll.add_widget(self.extra_emp_box)
        self.extra_container.add_widget(self.extra_scroll)
        
        self.extra_wrapper.add_widget(self.extra_container)
        self.add_widget(self.extra_wrapper)
        # ---------------------------------------

        # --- ОТСТУП СНИЗУ ПОД ТАБЛИЦЕЙ ВРЕМЕННЫХ СОТРУДНИКОВ ---
        self.bottom_margin = Widget(size_hint_y=None, height=dp(20))
        self.add_widget(self.bottom_margin)

        HINT_BG   = config.TOPBAR_BG
        HINT_FG   = (0.88, 0.90, 0.94, 1)
        HINT_CODE = (1.00, 0.85, 0.35, 1)
        HINT_DASH = (0.40, 0.42, 0.48, 1)

        hint_items = [
            ('В',    '  выходной'),
            ('О',    '  трудовой отпуск'),
            ('Б',    '  больничный'),
            ('А',    '  за свой счёт'),
            ('Р',    '  отпуск по родам'),
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
                              height=dp(64),
                              padding=(dp(6), dp(4), dp(6), dp(4)))
        with self.hint_wrap.canvas.before:
            Color(*HINT_BG)
            _hw = Rectangle(pos=self.hint_wrap.pos, size=self.hint_wrap.size)
        self.hint_wrap.bind(pos=lambda i, v, r=_hw: setattr(r, 'pos', v),
                       size=lambda i, v, r=_hw: setattr(r, 'size', v))

        hint_grid = GridLayout(cols=7, size_hint_y=None, height=dp(56),
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
        
        # Прижимаем условные обозначения к низу
        self.add_widget(self.hint_wrap)

        self.month_spinner.bind(text=self._on_period_change)
        self.year_spinner.bind(text=self._on_period_change)

        # Автоматический пересчёт ширины колонок при изменении размера окна
        self.bind(width=lambda *a: Clock.schedule_once(
            lambda dt: self._apply_results_visibility(), 0))

        self._refresh_extra_list()
        self.load_timesheet()

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
            
        set_local_results_hidden(self._results_hidden)  # <--- Сохраняем настройку
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
            
        # Пересчет ширины колонок дней месяца
        if getattr(self, 'LEFT_W', 0) and self._days_in_month > 0:
            # Учитываем отступы контейнера (по 10dp с каждой стороны)
            avail_w = self.width - dp(20) - self.LEFT_W - w 
            new_w_day = max(dp(46), int(avail_w / self._days_in_month))
            
            for hdr in getattr(self, '_all_day_headers', []):
                hdr.width = new_w_day
            for row in getattr(self, '_all_day_rows', []):
                row.width = self._days_in_month * new_w_day
                for child in row.children:
                    if hasattr(child, 'width'):
                        child.width = new_w_day
                        
            # БЫЛО:
            # if getattr(self, '_days_grid', None) is not None:
            #     self._days_grid.width = self._days_in_month * new_w_day

            # СТАЛО:
            if getattr(self, '_days_grid', None) is not None:
                # Так как мы привязали width к minimum_width в load_timesheet,
                # нам достаточно обновить ширину дочерних элементов (строк и ячеек).
                # GridLayout сам подстроит свою ширину под них.
                pass
                
            if getattr(self, '_dh', None) is not None:
                self._dh.width = self._days_in_month * new_w_day
            
            self.W_DAY = new_w_day
            
            # --- НОВЫЙ КОД: Сброс прокрутки в 0, если всё помещается ---
            if getattr(self, '_days_sv', None) is not None and getattr(self, '_days_grid', None) is not None:
                if self._days_grid.width <= self._days_sv.width:
                    self._days_sv.scroll_x = 0
            # -----------------------------------------------------------
            
        if self._sync_body_height:
            Clock.schedule_once(self._sync_body_height, 0)
            
        if getattr(self, '_update_days_header_func', None):
            # Несколько вызовов, чтобы шапка точно выровнялась после перерисовки
            Clock.schedule_once(self._update_days_header_func, 0)
            Clock.schedule_once(self._update_days_header_func, 0.05)
            Clock.schedule_once(self._update_days_header_func, 0.1)
    # =======================================================================

    def _get_active_dept(self):
        """Возвращает отдел, по которому сейчас ведется табель (первый отмеченный)."""
        for emp in self.app.data.get('employees', []):
            if emp.get('show_in_timesheet', False):
                return emp.get('department', '')
        return ''

    def _get_month_dict(self, key):
        """Безопасно достает словарь отделов для указанного месяца. 
        Конвертирует старый формат (список) в новый (словарь)."""
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

    def _refresh_extra_list(self):
        self.extra_emp_box.clear_widgets()
        key = self._get_key()
        dept = self._get_active_dept()
        
        month_dict = self._get_month_dict(key)
        extra = month_dict.get(dept, [])

        self.extra_header.height = dp(30)
        
        if not dept:
            empty_lbl = Label(
                text="Сначала выберите отдел на вкладке «Рабочий персонал»", 
                color=(0.8, 0.6, 0.4, 1), 
                font_name=FONT_NAME, 
                size_hint_y=None, 
                height=dp(34)
            )
            self.extra_emp_box.add_widget(empty_lbl)
            self.extra_container.height = dp(36) + dp(5) + dp(30) + dp(34) + dp(5)
            self.extra_wrapper.height = self.extra_container.height
            return

        for emp in extra:
            # Оставляем высоту строки 34, чтобы кнопки не слипались
            r_box = BoxLayout(size_hint_y=None, height=dp(34), spacing=0)
            
            # ФИО
            n_lbl = Label(text=emp['name'], color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_x=None, width=dp(350), halign='left', valign='middle', padding=(dp(10), 0), shorten=True, shorten_from='right')
            n_lbl.bind(size=lambda i, v: setattr(i, 'text_size', (v[0]-dp(10), v[1])))
            r_box.add_widget(n_lbl)
            
            r_box.add_widget(vsep(color=(0.4, 0.4, 0.4, 1)))
            
            # Должность (растягиваем на всю ширину, убираем переносы строк)
            pos_text = emp['position'].replace('\n', ' ').strip()
            p_lbl = Label(text=pos_text, color=LABEL_LIGHT, font_name=FONT_NAME, size_hint_x=1, halign='left', valign='middle', padding=(dp(10), 0), shorten=True, shorten_from='right')
            p_lbl.bind(size=lambda i, v: setattr(i, 'text_size', (v[0]-dp(10), v[1])))
            r_box.add_widget(p_lbl)
            
            r_box.add_widget(vsep(color=(0.4, 0.4, 0.4, 1)))
            
            # Действие (оборачиваем в AnchorLayout, чтобы кнопка была по центру и не растягивалась)
            btn_wrap = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_x=None, width=dp(100))
            d_btn = Button(
                text="Удалить", 
                size_hint=(None, None), 
                size=(dp(84), dp(24)), # Оставляем компактный размер
                font_name=FONT_NAME, 
                font_size=dp(12), 
                background_normal='', 
                background_color=(0.8, 0.3, 0.3, 1), 
                color=(1,1,1,1)
            )
            
            d_btn.bind(on_press=lambda *args, eid=emp['id']: self._delete_extra_emp(eid))
            btn_wrap.add_widget(d_btn)
            r_box.add_widget(btn_wrap)

            add_bottom_border(r_box, color=(0.4, 0.4, 0.4, 1))
            self.extra_emp_box.add_widget(r_box)
            
        if not extra:
            empty_lbl = Label(
                text="Нет добавленных сотрудников", 
                color=(0.6, 0.6, 0.6, 1), 
                font_name=FONT_NAME, 
                size_hint_y=None, 
                height=dp(34) # Тоже 34, чтобы не было скачков
            )
            self.extra_emp_box.add_widget(empty_lbl)

        # Пересчитываем высоту с учетом новой высоты строк (34)
        h = min(max(len(extra), 1) * dp(34), dp(170))
        self.extra_scroll.height = h
        self.extra_container.height = dp(36) + dp(5) + dp(30) + h + dp(5)
        self.extra_wrapper.height = self.extra_container.height
        
        if self._sync_body_height:
            Clock.schedule_once(self._sync_body_height, 0)

    def _show_selection_popup(self, title, items, callback):
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
        
        scroll = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=2)
        grid.bind(minimum_height=grid.setter('height'))
        
        popup = Popup(title=title, content=content, size_hint=(0.6, 0.5), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
        
        def do_select(val):
            callback(val)
            popup.dismiss()
            
        def rebuild_list(query=''):
            grid.clear_widgets()
            q = query.lower()
            for it in items:
                if q in it.lower():
                    btn = Button(
                        text=it, size_hint_y=None, height=dp(36), 
                        font_name=FONT_NAME, font_size=dp(14), 
                        background_normal='', background_color=(0.2, 0.2, 0.25, 1), color=(1,1,1,1),
                        halign='center', valign='middle',
                        shorten=True, shorten_from='right'
                    )
                    btn.bind(size=lambda instance, value: setattr(instance, 'text_size', (value[0] - 20, None)))
                    btn.bind(on_press=lambda *a, x=it: do_select(x))
                    grid.add_widget(btn)
                    
        search_input.bind(text=lambda inst, val: rebuild_list(val))
        rebuild_list()
        
        scroll.add_widget(grid)
        content.add_widget(scroll)
        
        close_btn = Button(text="Отмена", size_hint_y=None, height=dp(40), font_name=FONT_NAME, color=(1,1,1,1))
        close_btn.bind(on_press=popup.dismiss)
        content.add_widget(close_btn)
        
        popup.open()

    def show_add_extra_popup(self, *args):
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

        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        
        # --- Пружина сверху для центрирования ---
        content.add_widget(Widget(size_hint_y=1))
        
        all_names = sorted(list(set(e['name'] for e in self.app.data.get('employees', []))))
        positions = self.app.data.get('positions', [])
        
        # Контейнер для полей
        fields = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10)
        fields.bind(minimum_height=fields.setter('height'))
        
        # ФИО
        name_input = TextInput(
            multiline=False, font_size=dp(15), font_name=FONT_NAME,
            foreground_color=(0.05, 0.05, 0.05, 1),
            background_color=(1, 1, 1, 1),
            cursor_color=(0.10, 0.30, 0.70, 1),
            cursor_width=dp(2),
            padding=[dp(8), dp(10), dp(8), dp(10)],
            size_hint_y=None, height=dp(40),
            hint_text="Введите любую фамилию",
            halign='center'
        )
        name_btn = Button(text="Выбрать...", size_hint=(None, None), size=(dp(100), dp(40)), font_name=FONT_NAME)
        name_btn.bind(on_press=lambda *a: self._show_selection_popup("Выбор сотрудника", all_names, lambda val: setattr(name_input, 'text', val)))
        
        name_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=5)
        name_row.add_widget(name_input)
        name_row.add_widget(name_btn)
        
        # Должность (заменено на Label для гарантированного отображения в одну строку)
        pos_holder = BoxLayout(size_hint_y=None, height=dp(40))
        with pos_holder.canvas.before:
            Color(1, 1, 1, 1)
            self._pos_rect = Rectangle(pos=pos_holder.pos, size=pos_holder.size)
        pos_holder.bind(pos=lambda i, v: setattr(self._pos_rect, 'pos', v),
                        size=lambda i, v: setattr(self._pos_rect, 'size', v))
        
        pos_input = Label(
            text="", font_size=dp(15), font_name=FONT_NAME,
            color=(0.05, 0.05, 0.05, 1),
            halign='center', valign='middle', shorten=False
        )
        pos_input.bind(size=lambda i, v: setattr(i, 'text_size', v))
        pos_holder.add_widget(pos_input)
        
        pos_btn = Button(text="Выбрать...", size_hint=(None, None), size=(dp(100), dp(40)), font_name=FONT_NAME)
        pos_btn.bind(on_press=lambda *a: self._show_selection_popup("Выбор должности", positions, lambda val: setattr(pos_input, 'text', val)))
        
        pos_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=5)
        pos_row.add_widget(pos_holder)
        pos_row.add_widget(pos_btn)
        
        fields.add_widget(Label(text="ФИО сотрудника:", color=LABEL_LIGHT, font_name=FONT_NAME, halign='left', size_hint_y=None, height=dp(24)))
        fields.add_widget(name_row)
        fields.add_widget(Label(text="Должность:", color=LABEL_LIGHT, font_name=FONT_NAME, halign='left', size_hint_y=None, height=dp(24)))
        fields.add_widget(pos_row)
        
        content.add_widget(fields)
        
        # --- Пружина снизу (отделяет поля от кнопок) ---
        content.add_widget(Widget(size_hint_y=1))
        
        # --- Кнопки ---
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=10)
        ok = Button(text="Добавить", font_name=FONT_NAME, background_color=(0.3, 0.7, 0.3, 1), color=(1,1,1,1))
        cancel = Button(text="Отмена", font_name=FONT_NAME, color=(1,1,1,1))
        btns.add_widget(ok)
        btns.add_widget(cancel)
        content.add_widget(btns)
        
        popup = Popup(title=f"Добавить временного сотрудника (Отдел: {dept})", content=content, size_hint=(0.65, 0.55), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
        
        def do_add(*args):
            name = name_input.text.strip()
            pos = pos_input.text.strip()
            
            if not name or not pos:
                missing = []
                if not name: missing.append("ФИО")
                if not pos: missing.append("Должность")
                
                err_content = BoxLayout(orientation='vertical', spacing=10, padding=10)
                err_content.add_widget(Label(
                    text="Не выбрано:\n• " + "\n• ".join(missing),
                    color=LABEL_LIGHT, halign='center', valign='middle',
                    font_name=FONT_NAME, font_size=dp(15)
                ))
                err_btn = Button(text="ОК", size_hint_y=None, height=dp(40), font_name=FONT_NAME, background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1))
                err_content.add_widget(err_btn)
                err_popup = Popup(title="Внимание", content=err_content, size_hint=(0.45, 0.3), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
                err_btn.bind(on_press=err_popup.dismiss)
                err_popup.open()
                return
            
            key = self._get_key()
            month_dict = self._get_month_dict(key)
            extra = month_dict.setdefault(dept, [])
            
            new_id = f"extra_{key}_{int(datetime.now().timestamp() * 1000)}"
            extra.append({'id': new_id, 'name': name, 'position': pos, 'is_contract': True})
            save_data(self.app.data)
            popup.dismiss()
            self._refresh_extra_list()
            self.load_timesheet()
            
        ok.bind(on_press=do_add)
        cancel.bind(on_press=popup.dismiss)
        name_input.bind(on_text_validate=do_add)
        bind_enter_key(popup, do_add)
        popup.open()

    def _delete_extra_emp(self, eid):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(
            text="Удалить временного сотрудника?",
            color=LABEL_LIGHT, halign='center',
            font_name=FONT_NAME, font_size=dp(15),
            outline_color=(0, 0, 0, 1), outline_width=1))
        btns = BoxLayout(size_hint_y=None, height=dp(40), spacing=10)
        yes = Button(text="Удалить", background_color=(0.9, 0.35, 0.35, 1), color=(1, 1, 1, 1), font_name=FONT_NAME, font_size=dp(16), bold=True)
        no = Button(text="Отмена", color=(1, 1, 1, 1), font_name=FONT_NAME, font_size=dp(16), bold=True)
        btns.add_widget(yes)
        btns.add_widget(no)
        content.add_widget(btns)
        popup = Popup(title="Подтверждение", content=content, size_hint=(0.5, 0.35), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)

        def do_delete(*a):
            key = self._get_key()
            dept = self._get_active_dept()
            month_dict = self._get_month_dict(key)
            extra = month_dict.get(dept, [])
            month_dict[dept] = [e for e in extra if e['id'] != eid]
            
            save_data(self.app.data)
            popup.dismiss()
            self._refresh_extra_list()
            self.load_timesheet()

        yes.bind(on_press=do_delete)
        no.bind(on_press=popup.dismiss)
        bind_enter_key(popup, do_delete)
        popup.open()

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
        self._refresh_extra_list()
        self.load_timesheet()

    def _on_win_key_down(self, window, key, scancode, codepoint, modifiers):
        if 'shift' in (modifiers or []):
            self._shift_held = True
            NavTextInput.shift_state['held'] = True

    def _on_win_key_up(self, window, key, scancode):
        if key in (303, 304):
            self._shift_held = False
            NavTextInput.shift_state['held'] = False

    def _save_for_key(self, key):
        ts = self.app.data['timesheets'].setdefault(key, {})
        for emp_id, cells in self.day_inputs.items():
            emp_data = {}
            for d, cell in enumerate(cells, start=1):
                txt = cell.input.text.strip()
                if txt:
                    emp_data[str(d)] = txt
            ts[emp_id] = emp_data
        save_data(self.app.data)

    def _save_all(self, dt=0):
        self._save_for_key(self._get_key())

    def _schedule_save(self, *a):
        if self._save_event:
            self._save_event.cancel()
        self._save_event = Clock.schedule_once(self._save_all, 0.6)

    def _on_day_change(self, emp_id):
        self._recalc_totals(emp_id)
        self._schedule_save()

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
                    if 0 <= c < len(RIGHT_COLUMNS):
                        key_ = RIGHT_COLUMNS[c][1]
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
                    if 0 <= cc < len(RIGHT_COLUMNS):
                        key_ = RIGHT_COLUMNS[cc][1]
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
                    if 0 <= c < len(RIGHT_COLUMNS):
                        key_ = RIGHT_COLUMNS[c][1]
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
            for col_idx, (_, key_, _) in enumerate(RIGHT_COLUMNS):
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
                    if 0 <= cc < len(RIGHT_COLUMNS):
                        key_ = RIGHT_COLUMNS[cc][1]
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
        if col_idx < 0 or col_idx >= len(RIGHT_COLUMNS):
            return None
        key_ = RIGHT_COLUMNS[col_idx][1]
        return self.total_labels.get(emp_id, {}).get(key_)

    def _focus_result_first(self, emp_id):
        return self._focus_result_by_index(emp_id, 0)

    def _focus_result_last(self, emp_id):
        return self._focus_result_by_index(emp_id, len(RIGHT_COLUMNS) - 1)

    def _focus_result_by_index(self, emp_id, col_idx):
        cell = self._get_result_cell(emp_id, col_idx)
        if cell is None:
            return False
        self._focus_result_cell(cell)
        return True

    def _focus_result_next(self, emp_id, col_idx):
        if col_idx + 1 < len(RIGHT_COLUMNS):
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
            save_data(self.app.data)
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
        save_data(self.app.data)
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
            save_data(self.app.data)
            popup.dismiss()
            self.load_timesheet()

        yes.bind(on_press=do_reset)
        no.bind(on_press=popup.dismiss)
        bind_enter_key(popup, do_reset)
        popup.open()

    def load_timesheet(self):
        self._loading = True
        try:
            self.main_container.clear_widgets()
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

            day_types = [classify_day(y, m, d)
                         for d in range(1, days_in_month + 1)]
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
            W_DAY = dp(46)
            ROW_H = dp(56)  
            HEAD_TOP_H = dp(24)
            HEAD_BOT_H = dp(120)

            max_name_w = dp(190)
            max_pos_w  = dp(100) 
            for emp in employees:
                nm_w = measure_text_width(emp.get('name', ''), font_size=14)
                ps_w = measure_text_width(emp.get('position', ''), font_size=14)
                if nm_w + dp(24) > max_name_w:
                    max_name_w = nm_w + dp(24)
                if ps_w + dp(24) > max_pos_w:
                    max_pos_w = ps_w + dp(24)
            max_name_w = min(max_name_w, dp(500))
            max_pos_w  = min(max_pos_w,  dp(140)) 

            W_NAME = max_name_w
            W_POS  = max_pos_w

            # ДИНАМИЧЕСКАЯ ВЫСОТА СТРОК (чтобы отображались длинные должности)
            row_heights = []
            for emp in employees:
                h_name = measure_text_height(emp.get('name', ''), W_NAME - dp(12))
                h_pos = measure_text_height(emp.get('position', ''), W_POS - dp(12))
                rh = max(ROW_H, h_name + dp(12), h_pos + dp(12))
                row_heights.append(rh)

            LEFT_W  = W_NUM + W_NAME + W_POS
            RIGHT_W = sum(w for _, _, w in RIGHT_COLUMNS)
            DAYS_W  = days_in_month * W_DAY
            
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

            w_days_att = RIGHT_COLUMNS[0][2] + RIGHT_COLUMNS[1][2]
            w_days_abs = sum(RIGHT_COLUMNS[i][2] for i in range(2, 11))
            w_work     = sum(RIGHT_COLUMNS[i][2] for i in range(11, 16))

            right_top = BoxLayout(size_hint=(None, 1), width=RIGHT_W, spacing=0)
            self.right_top = right_top # СОХРАНЯЕМ ССЫЛКУ
            add_left_border(right_top, color=BORDER_BLACK, thickness=LINE_T)
            right_top.add_widget(self._lbl_bg("Дни явок",
                                               w_days_att - 1, HEAD_TOP_H))
            right_top.add_widget(vsep(color=BORDER_BLACK, thickness=LINE_T))
            right_top.add_widget(self._lbl_bg("Дни неявок",
                                               w_days_abs - 1, HEAD_TOP_H))
            right_top.add_widget(vsep(color=BORDER_BLACK, thickness=LINE_T))
            right_top.add_widget(self._lbl_bg("Отработано часов",
                                               w_work, HEAD_TOP_H))
            header_strip.add_widget(right_top)

            add_bottom_border(c_holder, color=BORDER_BLACK, thickness=LINE_T)
            add_bottom_border(right_top, color=BORDER_BLACK, thickness=LINE_T)

            self.main_container.add_widget(header_strip)

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
            c = self._lbl_bg("Фамилия Имя Отчество", W_NAME, HEAD_BOT_H)
            add_right_border(c, color=BORDER_BLACK, thickness=LINE_T)
            lh.add_widget(c)
            c = self._lbl_bg("Должность", W_POS, HEAD_BOT_H)
            add_right_border(c, color=BORDER_BLACK, thickness=LINE_T)
            lh.add_widget(c)
            add_bottom_border(lh, color=BORDER_BLACK, thickness=LINE_T)

            # Контейнер для шапки дней
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
                                         size=(W_DAY, HEAD_BOT_H))
                self._all_day_headers.append(day_hdr)
                dh.add_widget(day_hdr)
            add_bottom_border(dh, color=BORDER_BLACK, thickness=LINE_T)
            days_head_container.add_widget(dh)

            rh_box = BoxLayout(size_hint=(None, 1), width=RIGHT_W, spacing=0)
            self.right_header = rh_box # СОХРАНЯЕМ ССЫЛКУ
            for i, (label, key_, w) in enumerate(RIGHT_COLUMNS):
                last = (i == len(RIGHT_COLUMNS) - 1)
                vl = VerticalLabel(text=label,
                                    font_size=9,
                                    pad_top=6,
                                    size_hint=(None, None),
                                    size=(w if last else w - LINE_T, HEAD_BOT_H))
                if i == 0:
                    add_left_border(vl, color=BORDER_BLACK, thickness=LINE_T)
                rh_box.add_widget(vl)
                if not last:
                    rh_box.add_widget(vsep(color=BORDER_BLACK, thickness=LINE_T))
            add_bottom_border(rh_box, color=BORDER_BLACK, thickness=LINE_T)

            header_bottom.add_widget(lh)
            header_bottom.add_widget(days_head_container)
            header_bottom.add_widget(rh_box)
            self.main_container.add_widget(header_bottom)

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
                r = BoxLayout(size_hint=(None, None),
                              size=(LEFT_W, rh), spacing=0)
                num_lbl = self._lbl(str(idx + 1), W_NUM, rh)
                add_left_border(num_lbl, color=BORDER_BLACK, thickness=LINE_T)
                add_right_border(num_lbl, color=BORDER_BLACK, thickness=LINE_T)
                r.add_widget(num_lbl)

                # Возвращаем перенос строк (shorten=False)
                name_lbl = self._lbl(emp.get('name', ''),
                                      W_NAME, rh, align_left=True, shorten=False)
                add_right_border(name_lbl, color=BORDER_BLACK, thickness=LINE_T)
                r.add_widget(name_lbl)

                pos_lbl = self._lbl(emp.get('position', ''), W_POS, rh,
                                     align_left=True, shorten=False)
                add_right_border(pos_lbl, color=BORDER_BLACK, thickness=LINE_T)
                r.add_widget(pos_lbl)

                add_bottom_border(r)
                left_grid.add_widget(r)
            left_sv.add_widget(left_grid)
            body.add_widget(left_sv)

            days_sv = HorizontalScrollView(do_scroll_x=True, do_scroll_y=True,
                                            bar_width=0,
                                            scroll_type=['content'],
                                            effect_cls=NoOverscrollEffect)
            self._days_sv = days_sv
            # БЫЛО:
            # days_grid = GridLayout(cols=1, size_hint=(None, None), spacing=0)
            # days_grid.width = DAYS_W  # <--- Явно задаем ширину вместо bind
            # _stretch_grid(days_grid, days_sv)

            # СТАЛО:
            days_grid = GridLayout(cols=1, size_hint=(None, None), spacing=0)
            # Привязываем ширину к minimum_width, чтобы GridLayout точно соответствовал содержимому
            days_grid.bind(minimum_width=days_grid.setter('width'))
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
                                    size=(W_DAY, rh))
                    cell.input.bind(text=lambda inst, val, eid=emp_id:
                                    self._on_day_change(eid))
                    r.add_widget(cell)
                    cells.append(cell)
                add_bottom_border(r)
                self.day_inputs[emp_id] = cells
                days_grid.add_widget(r)
            days_sv.add_widget(days_grid)
            body.add_widget(days_sv)

            # Синхронизация горизонтальной прокрутки и позиции шапки
            def _update_days_header(*args):
                try:
                    dh.y = days_head_container.y
                    # Жестко ограничиваем scroll_x, чтобы не было сдвигов из-за погрешностей float
                    sx = max(0.0, min(1.0, days_sv.scroll_x))
                    max_scroll = max(0, dh.width - days_sv.width)
                    if max_scroll > 0:
                        dh.x = days_head_container.x - (sx * max_scroll)
                    else:
                        dh.x = days_head_container.x
                except Exception:
                    pass
            
            # Отложенный вызов нужен только для изменения размеров окна,
            # чтобы Kivy успел пересчитать лэйаут
            def _delayed_update_days_header(*args):
                Clock.schedule_once(_update_days_header, 0)

            self._update_days_header_func = _update_days_header

            # Прямая привязка для мгновенной прокрутки без задержек
            days_sv.bind(scroll_x=_update_days_header)
            
            # Отложенная привязка для изменения размеров (чтобы не ломалось при разворачивании окна)
            days_sv.bind(size=_delayed_update_days_header)
            days_head_container.bind(pos=_delayed_update_days_header, size=_delayed_update_days_header)
            
            Clock.schedule_once(_update_days_header, 0)

            right_sv = SmartScrollView(do_scroll_x=False, do_scroll_y=True,
                                  size_hint=(None, 1), width=RIGHT_W,
                                  bar_width=0, scroll_type=['content'],
                                  effect_cls=NoOverscrollEffect)
            self._right_sv = right_sv
            self.right_sv = right_sv # СОХРАНЯЕМ ССЫЛКУ
            right_grid = GridLayout(cols=1, size_hint=(None, None), spacing=0)
            right_grid.width = RIGHT_W
            _stretch_grid(right_grid, right_sv)

            for idx, emp in enumerate(employees):
                rh = row_heights[idx]
                emp_id = emp['id']
                r = BoxLayout(size_hint=(None, None),
                              size=(RIGHT_W, rh), spacing=0)
                labels = {}
                last_i = len(RIGHT_COLUMNS) - 1
                for i, (_, key_, w) in enumerate(RIGHT_COLUMNS):
                    cb = self._make_result_nav_callback(emp_id, i)
                    cell = ResultCell(
                        text='0', fg_color=config.TABLE_FG,
                        show_left=(i == 0),
                        show_right=(i < last_i),
                        border_color=BORDER_BLACK, border_th=LINE_T,
                        size_hint=(None, None), size=(w, rh),
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
                self.total_labels[emp_id] = labels
                add_bottom_border(r)
                right_grid.add_widget(r)
            right_sv.add_widget(right_grid)
            body.add_widget(right_sv)

            self.main_container.add_widget(body)
            sync_vertical([left_sv, days_sv, right_sv])

            for emp_id in list(self.day_inputs.keys()):
                self._recalc_totals(emp_id)

            self._last_key = key

            # --- Динамическая высота таблицы (чтобы скроллбар был прямо под последней строкой) ---
            def _sync_body_height(*args):
                try:
                    if self.height <= 100:
                        return # Пропускаем, если окно еще не отрисовано
                        
                    avail_for_main = self.height - self.top_bar.height - self.spacer_gap.height - self.extra_wrapper.height - self.bottom_margin.height - self.hint_wrap.height - dp(10)
                    avail_for_body = avail_for_main - header_strip.height - header_bottom.height
                    content_h = sum(row_heights)
                    target_body_h = min(avail_for_body, content_h + dp(16))
                    if target_body_h < dp(50):
                        target_body_h = dp(50)
                        
                    if abs(body.height - target_body_h) > 0.5:
                        body.height = target_body_h
                    
                    main_h = header_strip.height + header_bottom.height + target_body_h
                    if abs(self.main_container.height - main_h) > 0.5:
                        self.main_container.height = main_h
                except Exception:
                    pass
                    
            self._sync_body_height = _sync_body_height
            self.bind(height=_sync_body_height)
            # ВЫЗЫВАЕМ СРАЗУ, БЕЗ ЗАДЕРЖКИ, ЧТОБЫ НЕ БЫЛО СКАЧКОВ
            _sync_body_height()
            
            # Применяем текущее состояние скрытия/отображения итогов
            self._apply_results_visibility()

        finally:
            self._loading = False

    @staticmethod
    def _lbl(text, w, h, bold=False, align_left=False, shorten=False):
        lbl = Label(text=text, bold=bold,
                    size_hint=(None, None), size=(w, h),
                    color=config.TABLE_FG,
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
        holder.add_widget(Label(text=text, bold=True, color=HEADER_FG,
                                 font_name=FONT_NAME,
                                 font_size=dp(11),
                                 halign='center', valign='middle'))
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