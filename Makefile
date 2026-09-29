.PHONY: install dev test compile smoke check

install:
	python -m pip install -e .

dev:
	python -m pip install -e ".[dev]"

test:
	PYTHONPATH=src python -m pytest -ra

compile:
	PYTHONPATH=src python -m compileall -q src tests server.py

smoke:
	PYTHONPATH=src python tools/release_smoke.py

check: test compile smoke
	test -f .gitignore
	test -f skill/mangome/SKILL.md
	test -f src/mangome/skill/SKILL.md
	diff -u skill/mangome/SKILL.md src/mangome/skill/SKILL.md
	@if test -f .github/skills/mangome/SKILL.md; then diff -u skill/mangome/SKILL.md .github/skills/mangome/SKILL.md; fi
	@if test -f .claude/skills/mangome/SKILL.md; then diff -u skill/mangome/SKILL.md .claude/skills/mangome/SKILL.md; fi
	test -f docs/START_HERE.md
	test -f docs/getting-started.md
	test -f docs/QUICKSTART_DEMO.md
	test -f docs/troubleshooting.md
	test -f docs/WHY_MANGOME.md
	test -f docs/COMPATIBILITY.md
	test -f docs/RELEASE_CHECKLIST.md
