# Security

MangoMe is an experimental self-hosted MCP and operational-truth service. Do not expose Streamable HTTP publicly without transport authentication, network controls, and deployment-specific authorization.

## Privileged state transitions

Verification and owner approval are protected by either:

- dedicated `MANGOME_RUNTIME_ROLE=VERIFIER|OWNER` processes with `MANGOME_RUNTIME_ACTOR`; or
- runtime capability tokens (`MANGOME_VERIFIER_TOKEN`, `MANGOME_APPROVAL_TOKEN`) with optional actor allowlists.

Capability values are never persisted by MangoMe. Prefer host/runtime injection and dedicated privileged processes so secrets do not appear in model prompts or tool-call arguments.

A WORKER client must not receive verifier or owner credentials. If the worker can access those credentials through its process environment, shell, filesystem, or another host channel, the verifier boundary has already been defeated outside MangoMe.

## Database boundary

MangoMe can enforce its invariants only for writes that pass through MangoMe. A worker with direct write/admin access to the canonical MongoDB can bypass the service-level state machine.

For production deployment:

- do not launch an untrusted worker from a shell/session that exports a MongoDB administrator URI;
- use a dedicated least-privilege database credential or a separately hosted MangoMe service boundary for worker clients;
- keep verifier/owner runtimes isolated from worker runtimes;
- treat direct database writers as trusted infrastructure, not ordinary agents.

The v0.1.8.1 managed client setup deliberately does not copy MongoDB credentials into generated client configuration. It cannot remove secrets that the parent client process already inherited.

## Discovery and admission

Filesystem/Big-Bang discovery is candidate-only. Discovery output is not canonical contract/specification truth and never receives verification or acceptance merely because it exists on disk.

The zero-touch `enter_work` path can create canonical operational state only from the current explicit user request relayed by the client. It does not promote discovered historical contracts, reports, or audit prose.

## Reporting vulnerabilities

Do not publish credentials, private deployment data, or an unpatched exploit in a public issue. Contact the repository maintainer privately with reproduction details and affected versions when practical.
