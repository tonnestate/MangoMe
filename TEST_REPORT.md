# MangoMe v0.1.0 test report

Date: 2026-09-24

## Passed

- 8 domain/unit tests passed.
- Plan-before-mutate enforcement.
- DONE_CLAIMED remains UNVERIFIED until all gates pass.
- Advisory collision warnings do not lock work.
- Last-started slice is derived from persistent timestamps.
- Duplicate declared contract IDs preserve both contributions and create a collision warning.
- Big-Bang scan is non-destructive and does not auto-create canonical contracts.
- Context compiler selects current active slice.
- Execution receipts calculate durable outcome cost and context-token savings.
- Python bytecode compilation succeeded for all MangoMe modules.
- In-memory bootstrap lifecycle executed successfully.
- Package build/install was validated locally with `--no-deps --no-build-isolation` against the container's installed build tooling.

## Environment limitation

The sandbox cannot download packages from PyPI, therefore a live runtime import/integration test of external `mcp>=2` and `pymongo>=4.10` dependencies could not be executed here. The MCP server targets the current official MCP Python SDK v2 API (`from mcp.server import MCPServer`, decorated tools, `MCPServer.run`).
