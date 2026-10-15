# ui_widgets.py
# -*- coding: utf-8 -*-
"""Кастомные виджеты: поля, спиннеры, ячейки, вертикальные заголовки."""
import config  # noqa: F401 — гарантирует настройку Kivy

from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Rectangle, PushMatrix, PopMatrix, Rotate
from kivy.metrics import dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from config import (FONT_NAME, LABEL_DARK, LABEL_LIGHT,
                    WEEKEND_BG, WEEKEND_FG, HOLIDAY_BG, HOLIDAY_FG,
                    WORKDAY_BG, WORKDAY_FG, HEADER_BG, HEADER_FG,
                    VHEADER_BG, VHEADER_FG, HEADER_DIVIDER,
                    WEEKDAYS_SHORT)
from ui_helpers import add_left_border, add_right_border


# ---------------------------------------------------------------------------
class NavTextInput(TextInput):
    """TextInput с двумя внешними обработчиками:
       - extra_key_callback(key, modifiers) — перехват Ctrl+C/V
       - nav_callback(key, modifiers)       — навигация по ячейкам
    Возврат True означает, что событие обработано и TextInput не должен
    выполнять своё действие.

    Дополнительно:
      • первый печатный символ после получения фокуса заменяет всё
        содержимое ячейки (как в Excel) — реализовано в insert_text;
      • при зажатом Shift касание поглощается: TextInput не получает
        фокус и не рисует синий прямоугольник выделения поверх
        фоновой подсветки ячейки (логика выделения диапазона —
        на уровне вкладки «Табель»).
    """
    nav_callback = None
    extra_key_callback = None
    _just_focused = False

    # Общий на все экземпляры флаг: зажат ли Shift.
    # Обновляется вкладкой «Табель» (_on_win_key_down / _on_win_key_up).
    shift_state = {'held': False}

    def on_touch_down(self, touch):
        if NavTextInput.shift_state['held'] and self.collide_point(*touch.pos):
            # Shift+клик: касание поглощаем. Фон ячейки уже подсвечен
            # через _on_cell_touch_down на уровне DayCell/ResultCell.
            # Без фокуса не будет ни курсора, ни встроенного
            # текстового выделения.
            return True
        return super().on_touch_down(touch)

    def insert_text(self, substring, from_undo=False):
        # Первый печатный символ после фокуса заменяет старое значение.
        if self._just_focused and substring and not from_undo:
            self._just_focused = False
            if not self.selection_text:
                # Очищаем поле, чтобы новый символ заменил всё,
                # а не добавился к старому («1.85» → «3», а не «1.3»).
                self.text = ''
                try:
                    self.cursor = (0, 0)
                except Exception:
                    pass
        return super().insert_text(substring, from_undo=from_undo)

    def keyboard_on_key_down(self, window, keycode, text, modifiers):
        # Определяем числовой код клавиши
        try:
            if isinstance(keycode, (tuple, list)):
                key = keycode[0]
            else:
                key = keycode
        except Exception:
            key = None

        mods = modifiers or []

        # 1. Сначала спец-перехват (Ctrl+C/V при выделенном диапазоне)
        if self.extra_key_callback is not None and key is not None:
            try:
                if self.extra_key_callback(key, mods):
                    return True
            except Exception:
                pass

        # 2. Затем обычная навигация
        if self.nav_callback is not None and key is not None:
            try:
                if self.nav_callback(key, mods):
                    return True
            except Exception:
                pass

        return super().keyboard_on_key_down(window, keycode, text, modifiers)


# ---------------------------------------------------------------------------
class CenteredField(FloatLayout):
    def __init__(self, text='', font_size=dp(15),
                 pad_lr=dp(10), fg_color=LABEL_DARK, halign='center',
                 on_key_callback=None, extra_key_callback=None,
                 **ti_kwargs):
        super().__init__()
        ti_kwargs.pop('valign', None)
        ti_kwargs.pop('input_height', None)

        self._font_size = float(font_size)
        self._fg = fg_color
        self._halign = halign
        self._pad_lr = int(round(pad_lr))
        self._cursor_on = True

        self.input = NavTextInput(
            text=text, multiline=False, font_size=font_size,
            font_name=FONT_NAME,
            foreground_color=(0, 0, 0, 0),
            cursor_color=(0, 0, 0, 0), cursor_width=0,
            cursor_blink=False,
            selection_color=(0.20, 0.45, 0.90, 0.40),
            padding=[0, 0, 0, 0],
            halign='center',
            **ti_kwargs,
        )
        self.input.nav_callback = on_key_callback
        self.input.extra_key_callback = extra_key_callback
        self.add_widget(self.input)
        self.input.bind(text=self._on_text)
        self.input.bind(focus=self._on_focus)

        self._texture = None
        self._rect = None
        self._cursor_rect = None

        self.bind(pos=self._redraw, size=self._redraw)
        self._rebuild_texture(text)

        self._blink_ev = None
        Clock.schedule_once(self._start_blink, 0)

    def _start_blink(self, dt):
        self._blink_ev = Clock.schedule_interval(self._blink, 0.5)

    def _blink(self, dt):
        if self.input.focused:
            self._cursor_on = not self._cursor_on
        else:
            self._cursor_on = False
        self._redraw()

    def _on_focus(self, inst, value):
        self._cursor_on = True
        if value:
            self.input._just_focused = True
        else:
            self.input._just_focused = False
        self._redraw()

    def on_parent(self, inst, parent):
        if parent is None and self._blink_ev is not None:
            self._blink_ev.cancel()
            self._blink_ev = None

    def _rebuild_texture(self, text):
        self.canvas.after.clear()
        core = CoreLabel(text=text, font_size=self._font_size,
                         color=self._fg, font_name=FONT_NAME)
        core.refresh()
        self._texture = core.texture

        with self.canvas.after:
            Color(1, 1, 1, 1)
            self._rect = Rectangle(texture=self._texture, pos=(0, 0),
                                    size=self._texture.size)
            Color(0.20, 0.45, 0.90, 1)
            self._cursor_rect = Rectangle(pos=(-100, -100), size=(0, 0))
        self._redraw()

    def _on_text(self, inst, value):
        self._rebuild_texture(value)

    def _redraw(self, *a):
        self.input.pos = (self.x, self.y)
        self.input.size = (self.width, self.height)
        if self._texture is None:
            return
        tw, th = self._texture.size
        cy = self.y + self.height / 2.0
        if self._halign == 'left':
            x = self.x + self._pad_lr
        elif self._halign == 'right':
            x = self.x + self.width - tw - self._pad_lr
        else:
            x = self.x + (self.width - tw) / 2.0
        y = cy - th / 2.0
        self._rect.pos = (x, y)
        self._rect.size = (tw, th)
        if self._cursor_rect is not None:
            if self._cursor_on and self.input.focused:
                ch = self._font_size * 1.15
                self._cursor_rect.pos = (x + tw + 1, cy - ch / 2.0)
                self._cursor_rect.size = (1.5, ch)
            else:
                self._cursor_rect.pos = (-100, -100)
                self._cursor_rect.size = (0, 0)

    @property
    def text(self):
        return self.input.text

    @text.setter
    def text(self, value):
        self.input.text = value


# ---------------------------------------------------------------------------
class LightSpinnerOption(SpinnerOption):
    NORMAL_BG = (0.14, 0.14, 0.16, 1)
    HOVER_BG  = (0.20, 0.45, 0.85, 1)
    TEXT_COL  = (1.00, 1.00, 1.00, 1)
    OUTLINE   = (0.00, 0.00, 0.00, 1)
    LINE_COL  = (0.42, 0.42, 0.48, 1)

    def __init__(self, **kwargs):
        kwargs.setdefault('background_normal', '')
        kwargs.setdefault('background_down', '')
        kwargs.setdefault('background_color', (0, 0, 0, 0))
        kwargs.setdefault('halign', 'center')
        kwargs.setdefault('valign', 'middle')
        kwargs.setdefault('font_size', 16)
        kwargs.setdefault('bold', True)
        kwargs.setdefault('font_name', FONT_NAME)
        kwargs['color'] = self.TEXT_COL
        super().__init__(**kwargs)

        self.color = self.TEXT_COL
        self.disabled_color = self.TEXT_COL
        self.bold = True

        with self.canvas.before:
            self._bg_color = Color(*self.NORMAL_BG)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        with self.canvas.after:
            Color(*self.LINE_COL)
            self._line = Rectangle(pos=self.pos, size=(self.width, 1))

        self.bind(pos=self._upd, size=self._upd)
        self.bind(state=self._on_state)
        self.bind(size=self._fix_align)

    def _upd(self, *a):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._line.pos = (self.x, self.y)
        self._line.size = (self.width, 1)

    def _fix_align(self, *a):
        self.text_size = (self.width - 8, self.height)

    def _on_state(self, inst, value):
        if value == 'down':
            self._bg_color.rgba = self.HOVER_BG
        else:
            self._bg_color.rgba = self.NORMAL_BG
        self.color = self.TEXT_COL
        self.bold = True


class CenteredSpinner(AnchorLayout):
    def __init__(self, text='', values=None, spinner_height=dp(30),
                 font_size=dp(15),
                 bg_color=(0.85, 0.92, 1.00, 1),
                 **sp_kwargs):
        super().__init__(anchor_x='center', anchor_y='center')
        sp_kwargs.setdefault('font_name', FONT_NAME)
        self.spinner = Spinner(
            text=text, values=values or [],
            size_hint=(1, None), height=spinner_height,
            font_size=font_size,
            background_color=bg_color,
            background_normal='', background_down='',
            color=(0.05, 0.05, 0.25, 1),
            option_cls=LightSpinnerOption,
            **sp_kwargs,
        )
        self.spinner.bind(is_open=self._on_open)
        self.add_widget(self.spinner)

    def _on_open(self, inst, value):
        if value:
            Clock.schedule_once(self._align_dropdown, 0)
            Clock.schedule_once(self._align_dropdown, 0.05)

    def _align_dropdown(self, dt):
        try:
            drop = self.spinner._dropdown
            sp = self.spinner
            wx, wy = sp.to_window(sp.x, sp.y)
            drop.width = sp.width
            drop.x = wx
            drop.top = wy
        except Exception:
            pass

    @property
    def text(self):
        return self.spinner.text

    @text.setter
    def text(self, value):
        self.spinner.text = value


# ---------------------------------------------------------------------------
class VerticalLabel(Widget):
    def __init__(self, text='', color=VHEADER_FG, bg=VHEADER_BG,
                 bold=True, font_size=10, pad_top=0, pad_bottom=0,
                 **kwargs):
        super().__init__(**kwargs)
        self._pad_top = dp(pad_top)
        self._pad_bottom = dp(pad_bottom)
        with self.canvas.before:
            Color(*bg)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        core = CoreLabel(text=text, font_size=dp(font_size),
                         bold=bold, color=color, font_name=FONT_NAME)
        core.refresh()
        self._texture = core.texture
        self._tw, self._th = core.texture.size
        with self.canvas:
            Color(1, 1, 1, 1)
            PushMatrix()
            self._rot = Rotate(angle=90, origin=self.center)
            self._rect = Rectangle(texture=self._texture, pos=self.pos,
                                    size=(self._tw, self._th))
            PopMatrix()
        self.bind(pos=self._update, size=self._update)
        Clock.schedule_once(lambda *a: self._update(), 0)

    def _update(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size
        cx = self.x + self.width / 2
        cy = self.y + self.height / 2 + (self._pad_bottom - self._pad_top) / 2.0
        self._rot.origin = (cx, cy)
        self._rect.pos = (cx - self._tw / 2, cy - self._th / 2)
        self._rect.size = (self._tw, self._th)


# ---------------------------------------------------------------------------
class DayCell(BoxLayout):
    def __init__(self, text='', day_type='work', show_right=True,
                 on_key_callback=None, on_cell_touch_down=None,
                 extra_key_callback=None, **kwargs):
        super().__init__(orientation='horizontal', **kwargs)
        self._on_cell_touch_down = on_cell_touch_down
        self._highlighted = False

        if day_type == 'holiday':
            bg, fg = HOLIDAY_BG, HOLIDAY_FG
        elif day_type == 'weekend':
            bg, fg = WEEKEND_BG, WEEKEND_FG
        else:
            bg, fg = WORKDAY_BG, WORKDAY_FG
        with self.canvas.before:
            Color(*bg)
            self._rect = Rectangle(pos=self.pos, size=self.size)
            Color(0.20, 0.45, 0.90, 0.35)
            self._hl_rect = Rectangle(pos=self.pos, size=(0, 0))
        self.bind(pos=self._update_rect, size=self._update_rect)
        if show_right:
            add_right_border(self, color=HEADER_DIVIDER, thickness=1)
        _w = CenteredField(
            text=text, font_size=dp(14), pad_lr=dp(2),
            halign='center', fg_color=fg,
            background_color=(0, 0, 0, 0),
            background_normal='', background_active='',
            on_key_callback=on_key_callback,
            extra_key_callback=extra_key_callback,
        )
        self.input = _w.input
        self.add_widget(_w)

    def set_highlight(self, on):
        self._highlighted = bool(on)
        self._update_rect()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self._on_cell_touch_down is not None:
                try:
                    self._on_cell_touch_down(self, touch)
                except Exception:
                    pass
        return super().on_touch_down(touch)

    def _update_rect(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size
        if self._highlighted:
            self._hl_rect.pos = self.pos
            self._hl_rect.size = self.size
        else:
            self._hl_rect.size = (0, 0)


class ResultCell(BoxLayout):
    def __init__(self, text='0', fg_color=LABEL_LIGHT,
                 show_left=False, show_right=True,
                 border_color=(0, 0, 0, 1), border_th=1,
                 on_key_callback=None, on_cell_touch_down=None,
                 extra_key_callback=None, **kwargs):
        super().__init__(orientation='horizontal', **kwargs)
        self._on_cell_touch_down = on_cell_touch_down
        self._highlighted = False
        if show_left:
            add_left_border(self, color=border_color, thickness=border_th)
        if show_right:
            add_right_border(self, color=border_color, thickness=border_th)
        with self.canvas.before:
            Color(0.20, 0.45, 0.90, 0.35)
            self._hl_rect = Rectangle(pos=self.pos, size=(0, 0))
        self.bind(pos=self._update_hl, size=self._update_hl)
        _w = CenteredField(
            text=text, font_size=dp(14), pad_lr=dp(2),
            halign='center', fg_color=fg_color,
            background_color=(0, 0, 0, 0),
            background_normal='', background_active='',
            on_key_callback=on_key_callback,
            extra_key_callback=extra_key_callback,
        )
        self.input = _w.input
        self._field = _w
        self.add_widget(_w)

    def set_highlight(self, on):
        self._highlighted = bool(on)
        self._update_hl()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self._on_cell_touch_down is not None:
                try:
                    self._on_cell_touch_down(self, touch)
                except Exception:
                    pass
        return super().on_touch_down(touch)

    def _update_hl(self, *a):
        if self._highlighted:
            self._hl_rect.pos = self.pos
            self._hl_rect.size = self.size
        else:
            self._hl_rect.size = (0, 0)

    @property
    def text(self):
        return self._field.text

    @text.setter
    def text(self, value):
        self._field.text = value


class DayHeader(BoxLayout):
    def __init__(self, day, day_type='work', weekday_idx=None,
                 show_right=True, height=None, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        if day_type == 'holiday':
            bg, fg = HOLIDAY_BG, HOLIDAY_FG
        elif day_type == 'weekend':
            bg, fg = WEEKEND_BG, WEEKEND_FG
        else:
            bg, fg = HEADER_BG, HEADER_FG
        with self.canvas.before:
            Color(*bg)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)
        if show_right:
            add_right_border(self, color=HEADER_DIVIDER, thickness=1)
        top = BoxLayout(orientation='vertical',
                        size_hint_y=None, height=dp(44))
        top.add_widget(Label(text=str(day), bold=True,
                             font_size=dp(14), color=fg,
                             font_name=FONT_NAME,
                             size_hint_y=None, height=dp(22)))
        if weekday_idx is not None:
            top.add_widget(Label(text=WEEKDAYS_SHORT[weekday_idx],
                                 bold=True, font_size=dp(10), color=fg,
                                 font_name=FONT_NAME,
                                 size_hint_y=None, height=dp(18)))
        self.add_widget(top)
        self.add_widget(Widget())

    def _update_rect(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size