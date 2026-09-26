.PHONY: install dev test compile check

install:
	python -m pip install -e .

dev:
	python -m pip install -e ".[dev]"

test:
	PYTHONPATH=src python -m pytest -ra

compile:
	PYTHONPATH=src python -m compileall -q src tests server.py

check: test compile
	test -f .github/workflows/ci.yml
	test -f .github/skills/mangome/SKILL.md
	test -f .claude/skills/mangome/SKILL.md
	test -f .gitignore
	diff -u skill/mangome/SKILL.md src/mangome/skill/SKILL.md
	diff -u skill/mangome/SKILL.md .github/skills/mangome/SKILL.md
	diff -u skill/mangome/SKILL.md .claude/skills/mangome/SKILL.md
