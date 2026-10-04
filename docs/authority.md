# Authority model

MangoMe separates normal worker mutation, work admission, verification authority, and owner approval.

## Worker runtime

Default:

```text
MANGOME_RUNTIME_ROLE=WORKER
```

Workers can read state, enter ordinary work from the current user request, submit plans, execute slices, submit un-attested evidence, and request approval. They cannot grant owner decisions or create verification assurance without a verifier capability.

`enter_work` is an operability bridge, not a privilege escalation. It records operational work from user intent relayed by the client and preserves the normal Request → Spec → Plan → Slice path. It never promotes Big-Bang/filesystem discovery candidates into canonical historical contract truth.

A high-assurance host should bind intake to an authenticated user principal outside the worker process. The current stdio MCP surface does not claim that a worker-supplied string is cryptographic user identity.

## Dedicated privileged runtime — preferred

Run a separate process/endpoint with:

```text
MANGOME_RUNTIME_ROLE=VERIFIER
MANGOME_RUNTIME_ACTOR=verifier-service
```

or:

```text
MANGOME_RUNTIME_ROLE=OWNER
MANGOME_RUNTIME_ACTOR=human-owner
```

The process role authorizes only the configured actor. Protect access to that endpoint with OS/network/transport controls. No capability token is required in the tool call when the dedicated runtime role is used. In v0.3.20 LOCAL_HOST this is still cooperative host configuration, not tamper resistance against a worker that can launch arbitrary same-host processes or write MongoDB directly. There is no aggregate `FULL` role; use the exact privileged role required.

## Shared-process capability fallback

For a shared local process, configure verifier/approval tokens and optional actor allowlists. The presented capability is compared with `secrets.compare_digest` and is never persisted.

This is a pragmatic self-hosted control plane, not a replacement for transport-native IAM.

## Database boundary

MangoMe's state-machine guarantees apply to writes that pass through MangoMe. A worker with direct MongoDB write/admin access can bypass those guarantees.

For untrusted workers, isolate the canonical database credential behind the MangoMe service/runtime boundary and do not expose that credential through the worker process environment, shell, or readable configuration.

## v0.3 control-plane authority

Durable WorkIdentity/WorkTurn authority is distinct from worker identity.

```text
MANGOME_RUNTIME_ROLE=CONTROL
MANGOME_RUNTIME_ACTOR=control-plane
```

or configure `MANGOME_CONTROLLER_TOKEN` plus optional `MANGOME_CONTROLLER_ACTORS`.

Ordinary task-scoped EXECUTE work may be bound from explicit current client-relayed user intent. Recovered ACTIVE state alone never grants continuation, but a worker must not invent or request controller identity merely to carry out an ordinary current user request.

Controller authority remains required for privileged control-plane operations and must stay outside worker prompts and direct model-visible state in high-assurance deployments.
## v0.3.10 validation and closure authority

Validation and verification are intentionally distinct. A validator uses a controller-bound `VERIFY` or `CONTROL` WorkTurn to classify a `DONE_CLAIMED` Slice as `VALIDATED`, `REWORK_REQUIRED`, or `INCONCLUSIVE`. That judgment can reopen execution but cannot create `VERIFIED` assurance.

Independent verification still requires the verifier capability. Slice closure is verifier-controlled: `VERIFIED` work closes only when no required PER/1 effect remains unresolved. Owner acceptance remains a separate CONTROL/approval decision after closure.

