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

from config import FONT_NAME, LABEL_LIGHT, ICON_EMOJI


class AboutTab(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        self._build()

    def _build(self):
        top = BoxLayout(size_hint_y=None, height=dp(52),
                        spacing=5, padding=(10, 6, 10, 6))
        top.add_widget(Label(
            text="О программе",
            bold=True, color=LABEL_LIGHT,
            font_name=FONT_NAME, font_size=dp(20),
            halign='left', valign='middle',
            size_hint_x=1,
            text_size=(dp(300), dp(40)),
        ))

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

        scroll = ScrollView(scroll_type=['bars'], effect_cls='ScrollEffect')
        content = BoxLayout(orientation='vertical',
                             size_hint_y=None, spacing=dp(8),
                             padding=(dp(20), dp(15)))
        content.bind(minimum_height=content.setter('height'))

        content.add_widget(self._mk_h1(
            "Табель учёта рабочего времени"))
        content.add_widget(self._mk_sub(
            "Настольное приложение на Kivy для ведения табеля "
            "рабочего времени по форме Т-13 (упрощённой). Работает "
            "локально, данные хранятся в файле рядом с программой."))

        content.add_widget(self._mk_h2("Основные возможности"))
        content.add_widget(self._mk_p(
            "•  Ежедневный учёт явок, неявок и отработанных часов.\n"
            "•  Автоматический подсчёт итогов по каждому сотруднику "
            "за месяц: явки, неявки по категориям, сумма часов, "
            "сверхурочные, ночные и праздничные.\n"
            "•  Три настраиваемых признака должности: «Ночные», "
            "«Сверхурочные», «Праздничные» — каждому сотруднику "
            "признаки назначаются автоматически по его должности.\n"
            "•  Ручная корректировка любой ячейки итогов с "
            "возможностью вернуться к авто-расчёту.\n"
            "•  Автосохранение введённых данных и защита от "
            "одновременного ведения нескольких отделов.\n"
            "•  Сводный отчёт за месяц и выгрузка табеля в Excel "
            "(.xlsx) с готовым оформлением и подписями.\n"
            "•  Иконка окна и панели задач из файла ico/tabel.ico; "
            f"если файла нет — в заголовке появится эмодзи {ICON_EMOJI}."))

        content.add_widget(self._mk_h2("Принцип работы"))

        content.add_widget(self._mk_h3("1. Рабочий персонал"))
        content.add_widget(self._mk_p(
            "Вкладка «Рабочий персонал» — это справочник. Здесь "
            "ведутся отделы и должности, добавляются и редактируются "
            "сотрудники (ФИО, отдел, должность). Сотрудники "
            "сгруппированы по отделам, а те, у кого отдел не указан, "
            "попадают в блок «Без отдела».\n\n"
            "Галочка «В таблицу» определяет, будет ли сотрудник "
            "отображаться в табеле. Одновременно табель может "
            "вестись только по одному отделу — при попытке "
            "включить сотрудника другого отдела программа "
            "предупредит и не даст этого сделать.\n\n"
            "Поле «Организация» в верхней панели редактируется "
            "и сохраняется автоматически; оно попадает в отчёт "
            "и в шапку Excel-файла."))

        content.add_widget(self._mk_h3("2. Должности"))
        content.add_widget(self._mk_p(
            "Список должностей открывается кнопкой «+ Должность». "
            "Для каждой должности задаются три независимых признака:\n\n"
            "  •  «Ночные» — если включён, для сотрудников этой "
            "должности автоматически считаются ночные часы по "
            "шкале: 4 ч → 1, 5 ч → 2, 6 ч → 3, 7–11 ч → 6.\n\n"
            "  •  «Сверхурочные» — если включён, для должности "
            "считаются сверхурочные: всё, что превышает норму "
            "месяца (число рабочих дней × 8).\n\n"
            "  •  «Праздничные» — если включён (по умолчанию), "
            "часы, введённые в выходные и праздничные дни, "
            "попадают в колонку «праздничные». Если снять — эти "
            "часы считаются как обычные рабочие: +1 к явкам, "
            "часы идут в «Всего», а при включённом флаге «Ночные» "
            "учитываются ещё и ночные.\n\n"
            "Должности можно переименовывать и удалять — все "
            "признаки и привязки сотрудников переносятся "
            "автоматически. Признаки «Ночные» и «Сверхурочные» "
            "по умолчанию выключены, «Праздничные» — включены."))

        content.add_widget(self._mk_h3("3. Табель"))
        content.add_widget(self._mk_p(
            "Вкладка «Табель» — основная рабочая область. Сверху "
            "выбирается месяц и год. Таблица состоит из трёх "
            "синхронно прокручиваемых панелей:"))
        content.add_widget(self._mk_p(
            "  •  Слева — №, ФИО и должность (шапка фиксирована).\n"
            "  •  В центре — дни месяца. В ячейку вводится либо "
            "число отработанных часов (8 или 7,5), либо код:\n"
            "         В — выходной,\n"
            "         О — трудовой отпуск,\n"
            "         Б — больничный,\n"
            "         А — отпуск за свой счёт,\n"
            "         Р — отпуск по родам,\n"
            "         Н — прочие неявки,\n"
            "         П — прогул,\n"
            "         Т — текущий простой,\n"
            "         Ц — целосменный простой,\n"
            "         У — опоздание.\n"
            "  •  Справа — итоги, которые пересчитываются сразу "
            "при вводе."))
        content.add_widget(self._mk_p(
            "Выходные и праздничные дни подсвечены цветом. "
            "Ширина колонок «ФИО» и «Должность» подстраивается "
            "автоматически под самого длинного сотрудника. "
            "Горизонтальная прокрутка центральной панели "
            "поддерживается колесом мыши."))

        content.add_widget(self._mk_h3("4. Автосохранение"))
        content.add_widget(self._mk_p(
            "Все введённые данные сохраняются автоматически через "
            "0,6 секунды после последнего изменения. Файл "
            "tabel_data.json лежит рядом с программой — его можно "
            "копировать как резервную копию. Если файл изменится "
            "извне, программа подхватит обновление в течение "
            "нескольких секунд без перезапуска."))

        content.add_widget(self._mk_h3("5. Ручные правки итогов"))
        content.add_widget(self._mk_p(
            "Любую ячейку в правой панели итогов можно "
            "отредактировать вручную — она перестанет "
            "пересчитываться автоматически и будет хранить "
            "введённое значение.\n\n"
            "  •  «Применить правки» — зафиксировать все текущие "
            "ручные значения (удобно, когда правок много).\n"
            "  •  «Сбросить правки» — вернуть все ячейки "
            "выбранного месяца к авто-расчёту.\n"
            "  •  «Очистить» — удалить все данные табеля за "
            "выбранный месяц (с подтверждением).\n\n"
            "Если очистить отдельную ячейку итогов вручную — "
            "авто-расчёт для неё вернётся сам."))

        content.add_widget(self._mk_h3("6. Отчёт и печать"))
        content.add_widget(self._mk_p(
            "Вкладка «Отчёт и печать» показывает сводку за месяц "
            "по всем сотрудникам, отмеченным «В таблицу»: "
            "количество явок и неявок по категориям, сумму часов, "
            "сверхурочные, ночные и праздничные, а также "
            "построчную разбивку по каждому сотруднику.\n\n"
            "Кнопка «Сохранить в Excel» формирует файл "
            "tabel_ГОД-МЕСЯЦ.xlsx с готовым оформлением: "
            "заголовок, шапка с числами месяца и днями недели, "
            "подсветка выходных и праздников, строки сотрудников, "
            "строка ИТОГО и подписи «Энергетик» и «Директор». "
            "Файл сразу открывается в Excel. Для работы функции "
            "требуется библиотека openpyxl (pip install openpyxl)."))

        content.add_widget(self._mk_h2("Иконка приложения"))
        content.add_widget(self._mk_p(
            "Иконка берётся из файла ico/tabel.ico рядом с "
            "программой. Она устанавливается и в заголовок окна, "
            "и на панель задач (в Windows). Если файла нет — в "
            f"заголовке окна автоматически появляется эмодзи {ICON_EMOJI}, "
            "а иконка остаётся системной по умолчанию."))

        content.add_widget(self._mk_h2("Горячие подсказки"))
        content.add_widget(self._mk_p(
            "•  Чтобы ночные/сверхурочные/праздничные считались "
            "правильно, задайте признаки у нужных должностей "
            "во вкладке «Должности».\n"
            "•  Переключение месяца/года автоматически "
            "сохраняет данные предыдущего периода и "
            "подгружает новый.\n"
            "•  Кнопка «Очистить» на вкладке «Табель» удаляет "
            "данные только за выбранный месяц — остальные "
            "месяцы не затрагиваются.\n"
            "•  Резервная копия — просто скопируйте файл "
            "tabel_data.json в надёжное место."))

        content.add_widget(self._mk_h2("Исходный код"))
        content.add_widget(self._mk_p(
            "Проект распространяется свободно. Полный исходный "
            "код, история изменений и возможность сообщить о "
            "проблемах — в репозитории на GitHub "
            "(кнопка сверху)."))

        scroll.add_widget(content)
        self.add_widget(scroll)

    @staticmethod
    def _mk_h1(text):
        lbl = Label(text=text, bold=True, color=LABEL_LIGHT,
                    font_name=FONT_NAME, font_size=dp(22),
                    halign='left', valign='top',
                    size_hint_y=None)
        lbl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1]))
        return lbl

    @staticmethod
    def _mk_h2(text):
        lbl = Label(text=text, bold=True, color=(0.85, 0.92, 1.0, 1),
                    font_name=FONT_NAME, font_size=dp(17),
                    halign='left', valign='top',
                    size_hint_y=None)
        lbl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1]))
        return lbl

    @staticmethod
    def _mk_h3(text):
        lbl = Label(text=text, bold=True, color=(0.75, 0.85, 1.0, 1),
                    font_name=FONT_NAME, font_size=dp(15),
                    halign='left', valign='top',
                    size_hint_y=None)
        lbl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1]))
        return lbl

    @staticmethod
    def _mk_sub(text):
        lbl = Label(text=text, color=(0.85, 0.85, 0.85, 1),
                    font_name=FONT_NAME, font_size=dp(14),
                    halign='left', valign='top',
                    size_hint_y=None)
        lbl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1]))
        return lbl

    @staticmethod
    def _mk_p(text):
        lbl = Label(text=text, color=LABEL_LIGHT,
                    font_name=FONT_NAME, font_size=dp(14),
                    halign='left', valign='top',
                    size_hint_y=None)
        lbl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1]))
        return lbl

    def _open_github(self):
        try:
            webbrowser.open("https://github.com/")
        except Exception as e:
            print("Не удалось открыть ссылку:", e)