# timetable-to-gcal

Мини‑утилита: парсит .xls расписание кафедры и создаёт события в Google Calendar
только для предметов **«Программирование и алгоритмизация» (ПИА)**.

## Быстрый старт

```bash
# 1) Создай и активируй венв
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

# 2) Установка
pip install -U pip
pip install -e .

# 3) Подготовь Google OAuth:
#   - В Google Cloud Console включи "Google Calendar API"
#   - Создай OAuth Client ID (Desktop)
#   - Скачай credentials.json и положи рядом с проектом
#   - Первый запуск откроет окно авторизации и создаст token.json
#
# 4) Запуск (сухой прогон):
timetable-to-gcal --file itkn-250509.xls --dry-run
#   Заливка:
timetable-to-gcal --file itkn-250509.xls --push
```

### Ключевые флаги

- `--file` — путь к .xls
- `--calendar` — ID календаря (по умолчанию `primary`)
- `--timezone` — таймзона; по умолчанию `Europe/Moscow`
- `--upper-start` — понедельник верхней недели; по умолчанию `2025-09-01`
- `--until` — дата конца повторений; по умолчанию `2025-12-31`
- `--push` — реально создаёт события
- `--dry-run` — только выводит, ничего не создаёт

### Гугл: куда нажимать

1. Google Cloud Console → **Create project**.
2. **APIs & Services → Library** → включить **Google Calendar API**.
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID** → *Desktop app*.
4. Скачай `credentials.json` в корень проекта. Первый запуск создаст `token.json`.

### Формат создаваемых событий

Заголовок: `ПИА — Лекция|Лаба — <Аудитория>`  
Повторение: раз в две недели. Верхняя неделя — **1–7 сент 2025** (пн 2025‑09‑01). Следующая — нижняя.
