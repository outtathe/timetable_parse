# -*- coding: utf-8 -*-
import datetime as dt
from typing import Dict
import pytz

from .parser import Hit, WEEKDAY_MAP

def monday_of(date_: dt.date) -> dt.date:
    return date_ - dt.timedelta(days=date_.weekday())

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

    # ⬇️ ключевое изменение: для ЛАБ добавляем группу
    if hit.lesson_type == "Лаба":
        summary = f"ПИА — Лаба — {hit.group} — {hit.room or 'Аудитория?'}"
    else:
        summary = f"ПИА — Лекция — {hit.room or 'Аудитория?'}"

    description = f"Группа: {hit.group}\nНеделя: {'верхняя' if hit.week=='upper' else 'нижняя'}"

    return {
        "summary": summary,
        "location": hit.room or "",
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": tz},
        "recurrence": [f"RRULE:FREQ=WEEKLY;INTERVAL=2;UNTIL={until_utc.strftime('%Y%m%dT%H%M%SZ')}"],
    }
