.PHONY: venv install run dry format

venv:
	python -m venv .venv

install:
	. .venv/bin/activate && pip install -U pip && pip install -e .

dry:
	. .venv/bin/activate && timetable-to-gcal --file itkn-250509.xls --dry-run

run:
	. .venv/bin/activate && timetable-to-gcal --file itkn-250509.xls --push

format:
	. .venv/bin/activate && python -m pip install ruff && ruff check --fix src
