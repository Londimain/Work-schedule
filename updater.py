# updater.py
# -*- coding: utf-8 -*-
import os
import sys
import json
import urllib.request
import subprocess
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp

from config import FONT_NAME, LABEL_LIGHT, APP_VERSION, DATA_FILE
from ui_helpers import bind_enter_key
from ui_widgets import HoverButton

def get_update_url():
    try:
        net_dir = os.path.dirname(DATA_FILE)
        return os.path.join(net_dir, "version.json")
    except Exception:
        return ""

def _parse_version(v_str):
    try:
        return [int(x) for x in v_str.strip().split('.')]
    except Exception:
        return [0, 0, 0]

def _show_info(title, text):
    """Простое окно с сообщением"""
    c = BoxLayout(orientation='vertical', spacing=15, padding=(15, 20, 15, 15))
    
    # Текст с переносом строк и выравниванием
    lbl = Label(text=text, color=LABEL_LIGHT, halign='center', valign='middle', 
                font_name=FONT_NAME, font_size=dp(14))
    lbl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
    c.add_widget(lbl)
    
    # Используем HoverButton для эффекта наведения
    b = HoverButton(text="ОК", size_hint_y=None, height=dp(40), 
                    font_name=FONT_NAME, background_color=(0.3, 0.7, 0.3, 1), color=(1,1,1,1))
    c.add_widget(b)
    
    # Делаем окно фиксированного небольшого размера
    p = Popup(title=title, content=c, size_hint=(None, None), size=(dp(450), dp(180)), 
              title_color=LABEL_LIGHT, title_font=FONT_NAME)
    
    b.bind(on_press=p.dismiss)
    p.open()

def check_for_updates(app, manual=False):
    """
    manual=False — тихая проверка при старте.
    manual=True  — проверка с кнопки (показывает сообщения, если нет обновлений или ошибка).
    """
    update_url = get_update_url()
    
    if not update_url or not os.path.exists(update_url):
        print(f"DEBUG: Файл version.json не найден по пути: {update_url}")
        if manual:
            Clock.schedule_once(lambda dt: _show_info("Проверка обновлений", f"Файл version.json не найден по пути:\n{update_url}"), 0)
        return

    def _bg_check(dt):
        try:
            if update_url.startswith("http"):
                req = urllib.request.Request(update_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode('utf-8'))
            else:
                with open(update_url, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            latest_ver = data.get("latest_version")
            download_url = data.get("download_url")
            notes = data.get("release_notes", "Нет описания.")

            if not latest_ver or not download_url:
                if manual:
                    Clock.schedule_once(lambda dt: _show_info("Ошибка", "В файле version.json отсутствуют нужные поля (latest_version или download_url)."), 0)
                return

            # Защита от неверного пути
            if str(download_url).endswith('.json') or 'tabel_data.json' in str(download_url) or not str(download_url).strip():
                download_url = f"Tabel_Setup_v{latest_ver}.exe"

            current_ver = _parse_version(APP_VERSION)
            new_ver = _parse_version(latest_ver)

            if new_ver > current_ver:
                Clock.schedule_once(lambda dt: _show_update_popup(app, latest_ver, download_url, notes), 0)
            else:
                print(f"DEBUG: Обновление не требуется. Текущая: {APP_VERSION}, В файле: {latest_ver}")
                if manual:
                    Clock.schedule_once(lambda dt: _show_info("Обновление не требуется", f"Вы используете последнюю версию программы (v{APP_VERSION})."), 0)
                
        except Exception as e:
            import traceback
            err_text = f"Не удалось прочитать version.json:\n{type(e).__name__}: {e}\n\nПуть: {update_url}"
            print(err_text)
            if manual:
                Clock.schedule_once(lambda dt: _show_info("Ошибка проверки обновления", err_text), 0)

    import threading
    threading.Thread(target=_bg_check, args=(0,)).start()

def _show_update_popup(app, new_version, download_url, notes):
    content = BoxLayout(orientation='vertical', spacing=10, padding=15)

    content.add_widget(Label(
        text=f"Доступна новая версия программы: [b]{new_version}[/b]\n"
             f"Текущая версия: {APP_VERSION}",
        markup=True,
        color=LABEL_LIGHT, halign='center', valign='middle',
        font_name=FONT_NAME, font_size=dp(16),
        size_hint_y=None, height=dp(60)
    ))

    content.add_widget(Label(
        text="Что нового в этой версии:",
        color=(1, 0.85, 0.35, 1),
        halign='left', valign='middle',
        font_name=FONT_NAME, font_size=dp(15), bold=True,
        size_hint_y=None, height=dp(24)
    ))

    scroll = ScrollView(size_hint=(1, 1))
    notes_lbl = Label(
        text=notes if notes and notes.strip() else "Описание изменений не предоставлено.",
        color=(0.85, 0.85, 0.85, 1),
        halign='left', valign='top',
        font_name=FONT_NAME, font_size=dp(14),
        size_hint_y=None, padding=(dp(5), dp(5))
    )
    notes_lbl.bind(width=lambda *a: setattr(notes_lbl, 'text_size', (notes_lbl.width - dp(10), None)))
    notes_lbl.bind(texture_size=notes_lbl.setter('size'))
    
    scroll.add_widget(notes_lbl)
    content.add_widget(scroll)

    btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=10)
    btn_update = Button(
        text="Обновить сейчас", 
        background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1), 
        font_name=FONT_NAME, bold=True)
    btn_later = Button(
        text="Напомнить позже", 
        color=(1, 1, 1, 1), 
        font_name=FONT_NAME, bold=True)
    
    btns.add_widget(btn_update)
    btns.add_widget(btn_later)
    content.add_widget(btns)

    popup = Popup(
        title="Обновление программы", 
        content=content, 
        size_hint=(0.65, 0.6),
        title_color=LABEL_LIGHT, 
        title_font=FONT_NAME, 
        auto_dismiss=False
    )

    def do_update(*a):
        popup.dismiss()
        _download_and_run(app, download_url)

    btn_update.bind(on_press=do_update)
    btn_later.bind(on_press=popup.dismiss)
    bind_enter_key(popup, do_update)
    popup.open()

def _download_and_run(app, download_url):
    content = BoxLayout(orientation='vertical', spacing=10, padding=10)
    content.add_widget(Label(text="Загрузка обновления. Пожалуйста, подождите...", color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15)))
    popup = Popup(title="Обновление", content=content, size_hint=(0.4, 0.2), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
    popup.open()

    def _bg_download(dt):
        try:
            actual_url = download_url
            
            if not actual_url.startswith("http") and not os.path.isabs(actual_url):
                base_dir = os.path.dirname(DATA_FILE)
                actual_url = os.path.join(base_dir, actual_url)

            temp_dir = os.environ.get('TEMP', os.path.dirname(os.path.abspath(__file__)))
            local_setup_path = os.path.join(temp_dir, "Tabel_Setup_Update.exe")

            if actual_url.startswith("http"):
                urllib.request.urlretrieve(actual_url, local_setup_path)
            else:
                import shutil
                shutil.copy2(actual_url, local_setup_path)

            Clock.schedule_once(lambda dt: _run_installer(app, local_setup_path, popup), 0)

        except Exception as e:
            err_msg = str(e)
            Clock.schedule_once(lambda dt: _show_error(popup, err_msg), 0)

    import threading
    threading.Thread(target=_bg_download, args=(0,)).start()

def _run_installer(app, setup_path, popup):
    try:
        subprocess.Popen([setup_path, '/SILENT', '/CLOSEAPPLICATIONS', '/RESTARTAPPLICATIONS'])
        popup.dismiss()
        app.stop()
    except Exception as e:
        _show_error(popup, f"Не удалось запустить установщик: {e}")

def _show_error(popup, err_msg):
    popup.dismiss()
    c = BoxLayout(orientation='vertical', spacing=10, padding=10)
    c.add_widget(Label(text=f"Ошибка обновления:\n{err_msg}", color=(1, 0.4, 0.4, 1), halign='center', font_name=FONT_NAME))
    btn = Button(text="ОК", size_hint_y=None, height=dp(40), font_name=FONT_NAME)
    c.add_widget(btn)
    p = Popup(title="Ошибка", content=c, size_hint=(0.5, 0.3), title_color=LABEL_LIGHT, title_font=FONT_NAME)
    btn.bind(on_press=p.dismiss)
    p.open()