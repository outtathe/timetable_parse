# -*- coding: utf-8 -*-
"""
CLI: .XLS расписание → Google Calendar (ПИА)
- Фильтр групп: только БИВТ-25-1..8
- Лекции по потокам (1–4 / 5–8), лабы по группам
- Идемпотентность: устойчивый xkey (+локальный set)
- Цвета: Tomato/Tangerine для лекций, Basil/Sage для лаб
- Повторы: раз в 2 недели до UNTIL
- Поддержка окна "С/По": --since / --until
"""

import argparse
import datetime as dt
import os
from typing import Optional, Tuple, List

import pytz
import xlrd

from .parser import SheetAccessor, find_header_and_week_rows, iter_hits, WEEKDAY_MAP
from .calendar_logic import build_event, monday_of, make_xkey
from .calendar_api import get_gcal_service


# ---------- даты/таймзона ----------
def end_of_current_month() -> dt.date:
    today = dt.date.today()
    first_next = (today.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return first_next - dt.timedelta(days=1)


def parse_date(s: str) -> dt.date:
    """YYYY-M-D или YYYY-MM-DD."""
    y, m, d = (int(x) for x in s.split("-"))
    return dt.date(y, m, d)


def localize(day: dt.date, t: dt.time, tzname: str) -> dt.datetime:
    tz = pytz.timezone(tzname)
    return tz.localize(dt.datetime.combine(day, t))


def day_bounds_rfc3339(day: dt.date, tzname: str) -> Tuple[str, str]:
    tz = pytz.timezone(tzname)
    tmin = tz.localize(dt.datetime.combine(day, dt.time(0, 0, 0))).isoformat()
    tmax = tz.localize(dt.datetime.combine(day, dt.time(23, 59, 59))).isoformat()
    return tmin, tmax


def compute_first_date(hit, upper_week_monday: dt.date, since_date: dt.date | None = None) -> dt.date:
    """Первая инстанция пары; если задан since_date — сдвигаем вперёд по шагу 14 дней."""
    upper_monday = monday_of(upper_week_monday)
    lower_monday = upper_monday + dt.timedelta(days=7)
    anchor = upper_monday if hit.week == "upper" else lower_monday
    d = anchor + dt.timedelta(days=WEEKDAY_MAP[hit.weekday_name])
    if since_date:
        while d < since_date:
            d += dt.timedelta(days=14)
    return d


# ---------- группы ----------
def normalize_group(s: str) -> str:
    s = (s or "").strip().upper()
    s = s.replace("—", "-").replace("–", "-").replace(" ", "")
    return s


def allowed_group(s: str) -> Optional[str]:
    """Разрешаем только БИВТ-25-<1..8>."""
    s = normalize_group(s)
    if not s.startswith("БИВТ-25-"):
        return None
    try:
        n = int(s.split("-")[-1])
    except ValueError:
        return None
    return s if 1 <= n <= 8 else None


# ---------- проверки календаря ----------
def lab_exists_on_date_time(service, calendar_id: str, day: dt.date, tzname: str, group: str, start_t: dt.time) -> bool:
    """Есть ли на дате лаба этой группы с таким же стартом."""
    tmin, tmax = day_bounds_rfc3339(day, tzname)
    resp = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=tmin,
            timeMax=tmax,
            singleEvents=True,
            orderBy="startTime",
            maxResults=2500,
        )
        .execute()
    )
    target_prefix = f"ПИА — Лаба — {normalize_group(group)}"
    for ev in resp.get("items", []):
        title = (ev.get("summary") or "").strip().upper()
        if not title.startswith(target_prefix):
            continue
        s_iso = ev.get("start", {}).get("dateTime")
        if not s_iso:
            continue
        try:
            ev_time = dt.datetime.fromisoformat(s_iso).timetz()
            if ev_time.hour == start_t.hour and ev_time.minute == start_t.minute:
                return True
        except Exception:
            pass
    return False


def event_exists_by_xkey(
    service, calendar_id: str, xkey: str, start_dt: dt.datetime, end_dt: dt.datetime, debug: bool = False
) -> bool:
    """Ищем событие с таким же xkey (extendedProperties.private.xkey) в окне ±1 мин."""
    time_min = (start_dt - dt.timedelta(minutes=1)).isoformat()
    time_max = (end_dt + dt.timedelta(minutes=1)).isoformat()
    resp = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=2500,
        )
        .execute()
    )
    for ev in resp.get("items", []):
        priv = ev.get("extendedProperties", {}).get("private", {}) or {}
        if priv.get("xkey") == xkey:
            if debug:
                print(
                    f"[DEBUG] matched by xkey {xkey}: {ev.get('summary')} @ {ev.get('start', {}).get('dateTime')}"
                )
            return True
        elif debug:
            print(f"[DEBUG] nearby event: {ev.get('summary')} xkey={priv.get('xkey')}")
    return False


# ---------- дедуп входящих ----------
def stream_of(group: str) -> str:
    try:
        n = int(group.split("-")[-1])
    except Exception:
        return ""
    return "1-4" if 1 <= n <= 4 else "5-8"


def dedupe_hits(hits):
    """Дедуп: для лекций ключ по потоку; для лаб — по группе."""
    seen = set()
    out: List = []
    for h in hits:
        room = (h.room or "").strip()
        if h.lesson_type == "Лекция":
            key = (h.week, h.weekday_name, h.start, h.end, room, "Лекция", stream_of(h.group))
        else:  # Лаба
            key = (h.week, h.weekday_name, h.start, h.end, room, "Лаба", normalize_group(h.group))
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="Парсер расписания → Google Calendar (ПИА)")
    ap.add_argument("--file", required=True, help=".xls файл с расписанием")
    ap.add_argument("--calendar", default="primary", help="ID календаря (по умолчанию primary)")
    ap.add_argument("--timezone", default="Europe/Moscow", help="Таймзона для событий")
    ap.add_argument("--upper-start", default="2025-09-01", help="Понедельник верхней недели (YYYY-MM-DD)")
    ap.add_argument(
        "--since", default=None, help="Добавлять пары, начиная с этой даты (YYYY-MM-DD, включительно)"
    )
    ap.add_argument(
        "--until",
        default=None,
        help="Дата окончания повторений включительно (YYYY-MM-DD). По умолчанию — конец текущего месяца.",
    )
    ap.add_argument("--push", action="store_true", help="Создать события в календаре")
    ap.add_argument("--dry-run", action="store_true", help="Только вывести найденное")
    ap.add_argument("--debug", action="store_true", help="Подробные логи поиска дублей")
    args = ap.parse_args()

    dry = True if args.dry_run or not args.push else False

    if not os.path.exists(args.file):
        raise FileNotFoundError(args.file)

    # читаем xls
    book = xlrd.open_workbook(args.file, formatting_info=True)
    sheet = book.sheet_by_index(0)
    sh = SheetAccessor(sheet)

    header_row, week_row = find_header_and_week_rows(sh)
    hits = iter_hits(sh, header_row, week_row)

    # фильтр по группам + нормализация
    filtered = []
    for h in hits:
        norm = allowed_group(h.group)
        if not norm:
            continue
        h.group = norm
        filtered.append(h)

    # дедуп по ключу (лекции по потоку, лабы по группе)
    hits = dedupe_hits(filtered)

    if not hits:
        print("Ничего не найдено/подходящего (после фильтров и дедупа).")
        return

    upper_start = parse_date(args.upper_start)
    until_date = parse_date(args.until) if args.until else end_of_current_month()
    since_date = parse_date(args.since) if args.since else None

    print("К созданию (после фильтров/дедупа):")
    for h in hits:
        tail = f'{h.group} - "{h.room}"' if h.lesson_type == "Лаба" else f'"{h.room}"'
        print(
            f'["ПИА" - "{h.lesson_type}" - {tail}] — {h.weekday_name} '
            f'{h.start.strftime("%H:%M")}-{h.end.strftime("%H:%M")} '
            f'({ "верхняя" if h.week=="upper" else "нижняя"})  key={make_xkey(h)[:8]}'
        )

    if dry:
        print("\nDRY-RUN: события НЕ создаются. Добавь --push чтобы залить в календарь.")
        return

    service = get_gcal_service()
    created = skipped_labs = skipped_dups = skipped_out_of_window = 0
    created_keys = set()  # локальная идемпотентность (xkey+дата)

    for h in hits:
        first_date = compute_first_date(h, upper_start, since_date)
        if first_date > until_date:
            print(f"[SKIP] В окно since/until не попадает: {h.lesson_type} {h.group}")
            skipped_out_of_window += 1
            continue

        start_dt = localize(first_date, h.start, args.timezone)
        end_dt = localize(first_date, h.end, args.timezone)

        # устойчивый ключ пары
        xkey = make_xkey(h)
        local_key = (xkey, first_date.isoformat())
        if local_key in created_keys:
            print(f"[SKIP] Локальный дубль xkey={xkey} {start_dt.isoformat()}")
            skipped_dups += 1
            continue

        # дубль уже в календаре по xkey рядом по времени
        if event_exists_by_xkey(service, args.calendar, xkey, start_dt, end_dt, debug=args.debug):
            print(f"[SKIP] Уже существует (xkey): {h.lesson_type} {h.group} {start_dt.isoformat()}")
            skipped_dups += 1
            continue

        # защита для лаб: та же группа и старт уже есть на этой дате
        if h.lesson_type == "Лаба" and lab_exists_on_date_time(
            service, args.calendar, first_date, args.timezone, h.group, h.start
        ):
            print(f"[SKIP] Лаба {h.group} уже есть {first_date.isoformat()} {h.start.strftime('%H:%M')}")
            skipped_labs += 1
            continue

        ev = build_event(h, args.timezone, upper_start, until_date, since_date=since_date)
        service.events().insert(calendarId=args.calendar, body=ev).execute()
        created_keys.add(local_key)
        print(f'[OK] {ev["summary"]} {ev["start"]["dateTime"]}')
        created += 1

    print(
        f"\nИтог: создано {created}, лаб пропущено {skipped_labs}, "
        f"дублей {skipped_dups}, вне окна {skipped_out_of_window}."
    )


if __name__ == "__main__":
    main()
