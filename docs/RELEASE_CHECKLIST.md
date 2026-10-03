# Release checklist

Use this checklist before publishing a MangoMe release.

## Repository consistency

- `pyproject.toml` and `src/mangome/__init__.py` expose the same version.
- `skill/mangome/SKILL.md` and `src/mangome/skill/SKILL.md` are byte-identical.
- Optional repository-local Skill mirrors, when present, are byte-identical to the canonical Skill.
- README and CHANGELOG describe the current release.
- Beginner documentation links resolve.
- Default worker MCP surface lists exactly seven semantic tools; `mangome-mcp-advanced` retains the precise compatibility API.
- `structural_status` does not create a cache or scan the repository.
- Structural refresh respects configured file/depth/time/relation bounds and reports `PARTIAL` when bounded.
- Root process artifacts `DELTA-MANIFEST.txt`, `REPO_AUDIT_2026-09-24.md`, and `UPLOAD_DOTFILES.md` are absent.

## Deterministic gate

```bash
python -m pip install -e ".[dev]"
make check
python -m pip check
```

GitHub Actions must be green. The `mongo-integration` job runs the release regressions against a real MongoDB service with `MANGOME_TEST_MONGO_URI` configured. Environment-dependent checks are not PASS unless they actually ran.

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
