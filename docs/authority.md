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

The process role authorizes only the configured actor. Protect access to that endpoint with OS/network/transport controls. No capability token is required in the tool call when the dedicated runtime role is used.

## Shared-process capability fallback

For a shared local process, configure verifier/approval tokens and optional actor allowlists. The presented capability is compared with `secrets.compare_digest` and is never persisted.

This is a pragmatic self-hosted control plane, not a replacement for transport-native IAM.

## Database boundary

MangoMe's state-machine guarantees apply to writes that pass through MangoMe. A worker with direct MongoDB write/admin access can bypass those guarantees.

For untrusted workers, isolate the canonical database credential behind the MangoMe service/runtime boundary and do not expose that credential through the worker process environment, shell, or readable configuration.
