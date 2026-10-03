# Security

MangoMe is an experimental self-hosted MCP and operational-record service. Do not expose Streamable HTTP publicly without transport authentication, network controls, and deployment-specific authorization.

## v0.3.20 trust model

The supported managed mode is `MANGOME_TRUST_BOUNDARY=LOCAL_HOST`.

`LOCAL_HOST` is a **cooperative host trust boundary**. MangoDB is expected to be credential-free and reachable only on loopback. MangoMe enforces workflow, role and state-transition rules for writes that pass through MangoMe, but it does not provide tamper resistance against a process that can write directly to the same MongoDB or otherwise controls the host.

Therefore:

- `VERIFIED` means MangoMe's verifier transition was satisfied inside the governed service workflow;
- it does **not** prove that a hostile same-host process could not forge database state;
- a worker with direct MongoDB write access is inside the LOCAL_HOST trust boundary;
- direct database writers must be treated as trusted infrastructure in this deployment mode.

Do not describe LOCAL_HOST verification as service-isolated, credential-isolated, or tamper-resistant.

## Privileged state transitions

Runtime roles are exact:

```text
WORKER
VERIFIER
OWNER
ROUTER
CONTROL
```

`MANGOME_RUNTIME_ROLE=FULL` is not an aggregate privileged role in v0.3.20. A dedicated runtime may use the exact role required for its operation, with `MANGOME_RUNTIME_ACTOR` bound to the actor performing that transition. Capability tokens remain available where the existing API requires them.

Environment roles are host configuration, not a security boundary against a worker that can arbitrarily control the same process environment. Stronger isolation requires a separate service/process identity outside the worker's control.

A future service-isolated deployment may use a dedicated OS user, authenticated MongoDB credentials unavailable to workers, and stronger privileged-actor provenance. That mode is **not** implemented by v0.3.20 LOCAL_HOST and must not be inferred from legacy documentation.

## Database boundary

MangoMe can enforce domain invariants only for writes that pass through MangoMe. In v0.3.20 the service adds atomic uniqueness for core work identities so concurrent normal clients cannot create duplicate Project/Family/Slice identities through the supported API.

A direct MongoDB writer can still bypass the service-level state machine in LOCAL_HOST. If that threat matters, place MangoMe and MongoDB behind a stronger service boundary before making stronger verification claims.

Managed setup does not persist MongoDB credentials into clients. Legacy `STRICT` / `MANGOME_MONGODB_URI_FILE` trust-boundary configuration is rejected by the current runtime; it is not a supported hardening mode in v0.3.20.

## Discovery and admission

Filesystem/Big-Bang discovery is candidate-only. Discovery output is not canonical Contract/Specification truth and never receives verification or acceptance merely because it exists on disk.

Prompt fingerprints are admission/deduplication hints only. They are not WorkIdentity. When MangoMe reports `EXISTING_WORK_CANDIDATE`, the caller must bind explicitly using the returned `work_ref` before continuing that durable work.

## Reporting vulnerabilities

Do not publish credentials, private deployment data, or an unpatched exploit in a public issue. Contact the repository maintainer privately with reproduction details and affected versions when practical.
