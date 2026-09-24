# Contributing

Preserve MangoMe's central invariants:

- workers make claims; assurance requires proof;
- contract contributions are append-only;
- productive mutation remains bound to a persisted plan;
- evidence is un-attested by default;
- verifier and owner authority remain separate from worker identity;
- collisions warn rather than lock;
- ambiguous discovery never becomes canonical truth automatically;
- concurrent state updates fail explicitly rather than silently overwrite newer state.

Before submitting changes:

```bash
python -m pip install -e ".[dev]"
pytest -ra
python -m compileall -q src tests server.py
```

If the change touches the Agent Skill, update both:

```text
skill/mangome/SKILL.md
.github/skills/mangome/SKILL.md
```

They must remain byte-identical.
