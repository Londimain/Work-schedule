# ui_inputs.py
# -*- coding: utf-8 -*-
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from config import FONT_NAME, LABEL_DARK

class HoverButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hovering = False
        with self.canvas.after:
            self._hover_color = Color(1, 1, 1, 0)
            self._hover_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect, state=self._on_state)
        from kivy.core.window import Window
        Window.bind(mouse_pos=self._on_mouse_pos)
        self.bind(parent=self._on_parent)

    def _update_rect(self, *a):
        self._hover_rect.pos = self.pos
        self._hover_rect.size = self.size
        if hasattr(self, '_border_line'):
            self._border_line.rectangle = (self.x, self.y, self.width, self.height)

    def _on_parent(self, instance, parent):
        if parent is None:
            from kivy.core.window import Window
            try: Window.unbind(mouse_pos=self._on_mouse_pos)
            except Exception: pass

    def _on_state(self, inst, value): self._update_hover()

    def _on_mouse_pos(self, window, pos):
        if not self.get_root_window() or self.disabled: return
        try:
            wx, wy = self.to_window(self.x, self.y)
            if wx <= pos[0] <= wx + self.width and wy <= pos[1] <= wy + self.height:
                if not self._hovering:
                    self._hovering = True; self._update_hover()
            else:
                if self._hovering:
                    self._hovering = False; self._update_hover()
        except Exception: pass

    def _update_hover(self):
        self._hover_color.rgba = (1, 1, 1, 0.15) if (self._hovering or self.state == 'down') else (1, 1, 1, 0)

class NavTextInput(TextInput):
    nav_callback = None
    extra_key_callback = None
    _just_focused = False
    shift_state = {'held': False}

    def on_touch_down(self, touch):
        if getattr(touch, 'is_mouse_scrolling', False): return False  
        if NavTextInput.shift_state['held'] and self.collide_point(*touch.pos): return True
        return super().on_touch_down(touch)

    def insert_text(self, substring, from_undo=False):
        if self._just_focused and substring and not from_undo:
            self._just_focused = False
            if not self.selection_text:
                self.text = ''
                try: self.cursor = (0, 0)
                except Exception: pass
        return super().insert_text(substring, from_undo=from_undo)

    def keyboard_on_key_down(self, window, keycode, text, modifiers):
        key = keycode[0] if isinstance(keycode, (tuple, list)) else keycode
        mods = modifiers or []
        if self.extra_key_callback is not None and key is not None:
            try:
                if self.extra_key_callback(key, mods): return True
            except Exception: pass
        if self.nav_callback is not None and key is not None:
            try:
                if self.nav_callback(key, mods): return True
            except Exception: pass
        return super().keyboard_on_key_down(window, keycode, text, modifiers)

class CenteredField(FloatLayout):
    def __init__(self, text='', font_size=dp(15), pad_lr=dp(10), fg_color=LABEL_DARK, halign='center',
                 on_key_callback=None, extra_key_callback=None, **ti_kwargs):
        super().__init__()
        for k in ['valign', 'input_height', 'background_color', 'background_normal', 'background_active']:
            ti_kwargs.pop(k, None)
        self._font_size = float(font_size); self._fg = fg_color; self._halign = halign
        self._pad_lr = int(round(pad_lr)); self._cursor_on = True
        self.input = NavTextInput(text=text, multiline=False, font_size=font_size, font_name=FONT_NAME,
            foreground_color=(0, 0, 0, 0), cursor_color=(0, 0, 0, 0), cursor_width=0, cursor_blink=False,
            selection_color=(0.20, 0.45, 0.90, 0.40), padding=[0, 0, 0, 0], halign='center',
            background_color=(0, 0, 0, 0), background_normal='', background_active='', **ti_kwargs)
        self.input.nav_callback = on_key_callback; self.input.extra_key_callback = extra_key_callback
        self.add_widget(self.input)
        self.input.bind(text=self._on_text, focus=self._on_focus)
        self._texture = None; self._rect = None; self._cursor_rect = None; self._blink_ev = None
        self.bind(pos=self._redraw, size=self._redraw)
        self._rebuild_texture(text)

    def _blink(self, dt):
        self._cursor_on = not self._cursor_on if self.input.focused else False
        self._redraw()

    def _on_focus(self, inst, value):
        self._cursor_on = True
        if value:
            self.input._just_focused = True
            if self._blink_ev is None: self._blink_ev = Clock.schedule_interval(self._blink, 0.5)
        else:
            self.input._just_focused = False
            if self._blink_ev is not None: self._blink_ev.cancel(); self._blink_ev = None
        self._redraw()

    def on_parent(self, inst, parent):
        if parent is None and self._blink_ev is not None:
            self._blink_ev.cancel(); self._blink_ev = None

    def _rebuild_texture(self, text):
        self.canvas.after.clear()
        if not text:
            self._texture = None; self._rect = None
            with self.canvas.after:
                Color(0.20, 0.45, 0.90, 1)
                self._cursor_rect = Rectangle(pos=(-100, -100), size=(0, 0))
            self._redraw(); return
        core = CoreLabel(text=str(text), font_size=self._font_size, color=self._fg, font_name=FONT_NAME)
        core.refresh(); self._texture = core.texture
        with self.canvas.after:
            Color(1, 1, 1, 1)
            self._rect = Rectangle(texture=self._texture, pos=(0, 0), size=self._texture.size)
            Color(0.20, 0.45, 0.90, 1)
            self._cursor_rect = Rectangle(pos=(-100, -100), size=(0, 0))
        self._redraw()

    def _on_text(self, inst, value): self._rebuild_texture(value)

    def _redraw(self, *a):
        self.input.pos = (self.x, self.y); self.input.size = (self.width, self.height)
        if self._texture is None:
            if self._cursor_rect is not None:
                if self._cursor_on and self.input.focused:
                    ch = self._font_size * 1.15
                    cx = self.x + self.width / 2.0; cy = self.y + self.height / 2.0
                    self._cursor_rect.pos = (cx, cy - ch / 2.0); self._cursor_rect.size = (1.5, ch)
                else: self._cursor_rect.pos = (-100, -100); self._cursor_rect.size = (0, 0)
            return
        tw, th = self._texture.size; cy = self.y + self.height / 2.0
        if self._halign == 'left': x = self.x + self._pad_lr
        elif self._halign == 'right': x = self.x + self.width - tw - self._pad_lr
        else: x = self.x + (self.width - tw) / 2.0
        y = cy - th / 2.0
        self._rect.pos = (x, y); self._rect.size = (tw, th)
        if self._cursor_rect is not None:
            if self._cursor_on and self.input.focused:
                ch = self._font_size * 1.15
                self._cursor_rect.pos = (x + tw + 1, cy - ch / 2.0); self._cursor_rect.size = (1.5, ch)
            else: self._cursor_rect.pos = (-100, -100); self._cursor_rect.size = (0, 0)

    @property
    def text(self): return self.input.text
    @text.setter
    def text(self, value): self.input.text = value