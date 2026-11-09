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

# Кэш для измерения текста (ускоряет загрузку таблицы в разы)
_TEXT_WIDTH_CACHE = {}
def measure_text_width(text, font_size=14):
    if not text:
        return 0
    key = (str(text), font_size)
    if key in _TEXT_WIDTH_CACHE:
        return _TEXT_WIDTH_CACHE[key]
    try:
        core = CoreLabel(text=str(text), font_size=dp(font_size),
                         font_name=FONT_NAME)
        core.refresh()
        w = core.texture.size[0]
        _TEXT_WIDTH_CACHE[key] = w
        return w
    except Exception:
        return len(str(text)) * 8

_TEXT_HEIGHT_CACHE = {}
def measure_text_height(text, width, font_size=14):
    """Вычисляет высоту текста с учетом переноса строк."""
    if not text:
        return 0
    key = (str(text), width, font_size)
    if key in _TEXT_HEIGHT_CACHE:
        return _TEXT_HEIGHT_CACHE[key]
    try:
        core = CoreLabel(text=str(text), font_size=dp(font_size),
                         font_name=FONT_NAME, text_size=(width, None))
        core.refresh()
        h = core.texture.size[1]
        _TEXT_HEIGHT_CACHE[key] = h
        return h
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
        if 'button' in touch.profile and touch.button in ('scrollup', 'scrolldown', 'scrollleft', 'scrollright'):
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
        # Обрабатываем только события колесика мыши
        if 'button' in touch.profile and touch.button in ('scrollup', 'scrolldown', 'scrollleft', 'scrollright'):
            from ui_widgets import DayCell
            is_over_day_cell = False
            
            # Проверяем, находится ли курсор непосредственно над ячейкой с днями
            for child in self.walk():
                if isinstance(child, DayCell):
                    try:
                        lx, ly = child.to_widget(*touch.pos)
                        if 0 <= lx <= child.width and 0 <= ly <= child.height:
                            is_over_day_cell = True
                            break
                    except Exception:
                        pass

            # Если курсор над ячейкой с днями -> крутим влево/вправо
            if is_over_day_cell:
                if self.children and self.children[0].width <= self.width:
                    self.scroll_x = 0
                    return True

                step = 0.1
                if touch.button in ('scrollup', 'scrollleft'):
                    self.scroll_x = max(0.0, self.scroll_x - step)
                else:
                    self.scroll_x = min(1.0, self.scroll_x + step)

                return True
            
            # Если курсор НЕ над ячейкой (например, над заголовком или пустым местом), 
            # то не перехватываем событие, пусть работает стандартный вертикальный скролл
            return False

        return super().on_scroll_start(touch, check_children)
    
from kivy.effects.scroll import ScrollEffect
from kivy.properties import NumericProperty


class NoOverscrollEffect(ScrollEffect):
    """ScrollEffect без упругого отскока."""
    overscroll = NumericProperty(0)


def bind_enter_key(popup, callback):
    """Привязывает Enter (и Numpad Enter) к вызову callback при открытом popup."""
    from kivy.core.window import Window
    from kivy.clock import Clock
    
    def _on_key_down(window, key, scancode, codepoint, modifiers):
        if key in (13, 271):  # 13 - Enter, 271 - Numpad Enter
            if Window.children and Window.children[0] is popup:
                callback()
                return True
        return False
        
    Window.bind(on_key_down=_on_key_down)
    
    def _on_dismiss(*args):
        # Откладываем отвязку на следующий кадр, чтобы не ломать итерацию по колбэкам в Window
        Clock.schedule_once(lambda dt: Window.unbind(on_key_down=_on_key_down), 0)
        
    popup.bind(on_dismiss=_on_dismiss)


def ask_password_and_run(password, on_success,
                         title="Подтверждение удаления",
                         description=None,
                         btn_text="Удалить",
                         password_prompt="Введите пароль для удаления:"):
    """Попап с запросом пароля. При верном пароле вызывает on_success()."""
    from kivy.uix.popup import Popup
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from ui_widgets import HoverButton as Button
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
        text=password_prompt,
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
    
    btn_bg = (0.9, 0.35, 0.35, 1) if btn_text == "Удалить" else (0.25, 0.55, 0.85, 1)
    
    ok = Button(text=btn_text,
                background_color=btn_bg,
                color=(1, 1, 1, 1), font_name=FONT_NAME,
                font_size=dp(15), bold=True)
    cancel = Button(text="Отмена", color=(1, 1, 1, 1),
                    font_name=FONT_NAME, font_size=dp(15), bold=True)
    btns.add_widget(ok)
    btns.add_widget(cancel)
    content.add_widget(btns)

    popup = Popup(title=title, content=content,
                  size_hint=(0.45, None), height=dp(220),
                  title_color=LABEL_LIGHT, title_font=FONT_NAME,
                  auto_dismiss=False) 

    def do_ok(*a):
        if pw.text == password:
            popup.dismiss()
            
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: on_success(), 0.1)
        else:
            err.text = "Неверный пароль"
            pw.text = ""

    ok.bind(on_press=do_ok)
    cancel.bind(on_press=popup.dismiss)
    pw.bind(on_text_validate=do_ok)
    
    bind_enter_key(popup, do_ok)
    popup.open()