# Test Report — MangoMe v0.1.8

Date: 2026-09-24

Command:

```bash
PYTHONPATH=src python -m pytest --disable-warnings
```

Result in the packaging environment:

```text
..........................................sss...................         [100%]
61 passed, 3 skipped in 0.57s
```

Skipped checks:

- MCP surface integration: optional `mcp` dependency unavailable in the packaging sandbox.
- Two MongoDB integration checks: `MANGOME_TEST_MONGO_URI` not configured.

Additional deterministic checks:

```text
python -m compileall -q src tests server.py  PASS
skill/mangome/SKILL.md == src/mangome/skill/SKILL.md  PASS
skill/mangome/SKILL.md == .github/skills/mangome/SKILL.md  PASS when mirror is present
```

New v0.1.8 regression coverage includes:

- first attachment of an unknown workspace performs deterministic inventory plus non-destructive Big-Bang discovery without creating canonical contracts;
- a known workspace refresh does not repeat semantic discovery admission;
- Claude Code managed setup preserves unrelated MCP configuration, removes stale MangoMe-named shadow entries, installs the current Agent Skill plus a short always-on project rule, and enables automatic workspace attachment;
- Codex managed setup preserves unrelated TOML, removes stale user/project MangoMe MCP entries such as an old `mangome_eval` launcher, preserves existing `AGENTS.md` content while adding one idempotent managed zero-touch block, and remains idempotent;
- managed runtime version mismatch fails closed before backing-store initialization;
- `MANGOME_AUTO_ATTACH=1` attaches/discovers the configured workspace without requiring a user Big-Bang command;
- health reports the sanitized managed-identity reason code without exposing the configured mismatch value.

A wheel build with build isolation disabled in the offline packaging environment also confirmed that `mangome/operability.py` and the packaged `mangome/skill/SKILL.md` are included in the `0.1.8` distribution.

This report is not a claim of full production validation. The real Claude Code/Codex client attestation paths are environment-dependent and require those clients to be installed; the three skipped optional MCP/MongoDB checks were not exercised in this packaging environment.
