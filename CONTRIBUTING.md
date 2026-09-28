# Contributing

Preserve MangoMe's central invariants:

- workers make claims; assurance requires proof;
- contract contributions are append-only;
- productive mutation remains bound to a persisted plan;
- discovery candidates do not silently become canonical history;
- current user intent admitted through `enter_work` still uses the normal Specification → Plan → Slice lifecycle;
- evidence is un-attested by default;
- verifier and owner authority remain separate from worker identity;
- collisions warn rather than lock;
- concurrent state updates fail explicitly rather than silently overwrite newer state.

Before submitting changes:

```bash
python -m pip install -e ".[dev]"
make check
python -m pip check
```

GitHub CI runs the suite with MongoDB 7 and the installed MCP dependency on Python 3.10, 3.11, and 3.12. See [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) for the release gate.

If the change touches the Agent Skill, the two authoritative release surfaces must remain byte-identical:

```text
skill/mangome/SKILL.md
src/mangome/skill/SKILL.md
```

Repository-local `.github` / `.claude` Skill mirrors are optional convenience surfaces. If present, they must match the canonical Skill exactly.

Do not weaken a failing integrity regression merely to make CI green. Preserve the failing case, repair the underlying invariant, then rerun the same case.

## Community conduct

Participation in the project is subject to [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Technical disagreement is welcome; harassment or personal abuse is not.
