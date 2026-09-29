# Worker Facade — MangoMe v0.3.11

v0.3.11 separates the normal worker surface from the advanced capability surface.

The default `mangome-mcp` entry point exposes exactly seven semantic tools:

1. `mangome_status`
2. `mangome_observe`
3. `mangome_query`
4. `mangome_work`
5. `mangome_effect`
6. `mangome_verify`
7. `mangome_control`

The existing precise MCP capabilities remain implemented in `mangome.mcp_server` and are available through the explicit `mangome-mcp-advanced` entry point. They are not duplicated or deleted. The normal `mangome` CLI is routed through `mangome.worker_cli`, so `mangome setup`, `doctor --repair`, and client attestation target `mangome.worker_mcp_server`; `mangome-advanced` retains the prior CLI behavior for explicit advanced/internal use.

Each semantic facade call routes deterministically through a fixed allowlist. Responses contain `disposition`, `recommended_next_action`, `allowed_next_actions`, `forbidden_next_actions`, and `reason_codes`. This is the weak-agent semantic bridge: a worker need not know MangoMe's internal capability taxonomy to select a safe next action.

Read-only `STATUS`, `OBSERVE`, and `QUERY` calls do not admit work. Mutating `WORK`, `EFFECT`, `VERIFY`, and `CONTROL` calls retain the underlying v0.3.10c gates. The facade does not bypass WorkIdentity, restore, controller/router, verifier, owner-approval, or effect-journal controls.

The governing degradation rule is:

> Fail closed on truth/effect mutation. Degrade gracefully on cognition.

Consequently, an unavailable structural map does not block work, a context budget is reduced in stages, missing verification capability blocks verification rather than ordinary reasoning, and ambiguity never authorizes canonical mutation.

Existing managed client configurations created by an older release may still point directly at `mangome.mcp_server`. After installing v0.3.11, rerun normal `mangome setup --client auto` (or `mangome doctor --repair`) to rewrite the managed binding to `mangome.worker_mcp_server`.
