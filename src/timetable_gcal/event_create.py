# -*- coding: utf-8 -*-
"""
Единый модуль добавления события в Google Calendar.
Не дублируется ни в CLI, ни в других местах — ВСЕ добавления идут через эти функции.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional, Dict, Any, Union

import pytz

from .calendar_api import get_gcal_service


DateLike = Union[str, dt.date]
TimeOrDTLike = Union[str, dt.time, dt.datetime]


def _parse_date(date_value: DateLike) -> dt.date:
    if isinstance(date_value, dt.date) and not isinstance(date_value, dt.datetime):
        return date_value
    if isinstance(date_value, str):
        # допускаем YYYY-M-D и YYYY-MM-DD
        y, m, d = (int(x) for x in date_value.strip().split("-"))
        return dt.date(y, m, d)
    raise TypeError("date must be a date or 'YYYY-MM-DD' string")


def _parse_time_or_dt(value: TimeOrDTLike) -> tuple[Optional[dt.time], Optional[dt.datetime]]:
    """
    Возвращает (time_part, dt_part). Ровно одно из двух будет непустым.
    Поддерживает:
      - 'HH:MM'
      - 'YYYY-MM-DDTHH:MM[:SS][±TZ]'
      - datetime.time / datetime.datetime
    """
    if isinstance(value, dt.datetime):
        return None, value
    if isinstance(value, dt.time):
        return value, None
    if isinstance(value, str):
        s = value.strip()
        # Пробуем ISO-дату-время
        if "T" in s or len(s) > 8:
            # допускаем без TZ; with TZ тоже проглотится
            return None, dt.datetime.fromisoformat(s)
        # иначе ожидаем HH:MM
        hh, mm = (int(x) for x in s.split(":"))
        return dt.time(hh, mm), None
    raise TypeError("time/datetime must be 'HH:MM' or ISO datetime string or a time/datetime object")


def _ensure_datetimes(
    date_str: DateLike,
    start_value: TimeOrDTLike,
    end_value: TimeOrDTLike,
    tzname: str,
) -> tuple[dt.datetime, dt.datetime]:
    """
    Превращает (date + start, end) в два локализованных datetime.
    Если start/end пришли как datetime — уважает их TZ, но
    если TZ нет — применяет tzname.
    Если start/end пришли как HH:MM — комбинирует с date.
    """
    tz = pytz.timezone(tzname)
    base_date = _parse_date(date_str)

    st_time, st_dt = _parse_time_or_dt(start_value)
    en_time, en_dt = _parse_time_or_dt(end_value)

    if st_dt is None:
        st_dt = dt.datetime.combine(base_date, st_time)
    if st_dt.tzinfo is None:
        st_dt = tz.localize(st_dt)

    if en_dt is None:
        en_dt = dt.datetime.combine(base_date, en_time)
    if en_dt.tzinfo is None:
        en_dt = tz.localize(en_dt)

    if en_dt <= st_dt:
        raise ValueError("end must be after start")
    return st_dt, en_dt


def build_event_body(
    *,
    title: str,
    date: DateLike,
    start: TimeOrDTLike,
    end: TimeOrDTLike,
    tz: str = "Europe/Moscow",
    location: str = "",
    description: str = "",
    color_id: Optional[str] = None,
    extended_properties: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Собирает тело события: минимально и предсказуемо.
    Повторов/правил не создаёт — это сознательно «простой» интерфейс.
    """
    start_dt, end_dt = _ensure_datetimes(date, start, end, tz)

    body: Dict[str, Any] = {
        "summary": title,
        "location": location or "",
        "description": description or "",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": tz},
    }
    if color_id:
        body["colorId"] = str(color_id)
    if extended_properties:
        body["extendedProperties"] = extended_properties
    return body


def add_event(
    *,
    title: str,
    date: DateLike,
    start: TimeOrDTLike,
    end: TimeOrDTLike,
    tz: str = "Europe/Moscow",
    calendar: str = "primary",
    location: str = "",
    description: str = "",
    color_id: Optional[str] = None,
    extended_properties: Optional[Dict[str, Dict[str, str]]] = None,
    service=None,
) -> Dict[str, Any]:
    """
    ЕДИНСТВЕННАЯ точка записи в календарь.
    - Принимает простые параметры.
    - Сервис можно передать снаружи (reuse), иначе поднимет свой.
    - Возвращает JSON созданного события.
    """
    body = build_event_body(
        title=title,
        date=date,
        start=start,
        end=end,
        tz=tz,
        location=location,
        description=description,
        color_id=color_id,
        extended_properties=extended_properties,
    )
    service = service or get_gcal_service()
    return service.events().insert(calendarId=calendar, body=body).execute()
