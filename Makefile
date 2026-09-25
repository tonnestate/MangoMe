.PHONY: install dev test compile check

install:
	python -m pip install -e .

dev:
	python -m pip install -e ".[dev]"

test:
	python -m pytest -ra

compile:
	python -m compileall -q src tests server.py

check: test compile
	test -f .github/workflows/ci.yml
	test -f .github/skills/mangome/SKILL.md
	test -f .gitignore
	diff -u skill/mangome/SKILL.md src/mangome/skill/SKILL.md
	diff -u skill/mangome/SKILL.md .github/skills/mangome/SKILL.md
