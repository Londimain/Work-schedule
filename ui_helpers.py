# ui_helpers.py
# -*- coding: utf-8 -*-
"""Мелкие UI-помощники: границы, измерение текста, синхронный скролл."""
import config  # noqa: F401 — гарантирует настройку Kivy

from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from config import FONT_NAME, DIVIDER_COLOR, HEADER_DIVIDER


def measure_text_width(text, font_size=14):
    if not text:
        return 0
    try:
        core = CoreLabel(text=str(text), font_size=dp(font_size),
                         font_name=FONT_NAME)
        core.refresh()
        return core.texture.size[0]
    except Exception:
        return len(str(text)) * 8


def add_bottom_border(widget, color=DIVIDER_COLOR, thickness=1):
    with widget.canvas.after:
        Color(*color)
        line = Rectangle(pos=(widget.x, widget.y),
                         size=(widget.width, thickness))

    def _update(*a):
        line.pos = (widget.x, widget.y)
        line.size = (widget.width, thickness)
    widget.bind(pos=_update, size=_update)


def add_top_border(widget, color=DIVIDER_COLOR, thickness=1):
    with widget.canvas.after:
        Color(*color)
        line = Rectangle(pos=(widget.x, widget.y + widget.height - thickness),
                         size=(widget.width, thickness))

    def _update(*a):
        line.pos = (widget.x, widget.y + widget.height - thickness)
        line.size = (widget.width, thickness)
    widget.bind(pos=_update, size=_update)


def add_right_border(widget, color=HEADER_DIVIDER, thickness=1):
    with widget.canvas.after:
        Color(*color)
        line = Rectangle(pos=(widget.x + widget.width - thickness, widget.y),
                         size=(thickness, widget.height))

    def _update(*a):
        line.pos = (widget.x + widget.width - thickness, widget.y)
        line.size = (thickness, widget.height)
    widget.bind(pos=_update, size=_update)


def add_left_border(widget, color=HEADER_DIVIDER, thickness=1):
    with widget.canvas.after:
        Color(*color)
        line = Rectangle(pos=(widget.x, widget.y),
                         size=(thickness, widget.height))

    def _update(*a):
        line.pos = (widget.x, widget.y)
        line.size = (thickness, widget.height)
    widget.bind(pos=_update, size=_update)


def vsep(color=DIVIDER_COLOR, thickness=1):
    w = Widget(size_hint_x=None, width=thickness)
    with w.canvas:
        Color(*color)
        rect = Rectangle(pos=w.pos, size=w.size)
    w.bind(pos=lambda i, v: setattr(rect, 'pos', v),
           size=lambda i, v: setattr(rect, 'size', v))
    return w


def sync_vertical(scrolls):
    state = {'busy': False}

    def make_cb(src):
        def cb(instance, value):
            if state['busy']:
                return
            state['busy'] = True
            try:
                for other in scrolls:
                    if other is src:
                        continue
                    if abs(other.scroll_y - value) > 1e-6:
                        other.scroll_y = value
            finally:
                state['busy'] = False
        return cb

    for sv in scrolls:
        sv.bind(scroll_y=make_cb(sv))


class HorizontalScrollView(ScrollView):
    def on_scroll_start(self, touch, check_children=True):
        if 'button' in touch.profile and touch.button in ('scrollup', 'scrolldown'):
            step = 0.05
            if touch.button == 'scrollup':
                self.scroll_x = max(0.0, self.scroll_x - step)
            else:
                self.scroll_x = min(1.0, self.scroll_x + step)
            return True
        return super().on_scroll_start(touch, check_children)