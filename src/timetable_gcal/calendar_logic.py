# -*- coding: utf-8 -*-
import datetime as dt
import hashlib
from typing import Dict

import pytz

from .parser import Hit, WEEKDAY_MAP


# ---------- helpers ----------
def monday_of(date_: dt.date) -> dt.date:
    return date_ - dt.timedelta(days=date_.weekday())


def _stream_from_group(group: str) -> str:
    """По номеру группы возвращает ярлык потока: '1-4' или '5-8'."""
    try:
        n = int(group.split("-")[-1])
    except Exception:
        return ""
    return "1-4" if 1 <= n <= 4 else "5-8"


def _color_id(lesson_type: str, week: str) -> str:
    """
    Цвета Google Calendar (event palette):
      Tomato=11, Tangerine=6, Basil=10, Sage=2
    """
    if lesson_type == "Лекция":
        return "11" if week == "upper" else "6"
    # Лаба
    return "10" if week == "upper" else "2"


# ---------- idempotency key ----------
def make_xkey(hit: Hit) -> str:
    """
    Стабильный ключ.
    Для лекций берём не конкретную группу, а поток (1-4 / 5-8),
    чтобы все группы потока считались одной лекцией.
    """
    group_component = _stream_from_group(hit.group) if hit.lesson_type == "Лекция" else hit.group.upper()
    payload = "|".join(
        [
            hit.lesson_type,
            hit.week,  # upper/lower
            hit.weekday_name,
            hit.start.strftime("%H:%M"),
            hit.end.strftime("%H:%M"),
            (hit.room or "").strip().upper(),
            group_component,
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


# ---------- main ----------
def build_event(
    hit: Hit,
    tz: str,
    upper_week_monday: dt.date,
    until_date: dt.date,
    since_date: dt.date | None = None,
) -> Dict:
    """
    Собирает тело события Google Calendar.
    Если задан since_date, сдвигает первую инстанцию вперёд шагом 14 дней,
    пока дата не станет >= since_date.
    """
    upper_monday = monday_of(upper_week_monday)
    lower_monday = upper_monday + dt.timedelta(days=7)
    week_anchor = upper_monday if hit.week == "upper" else lower_monday

    day_offset = WEEKDAY_MAP[hit.weekday_name]
    start_date = week_anchor + dt.timedelta(days=day_offset)

    # сдвиг "С" (только вперёд по серии раз в 2 недели)
    if since_date:
        while start_date < since_date:
            start_date += dt.timedelta(days=14)

    tzinfo = pytz.timezone(tz)
    start_dt = tzinfo.localize(dt.datetime.combine(start_date, hit.start))
    end_dt = tzinfo.localize(dt.datetime.combine(start_date, hit.end))

    until_utc = pytz.UTC.localize(dt.datetime.combine(until_date, dt.time(23, 59, 59)))

    # --- summary + цвет ---
    if hit.lesson_type == "Лекция":
        stream = _stream_from_group(hit.group)
        stream_suffix = f" {stream}" if stream else ""
        summary = f"ПИА — Лекция{stream_suffix} — {hit.room or 'Аудитория?'}"
    else:
        summary = f"ПИА — Лаба — {hit.group} — {hit.room or 'Аудитория?'}"

    description = f"Группа: {hit.group}\nНеделя: {'верхняя' if hit.week == 'upper' else 'нижняя'}"

    xkey = make_xkey(hit)
    summary = f"{summary} · {xkey[:8]}"  # короткий ключ в title для отладки

    return {
        "summary": summary,
        "location": hit.room or "",
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": tz},
        "recurrence": [f"RRULE:FREQ=WEEKLY;INTERVAL=2;UNTIL={until_utc.strftime('%Y%m%dT%H%M%SZ')}"],
        "colorId": _color_id(hit.lesson_type, hit.week),
        "extendedProperties": {"private": {"xkey": xkey, "tool": "timetable-to-gcal"}},
    }
