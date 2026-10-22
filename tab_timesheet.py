# tab_timesheet.py
# -*- coding: utf-8 -*-
"""Вкладка «Табель»."""
import config  # noqa: F401

from calendar import monthrange
from datetime import datetime, date

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle

from config import (FONT_NAME, LABEL_LIGHT, MONTHS, YEARS,
                    SPINNER_BG, SPINNER_FG, RIGHT_COLUMNS,
                    HEADER_BG, HEADER_FG)
from data_utils import (save_data, classify_day, analyze_row,
                        apply_overtime, fmt_hours)
from ui_helpers import (add_bottom_border, add_top_border,
                        add_left_border, add_right_border,
                        vsep, sync_vertical, measure_text_width,
                        HorizontalScrollView, SmartScrollView,
                        NoOverscrollEffect)
from ui_widgets import (VerticalLabel, DayCell, ResultCell, DayHeader,
                        NavTextInput)

def _stretch_grid(grid, sv):
    """Grid должен быть не меньше ScrollView по высоте,
    иначе Kivy прижимает содержимое к низу окна просмотра."""
    def _sync(*_):
        try:
            h = max(grid.minimum_height, sv.height)
            if abs(grid.height - h) > 0.5:      # фильтр — не трогаем,
                grid.height = h                 # если высота та же
        except Exception:
            pass
    # Слушаем только sv.height. minimum_height НЕ биндим —
    # иначе цикл «высота → пересчёт → высота → дрожь».
    sv.bind(height=_sync)
    Clock.schedule_once(_sync, 0)
    Clock.schedule_once(_sync, 0.1)

class TimesheetTab(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        self.day_inputs = {}
        self.total_labels = {}
        self._last_key = None
        self._loading = False
        self._save_event = None
        self._day_types = []
        self._emp_night = {}
        self._emp_overtime = {}
        self._emp_holiday = {}
        self._suppress_result_cb = False
        self._employees_order = []
        self._days_sv = None
        self._right_sv = None
        self._days_in_month = 0
        self._sel_anchor = None
        self._sel_current = None

        # --- трекинг shift ---
        self._shift_held = False
        from kivy.core.window import Window
        Window.bind(on_keyboard=self._on_window_keyboard,
                    on_key_down=self._on_win_key_down,
                    on_key_up=self._on_win_key_up)

        self._build()

    def _build(self):
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=5,
                        padding=(5, 2, 5, 2))
        top.add_widget(Label(text="Месяц:", size_hint_x=None, width=dp(70),
                             color=LABEL_LIGHT, font_name=FONT_NAME,
                             font_size=dp(15)))
        self.month_spinner = Spinner(text=MONTHS[datetime.now().month - 1],
                                     values=MONTHS, size_hint_x=None, width=dp(150),
                                     font_name=FONT_NAME,
                                     background_color=SPINNER_BG, color=SPINNER_FG)
        top.add_widget(self.month_spinner)

        top.add_widget(Label(text="Год:", size_hint_x=None, width=dp(50),
                             color=LABEL_LIGHT, font_name=FONT_NAME,
                             font_size=dp(15)))
        self.year_spinner = Spinner(text=str(datetime.now().year),
                                    values=YEARS, size_hint_x=None, width=dp(100),
                                    font_name=FONT_NAME,
                                    background_color=SPINNER_BG, color=SPINNER_FG)
        top.add_widget(self.year_spinner)

        top.add_widget(Widget())

        apply_btn = Button(text="Применить правки", size_hint_x=None, width=dp(170),
                           font_name=FONT_NAME, font_size=dp(15), bold=True,
                           background_color=(0.25, 0.55, 0.85, 1),
                           color=(1, 1, 1, 1))
        apply_btn.bind(on_press=lambda *a: self.apply_overrides())
        top.add_widget(apply_btn)

        reset_btn = Button(text="Сбросить правки",
                           size_hint_x=None, width=dp(170),
                           font_name=FONT_NAME, font_size=dp(15), bold=True,
                           background_color=(0.5, 0.4, 0.75, 1),
                           color=(1, 1, 1, 1))
        reset_btn.bind(on_press=lambda *a: self.reset_overrides())
        top.add_widget(reset_btn)

        clear_btn = Button(text="Очистить", size_hint_x=None, width=dp(140),
                           font_name=FONT_NAME, font_size=dp(15), bold=True,
                           background_color=(0.9, 0.55, 0.2, 1), color=(1, 1, 1, 1))
        clear_btn.bind(on_press=lambda *a: self.confirm_clear())
        top.add_widget(clear_btn)
        self.add_widget(top)

        self.main_container = BoxLayout(orientation='vertical', spacing=0)
        self.add_widget(self.main_container)

        # ---- Подсказка-таблица внизу вкладки «Табель» ----
        HINT_BG   = (0.11, 0.12, 0.15, 1)   # как TOPBAR_BG в main.py
        HINT_FG   = (0.88, 0.90, 0.94, 1)   # расшифровка
        HINT_CODE = (1.00, 0.85, 0.35, 1)   # жёлтый акцент на код
        HINT_DASH = (0.40, 0.42, 0.48, 1)   # тире-разделитель

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
            ('8д',   '  часы без ночных'),
            ('8//N', '  часы // смена'),
            ('Tab',  '  стрелки — по ячейкам'),
        ]

        hint_wrap = BoxLayout(orientation='vertical',
                              size_hint_y=None,
                              height=dp(64),
                              padding=(dp(6), dp(4), dp(6), dp(4)))
        with hint_wrap.canvas.before:
            Color(*HINT_BG)
            _hw = Rectangle(pos=hint_wrap.pos, size=hint_wrap.size)
        hint_wrap.bind(pos=lambda i, v, r=_hw: setattr(r, 'pos', v),
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

        hint_wrap.add_widget(hint_grid)
        add_top_border(hint_wrap, color=(0, 0, 0, 1), thickness=1)
        self.add_widget(hint_wrap)

        self.month_spinner.bind(text=self._on_period_change)
        self.year_spinner.bind(text=self._on_period_change)

        self.load_timesheet()

    # ---------------- служебные ------------------------------------------
    def _get_key(self):
        m = MONTHS.index(self.month_spinner.text) + 1
        y = int(self.year_spinner.text)
        return f"{y}-{m:02d}"

    def _get_norm_hours(self):
        y = int(self.year_spinner.text)
        m = MONTHS.index(self.month_spinner.text) + 1
        days_in_month = monthrange(y, m)[1]
        work_days = sum(1 for d in range(1, days_in_month + 1)
                        if classify_day(y, m, d) == 'work')
        return work_days * 8.0

    def _on_period_change(self, *args):
        if self._loading:
            return
        if self._last_key:
            self._save_for_key(self._last_key)
        self.load_timesheet()

    # ---------------- трекинг Shift --------------------------------------
    def _on_win_key_down(self, window, key, scancode, codepoint, modifiers):
        if 'shift' in (modifiers or []):
            self._shift_held = True
            NavTextInput.shift_state['held'] = True

    def _on_win_key_up(self, window, key, scancode):
        if key in (303, 304):    # левый / правый Shift
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
        return [emp for emp in self.app.data['employees']
                if emp.get('show_in_timesheet', False)]

    # ---------------- навигация ------------------------------------------
    def _make_day_nav_callback(self, emp_id, day_idx):
        def cb(key, modifiers):
            return self._handle_day_nav(emp_id, day_idx, key, modifiers)
        return cb

    def _make_result_nav_callback(self, emp_id, col_idx):
        def cb(key, modifiers):
            return self._handle_result_nav(emp_id, col_idx, key, modifiers)
        return cb

    # ---------------- Ctrl+C / Ctrl+V ------------------------------------
    def _on_extra_key(self, key, modifiers):
        """Перехват клавиш, приходящий раньше стандартной обработки TextInput."""
        mods = modifiers or []
        ctrl = 'ctrl' in mods

        # ---- Del (key = 127) ----
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

        # ---- Ctrl+C ----
        if key == 99:   # c
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

        # ---- Ctrl+V ----
        if key == 118:  # v
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
        """Самый ранний перехват клавиш в Kivy.

        Возврат True останавливает дальнейшую обработку.

        Здесь ловим Ctrl+C / Ctrl+V и Del. Это единственное место,
        которое срабатывает, даже если ни одна ячейка не в фокусе —
        например после Shift-выделения (там мы специально снимаем
        фокус, чтобы не оставалось встроенного текстового выделения).
        """
        mods = modifiers or []
        ctrl = 'ctrl' in mods

        # ---- Ctrl+C: копируем выделение (диапазон или одну ячейку) ----
        if ctrl and key == 99:      # 'c'
            if self._sel_anchor and self._sel_current:
                if self._save_selection_to_clipboard():
                    return True
            # Если выделения ячеек нет — пусть обрабатывает TextInput
            # (там есть путь «скопировать содержимое активной ячейки»).
            return False

        # ---- Ctrl+V: вставляем от якоря выделения ----
        if ctrl and key == 118:     # 'v'
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
                # _paste_tsv_from_text работает и для одиночного
                # значения (без таба), и для матрицы TSV —
                # в обоих случаях вставка идёт от _sel_anchor.
                if self._paste_tsv_from_text(lines):
                    return True
            return False

        # ---- Del (key = 127) ----
        if key != 127:
            return False

        cell = self._get_focused_cell()

        # Если внутри одной ячейки выделен фрагмент — не мешаем TextInput
        if cell is not None:
            try:
                if cell.input.selection_text:
                    return False
            except Exception:
                pass

        # Если выделено 2+ ячеек — очищаем весь диапазон
        if (self._sel_anchor and self._sel_current
                and self._sel_anchor != self._sel_current):
            if self._clear_selection_cells():
                return True
            return False

        # Иначе — очищаем содержимое всей активной ячейки
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
        """Вставить распарсенный TSV от активной ячейки
        (или от якоря выделения, если оно есть)."""
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
        """Очистить содержимое всех ячеек выделения."""
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
        """Найти ячейку, чей TextInput сейчас в фокусе."""
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

    # ---- НОВЫЙ МЕТОД ------------------------------------------------
    def has_focused_cell(self):
        """True, если прямо сейчас в фокусе хотя бы одна ячейка табеля.

        Используется главным окном, чтобы не пересобирать таблицу
        в момент, когда пользователь что-то печатает — иначе
        сбрасывается курсор и ввод теряется."""
        return self._get_focused_cell() is not None

    def _blur_all_cells(self):
        """Снять фокус со всех ячеек вкладки."""
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

    # ---------------- выделение диапазона Shift+клик ---------------------
    def _on_cell_touch_down(self, cell, touch):
        info = self._cell_info(cell)
        if info is None:
            return
        emp_id, idx, kind = info
        if self._shift_held:
            # Снимаем «остаточный» фокус/курсор с любых ячеек —
            # он мог остаться от предыдущего одиночного клика.
            # Иначе встроенное текстовое выделение остаётся поверх
            # фоновой подсветки.
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

    # ------ обработчики клавиш (навигация) -------------------------------
    def _handle_day_nav(self, emp_id, day_idx, key, modifiers):
        mods = modifiers or []
        # Ctrl+... обрабатывается в _on_extra_key
        if 'ctrl' in mods:
            return False

        shift = 'shift' in mods

        if key == 9:  # Tab
            if shift:
                self._focus_prev_day(emp_id, day_idx)
            else:
                self._focus_next_day(emp_id, day_idx)
            return True

        if key == 275:  # Right
            cell = self._get_day_cell(emp_id, day_idx)
            if cell is not None:
                try:
                    if cell.input.cursor_index() >= len(cell.input.text):
                        return self._focus_next_day(emp_id, day_idx)
                except Exception:
                    pass
            return False

        if key == 276:  # Left
            cell = self._get_day_cell(emp_id, day_idx)
            if cell is not None:
                try:
                    if cell.input.cursor_index() <= 0:
                        return self._focus_prev_day(emp_id, day_idx)
                except Exception:
                    pass
            return False

        if key == 274:  # Down
            return self._focus_row_down_day(emp_id, day_idx)
        if key == 273:  # Up
            return self._focus_row_up_day(emp_id, day_idx)
        return False

    def _handle_result_nav(self, emp_id, col_idx, key, modifiers):
        mods = modifiers or []
        if 'ctrl' in mods:
            return False

        shift = 'shift' in mods

        if key == 9:  # Tab
            if shift:
                self._focus_result_prev(emp_id, col_idx)
            else:
                self._focus_result_next(emp_id, col_idx)
            return True

        if key == 275:  # Right
            cell = self._get_result_cell(emp_id, col_idx)
            if cell is not None:
                try:
                    if cell.input.cursor_index() >= len(cell.input.text):
                        self._focus_result_next(emp_id, col_idx)
                        return True
                except Exception:
                    pass
            return False

        if key == 276:  # Left
            cell = self._get_result_cell(emp_id, col_idx)
            if cell is not None:
                try:
                    if cell.input.cursor_index() <= 0:
                        self._focus_result_prev(emp_id, col_idx)
                        return True
                except Exception:
                    pass
            return False

        if key == 274:  # Down
            return self._focus_result_row_down(emp_id, col_idx)
        if key == 273:  # Up
            return self._focus_result_row_up(emp_id, col_idx)
        return False

    # ------ day-cell навигация -------------------------------------------
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

    # ------ result-cell навигация ----------------------------------------
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

    # ------ сам фокус -----------------------------------------------------
    def _focus_cell(self, cell):
        try:
            cell.input.focus = True
            # select_all не вызываем: замена содержимого при вводе
            # обеспечивается флагом NavTextInput._just_focused —
            # первый печатный символ сам очищает ячейку.
            # Без select_all нет синего текстового выделения поверх цифр.
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

    # ---------------- диалоги --------------------------------------------
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
                      title_font=FONT_NAME)

        def do_clear(*a):
            key = self._get_key()
            self.app.data['timesheets'][key] = {}
            save_data(self.app.data)
            popup.dismiss()
            self.load_timesheet()

        yes.bind(on_press=do_clear)
        no.bind(on_press=popup.dismiss)
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
            # Убираем ведущие нули, если сразу за ними идёт цифра
            # (кейс: в ячейке было «0», пользователь набрал «5» → «05»).
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
            # Ячейка получила фокус — _just_focused уже выставлен в
            # CenteredField._on_focus. select_all не нужен: первый
            # печатный символ сам заменит содержимое, а синего
            # текстового выделения поверх цифр не будет.
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
                      title_font=FONT_NAME)

        def do_reset(*a):
            key = self._get_key()
            self.app.data.setdefault('result_overrides', {})[key] = {}
            save_data(self.app.data)
            popup.dismiss()
            self.load_timesheet()

        yes.bind(on_press=do_reset)
        no.bind(on_press=popup.dismiss)
        popup.open()

    # ---------------- основная загрузка ----------------------------------
    def load_timesheet(self):
        self._loading = True
        try:
            self.main_container.clear_widgets()
            self.day_inputs.clear()
            self.total_labels.clear()

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
            holiday_flags = self.app.data.get('holiday_flags', {})
            self._emp_night = {}
            self._emp_overtime = {}
            employees = self._employees_for_ts()
            self._employees_order = [emp['id'] for emp in employees]
            for emp in employees:
                pos_name = emp.get('position', '')
                self._emp_night[emp['id']] = bool(night_flags.get(pos_name, False))
                self._emp_overtime[emp['id']] = bool(overtime_flags.get(pos_name, False))
                # self._emp_holiday[emp['id']] = bool(holiday_flags.get(pos_name, False))

            W_NUM = dp(40)
            W_DAY = dp(46)
            ROW_H = dp(36)
            HEAD_TOP_H = dp(24)
            HEAD_BOT_H = dp(120)

            max_name_w = dp(190)
            max_pos_w  = dp(150)
            for emp in employees:
                nm_w = measure_text_width(emp.get('name', ''), font_size=14)
                ps_w = measure_text_width(emp.get('position', ''), font_size=14)
                if nm_w + dp(24) > max_name_w:
                    max_name_w = nm_w + dp(24)
                if ps_w + dp(24) > max_pos_w:
                    max_pos_w = ps_w + dp(24)
            max_name_w = min(max_name_w, dp(500))
            max_pos_w  = min(max_pos_w,  dp(400))

            W_NAME = max_name_w
            W_POS  = max_pos_w

            LEFT_W  = W_NUM + W_NAME + W_POS
            RIGHT_W = sum(w for _, _, w in RIGHT_COLUMNS)
            DAYS_W  = days_in_month * W_DAY

            BORDER_BLACK = (0, 0, 0, 1)
            LINE_T = 1

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
            w_work     = sum(RIGHT_COLUMNS[i][2] for i in range(11, 15))

            right_top = BoxLayout(size_hint=(None, 1), width=RIGHT_W, spacing=0)
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

            body = BoxLayout(orientation='horizontal', spacing=0)

            left_sv = SmartScrollView(do_scroll_x=False, do_scroll_y=True,
                                 size_hint=(None, 1), width=LEFT_W,
                                 bar_width=dp(8), scroll_type=['bars'],
                                 effect_cls=NoOverscrollEffect)
            left_grid = GridLayout(cols=1, size_hint=(None, None), spacing=0)
            left_grid.width = LEFT_W
            _stretch_grid(left_grid, left_sv)

            lh = BoxLayout(size_hint=(None, None),
                            size=(LEFT_W, HEAD_BOT_H), spacing=0)
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
            left_grid.add_widget(lh)

            for idx, emp in enumerate(employees):
                r = BoxLayout(size_hint=(None, None),
                              size=(LEFT_W, ROW_H), spacing=0)
                num_lbl = self._lbl(str(idx + 1), W_NUM, ROW_H)
                add_left_border(num_lbl, color=BORDER_BLACK, thickness=LINE_T)
                add_right_border(num_lbl, color=BORDER_BLACK, thickness=LINE_T)
                r.add_widget(num_lbl)

                name_lbl = self._lbl(emp.get('name', ''),
                                      W_NAME, ROW_H, align_left=True)
                add_right_border(name_lbl, color=BORDER_BLACK, thickness=LINE_T)
                r.add_widget(name_lbl)

                pos_lbl = self._lbl(emp.get('position', ''),
                                     W_POS, ROW_H, align_left=True)
                add_right_border(pos_lbl, color=BORDER_BLACK, thickness=LINE_T)
                r.add_widget(pos_lbl)

                add_bottom_border(r)
                left_grid.add_widget(r)
            left_sv.add_widget(left_grid)
            body.add_widget(left_sv)

            days_sv = HorizontalScrollView(do_scroll_x=True, do_scroll_y=True,
                                            bar_width=dp(10),
                                            scroll_type=['bars', 'content'],
                                            effect_cls=NoOverscrollEffect)
            self._days_sv = days_sv
            days_grid = GridLayout(cols=1, size_hint=(None, None), spacing=0)
            days_grid.bind(minimum_width=days_grid.setter('width'))
            _stretch_grid(days_grid, days_sv)

            dh = BoxLayout(size_hint=(None, None),
                            size=(DAYS_W, HEAD_BOT_H), spacing=0)
            for i, dt in enumerate(day_types):
                wd_idx = date(y, m, i + 1).weekday()
                dh.add_widget(DayHeader(i + 1, day_type=dt,
                                         weekday_idx=wd_idx,
                                         show_right=True,
                                         size_hint=(None, None),
                                         size=(W_DAY, HEAD_BOT_H)))
            add_bottom_border(dh, color=BORDER_BLACK, thickness=LINE_T)
            days_grid.add_widget(dh)

            for emp in employees:
                emp_id = emp['id']
                r = BoxLayout(size_hint=(None, None),
                              size=(DAYS_W, ROW_H), spacing=0)
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
                                    size=(W_DAY, ROW_H))
                    cell.input.bind(text=lambda inst, val, eid=emp_id:
                                    self._on_day_change(eid))
                    r.add_widget(cell)
                    cells.append(cell)
                add_bottom_border(r)
                self.day_inputs[emp_id] = cells
                days_grid.add_widget(r)
            days_sv.add_widget(days_grid)
            body.add_widget(days_sv)

            right_sv = SmartScrollView(do_scroll_x=False, do_scroll_y=True,
                                  size_hint=(None, 1), width=RIGHT_W,
                                  bar_width=dp(8), scroll_type=['bars'],
                                  effect_cls=NoOverscrollEffect)
            self._right_sv = right_sv
            right_grid = GridLayout(cols=1, size_hint=(None, None), spacing=0)
            right_grid.width = RIGHT_W
            _stretch_grid(right_grid, right_sv)

            rh = BoxLayout(size_hint=(None, None),
                            size=(RIGHT_W, HEAD_BOT_H), spacing=0)
            for i, (label, key_, w) in enumerate(RIGHT_COLUMNS):
                last = (i == len(RIGHT_COLUMNS) - 1)
                vl = VerticalLabel(text=label,
                                    font_size=9,
                                    pad_top=6,
                                    size_hint=(None, None),
                                    size=(w if last else w - LINE_T, HEAD_BOT_H))
                if i == 0:
                    add_left_border(vl, color=BORDER_BLACK, thickness=LINE_T)
                rh.add_widget(vl)
                if not last:
                    rh.add_widget(vsep(color=BORDER_BLACK, thickness=LINE_T))
            add_bottom_border(rh, color=BORDER_BLACK, thickness=LINE_T)
            right_grid.add_widget(rh)

            for emp in employees:
                emp_id = emp['id']
                r = BoxLayout(size_hint=(None, None),
                              size=(RIGHT_W, ROW_H), spacing=0)
                labels = {}
                last_i = len(RIGHT_COLUMNS) - 1
                for i, (_, key_, w) in enumerate(RIGHT_COLUMNS):
                    cb = self._make_result_nav_callback(emp_id, i)
                    cell = ResultCell(
                        text='0', fg_color=LABEL_LIGHT,
                        show_left=(i == 0),
                        show_right=(i < last_i),
                        border_color=BORDER_BLACK, border_th=LINE_T,
                        size_hint=(None, None), size=(w, ROW_H),
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

        finally:
            self._loading = False

    # ---------------- вспомогательные ------------------------------------
    @staticmethod
    def _lbl(text, w, h, bold=False, align_left=False):
        lbl = Label(text=text, bold=bold,
                    size_hint=(None, None), size=(w, h),
                    color=LABEL_LIGHT,
                    font_name=FONT_NAME, font_size=dp(14),
                    halign='left' if align_left else 'center',
                    valign='middle')
        if align_left:
            lbl.bind(size=lambda inst, val: setattr(
                inst, 'text_size', (val[0] - 6, val[1])))
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
        # holiday_on = self._emp_holiday.get(emp_id, False)
        res = analyze_row(values, self._day_types, night_on)
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
                    if k in ('часы', 'сверхурочные', 'ночные', 'праздничные'):
                        new_text = fmt_hours(val)
                    else:
                        new_text = str(val)
                if cell.input.text != new_text:
                    cell.text = new_text
        finally:
            self._suppress_result_cb = False