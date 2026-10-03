# Test Report — MangoMe v0.3.20

Date: 2026-10-03

Base: public `tonnestate/MangoMe` v0.3.19 commit `b5e1ed992e127076e5665da084ee6d6f535190f5`.

## Release purpose

v0.3.20 is a bounded correctness-recovery release after adversarial evaluation of v0.3.19. It does not add a new feature family. The release repairs concurrency/identity invariants, separates prompt deduplication from durable WorkIdentity, removes write side effects from status reads, makes LOCAL_HOST verification claims honest about their cooperative trust boundary, and restores the release gate around the current codebase.

## Local validation

Commands run against the reconstructed v0.3.19 baseline with the v0.3.20 delta applied:

```bash
PYTHONPATH=src pytest -ra
python -m compileall -q src tests tools server.py
python -m pip wheel --no-deps --no-build-isolation -w /tmp/mangome-wheel .
```

Result:

```text
213 passed, 6 skipped
compileall PASS
wheel build PASS
mangome_mcp-0.3.20-py3-none-any.whl
packaged mangome/skill/SKILL.md PASS
canonical + packaged + GitHub + Claude Skill copies byte-identical PASS
```

The six local skips are explicit non-PASS results:

- 2 MCP-dependent checks were skipped because the local validation interpreter does not have the `mcp` package installed.
- 4 real-MongoDB integration checks were skipped because `MANGOME_TEST_MONGO_URI` is not configured in this sandbox.

`tools/release_smoke.py` was also attempted locally and stopped immediately with `ModuleNotFoundError: No module named 'mcp'`. It is therefore **NOT RUN / NOT PASS locally**. The GitHub Actions workflow installs `.[dev]`, so the smoke path is part of the configured CI gate, but this report does not claim that GitHub CI has already executed.

## v0.3.20 regression focus

The local suite covers the evaluated correctness findings with dedicated regression tests:

1. **Atomic durable identity**
   - Project creation is atomic on `project_key`.
   - Family creation is atomic on `family_key` / admission key.
   - Slice materialization is unique on `(family_id, declared_id)`.
   - WorkIdentity remains unique per Family.
   - The in-memory backend mirrors these uniqueness rules instead of hiding MongoDB-only races.
   - A forced two-thread `enter_work` race produces one Project, one Family, one WorkIdentity and one Slice, with at most one active execution target.

2. **Prompt text is not WorkIdentity**
   - Admission text is conservatively normalized for a deterministic deduplication hint.
   - Case, whitespace and trailing punctuation variants return an existing-work candidate instead of silently creating a second durable task.
   - Continuation is explicit through `work_ref`.
   - The fingerprint is documented and tested as a deduplication hint, not canonical identity.

3. **Read paths are side-effect free**
   - Family status can compute an in-memory projection without mutating Family or project-view revisions.
   - v0.3 Work status reads existing materialized views without rewriting them.
   - Workspace-root discovery uses direct Project/Family reads and no longer calls recursive project-overview/status projections.

4. **LOCAL_HOST trust claims are bounded**
   - LOCAL_HOST is reported as `COOPERATIVE_HOST` with `tamper_resistant_verification=false`.
   - Direct host/MongoDB writers are explicitly inside the trust boundary and can bypass MangoMe's service-level state machine.
   - Aggregate `MANGOME_RUNTIME_ROLE=FULL` no longer grants verifier/owner/router/control authority; privileged runtime roles are exact.
   - Legacy STRICT/credential-file configuration remains rejected rather than being documented as an active hardening mode.

5. **Release gate / real Mongo coverage**
   - CI now defines Python unit jobs plus a MongoDB 7 service integration job.
   - Real-Mongo regressions include concurrent `enter_work` and creation of v0.3.20 unique indexes when legacy non-unique indexes already exist.
   - Existing duplicate logical identities are intentionally fail-closed during unique-index establishment; v0.3.20 does not silently merge ambiguous canonical rows.

## Environment-dependent acceptance still required

Before calling an uploaded v0.3.20 release accepted, run the configured CI and confirm:

```text
1. Unit matrix is green on supported Python versions.
2. Real MongoDB integration tests are green.
3. MCP release smoke is green with the declared dependency installed.
4. Concurrent same-task admission leaves exactly one canonical Project/Family/WorkIdentity/Slice.
5. Prompt punctuation/case/spacing variants return an existing-work candidate rather than a second WorkIdentity.
6. Repeated status reads do not advance canonical revisions.
7. LOCAL_HOST reports COOPERATIVE_HOST and never claims tamper-resistant verification.
```

These checks are configured by v0.3.20, but environment-dependent results are not claimed by this local report until they actually run.
