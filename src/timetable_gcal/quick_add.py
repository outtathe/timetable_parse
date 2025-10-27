# -*- coding: utf-8 -*-
"""
Мини-CLI: добавить одно событие в календарь через единый модуль event_create.add_event.
Пример:
  python -m timetable_gcal.quick_add \
    --title "Проба" --date 2025-09-01 --start 10:00 --end 11:00 \
    --tz Europe/Moscow --location "Л-550" --calendar primary
"""
import argparse

from .event_create import add_event

def main():
    ap = argparse.ArgumentParser(description="Добавить одно событие в Google Calendar")
    ap.add_argument("--title", required=True, help="Название события")
    ap.add_argument("--date", required=True, help="Дата YYYY-MM-DD")
    ap.add_argument("--start", required=True, help="Начало: HH:MM или ISO datetime")
    ap.add_argument("--end", required=True, help="Конец: HH:MM или ISO datetime")
    ap.add_argument("--tz", default="Europe/Moscow", help="Таймзона (например, Europe/Moscow)")
    ap.add_argument("--calendar", default="primary", help="ID календаря (по умолчанию primary)")
    ap.add_argument("--location", default="", help="Место/аудитория")
    ap.add_argument("--description", default="", help="Описание (опционально)")
    ap.add_argument("--color-id", default=None, help="colorId из палитры Google Calendar (1..11)")
    args = ap.parse_args()

    created = add_event(
        title=args.title,
        date=args.date,
        start=args.start,
        end=args.end,
        tz=args.tz,
        calendar=args.calendar,
        location=args.location,
        description=args.description,
        color_id=args.color_id,
    )
    print("OK:", created.get("htmlLink", "<без ссылки>"))

if __name__ == "__main__":
    main()
