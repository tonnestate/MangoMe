# Security

MangoMe is an experimental self-hosted MCP and operational-truth service. Do not expose Streamable HTTP publicly without transport authentication, network controls, and deployment-specific authorization.

## Privileged state transitions

Verification and owner approval are protected by either:

- dedicated `MANGOME_RUNTIME_ROLE=VERIFIER|OWNER` processes with `MANGOME_RUNTIME_ACTOR`; or
- runtime capability tokens (`MANGOME_VERIFIER_TOKEN`, `MANGOME_APPROVAL_TOKEN`) with optional actor allowlists.

Capability values are never persisted by MangoMe. Prefer host/runtime injection and dedicated privileged processes so secrets do not appear in model prompts or tool-call arguments.

A WORKER client must not receive verifier or owner credentials. If the worker can access those credentials through its process environment, shell, filesystem, or another host channel, the verifier boundary has already been defeated outside MangoMe.

The same applies to the router capability. `MANGOME_ROUTER_TOKEN` authorizes publication of host-observed runtime mode, capability and cost facts; a normal worker must not possess it, otherwise the worker could attempt to self-promote its execution profile.

## Database boundary

MangoMe can enforce its invariants only for writes that pass through MangoMe. A worker with direct write/admin access to the canonical MongoDB can bypass the service-level state machine.

For production deployment:

- do not launch an untrusted worker from a shell/session that exports a MongoDB administrator URI;
- use least-privilege database credentials and deployment controls appropriate to the host environment;
- keep verifier/owner runtimes isolated from worker runtimes;
- treat direct database writers as trusted infrastructure, not ordinary agents.

The managed client setup deliberately does not copy MongoDB credentials into generated client configuration. MangoMe does not require a separate service, container, or OS identity as part of its core architecture. Deployments that expose direct MongoDB write credentials to an unrestricted worker must, however, treat that worker as inside the trusted database boundary and must not claim that MangoMe's service-level transition checks protect against that worker bypassing the API.

## Discovery and admission

Filesystem/Big-Bang discovery is candidate-only. Discovery output is not canonical contract/specification truth and never receives verification or acceptance merely because it exists on disk.

The zero-touch `enter_work` path can create canonical operational state only from the current explicit user request relayed by the client. It does not promote discovered historical contracts, reports, or audit prose.

## Reporting vulnerabilities

Do not publish credentials, private deployment data, or an unpatched exploit in a public issue. Contact the repository maintainer privately with reproduction details and affected versions when practical.
