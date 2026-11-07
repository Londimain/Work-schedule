# ui_cells.py
# -*- coding: utf-8 -*-
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from config import FONT_NAME, WEEKEND_BG, WEEKEND_FG, HOLIDAY_BG, HOLIDAY_FG, WORKDAY_BG, WORKDAY_FG, HEADER_BG, HEADER_FG, HEADER_DIVIDER, WEEKDAYS_SHORT, LABEL_LIGHT
from ui_helpers import add_left_border, add_right_border
from ui_inputs import CenteredField

class DayCell(BoxLayout):
    def __init__(self, text='', day_type='work', show_right=True, on_key_callback=None, on_cell_touch_down=None, extra_key_callback=None, **kwargs):
        super().__init__(orientation='horizontal', **kwargs)
        self._on_cell_touch_down = on_cell_touch_down; self._highlighted = False
        bg, fg = (HOLIDAY_BG, HOLIDAY_FG) if day_type == 'holiday' else (WEEKEND_BG, WEEKEND_FG) if day_type == 'weekend' else (WORKDAY_BG, WORKDAY_FG)
        with self.canvas.before:
            Color(*bg); self._rect = Rectangle(pos=self.pos, size=self.size)
            Color(0.20, 0.45, 0.90, 0.35); self._hl_rect = Rectangle(pos=self.pos, size=(0, 0))
        self.bind(pos=self._update_rect, size=self._update_rect)
        if show_right: add_right_border(self, color=HEADER_DIVIDER, thickness=1)
        _w = CenteredField(text=text, font_size=dp(14), pad_lr=dp(2), halign='center', fg_color=fg,
            background_color=(0, 0, 0, 0), background_normal='', background_active='',
            on_key_callback=on_key_callback, extra_key_callback=extra_key_callback)
        self.input = _w.input; self.add_widget(_w)

    def set_highlight(self, on): self._highlighted = bool(on); self._update_rect()
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and self._on_cell_touch_down:
            try: self._on_cell_touch_down(self, touch)
            except Exception: pass
        return super().on_touch_down(touch)
    def _update_rect(self, *a):
        self._rect.pos = self.pos; self._rect.size = self.size
        if self._highlighted: self._hl_rect.pos = self.pos; self._hl_rect.size = self.size
        else: self._hl_rect.size = (0, 0)

class ResultCell(BoxLayout):
    def __init__(self, text='0', fg_color=LABEL_LIGHT, show_left=False, show_right=True, border_color=(0, 0, 0, 1), border_th=1, on_key_callback=None, on_cell_touch_down=None, extra_key_callback=None, **kwargs):
        super().__init__(orientation='horizontal', **kwargs)
        self._on_cell_touch_down = on_cell_touch_down; self._highlighted = False
        if show_left: add_left_border(self, color=border_color, thickness=border_th)
        if show_right: add_right_border(self, color=border_color, thickness=border_th)
        with self.canvas.before:
            Color(0.20, 0.45, 0.90, 0.35); self._hl_rect = Rectangle(pos=self.pos, size=(0, 0))
        self.bind(pos=self._update_hl, size=self._update_hl)
        _w = CenteredField(text=text, font_size=dp(14), pad_lr=dp(2), halign='center', fg_color=fg_color,
            background_color=(0, 0, 0, 0), background_normal='', background_active='',
            on_key_callback=on_key_callback, extra_key_callback=extra_key_callback)
        self.input = _w.input; self._field = _w; self.add_widget(_w)

    def set_highlight(self, on): self._highlighted = bool(on); self._update_hl()
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and self._on_cell_touch_down:
            try: self._on_cell_touch_down(self, touch)
            except Exception: pass
        return super().on_touch_down(touch)
    def _update_hl(self, *a):
        if self._highlighted: self._hl_rect.pos = self.pos; self._hl_rect.size = self.size
        else: self._hl_rect.size = (0, 0)
    @property
    def text(self): return self._field.text
    @text.setter
    def text(self, value): self._field.text = value

class DayHeader(BoxLayout):
    def __init__(self, day, day_type='work', weekday_idx=None, show_right=True, height=None, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        bg, fg = (HOLIDAY_BG, HOLIDAY_FG) if day_type == 'holiday' else (WEEKEND_BG, WEEKEND_FG) if day_type == 'weekend' else (HEADER_BG, HEADER_FG)
        with self.canvas.before:
            Color(*bg); self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)
        if show_right: add_right_border(self, color=HEADER_DIVIDER, thickness=1)
        top = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(44))
        top.add_widget(Label(text=str(day), bold=True, font_size=dp(14), color=fg, font_name=FONT_NAME, size_hint_y=None, height=dp(22)))
        if weekday_idx is not None:
            top.add_widget(Label(text=WEEKDAYS_SHORT[weekday_idx], bold=True, font_size=dp(10), color=fg, font_name=FONT_NAME, size_hint_y=None, height=dp(18)))
        self.add_widget(top); self.add_widget(Widget())
    def _update_rect(self, *a): self._rect.pos = self.pos; self._rect.size = self.size