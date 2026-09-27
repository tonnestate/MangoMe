# WorkIdentity and Progressive Persistence — v0.3

## Core invariant

> Playbooks may change. Specs may evolve. Workers and sessions may disappear. The identity of the work and its assurance history must survive them all.

MangoMe therefore treats `WorkIdentity` as the durable authority anchor. Playbooks are procedural, Specifications are normative inputs, Plans/Slices are execution decomposition, and assurance is independently accumulated history.

## Persistence levels

| Level | Meaning | Examples | Can become project truth by itself? |
| --- | --- | --- | --- |
| `VOLATILE` | disposable execution context | Playbook body, transient tool context | No |
| `PROGRESSIVE` | crash-recoverable but non-normative state | checkpoint, working cursor, Playbook selection | No |
| `CANONICAL` | durable operational truth | WorkIdentity, NormativeBaseline, Plan binding, Evidence, Claims, Assurance events | Already canonical by typed admission only |

Promotion is object-specific; there is no generic "make this canonical" operation. A progressive checkpoint can never create WorkIdentity. Discovery/recovery can never promote themselves. Normative truth changes only through an authorized `MODIFY` path. Verification/acceptance use their existing privileged assurance paths.

## Admission and execution

```text
USER INTENT
    ↓
classification / Playbook routing
    ↓
durable productive work admitted?
    ↓ YES
CANONICAL WorkIdentity
    ↓
controller-minted WorkTurn
    ↓
CURRENT NormativeBaseline
    ↓
Plan(work_id, turn_id, baseline_id)
    ↓
execution / progressive checkpoints
    ↓
claims + evidence
    ↓
independent assurance
```

A prompt is not automatically a Specification. When no Specification exists, the initial baseline is an `OPERATIONAL_INTENT` baseline bound to the admitted request hash. An explicitly admitted Specification later creates a new baseline.

## Deterministic effective truth

A NormativeBaseline hashes the effective semantic target for one WorkIdentity: current effective Specification content plus effective Contract identities and their canonical generation/hash bindings. Playbooks are excluded.

A Plan never silently floats to a later baseline. If the effective baseline changes, productive mutation under the older Plan fails with `BASELINE_DRIFT`; reconciliation must explicitly bind a new Plan.

## Assurance continuity

Assurance events are append-only and carry both `work_id` and the baseline under which the event occurred. A later Spec amendment or Playbook change does not erase or reinterpret earlier claims/verification. This makes historical assurance inspectable rather than mutable.

## Recovery and filesystem boundary

Filesystem, Git, DMS, Playbooks and previous-agent prose are observable inputs. They may corroborate or guide bounded work, but they do not define WorkIdentity, current normative truth, or assurance. Recovery starts from canonical WorkIdentity and WorkView.

## Context transport

ContextCompiler and UAI explicitly separate canonical, progressive and volatile sections. Reduction order is:

1. compact/drop volatile Playbook detail;
2. compact progressive checkpoint payload;
3. trim older non-mandatory Evidence detail;
4. never drop canonical WorkIdentity, baseline binding, active authority binding, or assurance summary.

## Control-plane boundary

At the managed MCP surface, first admission after `STATE_NOT_FOUND` may trust the current client-relayed user intent. Once canonical workspace state exists, minting additional durable work authority or a new WorkTurn requires the controller capability. A WorkTurn authorizes one actor/mode against one WorkIdentity. A recovered worker cannot infer authority from ACTIVE state or self-authored Playbook text.

Direct Python/library access is a lower trust boundary. High-assurance deployments must not expose direct MongoDB or unrestricted in-process service access to untrusted workers.

## Performance rule

Writes refresh materialized views. Reads consume them. v0.3 introduces `work_views` so the hot path does not repeatedly ask whether every object is canonical. The canonical/persistence type is decided at write/admission time and indexed explicitly.
