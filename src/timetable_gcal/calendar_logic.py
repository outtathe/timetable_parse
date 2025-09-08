# -*- coding: utf-8 -*-
import datetime as dt
from typing import Dict
import hashlib
import pytz

from .parser import Hit, WEEKDAY_MAP

def monday_of(date_: dt.date) -> dt.date:
    return date_ - dt.timedelta(days=date_.weekday())

# === УСТОЙЧИВЫЙ КЛЮЧ ДЛЯ ИДЕМПОТЕНТНОСТИ ===
def _stream_from_group(group: str) -> str:
    try:
        n = int(group.split("-")[-1])
    except Exception:
        return ""
    return "1-4" if 1 <= n <= 4 else "5-8"

def make_xkey(hit) -> str:
    """
    Стабильный ключ идемпотентности.
    Для лекций берём не группу, а поток (1-4 или 5-8),
    чтобы все группы одного потока считались одной лекцией.
    """
    group_component = _stream_from_group(hit.group) if hit.lesson_type == "Лекция" else hit.group.upper()
    payload = "|".join([
        hit.lesson_type,
        hit.week,
        hit.weekday_name,
        hit.start.strftime("%H:%M"),
        hit.end.strftime("%H:%M"),
        (hit.room or "").strip().upper(),
        group_component,
    ])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]

def build_event(hit: Hit, tz: str, upper_week_monday: dt.date, until_date: dt.date) -> Dict:
    upper_monday = monday_of(upper_week_monday)
    lower_monday = upper_monday + dt.timedelta(days=7)
    week_anchor = upper_monday if hit.week == "upper" else lower_monday

    day_offset = WEEKDAY_MAP[hit.weekday_name]
    start_date = week_anchor + dt.timedelta(days=day_offset)

    tzinfo = pytz.timezone(tz)
    start_dt = tzinfo.localize(dt.datetime.combine(start_date, hit.start))
    end_dt = tzinfo.localize(dt.datetime.combine(start_date, hit.end))

    until_utc = pytz.UTC.localize(dt.datetime.combine(until_date, dt.time(23, 59, 59)))

    # Имена + цвета (как было)
    # стрим 1-4/5-8:
    def _group_num(g): 
        try: return int(g.split("-")[-1])
        except: return None
    n = _group_num(hit.group)
    stream = "1-4" if (n and 1 <= n <= 4) else "5-8" if n else ""
    if hit.lesson_type == "Лекция":
        stream_suffix = f" {stream}" if stream else ""
        summary = f"ПИА — Лекция{stream_suffix} — {hit.room or 'Аудитория?'}"
    else:
        summary = f"ПИА — Лаба — {hit.group} — {hit.room or 'Аудитория?'}"

    def _color_id(kind, week):
        return {"Лекция":{"upper":"11","lower":"6"},
                "Лаба":{"upper":"10","lower":"2"}}[kind][week]

    description = (
        f"Группа: {hit.group}\n"
        f"Неделя: {'верхняя' if hit.week=='upper' else 'нижняя'}"
    )

    xkey = make_xkey(hit)

    return {
        "summary": summary,
        "location": hit.room or "",
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": tz},
        "recurrence": [f"RRULE:FREQ=WEEKLY;INTERVAL=2;UNTIL={until_utc.strftime('%Y%m%dT%H%M%SZ')}"],
        "colorId": _color_id(hit.lesson_type, hit.week),
        # <<< ключ для идемпотентности
        "extendedProperties": {"private": {"xkey": xkey, "tool": "timetable-to-gcal"}},
    }
