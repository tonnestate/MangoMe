# MangoMe v0.1.4 test report

Date: 2026-09-24

## Local regression run

```text
39 tests collected
36 passed
3 skipped
```

Expected local skips:

- MCP v2 integration test: external `mcp` dependency is not installed in this sandbox runtime.
- two real MongoDB integration tests: `MANGOME_TEST_MONGO_URI` is not configured in this sandbox runtime.

## v0.1.4 regression coverage

- MongoDB insert results no longer leak PyMongo-injected BSON `_id` / `ObjectId` values into the MangoMe domain/MCP response.
- A real-Mongo MCP regression test now calls `create_project` through the MCP client and asserts a successful serializable response with no `_id` leakage.
- Runtime health survives backing-store/bootstrap exceptions and returns sanitized diagnostics rather than raising a generic MCP tool failure.
- Health output is checked not to expose credential-bearing exception text.
- Memory-backend health remains healthy.
- Existing v0.1.0-v0.1.3 behavior remains covered by the full suite.

Python compilation succeeded for `src`, `tests`, and `server.py`.
