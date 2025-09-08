# -*- coding: utf-8 -*-
"""
timetable-purge: удалить события по префиксу (по умолчанию 'ПИА')
в указанном интервале времени.

Примеры:
  # Посмотреть, что будет удалено (ничего не трогает):
  timetable-purge --since 2025-09-01 --until 2025-09-30

  # Реально удалить:
  timetable-purge --since 2025-09-01 --until 2025-09-30 --apply

  # Другой календарь и префикс:
  timetable-purge --calendar my@group.calendar.google.com --prefix "ПИА"
"""

import argparse
import datetime as dt
import pytz

from .calendar_api import get_gcal_service


def parse_date(s: str) -> dt.date:
    """терпим к YYYY-M-D и YYYY-MM-DD."""
    y, m, d = (int(x) for x in s.split("-"))
    return dt.date(y, m, d)


def rfc3339(day: dt.date, tzname: str, end: bool = False) -> str:
    """дата -> RFC3339 с таймзоной (лок. полночь / 23:59:59)."""
    t = dt.time(23, 59, 59) if end else dt.time(0, 0, 0)
    tz = pytz.timezone(tzname)
    return tz.localize(dt.datetime.combine(day, t)).isoformat()


def fmt_when(ev: dict) -> str:
    s = ev.get("start", {})
    e = ev.get("end", {})
    key = "dateTime" if "dateTime" in s else "date"
    return f'{s.get(key, "?")} → {e.get(key, "?")}'


def main():
    ap = argparse.ArgumentParser(
        description="Удалить события, чей заголовок начинается с префикса (default: 'ПиА')"
    )
    ap.add_argument("--calendar", default="primary", help="ID календаря")
    ap.add_argument("--prefix", default="ПиА", help="С каким префиксом начинается summary")
    ap.add_argument("--since", required=True, help="Начало интервала YYYY-MM-DD")
    ap.add_argument("--until", required=True, help="Конец интервала YYYY-MM-DD (включительно)")
    ap.add_argument("--tz", default="Europe/Moscow", help="Таймзона для интервала времени")
    ap.add_argument("--apply", action="store_true", help="Выполнить удаление (по умолчанию dry-run)")
    args = ap.parse_args()

    since = parse_date(args.since)
    until = parse_date(args.until)

    time_min = rfc3339(since, args.tz, end=False)
    time_max = rfc3339(until, args.tz, end=True)

    service = get_gcal_service()

    to_delete = []
    page_token = None
    while True:
        resp = (
            service.events()
            .list(
                calendarId=args.calendar,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,   # разворачиваем повторяющиеся инстансы
                orderBy="startTime",
                maxResults=2500,
                pageToken=page_token,
            )
            .execute()
        )
        for ev in resp.get("items", []):
            summary = (ev.get("summary") or "").strip()
            if summary.startswith(args.prefix):
                to_delete.append(ev)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    print(f"Найдено совпадений: {len(to_delete)} (prefix='{args.prefix}')")
    for ev in to_delete:
        print(f"- {ev.get('summary', '<без заголовка>')}  [{fmt_when(ev)}]  id={ev['id']}")

    if not to_delete:
        return

    if not args.apply:
        print("\nDRY-RUN: ничего не удалено. Добавь --apply чтобы выполнить удаление.")
        return

    # удаляем
    for ev in to_delete:
        service.events().delete(calendarId=args.calendar, eventId=ev["id"]).execute()
        print(f"[DEL] {ev.get('summary')}  id={ev['id']}")

    print(f"\nГотово. Удалено: {len(to_delete)}")
    

if __name__ == "__main__":
    main()
