# tab_about.py
# -*- coding: utf-8 -*-
"""Вкладка «О программе»."""
import config  # noqa: F401

import webbrowser

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle

from config import FONT_NAME, LABEL_LIGHT, ICON_EMOJI, DELETE_PASSWORD, APP_VERSION
from ui_helpers import NoOverscrollEffect


class AboutTab(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        
        with self.canvas.before:
            Color(*config.TABLE_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda i, v: setattr(self._bg, 'pos', v),
                  size=lambda i, v: setattr(self._bg, 'size', v))

        self._build()

    def _build(self):
        top = BoxLayout(size_hint_y=None, height=dp(52),
                        spacing=5, padding=(10, 6, 10, 6))
        
        top.add_widget(Widget())

        gh_btn = Button(
            text="Открыть репозиторий на GitHub",
            size_hint_x=None, width=dp(320),
            font_name=FONT_NAME, font_size=dp(15), bold=True,
            background_color=(0.15, 0.25, 0.45, 1),
            color=(1, 1, 1, 1),
        )
        gh_btn.bind(on_press=lambda *a: self._open_github())
        top.add_widget(gh_btn)
        self.add_widget(top)

        line = Widget(size_hint_y=None, height=dp(2))
        with line.canvas:
            Color(0.5, 0.5, 0.5, 1)
            line._rect = Rectangle(pos=line.pos, size=line.size)
        line.bind(pos=lambda i, v: setattr(i._rect, 'pos', v),
                  size=lambda i, v: setattr(i._rect, 'size', v))
        self.add_widget(line)

        scroll = ScrollView(scroll_type=['bars'],
                            effect_cls=NoOverscrollEffect)
        content = BoxLayout(orientation='vertical',
                             size_hint_y=None, spacing=dp(10),
                             padding=(dp(30), dp(20)))
        content.bind(minimum_height=content.setter('height'))

        # ==========================================
        # ЗАГОЛОВОК
        # ==========================================
        content.add_widget(self._mk_title("ТАБЕЛЬ УЧЁТА РАБОЧЕГО ВРЕМЕНИ"))
        content.add_widget(self._mk_sub(
            "Настольное приложение на Kivy для ведения табеля по форме Т-13 (упрощённой). "
            "Работает локально, поддерживает совместную работу нескольких компьютеров.\n"
            f"Текущая версия: [b]{APP_VERSION}[/b]"))
        content.add_widget(self._mk_sep())

        # ==========================================
        # ВОЗМОЖНОСТИ
        # ==========================================
        content.add_widget(self._mk_h2("Основные возможности"))
        content.add_widget(self._mk_p(
            "•  [b]Ежедневный учёт[/b] явок, неявок и отработанных часов.\n"
            "•  [b]Автоматический подсчёт[/b] итогов: явки, неявки по категориям, сверхурочные, ночные и праздничные.\n"
            "•  [b]Списочная и среднесписочная численность[/b] рассчитывается автоматически.\n"
            "•  Три настраиваемых признака должности: «Ночные», «Сверхурочные» и «Без вых.».\n"
            "•  [b]Гибкий ввод часов[/b]: обычные числа (8, 7.5), смены (8//2), пометка «д» (8д).\n"
            "•  Коды неявок: В, О, Б, А, РО, К, МК, СР, Р, ТО, КД, Н, ДМ, П, Т, Ц, У.\n"
            "•  [b]Свой набор итогов[/b]: кнопка «Настроить итоги» — на каждой машине свой.\n"
            "•  [b]Адаптивный интерфейс[/b]: колонки и кнопки автоматически подстраиваются под ширину окна.\n"
            "•  [b]Навигация как в Excel[/b]: Tab, стрелки, Ctrl+C / Ctrl+V, Shift+клик, Del.\n"
            "•  Свободная перестановка сотрудников и отделов (правый клик мыши).\n"
            "•  Автосохранение данных через 0,6 секунды после изменения.\n"
            "•  [b]5 тем оформления[/b] на выбор.\n"
            "•  Экспорт в Excel с готовым оформлением (умная шапка, подсветка, итоги).\n"
            "•  Совместная работа через общий файл `tabel_data.json`.\n"
            "•  Защита удаления записей паролем."))
        content.add_widget(self._mk_sep())

        # ==========================================
        # ПРИНЦИП РАБОТЫ
        # ==========================================
        content.add_widget(self._mk_h2("Принцип работы"))

        content.add_widget(self._mk_h3("1. Рабочий персонал"))
        content.add_widget(self._mk_p(
            "Вкладка «Рабочий персонал» — это справочник. Здесь ведутся отделы, должности и сотрудники. "
            "Сотрудники сгруппированы по отделам.\n\n"
            "[color=ffaa00]Галочка «В таблицу»[/color] определяет, будет ли сотрудник отображаться в табеле. "
            "Одновременно табель может вестись только по одному отделу. Выбор галочек индивидуален для каждого ПК!\n\n"
            "[color=ffaa00]Сотрудники без отдела[/color] попадают в блок «Без отдела».\n"
            "[color=ffaa00]Поля «Организация» и «Директор»[/color] редактируются в верхней панели и попадают в Excel.\n\n"
            "Списки сотрудников внутри отделов можно [b]сворачивать[/b] (клик по полосе отдела), чтобы не листать длинный список. "
            "Состояние запоминается для каждого компьютера."))

        content.add_widget(self._mk_h3("2. Перестановка и настройка"))
        content.add_widget(self._mk_p(
            "Порядок сотрудников и отделов меняется произвольно через [b]контекстное меню (правый клик)[/b]. "
            "Выбранная строка подсвечивается желтой рамкой.\n\n"
            "Для каждой должности задаются три независимых признака:\n"
            "  •  [b]«Ночные»[/b] — если включён, для должности считаются ночные часы при вводе обычного числа (без смены).\n"
            "  •  [b]«Сверхурочные»[/b] — считаются часы, превышающие норму месяца (часы в выходные/праздники исключаются).\n"
            "  •  [b]«Без вых.»[/b] — часы в выходные не попадают в колонку «в т.ч. выходной», оставаясь в «Всего».\n\n"
            "[color=ffaa00]Изменение этих признаков, как и удаление записей, защищено паролем![/color]"))

        content.add_widget(self._mk_h3("3. Табель"))
        content.add_widget(self._mk_p(
            "Вкладка «Табель» — основная рабочая область. В ячейки вводится число часов или код:\n"
            "  [b]В[/b] — выходной\n"
            "  [b]О[/b] — трудовой отпуск\n"
            "  [b]Б[/b] — больничный\n"
            "  [b]А[/b] — отпуск за свой счёт\n"
            "  [b]РО[/b] — отпуск по родам\n"
            "  [b]К[/b] — командировка\n"
            "  [b]МК[/b] — медицинская комиссия\n"
            "  [b]СР[/b] — оплата по среднему\n"
            "  [b]Р[/b] — ремонт\n"
            "  [b]ТО[/b] — тех. обслуживание\n"
            "  [b]КД[/b] — коллективный договор\n"
            "  [b]Н[/b] — прочие неявки\n"
            "  [b]ДМ[/b] — день матери (идёт в «Прочие неявки»)\n"
            "  [b]П[/b] — прогул\n"
            "  [b]Т[/b] — текущий простой\n"
            "  [b]Ц[/b] — целосменный простой\n"
            "  [b]У[/b] — опоздание\n\n"
            "[color=4da6ff][b]Форматы ввода смен и часов:[/b][/color]\n"
            "  •  [b]Простое число:[/b] 8, 7.5, 4 (ночные считаются по спец. шкале, 8 и 8д ночных не дают).\n"
            "  •  [b]Со сменой:[/b] 8//1 (1 смена, ночных нет), 8//2 (2 смена, 1 ночной час), 12//2 (8 ночных часов).\n"
            "  •  [b]Без ночных:[/b] 8д, 7.5д (явка есть, часы идут в общие, ночные не начисляются).\n\n"
            "[color=ffaa00]Важно про выходные и праздники:[/color]\n"
            "Часы за реальные праздники идут в колонку «праздничные». В обычные выходные — в «Всего» и «в т.ч. выходной» (если нет галочки «Без вых.»). Эти часы [b]не участвуют[/b] в расчёте сверхурочных, чтобы не было двойной оплаты."))

        content.add_widget(self._mk_h3("4. Настройка отображаемых итогов"))
        content.add_widget(self._mk_p(
            "На вкладке «Табель» есть кнопка [b]«Настроить итоги»[/b]. В открывшемся окне можно отметить галочками те "
            "колонки итогов, которые вы хотите видеть в таблице лично у себя. Если колонка скрыта, она не будет занимать место, "
            "а таблица станет компактнее.\n\n"
            "Настройка сохраняется в файле компьютера — у каждого пользователя она своя. "
            "Те же колонки попадают и в Excel-файл (кнопка «Сохранить в Excel»).\n\n"
            "[color=ffaa00]Кнопка «Скрыть итоги»[/color] полностью убирает правую часть таблицы — удобно, когда нужно "
            "увидеть сразу все дни месяца на узком экране. Повторное нажатие возвращает колонки."))

        content.add_widget(self._mk_sep())

        # ==========================================
        # ДОПОЛНИТЕЛЬНО
        # ==========================================
        content.add_widget(self._mk_h2("Временные сотрудники, Подписанты и Excel"))
        
        content.add_widget(self._mk_p(
            "[b]Временные сотрудники[/b]\n"
            "Добавляются под таблицей табеля (кнопка в верхней панели). Привязаны к месяцу и отделу. В общий справочник не попадают, "
            "в списочной численности не учитываются. В таблице выделяются другим цветом.\n\n"
            
            "[b]Дополнительные подписанты[/b]\n"
            "На вкладке «Отчёт и печать» есть кнопка «Доп. подписанты». Здесь можно добавить произвольных людей для подписи табеля.\n"
            "Список подписантов выводится в Excel с отступами. Окно выбора из общей базы имеет удобную таблицу с разделительными линиями и поиском. "
            "Если вы работаете в сети, то подписанты, добавленные другими пользователями, сохраняются в общей базе `tabel_data.json` и становятся доступны всем.\n\n"

            "[b]Ручные правки и Отчёт[/b]\n"
            "Любую ячейку итогов можно поправить вручную (кнопки «Применить правки» / «Сбросить правки» в верхней панели). "
            "Вкладка «Отчёт и печать» показывает сводку и позволяет выгрузить файл в Excel (кнопки «Сохранить в Excel» и «Кратко в Excel»).\n\n"))

        scroll.add_widget(content)
        self.add_widget(scroll)

    # ------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ДЛЯ ТЕКСТА С РАЗМЕТКОЙ
    # ------------------------------------------------------------------
    @staticmethod
    def _mk_title(text):
        lbl = Label(text=f"[b][color=4da6ff]{text}[/color][/b]", 
                    markup=True, color=config.TABLE_FG,
                    font_name=FONT_NAME, font_size=dp(22),
                    halign='center', valign='middle', size_hint_y=None)
        lbl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1] + dp(10)))
        return lbl

    @staticmethod
    def _mk_h2(text):
        lbl = Label(text=f"[b][color=4da6ff]{text}[/color][/b]", 
                    markup=True, color=config.TABLE_FG,
                    font_name=FONT_NAME, font_size=dp(18),
                    halign='left', valign='top', size_hint_y=None)
        lbl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1] + dp(8)))
        return lbl

    @staticmethod
    def _mk_h3(text):
        lbl = Label(text=f"[b][color=ffaa00]{text}[/color][/b]", 
                    markup=True, color=config.TABLE_FG,
                    font_name=FONT_NAME, font_size=dp(15),
                    halign='left', valign='top', size_hint_y=None)
        lbl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1] + dp(5)))
        return lbl

    @staticmethod
    def _mk_sub(text):
        lbl = Label(text=text, markup=True, color=config.TABLE_FG,
                    font_name=FONT_NAME, font_size=dp(14),
                    halign='left', valign='top', size_hint_y=None)
        lbl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1]))
        return lbl

    @staticmethod
    def _mk_p(text):
        lbl = Label(text=text, markup=True, color=config.TABLE_FG,
                    font_name=FONT_NAME, font_size=dp(14),
                    halign='left', valign='top', size_hint_y=None)
        lbl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1]))
        return lbl

    @staticmethod
    def _mk_sep():
        # Визуальный разделитель
        lbl = Label(text="[color=555555]" + "─" * 80 + "[/color]", 
                    markup=True, font_name=FONT_NAME, font_size=dp(12),
                    halign='center', valign='middle', size_hint_y=None, height=dp(20))
        return lbl

    def _open_github(self):
        try:
            webbrowser.open("https://github.com/Londimain/Work-schedule")
        except Exception as e:
            print("Не удалось открыть ссылку:", e)