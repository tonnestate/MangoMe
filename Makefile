.PHONY: install dev test compile check

install:
	python -m pip install -e .

dev:
	python -m pip install -e ".[dev]"

test:
	pytest -ra

compile:
	python -m compileall -q src tests server.py

check: test compile
	diff -u skill/mangome/SKILL.md .github/skills/mangome/SKILL.md
