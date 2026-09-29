# Worker Facade — MangoMe v0.3.12

v0.3.12 keeps the normal worker surface separate from the advanced capability surface and repairs the v0.3.11 capability-loss regression.

The default `mangome-mcp` entry point exposes exactly seven semantic tools:

1. `mangome_status`
2. `mangome_observe`
3. `mangome_query`
4. `mangome_work`
5. `mangome_effect`
6. `mangome_verify`
7. `mangome_control`

The existing precise MCP capabilities remain implemented in `mangome.mcp_server` and remain available through `mangome-mcp-advanced`. The semantic facade routes all 100 pre-existing advanced capabilities into the seven categories; reducing top-level tool count no longer removes functionality.

Each facade call routes through a fixed allowlist and returns `disposition`, `recommended_next_action`, `allowed_next_actions`, `forbidden_next_actions`, and `reason_codes`. This is a semantic bridge for weaker workers, not a replacement governance system. Underlying WorkIdentity, controller/router, verifier, owner-approval, effect and recovery gates still decide authority.

The governing degradation rule is:

> Fail closed on truth/effect mutation. Degrade gracefully on cognition.

Structural/parser failure therefore does not block ordinary work, context pressure can reduce optional derived context, missing verifier authority blocks verification rather than reasoning, and ambiguity never grants mutation authority.

Structural enrichment is intentionally advisory. `COGNITIVE_HYGIENE` may return a separate structural-relevance projection without changing PCH/1 temperatures. `START_SCOPED_AUDIT` may return structural impact candidates without mutating the persisted SRA/1 frontier.

Managed clients created before the semantic facade may still point directly at `mangome.mcp_server`. The normal v0.3.12 `mangome setup --client auto` / `mangome doctor --repair` path targets `mangome.worker_mcp_server`; the explicit `mangome-advanced` path retains advanced/internal behavior.
