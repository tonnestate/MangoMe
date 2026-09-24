# Authority model

MangoMe separates normal worker mutation, verification authority and owner approval.

## Worker runtime

Default:

```text
MANGOME_RUNTIME_ROLE=WORKER
```

Workers can read state, submit plans, execute slices, submit un-attested evidence and request approval. They cannot grant owner decisions or create verification assurance without a verifier capability.

## Dedicated privileged runtime (preferred)

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

The process role itself authorizes only the configured actor. Protect access to that endpoint with OS/network/transport controls. No capability token is needed in the tool call.

## Shared-process capability fallback

For a shared local process, configure verifier/approval tokens and optional actor allowlists. The presented capability is compared with `secrets.compare_digest` and never persisted.

This is a pragmatic self-hosted control plane, not a replacement for transport-native IAM.
