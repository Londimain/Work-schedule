# kivy_patches.py
# -*- coding: utf-8 -*-
from kivy.uix.textinput import TextInput

_CTRL_ALIASES = {
    1089: 99,   # с → c
    1057: 67,   # С → C
    1084: 118,  # м → v
    1052: 86,   # М → V
    1095: 120,  # ч → x
    1063: 88,   # Ч → X
    1092: 97,   # ф → a
    1060: 65,   # Ф → A
    1103: 122,  # я → z
    1071: 90,   # Я → Z
}

def _translate_keycode(keycode, modifiers):
    """Переводит кириллический код клавиши в ASCII при зажатом Ctrl."""
    if not modifiers or 'ctrl' not in modifiers:
        return keycode
    if isinstance(keycode, (tuple, list)):
        k = keycode[0]
        if k in _CTRL_ALIASES:
            return (_CTRL_ALIASES[k],) + tuple(keycode[1:])
    elif keycode in _CTRL_ALIASES:
        return _CTRL_ALIASES[keycode]
    return keycode

_orig_ti_key_down = TextInput.keyboard_on_key_down

def _patched_ti_key_down(self, window, keycode, text, modifiers):
    keycode = _translate_keycode(keycode, modifiers)
    return _orig_ti_key_down(self, window, keycode, text, modifiers)

# КРИТИЧЕСКИ ВАЖНО: Kivy ищет метод по его имени (__name__).
# Без этой строчки Kivy выдаст ошибку AttributeError при вводе текста (например, пароля).
_patched_ti_key_down.__name__ = 'keyboard_on_key_down'

TextInput.keyboard_on_key_down = _patched_ti_key_down