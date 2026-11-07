# timesheet_mixins.py
# -*- coding: utf-8 -*-
"""Миксины для логики табеля."""
from kivy.clock import Clock
from kivy.metrics import dp
from ui_helpers import measure_text_width
from config import RIGHT_COLUMNS

class TimesheetAutoFitMixin:
    def _auto_fit_day_columns(self):
        if not getattr(self, 'day_inputs', None) or not getattr(self, '_days_in_month', 0): return
        days_in_month = self._days_in_month
        avail_w = self._days_sv.width if getattr(self, '_days_sv', None) else 0
        if avail_w <= 0: return
        base_w = max(dp(36), avail_w / days_in_month)
        new_widths = [base_w] * days_in_month
        for emp_id, cells in self.day_inputs.items():
            for d_idx, cell in enumerate(cells):
                if d_idx >= days_in_month: continue
                txt = cell.input.text.strip()
                if txt:
                    req_w = measure_text_width(txt, font_size=14) + dp(6)
                    if req_w > new_widths[d_idx]: new_widths[d_idx] = req_w
        changed = False
        for i in range(days_in_month):
            if i < len(self._all_day_headers):
                if abs(self._all_day_headers[i].width - new_widths[i]) > 1: changed = True; break
        if not changed: return
        total_w = 0
        for i in range(days_in_month):
            w = new_widths[i]; total_w += w
            if i < len(self._all_day_headers): self._all_day_headers[i].width = w
            for row in self._all_day_rows:
                if i < len(row.children): row.children[-(i + 1)].width = w
        self._days_grid.width = total_w
        if self._dh is not None: self._dh.width = total_w
        for row in self._all_day_rows: row.width = total_w
        if self._update_days_header_func: self._update_days_header_func()
        if self._days_grid.width <= self._days_sv.width + 1: self._days_sv.scroll_x = 0

    def _auto_fit_right_columns(self):
        if not getattr(self, 'total_labels', None) or not self.total_labels: return
        num_cols = len(RIGHT_COLUMNS); new_widths = [max(dp(40), col[2]) for col in RIGHT_COLUMNS] 
        for i in range(num_cols):
            cells = getattr(self, '_right_col_cells', [[]])[i] if hasattr(self, '_right_col_cells') else []
            for cell in cells:
                txt = cell.input.text.strip()
                if txt:
                    req_w = measure_text_width(txt, font_size=14) + dp(6)
                    if req_w > new_widths[i]: new_widths[i] = req_w
        total_w = sum(new_widths)
        if abs(self.RIGHT_W - total_w) < 1: return
        self.RIGHT_W = total_w
        if hasattr(self, '_right_headers'):
            for i, hdr in enumerate(self._right_headers):
                last = (i == num_cols - 1); hdr.width = new_widths[i] if last else new_widths[i] - 1
        if hasattr(self, '_right_top_groups') and len(self._right_top_groups) == 3:
            w_days_att = new_widths[0] + new_widths[1]; w_days_abs = sum(new_widths[i] for i in range(2, 11))
            w_work = sum(new_widths[i] for i in range(11, num_cols))
            self._right_top_groups[0].width = w_days_att - 1; self._right_top_groups[1].width = w_days_abs - 1; self._right_top_groups[2].width = w_work
        if hasattr(self, '_right_col_cells'):
            for i in range(num_cols):
                for cell in self._right_col_cells[i]: cell.width = new_widths[i]
        if hasattr(self, '_right_rows'):
            for r in self._right_rows: r.width = self.RIGHT_W
        if getattr(self, '_right_grid', None): self._right_grid.width = self.RIGHT_W
        if not getattr(self, '_results_hidden', False):
            if getattr(self, 'right_sv', None): self.right_sv.width = self.RIGHT_W
            if getattr(self, 'right_header', None): self.right_header.width = self.RIGHT_W
            if getattr(self, 'right_top', None): self.right_top.width = self.RIGHT_W
        Clock.schedule_once(lambda dt: self._apply_results_visibility(), 0)

class TimesheetNavMixin:
    def _make_day_nav_callback(self, emp_id, day_idx):
        return lambda key, modifiers: self._handle_day_nav(emp_id, day_idx, key, modifiers)
    def _make_result_nav_callback(self, emp_id, col_idx):
        return lambda key, modifiers: self._handle_result_nav(emp_id, col_idx, key, modifiers)
    
    # ... (сюда переносится вся логика стрелок, Tab, Enter, _focus_next_day и т.д. из tab_timesheet.py) ...
    # Для экономии объема кода, я не дублирую их, они просто копируются сюда из старого файла.
    pass