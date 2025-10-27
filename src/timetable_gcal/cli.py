# -*- coding: utf-8 -*-
"""
CLI: добавить одно событие в Google Calendar через единый модуль event_create.add_event.

Примеры:
  # базовый
  timetable-gcal add \
    --title "Проба" --date 2025-09-01 --start 10:00 --end 11:00

  # с таймзоной, аудиторией и цветом
  timetable-gcal add \
    --title "ПИА — Лекция" --date 2025-09-01 --start 09:00 --end 10:35 \
    --tz Europe/Moscow --location "Л-550" --color-id 11

  # в другой календарь
  timetable-gcal add \
    --title "Митап" --date 2025-09-02 --start 19:00 --end 20:00 \
    --calendar my-team@group.calendar.google.com
"""
import argparse
import sys

from .event_create import add_event


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="timetable-gcal",
        description="Утилита для добавления событий в Google Calendar"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="Добавить одно событие")
    add.add_argument("--title", required=True, help="Название события")
    add.add_argument("--date", required=True, help="Дата YYYY-MM-DD")
    add.add_argument("--start", required=True, help="Начало: HH:MM или ISO datetime")
    add.add_argument("--end", required=True, help="Конец: HH:MM или ISO datetime")
    add.add_argument("--tz", default="Europe/Moscow", help="Таймзона (например, Europe/Moscow)")
    add.add_argument("--calendar", default="primary", help="ID календаря (по умолчанию primary)")
    add.add_argument("--location", default="", help="Место/аудитория")
    add.add_argument("--description", default="", help="Описание (опционально)")
    add.add_argument("--color-id", default=None, help="colorId из палитры Google Calendar (1..11)")
    return ap


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)

    if args.cmd == "add":
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
        return

    # на всякий
    print("Неизвестная команда", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
