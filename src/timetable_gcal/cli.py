# -*- coding: utf-8 -*-
import argparse
import datetime as dt
import os
import pytz

import xlrd

from .parser import SheetAccessor, find_header_and_week_rows, iter_hits, WEEKDAY_MAP
from .calendar_logic import build_event, monday_of
from .calendar_api import get_gcal_service


def end_of_current_month() -> dt.date:
    today = dt.date.today()
    last = (today.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
    return last


# --- утилиты для групп ---
def normalize_group(s: str) -> str:
    s = (s or "").strip().upper()
    s = s.replace("—", "-").replace("–", "-").replace(" ", "")
    return s

def allowed_group(s: str) -> str | None:
    """Разрешаем только БИВТ-25-<1..8>."""
    s = normalize_group(s)
    if not s.startswith("БИВТ-25-"):
        return None
    tail = s.split("-")[-1]
    try:
        n = int(tail)
    except ValueError:
        return None
    return s if 1 <= n <= 8 else None


# --- даты/проверки в календаре ---
def compute_first_date(hit, upper_week_monday: dt.date) -> dt.date:
    upper_monday = monday_of(upper_week_monday)
    lower_monday = upper_monday + dt.timedelta(days=7)
    anchor = upper_monday if hit.week == "upper" else lower_monday
    return anchor + dt.timedelta(days=WEEKDAY_MAP[hit.weekday_name])

def day_bounds_rfc3339(day: dt.date, tz: str) -> tuple[str, str]:
    tzinfo = pytz.timezone(tz)
    tmin = tzinfo.localize(dt.datetime.combine(day, dt.time(0, 0, 0))).isoformat()
    tmax = tzinfo.localize(dt.datetime.combine(day, dt.time(23, 59, 59))).isoformat()
    return tmin, tmax

def lecture_exists_on_date(service, calendar_id: str, day: dt.date, tz: str) -> bool:
    """Есть ли на этой дате хоть одна 'ПИА — Лекция ...'"""
    tmin, tmax = day_bounds_rfc3339(day, tz)
    resp = service.events().list(
        calendarId=calendar_id,
        timeMin=tmin,
        timeMax=tmax,
        singleEvents=True,
        orderBy="startTime",
        maxResults=2500,
    ).execute()
    for ev in resp.get("items", []):
        title = (ev.get("summary") or "").strip()
        if title.startswith("ПИА — Лекция"):
            return True
    return False


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

    # ФИЛЬТРЫ ПО ГРУППАМ: только БИВТ-25-1..8
    filtered = []
    for h in hits:
        norm = allowed_group(h.group)
        if not norm:
            continue
        h.group = norm  # нормализуем в объекте
        filtered.append(h)
    hits = filtered

    if not hits:
        print("Ничего не найдено/подходящего (фильтры по группам БИВТ-25-1..8).")
        return

    upper_start = dt.datetime.strptime(args.upper_start, "%Y-%m-%d").date()
    until_date = (
        dt.datetime.strptime(args.until, "%Y-%m-%d").date()
        if args.until
        else end_of_current_month()
    )

    # Предварительная сводка
    print('Пары к обработке (["ПИА" - "Лекция/Лаба" - "Аудитория/Группа"]):')
    for h in hits:
        tail = f'{h.group} - "{h.room}"' if h.lesson_type == "Лаба" else f'"{h.room}"'
        print(f'["ПИА" - "{h.lesson_type}" - {tail}] — {h.weekday_name} {h.start.strftime("%H:%M")}-{h.end.strftime("%H:%M")} ({ "верхняя" if h.week=="upper" else "нижняя"})')

    if dry:
        print("\nDRY-RUN: события НЕ создаются. Добавь --push чтобы залить в календарь.")
        return

    service = get_gcal_service()

    # Создаём события с проверкой 'лекция уже есть в этот день'
    created = 0
    skipped_lectures = 0
    for h in hits:
        # пропускаем лекцию, если уже есть любая ПИА-лекция на этой дате
        if h.lesson_type == "Лекция":
            first_date = compute_first_date(h, upper_start)
            if lecture_exists_on_date(service, args.calendar, first_date, args.timezone):
                print(f"[SKIP] Лекция уже есть на {first_date.isoformat()}")
                skipped_lectures += 1
                continue

        ev = build_event(h, args.timezone, upper_start, until_date)
        service.events().insert(calendarId=args.calendar, body=ev).execute()
        print(f'[OK] {ev["summary"]} {ev["start"]["dateTime"]}')
        created += 1

    print(f"\nИтог: создано {created}, пропущено лекций {skipped_lectures}.")
    

if __name__ == "__main__":
    main()
