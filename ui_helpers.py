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

def measure_text_height(text, width, font_size=14):
    """Вычисляет высоту текста с учетом переноса строк."""
    if not text:
        return 0
    try:
        core = CoreLabel(text=str(text), font_size=dp(font_size),
                         font_name=FONT_NAME, text_size=(width, None))
        core.refresh()
        return core.texture.size[1]
    except Exception:
        return dp(20)


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
                    if abs(other.scroll_y - value) > 0.001:
                        other.scroll_y = value
            finally:
                state['busy'] = False
        return cb

    for sv in scrolls:
        sv.bind(scroll_y=make_cb(sv))

class SmartScrollView(ScrollView):
    """ScrollView, который не перехватывает касание, если оно
    началось внутри TextInput — иначе не работает выделение мышью."""

    def _find_textinput_under(self, touch):
        try:
            from kivy.uix.textinput import TextInput
            for w in self.walk():
                if isinstance(w, TextInput) and not w.disabled:
                    try:
                        lx, ly = w.to_widget(*touch.pos)
                        if 0 <= lx <= w.width and 0 <= ly <= w.height:
                            return w
                    except Exception:
                        continue
        except Exception:
            pass
        return None

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if 'button' in touch.profile and touch.button in ('scrollup', 'scrolldown'):
            return super().on_touch_down(touch)
        if self._find_textinput_under(touch) is not None:
            return False
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._find_textinput_under(touch) is not None:
            return False
        return super().on_touch_move(touch)

class HorizontalScrollView(SmartScrollView):
    def on_scroll_start(self, touch, check_children=True):
        if 'button' in touch.profile and touch.button in ('scrollup', 'scrolldown'):
            step = 0.05
            if touch.button == 'scrollup':
                self.scroll_x = max(0.0, self.scroll_x - step)
            else:
                self.scroll_x = min(1.0, self.scroll_x + step)
            return True
        return super().on_scroll_start(touch, check_children)
    
from kivy.effects.scroll import ScrollEffect
from kivy.properties import NumericProperty


class NoOverscrollEffect(ScrollEffect):
    """ScrollEffect без упругого отскока."""
    overscroll = NumericProperty(0)
    
def ask_password_and_run(password, on_success,
                         title="Подтверждение удаления",
                         description=None):
    """Попап с запросом пароля. При верном пароле вызывает on_success()."""
    from kivy.uix.popup import Popup
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.button import Button
    from kivy.uix.textinput import TextInput
    from kivy.metrics import dp
    from config import FONT_NAME, LABEL_LIGHT

    content = BoxLayout(orientation='vertical', spacing=8, padding=12,
                        size_hint=(1, None), height=dp(230))

    if description:
        d = Label(text=description, color=LABEL_LIGHT,
                  font_name=FONT_NAME, font_size=dp(15),
                  halign='center', valign='middle',
                  outline_color=(0, 0, 0, 1), outline_width=1,
                  size_hint_y=None)
        d.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        d.bind(texture_size=lambda i, v: setattr(i, 'height', v[1]))
        content.add_widget(d)

    content.add_widget(Label(
        text="Введите пароль для удаления:",
        color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(14),
        halign='center', valign='middle',
        outline_color=(0, 0, 0, 1), outline_width=1,
        size_hint_y=None, height=dp(24)))

    pw = TextInput(
        multiline=False, password=True,
        font_size=dp(15), font_name=FONT_NAME,
        foreground_color=(0.05, 0.05, 0.05, 1),
        background_color=(1, 1, 1, 1),
        cursor_color=(0.10, 0.30, 0.70, 1),
        cursor_width=dp(2),
        padding=[dp(8), dp(6), dp(8), dp(6)],
        size_hint_y=None, height=dp(34))
    content.add_widget(pw)

    err = Label(text="", color=(1, 0.4, 0.4, 1),
                font_name=FONT_NAME, font_size=dp(13),
                size_hint_y=None, height=dp(20))
    content.add_widget(err)

    btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=10)
    ok = Button(text="Удалить",
                background_color=(0.9, 0.35, 0.35, 1),
                color=(1, 1, 1, 1), font_name=FONT_NAME,
                font_size=dp(15), bold=True)
    cancel = Button(text="Отмена", color=(1, 1, 1, 1),
                    font_name=FONT_NAME, font_size=dp(15), bold=True)
    btns.add_widget(ok)
    btns.add_widget(cancel)
    content.add_widget(btns)

    popup = Popup(title=title, content=content,
                  size_hint=(0.48, None), height=dp(280),
                  title_color=LABEL_LIGHT, title_font=FONT_NAME,
                  auto_dismiss=False) 

    def do_ok(*a):
        if pw.text == password:
            popup.dismiss()
            on_success()
        else:
            err.text = "Неверный пароль"
            pw.text = ""

    ok.bind(on_press=do_ok)
    cancel.bind(on_press=popup.dismiss)
    pw.bind(on_text_validate=do_ok)
    popup.open()