# Security

MangoMe is an experimental self-hosted MCP. Do not expose Streamable HTTP publicly without transport authentication, network controls and deployment-specific authorization.

## Privileged state transitions

Verification and owner approval are protected by either:

- dedicated `MANGOME_RUNTIME_ROLE=VERIFIER|OWNER` processes with `MANGOME_RUNTIME_ACTOR`; or
- runtime capability tokens (`MANGOME_VERIFIER_TOKEN`, `MANGOME_APPROVAL_TOKEN`) with optional actor allowlists.

Capability values are never persisted by MangoMe. Prefer host/runtime injection and dedicated privileged endpoints so secrets do not appear in model prompts or tool-call arguments.

A compromised process or direct database writer remains outside MangoMe's trust boundary. v0.1.2 is not a full IAM system.

MangoMe intentionally does not store application secrets as part of contract/project state.
