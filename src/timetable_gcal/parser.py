"""
    Логика парсинга расписания будет здесь
"""
# -*- coding: utf-8 -*-
import datetime as dt
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import xlrd  # ==1.2.0

WEEKDAY_MAP = {
    "понедельник": 0,
    "вторник": 1,
    "среда": 2,
    "четверг": 3,
    "пятница": 4,
    "суббота": 5,
    "воскресенье": 6,
}

SUBJECT_KEY = "программирование и алгоритмизация"
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})(?::\d{2})?\s*[-–]\s*(\d{1,2}):(\d{2})(?::\d{2})?")

@dataclass
class GroupCol:
    group: str
    week: str  # "upper" | "lower"
    col_subject: int
    col_room: int

@dataclass
class Hit:
    group: str
    week: str
    weekday_name: str
    start: dt.time
    end: dt.time
    room: str
    lesson_type: str  # "Лекция" | "Лаба"

def lesson_type_from_text(text: str) -> str:
    t = text.lower()
    if "лекц" in t:
        return "Лекция"
    return "Лаба"

class SheetAccessor:
    """Обёртка над xlrd sheet, которая разворачивает объединённые ячейки."""
    def __init__(self, sheet: xlrd.sheet.Sheet):
        self.s = sheet
        self.merged_map: Dict[Tuple[int, int], Tuple[int, int]] = {}
        for rlo, rhi, clo, chi in sheet.merged_cells:
            for r in range(rlo, rhi):
                for c in range(clo, chi):
                    self.merged_map[(r, c)] = (rlo, clo)

    def value(self, r: int, c: int) -> str:
        if r < 0 or c < 0 or r >= self.s.nrows or c >= self.s.ncols:
            return ""
        tl = self.merged_map.get((r, c), (r, c))
        v = self.s.cell_value(*tl)
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v).strip()

    def is_top_left(self, r: int, c: int) -> bool:
        return self.merged_map.get((r, c), (r, c)) == (r, c)

def find_header_and_week_rows(sh: SheetAccessor):
    header_row = None
    week_row = None
    max_12_count = -1
    for r in range(min(15, sh.s.nrows)):
        row_vals = [sh.value(r, c).lower() for c in range(sh.s.ncols)]
        if header_row is None and any("время" in v for v in row_vals):
            header_row = r
        count_12 = sum(v in {"1", "2"} for v in row_vals[3:])
        if count_12 > max_12_count:
            max_12_count = count_12
            week_row = r
    if header_row is None or week_row is None:
        raise RuntimeError("Не удалось найти строку заголовков / строку недель.")
    return header_row, week_row

def collect_group_columns(sh: SheetAccessor, week_row: int) -> List[GroupCol]:
    cols: List[GroupCol] = []
    for c in range(3, sh.s.ncols - 1):
        mark = sh.value(week_row, c)
        if mark not in {"1", "2"}:
            continue
        week = "upper" if mark == "1" else "lower"
        group = sh.value(week_row - 1, c) or sh.value(week_row - 2, c)
        if not group:
            continue
        cols.append(GroupCol(group=group.strip(), week=week, col_subject=c, col_room=c + 1))
    if not cols:
        raise RuntimeError("Не нашёл столбцы групп.")
    return cols

def parse_time_cell(val: str):
    m = TIME_RE.search(val.replace("—", "-"))
    if not m:
        return None
    h1, m1, h2, m2 = map(int, m.groups())
    return dt.time(h1, m1), dt.time(h2, m2)

def iter_hits(sh: SheetAccessor, header_row: int, week_row: int) -> List[Hit]:
    gcols = collect_group_columns(sh, week_row)
    res: List[Hit] = []
    current_weekday = None

    for r in range(week_row + 1, sh.s.nrows):
        left = sh.value(r, 0).strip().lower()
        if left in WEEKDAY_MAP:
            current_weekday = left
        if not current_weekday:
            continue

        parsed = parse_time_cell(sh.value(r, 2))
        if not parsed:
            continue
        start_t, end_t = parsed

        for gc in gcols:
            if not sh.is_top_left(r, gc.col_subject):
                continue
            subj_text = sh.value(r, gc.col_subject)
            if not subj_text:
                continue
            low = subj_text.lower()
            if "программирование" in low and "алгоритм" in low:
                room = sh.value(r, gc.col_room)
                lesson_type = lesson_type_from_text(subj_text)
                res.append(
                    Hit(
                        group=gc.group,
                        week=gc.week,
                        weekday_name=current_weekday,
                        start=start_t,
                        end=end_t,
                        room=room,
                        lesson_type=lesson_type,
                    )
                )
    return res
