# MangoMe v0.1.1 patch manifest

This ZIP is an **overlay patch** for `tonnestate/MangoMe` v0.1.0.

Extract it over the repository root. Paths in this archive are repository-relative.

## Replaced files

- `server.py`
- `src/mangome/__init__.py`
- `src/mangome/runtime.py`
- `pyproject.toml`
- `CHANGELOG.md`
- `README.md`
- `TEST_REPORT.md`
- `skill/mangome/SKILL.md`

## New files

- `.gitignore`
- `.github/workflows/ci.yml`
- `.github/skills/mangome/SKILL.md`
- `src/mangome/integrity.py`
- `src/mangome/mcp_integrity.py`
- `tests/test_integrity.py`
- `tests/test_mongo_integration.py`
- `docs/integrity-v0.1.1.md`

## Intentionally not changed

- `src/mangome/service.py`
- `src/mangome/mcp_server.py`
- existing storage classes
- existing tests
- Big-Bang scanner/reconciler behavior

The integrity layer subclasses the existing service and extends the existing MCP server to keep this patch small and reversible.
