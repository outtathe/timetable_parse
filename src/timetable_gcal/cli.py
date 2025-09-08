# -*- coding: utf-8 -*-
import argparse
import datetime as dt
import calendar
import os

import xlrd

from .parser import SheetAccessor, find_header_and_week_rows, iter_hits
from .calendar_logic import build_event
from .calendar_api import get_gcal_service


def end_of_current_month() -> dt.date:
    today = dt.date.today()
    last = calendar.monthrange(today.year, today.month)[1]
    return dt.date(today.year, today.month, last)


def main():
    ap = argparse.ArgumentParser(description="Парсер расписания → Google Calendar (ПИА)")
    ap.add_argument("--file", required=True, help=".xls файл с расписанием")
    ap.add_argument("--calendar", default="primary", help="ID календаря (по умолчанию primary)")
    ap.add_argument("--timezone", default="Europe/Moscow", help="Таймзона для событий")
    ap.add_argument("--upper-start", default="2025-09-01", help="Понедельник верхней недели (YYYY-MM-DD)")
    ap.add_argument(
        "--until",
        default=None,
        help="Дата окончания повторений включительно (YYYY-MM-DD). По умолчанию — конец текущего месяца.",
    )
    ap.add_argument("--push", action="store_true", help="Создать события в календаре")
    ap.add_argument("--dry-run", action="store_true", help="Только вывести найденное")
    args = ap.parse_args()

    dry = True if args.dry_run or not args.push else False

    if not os.path.exists(args.file):
        raise FileNotFoundError(args.file)

    book = xlrd.open_workbook(args.file, formatting_info=True)
    sheet = book.sheet_by_index(0)
    sh = SheetAccessor(sheet)

    header_row, week_row = find_header_and_week_rows(sh)
    hits = iter_hits(sh, header_row, week_row)

    if not hits:
        print("Ничего не найдено для 'Программирование и алгоритмизация'.")
        return

    upper_start = dt.datetime.strptime(args.upper_start, "%Y-%m-%d").date()
    until_date = (
        dt.datetime.strptime(args.until, "%Y-%m-%d").date()
        if args.until
        else end_of_current_month()
    )

    events = [build_event(h, args.timezone, upper_start, until_date) for h in hits]

    print('Найдены пары (["ПИА" - "Лекция/Лаба" - "Аудитория"]):')
    for h in hits:
        print(f'["ПИА" - "{h.lesson_type}" - "{h.room}"] — {h.group}, {h.weekday_name}, '
              f'{h.start.strftime("%H:%M")}-{h.end.strftime("%H:%M")} '
              f'({ "верхняя" if h.week=="upper" else "нижняя"})')

    if dry:
        print("\nDRY-RUN: события НЕ создаются. Добавь --push чтобы залить в календарь.")
        return

    service = get_gcal_service()
    for ev in events:
        service.events().insert(calendarId=args.calendar, body=ev).execute()
        print(f'[OK] {ev["summary"]} {ev["start"]["dateTime"]}')


if __name__ == "__main__":
    main()
