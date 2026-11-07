# ui_spinners.py
# -*- coding: utf-8 -*-
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.spinner import Spinner, SpinnerOption
from config import FONT_NAME

class LightSpinnerOption(SpinnerOption):
    NORMAL_BG = (0.14, 0.14, 0.16, 1); HOVER_BG = (0.30, 0.30, 0.35, 1)
    TEXT_COL = (1.00, 1.00, 1.00, 1); LINE_COL = (0.42, 0.42, 0.48, 1)

    def __init__(self, **kwargs):
        kwargs.setdefault('size_hint_y', None); kwargs.setdefault('height', dp(44))
        kwargs.setdefault('background_normal', ''); kwargs.setdefault('background_down', '')
        kwargs.setdefault('background_color', (0, 0, 0, 0)); kwargs.setdefault('halign', 'center')
        kwargs.setdefault('valign', 'middle'); kwargs.setdefault('font_size', 16)
        kwargs.setdefault('bold', True); kwargs.setdefault('font_name', FONT_NAME)
        kwargs['color'] = self.TEXT_COL
        super().__init__(**kwargs)
        self.color = self.TEXT_COL; self.disabled_color = self.TEXT_COL; self.bold = True; self._hovering = False
        with self.canvas.before:
            self._bg_color = Color(*self.NORMAL_BG); self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        with self.canvas.after:
            Color(*self.LINE_COL); self._line = Rectangle(pos=self.pos, size=(self.width, 1))
        self.bind(pos=self._upd, size=self._upd, state=self._on_state, size=self._fix_align)
        from kivy.core.window import Window
        Window.bind(mouse_pos=self._on_mouse_pos)
        self.bind(parent=self._on_parent)

    def _on_parent(self, instance, parent):
        if parent is None:
            from kivy.core.window import Window
            try: Window.unbind(mouse_pos=self._on_mouse_pos)
            except Exception: pass

    def _on_mouse_pos(self, window, pos):
        if not self.get_root_window() or self.disabled: return
        try:
            wx, wy = self.to_window(self.x, self.y)
            if wx <= pos[0] <= wx + self.width and wy <= pos[1] <= wy + self.height:
                if not self._hovering: self._hovering = True; self._update_bg()
            else:
                if self._hovering: self._hovering = False; self._update_bg()
        except Exception: pass

    def _upd(self, *a):
        self._bg_rect.pos = self.pos; self._bg_rect.size = self.size
        self._line.pos = (self.x, self.y); self._line.size = (self.width, 1)

    def _fix_align(self, *a): self.text_size = (self.width - 8, self.height)
    def _on_state(self, inst, value): self._update_bg()
    def _update_bg(self):
        self._bg_color.rgba = self.HOVER_BG if (self._hovering or self.state == 'down') else self.NORMAL_BG

class CenteredSpinner(AnchorLayout):
    def __init__(self, text='', values=None, spinner_height=dp(30), font_size=dp(15),
                 bg_color=(0.85, 0.92, 1.00, 1), **sp_kwargs):
        super().__init__(anchor_x='center', anchor_y='center')
        sp_kwargs.setdefault('font_name', FONT_NAME)
        self.spinner = Spinner(text=text, values=values or [], size_hint=(1, None), height=spinner_height,
            font_size=font_size, background_color=bg_color, background_normal='', background_down='',
            color=(0.05, 0.05, 0.25, 1), option_cls=LightSpinnerOption, **sp_kwargs)
        self.spinner.bind(is_open=self._on_open)
        self.add_widget(self.spinner)

    def _on_open(self, inst, value):
        if value:
            from kivy.core.window import Window
            self.spinner._dropdown.max_height = Window.height * 0.7
            Clock.schedule_once(self._align_dropdown, 0)
            Clock.schedule_once(self._align_dropdown, 0.05)

    def _align_dropdown(self, dt):
        try:
            drop = self.spinner._dropdown; sp = self.spinner
            from kivy.core.window import Window
            wx, wy = sp.to_window(sp.x, sp.y)
            drop.width = sp.width; drop.x = wx; margin = dp(40)
            if drop.y < margin: drop.y = margin
            if drop.top > Window.height - margin: drop.top = Window.height - margin
        except Exception: pass

    @property
    def text(self): return self.spinner.text
    @text.setter
    def text(self, value): self.spinner.text = value