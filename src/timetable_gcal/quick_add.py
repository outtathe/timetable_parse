# -*- coding: utf-8 -*-
"""
timetable-add-one: минимальная команда для добавления ОДНОГО события в календарь.
Устанавливается вместе с проектом и работает после `pip install -e .`.
"""
import argparse
import datetime as dt

from .calendar_api import get_gcal_service

def main():
    ap = argparse.ArgumentParser(description="Добавить одно событие в Google Calendar (минимально)")
    ap.add_argument("--title", default="Тестовое событие")
    ap.add_argument("--date", help="YYYY-MM-DD (по умолчанию — завтра)")
    ap.add_argument("--start", default="10:00", help="HH:MM")
    ap.add_argument("--end", default="11:00", help="HH:MM")
    ap.add_argument("--tz", default="Europe/Moscow", help="Таймзона")
    ap.add_argument("--calendar", default="primary", help="ID календаря")
    args = ap.parse_args()

    # дата по умолчанию — завтра
    if args.date:
        day = dt.datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        day = dt.date.today() + dt.timedelta(days=1)

    h1, m1 = map(int, args.start.split(":"))
    h2, m2 = map(int, args.end.split(":"))
    start_dt = dt.datetime.combine(day, dt.time(h1, m1))
    end_dt = dt.datetime.combine(day, dt.time(h2, m2))

    body = {
        "summary": args.title,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": args.tz},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": args.tz},
    }

    service = get_gcal_service()
    created = service.events().insert(calendarId=args.calendar, body=body).execute()
    print("OK:", created.get("htmlLink", "<без ссылки>"))
