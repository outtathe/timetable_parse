# timetable-to-gcal — краткий гайд

## 1) Что это
CLI-утилита, которая:
- парсит .XLS расписание и создаёт события **ПИА** в Google Calendar;
- берёт **только группы `БИВТ-25-1..8`**;
- лекции — по потокам `1–4` / `5–8`, лабы — по конкретным группам;
- делает события идемпотентно (стабильный `xkey` + проверка дублей), цвета:
  - лекции верх/низ: Tomato / Tangerine;
  - лабы верх/низ: Basil / Sage.

## 2) Установка
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -U pip
pip install -e .
```
Google API: включите **Google Calendar API**, создайте **OAuth Client (Desktop)**, положите `credentials.json` в корень проекта. Первый запуск создаст `token.json`.

## 3) Команды

### 3.1 Добавить одно событие (quick add)
```bash
timetable-add-one --title "Проба" --date 2025-09-01 --start 10:00 --end 11:00   --tz Europe/Moscow --location "Л-550" --repeat 2w --until 2025-09-30
```
- `--repeat none|weekly|2w` (по умолчанию none). Если `--until` не задан — берётся **конец текущего месяца**.

### 3.2 Парсинг .xls и заливка
```bash
# сухой прогон
timetable-to-gcal --file itkn-250509.xls --dry-run --debug

# запись в календарь (по умолчанию до конца текущего месяца)
timetable-to-gcal --file itkn-250509.xls --push
```
Флаги: `--calendar <id>` · `--timezone Europe/Moscow` · `--upper-start 2025-09-01` · `--until YYYY-MM-DD`.

Поведение:
- лекции считаются **по потоку** (1–4 или 5–8);
- для лаб проверяем «та же группа и то же время в этот день» — дубль не создаём;
- у всех событий повторение раз в 2 недели; в заголовке короткий ключ (`· ab12cdef`).

### 3.3 «Судная ночь» (purge)
Удалить все ПИА-события за диапазон по префиксу заголовка (по умолчанию `ПИА`):
```bash
# посмотреть
timetable-purge --since 2025-09-01 --until 2025-10-31

# удалить
timetable-purge --since 2025-09-01 --until 2025-10-31 --apply
```
Удаляются **инстансы** в интервале, серия вне интервала остаётся.

## 4) Кастомизация (меняем предмет)
По умолчанию парсер ищет ячейки, где встречаются слова «программирование» и «алгоритм». Чтобы сменить предмет — правьте фильтр в `src/timetable_gcal/parser.py` внутри `iter_hits()`:
```python
# было (пример)
if "программирование" in low and "алгоритм" in low:
    ...

# стало (строго по фразе)
TARGET = "базы данных"
if TARGET in low:
    ...
```
После правок: `pip install -e .` и перезапуск.
