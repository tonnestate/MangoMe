# External Runtime Enforcement Boundary

MangoMe governs durable work identity, authority, effects, evidence, truth maintenance and assurance. It does not need to implement the operating-system sandbox that physically constrains an untrusted worker.

## Boundary

```text
MangoMe
  execution_eligibility
  authorize_delegation
        |
        v
Host / Router
  select external enforcement policy
  filesystem / network / commands / credentials
        |
        v
Worker
        |
        v
Host audit / outcome
        |
        v
record_execution_receipt(metadata=...)
        |
        v
Evidence / AV/1 when required
```

The enforcement backend is outside worker prompt authority. A worker may request a capability, but it must not widen the host policy that constrains its process or delegated tools.

## Receipt convention

No new MangoMe schema is required for a first integration. The existing execution-receipt metadata can carry bounded provenance:

```json
{
  "enforcement_backend": "external",
  "enforcement_version": "<version>",
  "policy_ref": "<stable policy reference>",
  "policy_digest": "<digest when available>",
  "audit_ref": "<external audit/session reference>",
  "enforcement_decision": "ALLOW|DENY|PARTIAL|UNKNOWN"
}
```

This metadata is descriptive. It does not itself become canonical truth, Evidence, assurance, verification or owner acceptance. If a material security claim must be trusted, preserve the relevant external observation and apply MangoMe's existing Evidence/AV/1 path.

## Epistemic rule

An external sandbox denial, prompt-injection detector, code scanner or model judge can provide useful signals, but the signal's source determines its MangoMe role. A model-derived security score is ordinarily FJD/1 `WORKER_JUDGMENT`; a reproducible independent scanner/verifier result can become Evidence according to existing AV/1 rules. Neither self-promotes to truth.

## Integration policy

v0.3.12 adds no sandbox/firewall/eval package dependency. Candidate backends should first be evaluated in isolated spikes for platform support, failure modes, policy expressiveness, auditability, performance, version stability and bypass resistance. Tighter coupling should be added only when that evidence justifies it.
