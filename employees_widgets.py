# employees_widgets.py
# -*- coding: utf-8 -*-
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout

class RightClickBox(BoxLayout):
    SELECT_COLOR = (1.00, 0.72, 0.10, 1); SELECT_TH = 3
    def __init__(self, on_right_click=None, on_left_click=None, **kwargs):
        super().__init__(**kwargs)
        self._on_right_click = on_right_click; self._on_left_click = on_left_click  
        self._selected = False; self._sel_top = None; self._sel_bottom = None; self._sel_left = None; self._sel_right = None
        self.bind(pos=self._update_sel, size=self._update_sel)
        Clock.schedule_once(self._init_sel_canvas, 0)

    def _init_sel_canvas(self, dt=0):
        if self._sel_top is not None: return
        with self.canvas.after:
            Color(*self.SELECT_COLOR)
            self._sel_top = Rectangle(pos=self.pos, size=(0, 0)); self._sel_bottom = Rectangle(pos=self.pos, size=(0, 0))
            self._sel_left = Rectangle(pos=self.pos, size=(0, 0)); self._sel_right = Rectangle(pos=self.pos, size=(0, 0))
        self._update_sel()

    def set_selected(self, on):
        self._selected = bool(on)
        if self._sel_top is None: self._init_sel_canvas()
        self._update_sel()

    def _update_sel(self, *a):
        if self._sel_top is None: return
        if not self._selected:
            for r in (self._sel_top, self._sel_bottom, self._sel_left, self._sel_right): r.size = (0, 0)
            return
        t = dp(self.SELECT_TH); x, y = self.x, self.y; w, h = self.width, self.height
        self._sel_top.pos = (x, y + h - t); self._sel_top.size = (w, t)
        self._sel_bottom.pos = (x, y); self._sel_bottom.size = (w, t)
        self._sel_left.pos = (x, y); self._sel_left.size = (t, h)
        self._sel_right.pos = (x + w - t, y); self._sel_right.size = (t, h)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if getattr(touch, 'button', None) == 'right':
                if self._on_right_click is not None:
                    try: self._on_right_click(touch)
                    except Exception as e: print("Right-click handler error:", e)
                return True
            elif getattr(touch, 'button', None) == 'left':
                if self._on_left_click is not None:
                    try: self._on_left_click(touch); return True  
                    except Exception as e: print("Left-click handler error:", e)
        return super().on_touch_down(touch)