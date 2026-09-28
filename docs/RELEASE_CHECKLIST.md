# Release checklist

Use this checklist before publishing a MangoMe release.

## Repository consistency

- `pyproject.toml` and `src/mangome/__init__.py` expose the same version.
- `skill/mangome/SKILL.md` and `src/mangome/skill/SKILL.md` are byte-identical.
- Optional repository-local Skill mirrors, when present, are byte-identical to the canonical Skill.
- README and CHANGELOG describe the current release.
- Beginner documentation links resolve.

## Deterministic gate

```bash
python -m pip install -e ".[dev]"
make check
python -m pip check
```

For environment-dependent release validation, also run the suite with the MCP dependency installed and a real MongoDB test instance configured.

## Package gate

```bash
python -m pip wheel --no-deps --no-build-isolation . -w dist
```

Inspect the wheel and confirm that `mangome/skill/SKILL.md` is packaged.

## Runtime acceptance

On the target host, verify at minimum:

1. `mangome health` reports the intended version and database.
2. The managed MCP server is `mangome`, not a stale/eval alias.
3. The current MangoMe Skill is installed and invoked by the client integration.
4. Observation-only discovery performs one bounded scan and stops.
5. Existing admitted work restores from canonical MangoMe state rather than filesystem archaeology.
6. A controlled test of validation → verification → effect reconciliation → closure behaves as documented.

Environment-dependent acceptance evidence must not be reported as a repository-test PASS unless it actually ran.
