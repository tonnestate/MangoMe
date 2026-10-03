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

GitHub Actions runs the deterministic suite on Python 3.10–3.12 and a separate real-MongoDB integration job. A release claim requires both CI and the local deterministic/package gates described in [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) to be green; a web-upload transport does not bypass those gates.

If the change touches the Agent Skill, the two authoritative release surfaces must remain byte-identical:

```text
skill/mangome/SKILL.md
src/mangome/skill/SKILL.md
```

Repository-local `.github` / `.claude` Skill mirrors are optional convenience surfaces. If present, they must match the canonical Skill exactly.

The default worker MCP surface must remain small. Add low-level operations to the internal/advanced surface unless a new worker-visible semantic domain is justified; `mangome-mcp-advanced` / `mangome.mcp_server` is the explicit compatibility surface.

Do not weaken a failing integrity regression merely to make the release gate green. Preserve the failing case, repair the underlying invariant, then rerun the same case.

## Community conduct

Participation in the project is subject to [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Technical disagreement is welcome; harassment or personal abuse is not.
