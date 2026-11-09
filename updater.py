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

from config import FONT_NAME, LABEL_LIGHT, APP_VERSION
from ui_helpers import bind_enter_key

# --- НАСТРОЙКА ПУТИ К ФАЙЛУ ОБНОВЛЕНИЙ ---
# Укажите путь к version.json (сетевой диск или URL)
# Пример: UPDATE_JSON_URL = r"\\Server\Share\TabelApp\version.json"
UPDATE_JSON_URL = r"\\Server\Share\TabelApp\version.json"

def _parse_version(v_str):
    """Превращает '1.2.9' в [1, 2, 9] для сравнения"""
    try:
        return [int(x) for x in v_str.strip().split('.')]
    except Exception:
        return [0, 0, 0]

def check_for_updates(app):
    """Вызывается при старте приложения"""
    if not UPDATE_JSON_URL or UPDATE_JSON_URL == r"\\Server\Share\TabelApp\version.json":
        return # Путь не настроен, выходим

    def _bg_check(dt):
        try:
            # Читаем локальный файл или скачиваем по URL
            if UPDATE_JSON_URL.startswith("http"):
                req = urllib.request.Request(UPDATE_JSON_URL, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode('utf-8'))
            else:
                with open(UPDATE_JSON_URL, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            latest_ver = data.get("latest_version")
            download_url = data.get("download_url")
            notes = data.get("release_notes", "Нет описания.")

            current_ver = _parse_version(APP_VERSION)
            new_ver = _parse_version(latest_ver)

            if new_ver > current_ver:
                Clock.schedule_once(lambda dt: _show_update_popup(app, latest_ver, download_url, notes), 0)
        except Exception as e:
            print("Ошибка проверки обновлений:", e)

    # Запускаем проверку в фоне через 2 секунды после старта
    Clock.schedule_once(_bg_check, 2.0)

def _show_update_popup(app, new_version, download_url, notes):
    content = BoxLayout(orientation='vertical', spacing=10, padding=10)

    content.add_widget(Label(
        text=f"Доступна новая версия программы: {new_version}\nТекущая версия: {APP_VERSION}",
        color=LABEL_LIGHT, halign='center', valign='middle',
        font_name=FONT_NAME, font_size=dp(16), bold=True,
        size_hint_y=None, height=dp(50)
    ))

    # Прокручиваемый список изменений
    scroll = ScrollView(size_hint=(1, 1))
    notes_lbl = Label(
        text=notes, color=(0.8, 0.8, 0.8, 1), halign='left', valign='top',
        font_name=FONT_NAME, font_size=dp(14), size_hint_y=None
    )
    notes_lbl.bind(width=lambda *a: setattr(notes_lbl, 'text_size', (notes_lbl.width, None)))
    notes_lbl.bind(texture_size=notes_lbl.setter('size'))
    scroll.add_widget(notes_lbl)
    content.add_widget(scroll)

    btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=10)
    btn_update = Button(text="Обновить сейчас", background_color=(0.3, 0.7, 0.3, 1), color=(1, 1, 1, 1), font_name=FONT_NAME, bold=True)
    btn_later = Button(text="Напомнить позже", color=(1, 1, 1, 1), font_name=FONT_NAME, bold=True)
    btns.add_widget(btn_update)
    btns.add_widget(btn_later)
    content.add_widget(btns)

    popup = Popup(title="Обновление программы", content=content, size_hint=(0.6, 0.5), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)

    def do_update(*a):
        popup.dismiss()
        _download_and_run(app, download_url)

    btn_update.bind(on_press=do_update)
    btn_later.bind(on_press=popup.dismiss)
    bind_enter_key(popup, do_update)
    popup.open()

def _download_and_run(app, download_url):
    # Показываем окно загрузки
    content = BoxLayout(orientation='vertical', spacing=10, padding=10)
    content.add_widget(Label(text="Загрузка обновления. Пожалуйста, подождите...", color=LABEL_LIGHT, font_name=FONT_NAME, font_size=dp(15)))
    popup = Popup(title="Обновление", content=content, size_hint=(0.4, 0.2), title_color=LABEL_LIGHT, title_font=FONT_NAME, auto_dismiss=False)
    popup.open()

    def _bg_download(dt):
        try:
            # 1. Определяем, куда скачивать
            temp_dir = os.environ.get('TEMP', os.path.dirname(os.path.abspath(__file__)))
            local_setup_path = os.path.join(temp_dir, "Tabel_Setup_Update.exe")

            # 2. Копируем/скачиваем файл
            if download_url.startswith("http"):
                urllib.request.urlretrieve(download_url, local_setup_path)
            else:
                import shutil
                shutil.copy2(download_url, local_setup_path)

            # 3. Запускаем установщик в тихом режиме и закрываем программу
            Clock.schedule_once(lambda dt: _run_installer(app, local_setup_path, popup), 0)

        except Exception as e:
            Clock.schedule_once(lambda dt: _show_error(popup, str(e)), 0)

    import threading
    threading.Thread(target=_bg_download, args=(0,)).start()

def _run_installer(app, setup_path, popup):
    try:
        # Запускаем установщик с ключом /SILENT (без участия пользователя)
        # Inno Setup поддерживает этот ключ из коробки
        subprocess.Popen([setup_path, '/SILENT', '/CLOSEAPPLICATIONS', '/RESTARTAPPLICATIONS'])
        popup.dismiss()
        app.stop() # Закрываем текущее приложение, чтобы установщик мог перезаписать файлы
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